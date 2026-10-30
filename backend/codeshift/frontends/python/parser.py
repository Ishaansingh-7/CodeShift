import copy

from ... import ast as A
from ...desugar import LITERALS, pure
from ...errors import CompileError
from ...library import LISTOPS, MAPOPS
import re

from .lexer import lex, unquote

SPEC = re.compile(r"([<>])?(\d+)?(?:\.(\d+)f)?(d)?$")

AUG = {"+=": "+", "-=": "-", "*=": "*", "//=": "/", "%=": "%", "/=": "fdiv", "&=": "&", "|=": "|", "^=": "^",
       "<<=": "<<", ">>=": ">>"}
CONVERT = {"int": "num_int", "float": "num_float", "str": "str"}
MATH = {
    "sqrt": "sqrt", "sin": "sin", "cos": "cos", "tan": "tan", "atan2": "atan2", "log": "log", "log10": "log10",
    "log2": "log2", "exp": "exp", "hypot": "hypot", "fabs": "abs", "pow": "pow_f",
}
MATH_INT = {"floor": "floor", "ceil": "ceil"}
BUILTIN_CALLS = {"abs": "abs", "min": "min", "max": "max", "pow": "pow", "ord": "ord", "chr": "chr", "sum": "sum",
                 "sorted": "sorted"}
LIST_METHODS = {"append": "push", "insert": "insert", "index": "index_of", "reverse": "reverse", "copy": "lcopy",
                "join": "join"}
HELPERS = {"cs_round_away": "round_away", "cs_round_js": "round_js"}
METHODS = {
    "upper": "to_upper", "lower": "to_lower", "strip": "trim", "startswith": "starts", "endswith": "ends",
    "find": "find", "replace": "replace_all", "isdigit": "is_digit", "isalpha": "is_alpha", "isspace": "is_space",
    "isupper": "is_upper", "islower": "is_lower",
}
USES_MATH = set(MATH.values()) | set(MATH_INT) | {"pi", "e", "round_away", "trunc", "pow_f"}
COMPARE = {"<", "<=", ">", ">=", "==", "!="}
BITWISE = {"<<", ">>", "&", "|", "^"}
NO_STMT = {
    "class", "import", "from", "try", "with", "global", "nonlocal", "lambda", "assert", "raise", "yield",
    "async", "await", "except", "finally",
}
FOUND = {"NEWLINE": "end of line", "INDENT": "indent", "DEDENT": "dedent", "EOF": "end of file"}


class Args(list):
    kw = ()


def parse(tokens):
    return Parser(tokens).module()


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0
        self.last = toks[0]
        self.in_func = False
        self.taken = {t.text for t in toks if t.kind == "NAME"}

    def fresh(self, base):
        name, k = base, 2
        while name in self.taken:
            name, k = f"{base}{k}", k + 1
        self.taken.add(name)
        return name

    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, kind, text=None, k=0):
        t = self.peek(k)
        return t.kind == kind and (text is None or t.text == text)

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        if t.kind not in FOUND:
            self.last = t
        return t

    def accept(self, kind, text=None):
        return self.next() if self.at(kind, text) else None

    def expect(self, kind, text=None, what=None):
        if self.at(kind, text):
            return self.next()
        raise self.error(f"expected {what or repr(text) if text else what or kind.lower()}")

    def error(self, msg, tok=None):
        t = tok or self.peek()
        found = FOUND.get(t.kind, repr(t.text))
        return CompileError("parser", f"Syntax error: {msg}, found {found}", t.line, t.col)

    def unsupported(self, what, tok=None):
        t = tok or self.peek()
        return CompileError("parser", f"Unsupported: {what}", t.line, t.col)

    def pos(self, t):
        return {"line": t.line, "col": t.col, "end": self.last.line}

    def module(self):
        funcs, body, imports, helpers = [], [], [], []
        while not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            if self.at("KEYWORD", "import"):
                t = self.next()
                name = self.expect("NAME", what="a module name")
                if name.text not in ("math", "sys"):
                    raise self.unsupported(f"import {name.text}", t)
                self.end_line()
                imports.append((name.text, t.line))
            elif self.at("KEYWORD", "def") and self.peek(1).text in HELPERS:
                helpers.append(self.skip_helper())
            elif self.at("KEYWORD", "def"):
                funcs.append(self.funcdef())
            else:
                body += self.statement()
        m = A.Module(funcs, body, line=1, col=1)
        stmts = sorted((s for s in A.walk_all([*funcs, *body]) if isinstance(s, A.Stmt)), key=lambda s: s.line)

        def owner(names):
            return next((s for s in stmts if any(isinstance(n, A.Intrinsic) and n.name in names
                                                 for e in A.heads(s) for n in A.walk(e))), None)

        for name, line in imports:
            s = owner(USES_MATH if name == "math" else {"exit"})
            if s is not None:
                s.extra.append(line)
        for name, start, end in helpers:
            s = owner({HELPERS[name]})
            if s is not None:
                s.extra += list(range(start, end + 1))
        return m

    def skip_helper(self):
        t = self.next()
        name = self.next()
        while not self.accept("PUNCT", ":"):
            if self.at("EOF"):
                raise self.error("expected ':'")
            self.next()
        self.expect("NEWLINE")
        self.expect("INDENT")
        depth = 1
        while depth:
            tok = self.next()
            if tok.kind == "EOF":
                raise self.error("expected the end of the helper")
            depth += {"INDENT": 1, "DEDENT": -1}.get(tok.kind, 0)
        return name.text, t.line, self.last.line

    def funcdef(self):
        t = self.next()
        if self.in_func:
            raise self.unsupported("nested function definition", t)
        name = self.expect("NAME", what="a function name")
        self.expect("PUNCT", "(")
        params = []
        while not self.at("PUNCT", ")"):
            if self.at("OP", "*") or self.at("OP", "**"):
                raise self.unsupported("*args and **kwargs")
            p = self.expect("NAME", what="a parameter name")
            ty = self.annotation() if self.accept("PUNCT", ":") else None
            default = None
            if self.accept("OP", "="):
                d = self.peek()
                default = self.expr()
                if not isinstance(default, LITERALS):
                    raise self.unsupported("a default value that is not a plain number, string or True/False", d)
            params.append(A.Param(p.text, ty, default=default, line=p.line, col=p.col))
            if not self.accept("PUNCT", ","):
                break
        self.expect("PUNCT", ")")
        ret = self.annotation() if self.accept("OP", "->") else None
        self.in_func = True
        body = self.block()
        self.in_func = False
        return A.FunctionDef(name.text, params, body, ret, **self.pos(t))

    def annotation(self):
        t = self.next()
        if t.kind == "TYPE" and t.text in ("int", "bool", "str", "float"):
            return t.text
        if t.kind == "TYPE" and t.text == "list":
            if self.accept("PUNCT", "["):
                self.expect("TYPE", "int")
                self.expect("PUNCT", "]")
            return "arr"
        if t.kind == "KEYWORD" and t.text == "None":
            return "void"
        raise self.unsupported(f"type annotation '{t.text}'", t)

    def block(self):
        self.expect("PUNCT", ":")
        if not self.accept("NEWLINE"):
            stmts = self.simple()
            self.end_line()
            return stmts
        if not self.accept("INDENT"):
            raise self.error("expected an indented block")
        stmts = []
        while not self.accept("DEDENT") and not self.at("EOF"):
            stmts += self.statement()
        return stmts

    def statement(self):
        t = self.peek()
        if t.kind == "INDENT":
            raise self.error("unexpected indent")
        if t.kind == "KEYWORD":
            if t.text == "if":
                return [self.if_stmt()]
            if t.text == "while":
                return self.while_stmt()
            if t.text == "for":
                return self.for_stmt()
            if t.text == "def":
                raise self.unsupported("nested function definition", t)
            if t.text in ("elif", "else"):
                raise self.error(f"'{t.text}' without a matching 'if'")
            if t.text in NO_STMT:
                raise self.unsupported(f"'{t.text}' statement", t)
        if t.kind == "OP" and t.text == "@":
            raise self.unsupported("decorators", t)
        if t.kind == "NAME" and t.text == "match" and self.is_match():
            return self.match_stmt()
        stmts = self.simple()
        self.end_line()
        return stmts

    def end_line(self):
        if self.at("PUNCT", ";"):
            raise self.unsupported("several statements on one line")
        if not (self.accept("NEWLINE") or self.at("EOF")):
            raise self.error("expected end of line")

    def simple(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "pass":
            self.next()
            return []
        if t.kind == "KEYWORD" and t.text == "del":
            self.next()
            target = self.postfix()
            if not isinstance(target, A.Index):
                raise self.unsupported("'del' of anything but a list element", t)
            item = A.Intrinsic("del", [target.target, target.index], line=t.line, col=t.col)
            return [A.ExprStmt(item, **self.pos(t))]
        if t.kind == "KEYWORD" and t.text in ("break", "continue"):
            self.next()
            return [(A.Break if t.text == "break" else A.Continue)(**self.pos(t))]
        if t.kind == "KEYWORD" and t.text == "return":
            self.next()
            if not self.in_func:
                raise CompileError("parser", "Syntax error: 'return' outside a function", t.line, t.col)
            value = None
            if not self.at("NEWLINE"):
                values = self.exprs()
                if len(values) > 1:
                    raise self.unsupported("returning several values", t)
                value = values[0]
            return [A.Return(value, **self.pos(t))]
        targets = self.exprs()
        if self.accept("OP", "="):
            values = self.exprs()
            chain = [targets]
            while self.accept("OP", "="):
                chain.append(values)
                values = self.exprs()
            if len(chain) == 1:
                return [self.assign(targets, values, t)]
            return self.chained(chain, values, t)
        op = self.peek()
        if op.kind == "OP" and op.text.endswith("=") and op.text not in COMPARE:
            self.next()
            if op.text not in AUG:
                raise self.unsupported(f"'{op.text}' operator", op)
            if len(targets) != 1:
                raise self.unsupported("augmented assignment to several targets", t)
            target = self.target(targets[0])
            value = self.expr()
            return [A.AugAssign(target, AUG[op.text], value, **self.pos(t))]
        if self.at("PUNCT", ":") and len(targets) == 1 and isinstance(targets[0], A.Name):
            self.next()
            ty = self.annotation()
            if not self.accept("OP", "="):
                raise self.unsupported("declaration without a value")
            value = self.expr()
            return [A.Assign(targets[0], value, ty, **self.pos(t))]
        if len(targets) > 1:
            raise self.unsupported("tuple expression", t)
        e = targets[0]
        if isinstance(e, A.StrLit):
            return []
        if isinstance(e, A.Call) and e.func == "print":
            node = A.Print(e.args, **self.pos(t))
            if getattr(e, "end", None) is not None:
                node.ending = e.end.value
            return [node]
        if isinstance(e, A.Intrinsic) and e.name == "@extend":
            xs, ys = e.args
            if not pure(xs):
                raise self.unsupported(".extend() on a computed list", t)
            v = self.fresh("item")
            push = A.ExprStmt(A.Intrinsic("push", [xs, A.Name(v, line=t.line, col=t.col)], line=t.line, col=t.col),
                              **self.pos(t))
            return [A.For(v, "each", [push], iter=ys, **self.pos(t))]
        if isinstance(e, A.Call) or isinstance(e, A.Intrinsic) and (e.name in LISTOPS or e.name in MAPOPS
                                                                    or e.name in ("exit", "remove_value")):
            return [A.ExprStmt(e, **self.pos(t))]
        raise self.unsupported("expression statement with no effect", t)

    def chained(self, chain, values, t):
        if any(len(x) != 1 for x in chain) or len(values) != 1:
            raise self.unsupported("chained assignment with several values", t)
        targets = [self.target(x[0]) for x in chain]
        value = values[0]
        if isinstance(value, LITERALS):
            return [A.Assign(x, copy.deepcopy(value), **self.pos(t)) for x in targets]
        holder = next((x for x in targets if isinstance(x, A.Name)), None)
        if holder is None:
            raise self.unsupported("chained assignment of a computed value to list elements", t)
        out = [A.Assign(holder, value, **self.pos(t))]
        out += [A.Assign(x, A.Name(holder.id, line=x.line, col=x.col), **self.pos(t)) for x in targets if x is not holder]
        return out

    def target(self, e):
        if isinstance(e, (A.Name, A.Index)):
            return e
        raise CompileError("parser", "Syntax error: cannot assign to this expression", e.line, e.col)

    def assign(self, targets, values, t):
        for x in targets:
            self.target(x)
        pos = self.pos(t)
        if len(targets) == 1:
            if len(values) != 1:
                raise self.unsupported("assigning a tuple", t)
            return A.Assign(targets[0], values[0], **pos)
        if len(values) == 1:
            raise self.unsupported("tuple unpacking", t)
        if len(values) != len(targets):
            raise CompileError("parser", f"Syntax error: {len(targets)} targets but {len(values)} values", t.line, t.col)
        if len(targets) == 2 and A.same(targets[0], values[1]) and A.same(targets[1], values[0]):
            return A.Swap(targets[0], targets[1], **pos)
        return A.TupleAssign(targets, values, **pos)

    def if_stmt(self):
        t = self.next()
        test = self.expr()
        body = self.block()
        orelse = []
        if self.at("KEYWORD", "elif"):
            orelse = [self.if_stmt()]
        elif self.accept("KEYWORD", "else"):
            orelse = self.block()
        return A.If(test, body, orelse, **self.pos(t))

    def while_stmt(self):
        t = self.next()
        test = self.expr()
        body = self.block()
        node = A.While(test, body, **self.pos(t))
        return self.loop_else(node, t) if self.at("KEYWORD", "else") else [node]

    def for_stmt(self):
        t = self.next()
        var = self.expect("NAME", what="a loop variable")
        second = None
        if self.accept("PUNCT", ","):
            second = self.expect("NAME", what="a second loop variable")
            if self.at("PUNCT", ","):
                raise self.unsupported("unpacking three or more values in a for loop")
        self.expect("KEYWORD", "in")
        self.hoisted = []
        head, prefix = self.loop_source(var, second, t)
        before = self.hoisted
        body = self.block()
        node = A.For(body=prefix + body, **head, **self.pos(t))
        return before + (self.loop_else(node, t) if self.at("KEYWORD", "else") else [node])

    def range_args(self):
        r = self.next()
        self.expect("PUNCT", "(")
        args = self.args()
        self.expect("PUNCT", ")")
        if not 1 <= len(args) <= 3:
            raise CompileError("parser", "Syntax error: range() takes 1 to 3 arguments", r.line, r.col)
        zero, one = A.IntLit(0, line=r.line, col=r.col), A.IntLit(1, line=r.line, col=r.col)
        return (zero, args[0], one) if len(args) == 1 else (*args, one)[:3]

    @staticmethod
    def minus(e, k):
        if isinstance(e, A.IntLit):
            return A.IntLit(e.value - k, line=e.line, col=e.col)
        return A.BinOp("-", e, A.IntLit(k, line=e.line, col=e.col), line=e.line, col=e.col)

    def loop_source(self, var, second, t):
        at = {"line": t.line, "col": t.col}
        name = self.peek()

        def setv(n, value):
            node = A.Assign(A.Name(n, **at), value, **self.pos(t))
            node.bound = True
            return node

        if self.at("BUILTIN", "range"):
            if second is not None:
                raise self.unsupported("unpacking a range", second)
            start, stop, step = self.range_args()
            return {"var": var.text, "kind": "range", "start": start, "stop": stop, "step": step}, []
        if name.kind == "NAME" and name.text in ("enumerate", "zip", "reversed") and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            if name.text == "reversed" and self.at("BUILTIN", "range"):
                start, stop, step = self.range_args()
                self.expect("PUNCT", ")")
                if second is not None or not (isinstance(step, A.IntLit) and step.value == 1):
                    raise self.unsupported("reversed() of a range with a step", name)
                return {"var": var.text, "kind": "range", "start": self.minus(stop, 1), "stop": self.minus(start, 1),
                        "step": A.IntLit(-1, **at)}, []
            args = self.args()
            self.expect("PUNCT", ")")
            for k, a in enumerate(args):
                if not pure(a):
                    v = self.fresh("values")
                    self.hoisted.append(A.Assign(A.Name(v, **at), a, line=t.line, col=t.col, end=t.line))
                    args[k] = A.Name(v, **at)
            if name.text == "enumerate":
                if second is None or not 1 <= len(args) <= 2:
                    raise self.unsupported("enumerate() without 'for i, x in ...'", name)
                seq, k = args[0], args[1] if len(args) == 2 else None
                stop = A.Len(seq, **at) if k is None else A.BinOp("+", A.Len(seq, **at), k, **at)
                idx = A.Name(var.text, **at) if k is None else A.BinOp("-", A.Name(var.text, **at), copy.deepcopy(k), **at)
                return ({"var": var.text, "kind": "range", "start": copy.deepcopy(k) if k else A.IntLit(0, **at),
                         "stop": stop, "step": A.IntLit(1, **at)}, [setv(second.text, A.Index(copy.deepcopy(seq), idx, **at))])
            if name.text == "zip":
                if second is None or len(args) != 2:
                    raise self.unsupported("zip() of other than two lists, or without 'for a, b in ...'", name)
                a, b = args
                i = self.fresh("i")
                stop = A.Intrinsic("min", [A.Len(a, **at), A.Len(b, **at)], **at)
                return ({"var": i, "kind": "range", "start": A.IntLit(0, **at), "stop": stop, "step": A.IntLit(1, **at)},
                        [setv(var.text, A.Index(copy.deepcopy(a), A.Name(i, **at), **at)),
                         setv(second.text, A.Index(copy.deepcopy(b), A.Name(i, **at), **at))])
            if second is not None or len(args) != 1:
                raise self.unsupported("reversed() with unpacking", name)
            i = self.fresh("i")
            return ({"var": i, "kind": "range", "start": self.minus(A.Len(args[0], **at), 1), "stop": A.IntLit(-1, **at),
                     "step": A.IntLit(-1, **at)}, [setv(var.text, A.Index(copy.deepcopy(args[0]), A.Name(i, **at), **at))])
        it = self.or_expr()
        if isinstance(it, A.Intrinsic) and it.name in ("@items", "@values"):
            d = it.args[0]
            if not pure(d):
                raise self.unsupported(f"looping over {it.name[1:]}() of a computed value", name)
            if it.name == "@items":
                if second is None:
                    raise self.unsupported(".items() without 'for k, v in ...'", name)
                return {"var": var.text, "kind": "each", "iter": d}, [
                    setv(second.text, A.Index(copy.deepcopy(d), A.Name(var.text, **at), **at))]
            if second is not None:
                raise self.unsupported("unpacking .values()", second)
            k = self.fresh("key")
            return {"var": k, "kind": "each", "iter": d}, [setv(var.text, A.Index(copy.deepcopy(d), A.Name(k, **at), **at))]
        if second is not None:
            raise self.unsupported("unpacking in a for loop (supported: enumerate, zip and .items())", second)
        return {"var": var.text, "kind": "each", "iter": it}, []

    def loop_else(self, loop, t):
        e = self.next()
        orelse = self.block()
        flag = self.fresh("broke")
        at = {"line": e.line, "col": e.col}

        def mark(stmts):
            out = []
            for s in stmts:
                if isinstance(s, A.Break):
                    out.append(A.Assign(A.Name(flag, line=s.line, col=s.col), A.BoolLit(True, line=s.line, col=s.col),
                                        line=s.line, col=s.col, end=s.end))
                elif isinstance(s, A.If):
                    s.body, s.orelse = mark(s.body), mark(s.orelse)
                out.append(s)
            return out

        loop.body = mark(loop.body)
        init = A.Assign(A.Name(flag, line=t.line, col=t.col), A.BoolLit(False, line=t.line, col=t.col),
                        line=t.line, col=t.col, end=t.line)
        after = A.If(A.UnaryOp("!", A.Name(flag, **at), **at), orelse, [], **self.pos(e))
        return [init, loop, after]

    def is_match(self):
        j = self.i
        while self.toks[j].kind not in ("NEWLINE", "EOF"):
            j += 1
        return self.toks[j - 1].text == ":" and self.toks[j + 1].kind == "INDENT" and self.toks[j + 2].text == "case"

    def match_stmt(self):
        t = self.next()
        subject = self.expr()
        self.expect("PUNCT", ":")
        self.expect("NEWLINE")
        self.expect("INDENT")
        pre = []
        if not pure(subject):
            v = self.fresh("value")
            pre.append(A.Assign(A.Name(v, line=t.line, col=t.col), subject, **self.pos(t)))
            subject = A.Name(v, line=t.line, col=t.col)
        cases = []
        while not self.accept("DEDENT") and not self.at("EOF"):
            c = self.expect("NAME", "case", "'case'")
            pats = [self.pattern()]
            while self.accept("OP", "|"):
                pats.append(self.pattern())
            guard = self.expr() if self.accept("KEYWORD", "if") else None
            body = self.block()
            cases.append((c, pats, guard, body, self.pos(c)))
        out = []
        for k, (c, pats, guard, body, at) in enumerate(reversed(cases)):
            if None in pats:
                if k:
                    raise self.unsupported("a 'case _' that is not the last case", c)
                test = None
            else:
                test = None
                for p in pats:
                    cmp = A.Compare("==", copy.deepcopy(subject), p, line=p.line, col=p.col)
                    test = cmp if test is None else A.BoolOp("||", test, cmp, line=p.line, col=p.col)
            if guard is not None:
                test = guard if test is None else A.BoolOp("&&", test, guard, line=guard.line, col=guard.col)
            out = body if test is None else [A.If(test, body, out, **at)]
        return pre + out

    def pattern(self):
        t = self.peek()
        if t.kind == "NAME" and t.text == "_":
            self.next()
            return None
        if t.kind == "NAME":
            raise self.unsupported("capture patterns in match (only literal values and _)", t)
        e = self.factor()
        if not isinstance(e, LITERALS):
            raise self.unsupported("this match pattern (only literal values and _)", t)
        return e

    def exprs(self):
        out = [self.expr()]
        while self.accept("PUNCT", ","):
            if self.at("NEWLINE") or self.at("OP", "="):
                break
            out.append(self.expr())
        return out

    def args(self, keywords=False):
        out, kw = Args(), []
        while not self.at("PUNCT", ")"):
            if self.at("NAME") and self.at("OP", "=", 1):
                if not keywords:
                    raise self.unsupported("keyword arguments")
                key = self.next()
                self.next()
                kw.append((key.text, self.expr()))
            elif kw:
                raise self.error("expected a keyword argument after keyword arguments")
            else:
                if self.at("OP", "*") or self.at("OP", "**"):
                    raise self.unsupported("argument unpacking")
                start = self.peek()
                e = self.expr()
                if self.at("KEYWORD", "for"):
                    e = self.comprehension(e, start)
                out.append(e)
            if not self.accept("PUNCT", ","):
                break
        out.kw = kw
        return out

    def expr(self):
        e = self.or_expr()
        if self.at("KEYWORD", "if"):
            t = self.next()
            cond = self.or_expr()
            self.expect("KEYWORD", "else")
            other = self.expr()
            if isinstance(e, A.Intrinsic) and e.name == "index_of" and isinstance(cond, A.Intrinsic) \
                    and cond.name == "contains" and A.same(cond.args, e.args) and isinstance(other, A.IntLit) \
                    and other.value == -1:
                return e
            return A.Cond(cond, e, other, line=e.line, col=e.col)
        return e

    def or_expr(self):
        e = self.and_expr()
        while self.at("KEYWORD", "or"):
            t = self.next()
            e = A.BoolOp("||", e, self.and_expr(), line=t.line, col=t.col)
        return e

    def and_expr(self):
        e = self.not_expr()
        while self.at("KEYWORD", "and"):
            t = self.next()
            e = A.BoolOp("&&", e, self.not_expr(), line=t.line, col=t.col)
        return e

    def not_expr(self):
        if self.at("KEYWORD", "not"):
            t = self.next()
            return A.UnaryOp("!", self.not_expr(), line=t.line, col=t.col)
        return self.comparison()

    def comparison(self):
        e = self.bitwise()
        t = self.peek()
        negate = t.kind == "KEYWORD" and t.text == "not" and self.at("KEYWORD", "in", 1)
        if t.kind == "KEYWORD" and t.text == "in" or negate:
            self.next()
            if negate:
                self.next()
            e = A.Intrinsic("contains", [self.bitwise(), e], line=t.line, col=t.col)
            return A.UnaryOp("!", e, line=t.line, col=t.col) if negate else e
        if t.kind == "KEYWORD" and t.text in ("is", "not"):
            raise self.unsupported(f"'{t.text}' operator", t)
        if t.kind == "OP" and t.text in COMPARE:
            self.next()
            right = self.bitwise()
            e = A.Compare(t.text, e, right, line=t.line, col=t.col)
            while self.peek().kind == "OP" and self.peek().text in COMPARE:
                n = self.next()
                if not pure(right):
                    raise self.unsupported("chained comparison around a function call", n)
                nxt = self.bitwise()
                e = A.BoolOp("&&", e, A.Compare(n.text, copy.deepcopy(right), nxt, line=n.line, col=n.col),
                             line=n.line, col=n.col)
                right = nxt
        return e

    def bitwise(self, level=0):
        ops = (("|",), ("^",), ("&",), ("<<", ">>"))
        if level == len(ops):
            return self.arith()
        e = self.bitwise(level + 1)
        while self.peek().kind == "OP" and self.peek().text in ops[level]:
            t = self.next()
            e = A.BinOp(t.text, e, self.bitwise(level + 1), line=t.line, col=t.col)
        return e

    def arith(self):
        e = self.term()
        while self.peek().kind == "OP" and self.peek().text in ("+", "-"):
            t = self.next()
            e = A.BinOp(t.text, e, self.term(), line=t.line, col=t.col)
        return e

    def term(self):
        e = self.factor()
        while self.peek().kind == "OP" and self.peek().text in ("*", "//", "%", "/", "@"):
            t = self.next()
            if t.text == "@":
                raise self.unsupported("'@' operator", t)
            if t.text == "%" and isinstance(e, A.StrLit):
                e = self.percent(e, t)
                continue
            op = {"//": "/", "/": "fdiv"}.get(t.text, t.text)
            e = A.BinOp(op, e, self.factor(), line=t.line, col=t.col)
        return e

    def factor(self):
        t = self.peek()
        if t.kind == "OP" and t.text == "-":
            self.next()
            e = self.factor()
            if isinstance(e, A.IntLit):
                return A.IntLit(-e.value, line=t.line, col=t.col)
            if isinstance(e, A.FloatLit):
                return A.FloatLit(-e.value, line=t.line, col=t.col)
            return A.UnaryOp("-", e, line=t.line, col=t.col)
        if t.kind == "OP" and t.text == "+":
            self.next()
            return self.factor()
        if t.kind == "OP" and t.text == "~":
            self.next()
            return A.UnaryOp("~", self.factor(), line=t.line, col=t.col)
        e = self.postfix()
        if self.at("OP", "**"):
            t = self.next()
            return A.Intrinsic("pow", [e, self.factor()], line=t.line, col=t.col)
        return e

    def postfix(self):
        e = self.atom()
        while True:
            if self.at("PUNCT", "["):
                self.next()
                pos = {"line": e.line, "col": e.col}
                index = None if self.at("PUNCT", ":") else self.expr()
                if self.accept("PUNCT", ":"):
                    stop = None if self.at("PUNCT", "]") else self.expr()
                    if self.at("PUNCT", ":"):
                        raise self.unsupported("slices with a step")
                    self.expect("PUNCT", "]")
                    start = self.from_end(e, index or A.IntLit(0, **pos))
                    stop = self.from_end(e, stop or A.Len(e, **pos))
                    e = A.Intrinsic("slice", [e, start, stop], **pos)
                    continue
                self.expect("PUNCT", "]")
                e = A.Index(e, self.from_end(e, index), **pos)
            elif self.at("PUNCT", "."):
                t = self.next()
                e = self.attribute(e, t)
            elif self.at("PUNCT", "("):
                raise self.unsupported("calling an expression")
            else:
                return e

    def from_end(self, e, x):
        if not (isinstance(x, A.IntLit) and x.value < 0):
            return x
        if not pure(e):
            raise self.unsupported("a negative index on a computed value", x)
        pos = {"line": x.line, "col": x.col}
        return A.BinOp("-", A.Len(copy.deepcopy(e), **pos), A.IntLit(-x.value, **pos), **pos)

    def attribute(self, e, dot):
        name = self.peek()
        if isinstance(e, A.Name) and e.id == "sys" and name.text == "exit" and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            if len(args) != 1:
                raise self.unsupported("sys.exit() without a status code", name)
            return A.Intrinsic("exit", args, line=e.line, col=e.col)
        if isinstance(e, A.Name) and e.id == "math" and name.kind in ("NAME", "TYPE", "BUILTIN"):
            self.next()
            pos = {"line": e.line, "col": e.col}
            if name.text in ("pi", "e") and not self.at("PUNCT", "("):
                return A.Intrinsic(name.text, [], **pos)
            if not self.accept("PUNCT", "("):
                raise self.unsupported(f"math.{name.text}", name)
            args = self.args()
            self.expect("PUNCT", ")")
            if name.text in MATH:
                return A.Intrinsic(MATH[name.text], args, **pos)
            if name.text in MATH_INT:
                return A.Intrinsic("f2i", [A.Intrinsic(MATH_INT[name.text], args, **pos)], **pos)
            if name.text == "trunc":
                return A.Intrinsic("num_int", args, **pos)
            raise self.unsupported(f"library call math.{name.text}", name)
        if name.text in ("sort", "pop", "split") + tuple(LIST_METHODS) and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            pos = {"line": e.line, "col": e.col}
            if name.text == "sort" and self.at("NAME", "reverse") and self.at("OP", "=", 1):
                self.next()
                self.next()
                flag = self.expect("KEYWORD", what="True or False")
                self.expect("PUNCT", ")")
                return A.Intrinsic("sort_desc" if flag.text == "True" else "sort", [e], **pos)
            args = self.args()
            self.expect("PUNCT", ")")
            if name.text == "pop":
                return A.Intrinsic("pop_at" if args else "pop", [e, *args], **pos)
            if name.text == "split":
                return A.Intrinsic("split" if args else "split_ws", [e, *args], **pos)
            if name.text == "sort":
                return A.Intrinsic("sort", [e, *args], **pos)
            return A.Intrinsic(LIST_METHODS[name.text], [e, *args], **pos)
        if name.text in ("get", "add", "discard", "remove", "keys") and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            pos = {"line": e.line, "col": e.col}
            if name.text == "keys" and not args:
                return e
            if name.text == "get" and len(args) == 2:
                return A.Intrinsic("map_get_or", [e, *args], **pos)
            if name.text == "get":
                raise self.unsupported("dict.get() without a default", name)
            if len(args) != 1:
                raise self.unsupported(f".{name.text}() with {len(args)} arguments", name)
            kind = {"add": "set_add", "remove": "remove_value"}.get(name.text, "set_del")
            return A.Intrinsic(kind, [e, *args], **pos)
        if name.text in ("rjust", "ljust") and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            if len(args) != 1:
                raise self.unsupported(f".{name.text}() with a fill character", name)
            return A.Intrinsic(name.text, [e, *args], line=e.line, col=e.col)
        if name.text in METHODS and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            return A.Intrinsic(METHODS[name.text], [e, *args], line=e.line, col=e.col)
        if name.text in ("format", "count", "extend", "items", "values") and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            pos = {"line": e.line, "col": e.col}
            if name.text == "format":
                if not isinstance(e, A.StrLit):
                    raise self.unsupported(".format() on anything but a string literal", name)
                return self.format_call(e, args, name)
            if name.text in ("items", "values"):
                if args:
                    raise self.error(f"{name.text}() takes no arguments")
                return A.Intrinsic("@" + name.text, [e], **pos)
            if len(args) != 1:
                raise self.unsupported(f".{name.text}() with {len(args)} arguments", name)
            if name.text == "extend":
                return A.Intrinsic("@extend", [e, args[0]], **pos)
            parts = A.Intrinsic("split", [e, args[0]], **pos)
            return A.BinOp("-", A.Len(parts, **pos), A.IntLit(1, **pos), **pos)
        raise self.unsupported(f"method or attribute '.{name.text}'", dot)

    def atom(self):
        t = self.peek()
        if t.kind == "NUMBER":
            self.next()
            return self.number(t)
        if t.kind == "FSTRING":
            self.next()
            return self.fstring(t)
        if t.kind == "BUILTIN" and t.text == "print" and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args, end, sep = [], None, None
            while not self.at("PUNCT", ")"):
                if self.at("NAME") and self.at("OP", "=", 1):
                    key = self.next()
                    self.next()
                    v = self.expr()
                    if key.text not in ("end", "sep") or not isinstance(v, A.StrLit):
                        raise self.unsupported(f"print({key.text}=...) (only end='...' and sep='...')", key)
                    if key.text == "end":
                        end = v
                    else:
                        sep = v
                else:
                    args.append(self.expr())
                if not self.accept("PUNCT", ","):
                    break
            self.expect("PUNCT", ")")
            if sep is not None and len(args) > 1:
                parts = []
                for k, a in enumerate(args):
                    if k:
                        parts.append(A.StrLit(sep.value, line=t.line, col=t.col))
                    parts.append(a if isinstance(a, A.StrLit) else self.formatted(a, "", t))
                args = [self.concat(parts, t)]
            call = A.Call("print", args, line=t.line, col=t.col)
            call.end = end
            return call
        if t.kind in ("NAME", "BUILTIN") and t.text == "input" and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            if not self.accept("PUNCT", ")"):
                prompt = self.expr()
                self.expect("PUNCT", ")")
                return A.Intrinsic("@prompt", [prompt], line=t.line, col=t.col)
            return A.Intrinsic("read_line", [], line=t.line, col=t.col)
        if t.kind == "TYPE" and t.text == "list" and [self.peek(k).text for k in range(1, 6)] == ["(", "map", "(", "int", ","]:
            for _ in range(6):
                self.next()
            x = self.expr()
            self.expect("PUNCT", ")")
            self.expect("PUNCT", ")")
            if not (isinstance(x, A.Intrinsic) and x.name == "split_ws"):
                raise self.unsupported("list(map(int, ...)) of anything but s.split()", t)
            return A.Intrinsic("s2ints", x.args, line=t.line, col=t.col)
        if t.kind == "NAME" and t.text == "format" and self.at("PUNCT", "(", 1):
            self.next()
            self.next()
            args = self.args()
            self.expect("PUNCT", ")")
            if len(args) != 2 or not isinstance(args[1], A.StrLit):
                raise self.unsupported("format() without a literal spec", t)
            return self.formatted(args[0], args[1].value, t)
        if t.kind == "STRING":
            value = ""
            while self.at("STRING"):
                s = self.next()
                try:
                    value += unquote(s.text)
                except ValueError as e:
                    raise self.unsupported(f"escape sequence '\\{e}'", s)
            return A.StrLit(value, line=t.line, col=t.col)
        if t.kind == "KEYWORD":
            if t.text in ("True", "False"):
                self.next()
                return A.BoolLit(t.text == "True", line=t.line, col=t.col)
            if t.text in ("None", "lambda"):
                raise self.unsupported(t.text, t)
            raise self.error("expected an expression")
        if t.kind in ("NAME", "BUILTIN", "TYPE"):
            self.next()
            if self.accept("PUNCT", "("):
                args = self.args(keywords=True)
                self.expect("PUNCT", ")")
                special = t.kind != "NAME" or t.text in BUILTIN_CALLS or t.text in HELPERS or t.text in (
                    "set", "dict", "round", "any", "all", "enumerate", "zip", "reversed")
                if args.kw and special:
                    raise self.unsupported(f"keyword arguments to {t.text}()", t)
                if t.kind == "NAME" and t.text in ("any", "all"):
                    return self.any_all(t, args)
                if t.kind == "NAME" and t.text in ("enumerate", "zip", "reversed"):
                    raise self.unsupported(f"{t.text}() outside a for loop header", t)
                if t.text == "len" and t.kind == "BUILTIN":
                    if len(args) != 1:
                        raise CompileError("parser", "Syntax error: len() takes exactly one argument", t.line, t.col)
                    return A.Len(args[0], line=t.line, col=t.col)
                if t.text == "range" and t.kind == "BUILTIN":
                    raise self.unsupported("range() outside a for loop", t)
                if t.kind == "TYPE" and t.text in CONVERT and len(args) == 1:
                    return A.Intrinsic(CONVERT[t.text], args, line=t.line, col=t.col)
                if t.kind == "NAME" and t.text in ("min", "max") and len(args) == 1:
                    return A.Intrinsic("l" + t.text, args, line=t.line, col=t.col)
                if t.kind == "NAME" and t.text in BUILTIN_CALLS:
                    if t.text in ("min", "max") and len(args) != 2:
                        raise self.unsupported(f"{t.text}() with {len(args)} argument(s)", t)
                    return A.Intrinsic(BUILTIN_CALLS[t.text], args, line=t.line, col=t.col)
                if t.kind == "NAME" and t.text in ("set", "dict") and not args:
                    return A.Intrinsic("set_new" if t.text == "set" else "map_new", [], line=t.line, col=t.col)
                if t.kind == "TYPE" and t.text == "list" and len(args) == 1:
                    return A.Intrinsic("lcopy", args, line=t.line, col=t.col)
                if t.kind == "NAME" and t.text == "round":
                    if len(args) != 1:
                        raise self.unsupported("round() with a number of digits", t)
                    inner = A.Intrinsic("round_even", args, line=t.line, col=t.col)
                    return A.Intrinsic("f2i", [inner], line=t.line, col=t.col)
                if t.kind == "NAME" and t.text in HELPERS:
                    return A.Intrinsic(HELPERS[t.text], args, line=t.line, col=t.col)
                if t.kind == "TYPE":
                    raise self.unsupported(f"conversion {t.text}()", t)
                return A.Call(t.text, list(args), kw=list(args.kw), line=t.line, col=t.col)
            if t.kind != "NAME":
                raise self.unsupported(f"using '{t.text}' as a value", t)
            return A.Name(t.text, line=t.line, col=t.col)
        if self.accept("PUNCT", "("):
            e = self.expr()
            if self.at("PUNCT", ","):
                raise self.unsupported("tuples")
            self.expect("PUNCT", ")")
            return e
        if self.accept("PUNCT", "["):
            items = []
            while not self.at("PUNCT", "]"):
                items.append(self.expr())
                if self.at("KEYWORD", "for"):
                    c = self.comprehension(items[0], t)
                    self.expect("PUNCT", "]")
                    return self.as_grid(c) or c
                if not self.accept("PUNCT", ","):
                    break
            self.expect("PUNCT", "]")
            return A.ArrayLit(items, line=t.line, col=t.col)
        if self.at("PUNCT", "{") and self.at("PUNCT", "}", 1):
            self.next()
            self.next()
            return A.Intrinsic("map_new", [], line=t.line, col=t.col)
        if self.accept("PUNCT", "{"):
            return self.braces(t)
        raise self.error("expected an expression")

    def braces(self, t):
        pos = {"line": t.line, "col": t.col}
        first = self.expr()
        if self.accept("PUNCT", ":"):
            value = self.expr()
            if self.at("KEYWORD", "for"):
                c = self.comprehension(value, t, key=first)
                self.expect("PUNCT", "}")
                return c
            keys, values = [first], [value]
            while self.accept("PUNCT", ",") and not self.at("PUNCT", "}"):
                keys.append(self.expr())
                self.expect("PUNCT", ":")
                values.append(self.expr())
            self.expect("PUNCT", "}")
            return A.DictLit(keys, values, **pos)
        if self.at("KEYWORD", "for"):
            raise self.unsupported("set comprehension")
        items = [first]
        while self.accept("PUNCT", ",") and not self.at("PUNCT", "}"):
            items.append(self.expr())
        self.expect("PUNCT", "}")
        return A.SetLit(items, **pos)

    def comprehension(self, elt, start, key=None):
        f = self.expect("KEYWORD", "for")
        var = self.expect("NAME", what="a loop variable")
        if self.at("PUNCT", ","):
            raise self.unsupported("unpacking in a comprehension", f)
        self.expect("KEYWORD", "in")
        at = {"line": f.line, "col": f.col, "end": f.line}
        if self.at("BUILTIN", "range"):
            a, b, c = self.range_args()
            loop = A.For(var.text, "range", [], a, b, c, **at)
        else:
            loop = A.For(var.text, "each", [], iter=self.or_expr(), **at)
        cond = self.or_expr() if self.accept("KEYWORD", "if") else None
        if self.at("KEYWORD", "for") or self.at("KEYWORD", "if"):
            raise self.unsupported("a comprehension with several for or if clauses")
        return A.Comp(elt, loop, cond, key, line=start.line, col=start.col)

    @staticmethod
    def as_grid(c):
        row, loop = c.elt, c.loop
        ok = c.cond is None and c.key is None and loop.kind == "range" and isinstance(row, A.BinOp) and row.op == "*" \
            and isinstance(row.left, A.ArrayLit) and len(row.left.items) == 1 and loop.var not in A.names(row) \
            and isinstance(loop.start, A.IntLit) and loop.start.value == 0 and loop.step.value == 1
        return A.Intrinsic("grid", [loop.stop, row.right, row.left.items[0]], line=c.line, col=c.col) if ok else None

    def any_all(self, t, args):
        if len(args) != 1 or not isinstance(args[0], A.Comp) or args[0].key is not None:
            raise self.unsupported(f"{t.text}() of anything but a generator (e.g. {t.text}(x > 0 for x in xs))", t)
        c = args[0]
        pos = {"line": t.line, "col": t.col}
        test = c.elt if t.text == "any" else A.UnaryOp("!", c.elt, **pos)
        cond = test if c.cond is None else A.BoolOp("&&", c.cond, test, **pos)
        hits = A.Comp(A.IntLit(1, **pos), c.loop, cond, line=c.line, col=c.col)
        return A.Compare(">" if t.text == "any" else "==", A.Len(hits, **pos), A.IntLit(0, **pos), **pos)

    def concat(self, parts, t):
        out = parts[0]
        for x in parts[1:]:
            out = A.BinOp("+", out, x, line=t.line, col=t.col)
        return out

    def percent(self, fmt, t):
        if self.accept("PUNCT", "("):
            values = [self.expr()]
            while self.accept("PUNCT", ",") and not self.at("PUNCT", ")"):
                values.append(self.expr())
            self.expect("PUNCT", ")")
        else:
            values = [self.factor()]
        parts, text, k = [], "", 0
        for m in re.finditer(r"%(-)?(\d+)?(?:\.(\d+))?([a-zA-Z%])|[^%]+|%", fmt.value):
            if not m.group(4):
                if m.group(0) == "%":
                    raise self.unsupported("a lone '%' in a format string", t)
                text += m.group(0)
                continue
            left, width, prec, conv = m.groups()
            if conv == "%":
                text += "%"
                continue
            if conv not in "disf":
                raise self.unsupported(f"'%{conv}' formatting (supported: %d, %s, %f)", t)
            if k >= len(values):
                raise self.error("not enough values for the format string", t)
            if conv == "f":
                spec = ("<" if left else "") + (width or "") + "." + (prec or "6") + "f"
            elif conv == "s":
                spec = ("<" if left else ">" if width else "") + (width or "")
            else:
                spec = ("<" if left else "") + (width or "") + "d"
            if text:
                parts.append(A.StrLit(text, line=t.line, col=t.col))
                text = ""
            parts.append(self.formatted(values[k], spec, t))
            k += 1
        if k != len(values):
            raise self.error("too many values for the format string", t)
        if text or not parts:
            parts.append(A.StrLit(text, line=t.line, col=t.col))
        return self.concat(parts, t)

    def format_call(self, template, args, t):
        parts, text, auto = [], "", 0
        body = template.value
        k = 0
        while k < len(body):
            c = body[k]
            if c in "{}" and body[k:k + 2] == c * 2:
                text += c
                k += 2
                continue
            if c == "}":
                raise self.error("single '}' in a format string", t)
            if c != "{":
                text += c
                k += 1
                continue
            end = body.find("}", k)
            if end < 0:
                raise self.error("unterminated '{' in a format string", t)
            field, _, spec = body[k + 1:end].partition(":")
            if field == "":
                idx, auto = auto, auto + 1
            elif field.isdigit():
                idx = int(field)
            else:
                raise self.unsupported("named fields in .format()", t)
            if idx >= len(args):
                raise self.error("not enough values for the format string", t)
            if text:
                parts.append(A.StrLit(text, line=t.line, col=t.col))
                text = ""
            parts.append(self.formatted(args[idx], spec, t))
            k = end + 1
        if text or not parts:
            parts.append(A.StrLit(text, line=t.line, col=t.col))
        return self.concat(parts, t)

    def fstring(self, t):
        q = t.text[0]
        n = 3 if t.text.startswith(q * 3) else 1
        body = t.text[n:-n]
        pos = {"line": t.line, "col": t.col}
        parts, text, k = [], "", 0
        while k < len(body):
            c = body[k]
            if c in "{}" and body[k:k + 2] == c * 2:
                text += c
                k += 2
                continue
            if c == "}":
                raise self.fail("Syntax error: single '}' in an f-string", t)
            if c != "{":
                text += c
                k += 1
                continue
            if text:
                parts.append(self.literal(q + text + q, t))
                text = ""
            depth, j = 0, k + 1
            while j < len(body) and (depth or body[j] not in ":}"):
                depth += {"[": 1, "(": 1, "]": -1, ")": -1}.get(body[j], 0)
                j += 1
            inner = body[k + 1:j]
            spec = ""
            if j < len(body) and body[j] == ":":
                end = body.index("}", j)
                spec, j = body[j + 1:end], end
            if j >= len(body):
                raise self.fail("Syntax error: unterminated '{' in an f-string", t)
            if "!" in inner.replace("!=", ""):
                raise self.unsupported("conversions (!r, !s) in f-strings", t)
            toks = [x for x in lex(inner.strip()) if x.kind not in ("NEWLINE", "INDENT", "DEDENT")]
            sub = Parser([*toks])
            sub.in_func = self.in_func
            e = sub.expr()
            if not sub.at("EOF"):
                raise self.fail("Syntax error: invalid expression in an f-string", t)
            for x in A.walk(e):
                x.line, x.col = t.line, t.col
            parts.append(self.formatted(e, spec, t))
            k = j + 1
        if text or not parts:
            parts.append(self.literal(q + text + q, t))
        out = parts[0]
        for p in parts[1:]:
            out = A.BinOp("+", out, p, **pos)
        return out

    def literal(self, quoted, t):
        try:
            return A.StrLit(unquote(quoted), line=t.line, col=t.col)
        except ValueError as e:
            raise self.unsupported(f"escape sequence '\\{e}'", t)

    def formatted(self, e, spec, t):
        pos = {"line": t.line, "col": t.col}
        m = SPEC.match(spec)
        if not m or m.group(3) and m.group(4):
            raise self.unsupported(f"format spec '{spec}' (supported: .2f, 8, >8, <8, 8.2f, d)", t)
        align, width, prec = m.group(1), m.group(2), m.group(3)
        value = A.Intrinsic("fixed", [e, A.IntLit(int(prec), **pos)], **pos) if prec else None
        if not width:
            return value or A.Intrinsic("str", [e], **pos)
        w = A.IntLit(int(width), **pos)
        if align or value:
            kind = "ljust" if align == "<" else "rjust"
            return A.Intrinsic(kind, [value or A.Intrinsic("str", [e], **pos), w], **pos)
        return A.Intrinsic("pad", [e, w], **pos)

    def grid(self, row, t):
        f = self.next()
        var = self.expect("NAME", what="a loop variable")
        self.expect("KEYWORD", "in")
        r = self.peek()
        if not (r.kind == "BUILTIN" and r.text == "range"):
            raise self.unsupported("list comprehension", f)
        self.next()
        self.expect("PUNCT", "(")
        args = self.args()
        self.expect("PUNCT", ")")
        self.expect("PUNCT", "]")
        ok = isinstance(row, A.BinOp) and row.op == "*" and isinstance(row.left, A.ArrayLit) \
            and len(row.left.items) == 1 and len(args) == 1 and var.text not in A.names(row)
        if not ok:
            raise self.unsupported("list comprehension (only [[v] * cols for _ in range(rows)])", f)
        return A.Intrinsic("grid", [args[0], row.right, row.left.items[0]], line=t.line, col=t.col)

    def number(self, t):
        text = t.text.replace("_", "").lower()
        if text.endswith("j"):
            raise self.unsupported("complex number", t)
        if not text.startswith(("0x", "0o", "0b")) and ("." in text or "e" in text):
            try:
                return A.FloatLit(float(text), line=t.line, col=t.col)
            except ValueError:
                raise CompileError("parser", f"Syntax error: invalid number '{t.text}'", t.line, t.col)
        try:
            return A.IntLit(int(text, 0), line=t.line, col=t.col)
        except ValueError:
            raise CompileError("parser", f"Syntax error: invalid number '{t.text}'", t.line, t.col)
