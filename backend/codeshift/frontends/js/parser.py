from dataclasses import dataclass

from ... import ast as A
from ...library import LISTOPS, MAP_GENERIC, MAPOPS
from ...semantic import rewrite
from .. import idioms
from ..cfamily import CFamily


@dataclass(eq=False)
class Path(A.Expr):
    text: str


@dataclass(eq=False)
class Log(A.Expr):
    args: list


@dataclass(eq=False)
class Arrow(A.Expr):
    params: list
    body: object


@dataclass(eq=False)
class Spread(A.Expr):
    value: object


@dataclass(eq=False)
class NewArray(A.Expr):
    size: object


@dataclass(eq=False)
class Obj(A.Expr):
    key: str
    value: object


@dataclass(eq=False)
class Splice(A.Expr):
    obj: object
    args: list


@dataclass(eq=False)
class Pick(A.Expr):
    op: str
    a: str
    b: str


HELPERS = {"csRoundEven": "round_even", "csRoundAway": "round_away", "csIsDigit": "is_digit", "csIsAlpha": "is_alpha",
           "csIsSpace": "is_space", "csIsUpper": "is_upper", "csIsLower": "is_lower", "csSplitWs": "split_ws",
           "csReadLine": "read_line"}
ARRAY_METHODS = {"push": "push", "pop": "pop", "reverse": "reverse", "split": "split"}
MARKERS = (Path, Log, Arrow, Spread, NewArray, Obj, Splice, Pick)
STRING_METHODS = {"toUpperCase": "to_upper", "toLowerCase": "to_lower", "trim": "trim", "startsWith": "starts",
                  "endsWith": "ends", "includes": "contains", "indexOf": "index", "replaceAll": "replace_all",
                  "repeat": "repeat"}
MATH = {
    "abs": "abs", "min": "min", "max": "max", "pow": "pow_f", "sqrt": "sqrt", "floor": "floor", "ceil": "ceil",
    "round": "round_js", "sin": "sin", "cos": "cos", "tan": "tan", "atan2": "atan2", "log": "log", "log10": "log10",
    "log2": "log2", "exp": "exp", "hypot": "hypot",
}


def splice_index(e):
    if isinstance(e, A.Index) and isinstance(e.target, Splice) and isinstance(e.index, A.IntLit) and e.index.value == 0:
        s = e.target
        if len(s.args) == 2 and isinstance(s.args[1], A.IntLit) and s.args[1].value == 1:
            return A.Intrinsic("pop_at", [s.obj, s.args[0]], line=e.line, col=e.col)
    return e


def written(e):
    spine = []
    while isinstance(e, A.BinOp) and e.op == "+":
        spine.append(e.right)
        e = e.left
    spine.append(e)
    spine.reverse()
    mark, text, exprs = chr(0), "", []
    for x in spine:
        if isinstance(x, A.StrLit):
            text += x.value
            continue
        if isinstance(x, A.Intrinsic) and x.name == "str":
            x = x.args[0]
        text += f"{mark}{len(exprs)}{mark}"
        exprs.append(x)
    return idioms.words(text, mark, exprs, {"line": e.line, "col": e.col})


def parse(tokens):
    return JSParser(tokens).module()


class JSParser(CFamily):
    lang = "js"

    def __init__(self, toks):
        super().__init__(toks)
        self.divs = {}

    def module(self):
        funcs, body, helpers = [], [], []
        while not self.at("EOF"):
            if self.at("KEYWORD", "function") and self.peek(1).text in HELPERS:
                t = self.next()
                name = self.next()
                users = {HELPERS[name.text]} | ({"s2ints"} if name.text == "csSplitWs" else set())
                helpers.append((users, t.line, self.skip_braced().line))
            elif self.at("KEYWORD", "function"):
                funcs.append(self.function())
            else:
                body += self.statement()
        m = A.Module(funcs, body, lang="js", line=1, col=1)
        for s in [*funcs, *body]:
            rewrite(s, splice_index)
        for n in A.walk_all([*funcs, *body]):
            if isinstance(n, MARKERS):
                raise self.unsupported("this JavaScript expression", n)
        idioms.attach(m, helpers)
        for n in self.divs.values():
            if n is not None:
                n.op = "fdiv"
        return m

    def function(self):
        t = self.next()
        name = self.expect("NAME", what="a function name")
        self.expect_op("(")
        params = []
        while not self.at_op(")"):
            p = self.expect("NAME", what="a parameter name")
            if self.at_op("="):
                raise self.unsupported("default parameter values")
            params.append(A.Param(p.text, line=p.line, col=p.col))
            if not self.accept_op(","):
                break
        self.expect_op(")")
        saved = self.fresh_scopes(p.name for p in params)
        body = self.block()
        self.scopes = saved
        return A.FunctionDef(name.text, params, body, **self.pos(t))

    def statement(self):
        if self.at("KEYWORD", "function"):
            raise self.unsupported("nested functions")
        return super().statement()

    def decl_start(self):
        return self.at("KEYWORD") and self.peek().text in ("let", "const", "var")

    def declaration(self):
        t = self.next()
        if self.at_op("["):
            targets = self.expr()
            self.expect_op("=")
            values = self.expr()
            if not (isinstance(targets, A.ArrayLit) and isinstance(values, A.ArrayLit)
                    and all(isinstance(x, A.Name) for x in targets.items) and len(targets.items) == len(values.items)):
                raise self.unsupported("this destructuring declaration", t)
            if t.text != "var":
                for x in targets.items:
                    self.declare_name(x.id, x)
            return [idioms.assign(targets.items, values.items, self.pos(t))]
        names, values = [], []
        while True:
            n = self.expect("NAME", what="a variable name")
            if t.text != "var":
                self.declare_name(n.text, n)
            value = self.expr() if self.accept_op("=") else None
            names.append(A.Name(n.text, line=n.line, col=n.col))
            values.append(value)
            if not self.accept_op(","):
                break
        if all(v is None for v in values):
            return []
        if any(v is None for v in values):
            raise self.unsupported("mixing initialised and uninitialised declarations", t)
        return idioms.declare(names, values, [None] * len(names), self.pos(t))

    def for_each(self, t):
        if not (self.at("KEYWORD") and self.peek().text in ("let", "const", "var") and self.peek(1).kind == "NAME"
                and self.peek(2).kind == "KEYWORD" and self.peek(2).text in ("of", "in")):
            return None
        self.next()
        var = self.next()
        self.declare_name(var.text, var)
        if self.next().text == "in":
            raise self.unsupported("for-in loops", var)
        it = self.expr()
        self.expect_op(")")
        return [A.For(var.text, "each", self.body(), iter=it, **self.pos(t))]

    def expr(self, level=1):
        e = super().expr(level)
        while level <= 1 and self.at_op("??"):
            t = self.next()
            if not (isinstance(e, A.Intrinsic) and e.name == "map_get"):
                raise self.unsupported("'??' (only map.get(k) ?? default)", t)
            e = A.Intrinsic("map_get_or", [*e.args, super().expr(2)], line=e.line, col=e.col)
        for n in A.walk(e):
            if isinstance(n, A.BinOp) and n.op == "/":
                self.divs.setdefault(id(n), n)
        return e

    def primary(self):
        t = self.peek()
        if self.at_op("(") and self.arrow_ahead():
            self.next()
            params = []
            while not self.at_op(")"):
                params.append(self.expect("NAME", what="a parameter").text)
                if not self.accept_op(","):
                    break
            self.expect_op(")")
            self.expect_op("=>")
            return Arrow(params, self.expr(), line=t.line, col=t.col)
        return super().primary()

    def ternary(self, cond, t, level):
        if level > 1:
            return cond
        if isinstance(cond, A.Compare) and cond.op in ("<", ">") and all(isinstance(x, A.Name) for x in (cond.left, cond.right)):
            save = self.i
            self.next()
            a = self.expr()
            if self.accept_op(":"):
                b = self.expr()
                if isinstance(a, A.Name) and isinstance(b, A.Name) and (a.id, b.id) == (cond.left.id, cond.right.id):
                    return Pick(cond.op, a.id, b.id, line=t.line, col=t.col)
            self.i = save
        return super().ternary(cond, t, level)

    def arrow_ahead(self):
        k, depth = 0, 0
        while True:
            tok = self.peek(k)
            if tok.kind == "EOF":
                return False
            depth += {"(": 1, ")": -1}.get(tok.text, 0) if tok.kind == "PUNCT" else 0
            if depth == 0:
                return self.peek(k + 1).text == "=>"
            k += 1

    def primary_extra(self):
        t = self.peek()
        if self.at_op("["):
            self.next()
            items = []
            while not self.at_op("]"):
                items.append(self.expr())
                if not self.accept_op(","):
                    break
            self.expect_op("]")
            if len(items) == 1 and isinstance(items[0], Spread):
                return A.Intrinsic("lcopy", [items[0].value], line=t.line, col=t.col)
            return A.ArrayLit(items, line=t.line, col=t.col)
        if self.at_op("..."):
            self.next()
            return Spread(self.unary(), line=t.line, col=t.col)
        if self.at_op("{"):
            self.next()
            key = self.expect("NAME", what="a property name")
            self.expect_op(":")
            value = self.expr()
            self.expect_op("}")
            return Obj(key.text, value, line=t.line, col=t.col)
        if t.kind == "KEYWORD" and t.text == "new" and self.peek(1).text in ("Map", "Set"):
            self.next()
            kind = self.next()
            if self.args():
                raise self.unsupported(f"new {kind.text}(...) with arguments", t)
            return A.Intrinsic("map_new" if kind.text == "Map" else "set_new", [], line=t.line, col=t.col)
        if t.kind == "KEYWORD" and t.text == "new" and self.peek(1).text == "Array":
            self.next()
            self.next()
            args = self.args()
            if len(args) != 1:
                raise self.unsupported("new Array with these arguments", t)
            return NewArray(args[0], line=t.line, col=t.col)
        if t.kind == "KEYWORD" and t.text in ("null", "undefined", "new", "this", "typeof", "function"):
            raise self.unsupported(t.text, t)
        if t.kind == "NAME" and t.text == "String" and self.peek(1).text == "(":
            self.next()
            args = self.args()
            if len(args) != 1:
                raise self.fail("Syntax error: String() takes one value", t)
            return A.Intrinsic("str", args, line=t.line, col=t.col)
        if t.kind == "NAME" and t.text in ("Math", "console", "Number", "String", "JSON", "Array", "process"):
            self.next()
            return Path(t.text, line=t.line, col=t.col)
        return None

    def call(self, t, args):
        if t.text in HELPERS:
            return A.Intrinsic(HELPERS[t.text], args, line=t.line, col=t.col)
        if t.text == "parseInt" and (len(args) == 1 or len(args) == 2 and isinstance(args[1], A.IntLit)
                                     and args[1].value == 10):
            return A.Intrinsic("s2i", args[:1], line=t.line, col=t.col)
        if t.text == "parseFloat" and len(args) == 1:
            return A.Intrinsic("s2f", args, line=t.line, col=t.col)
        return super().call(t, args)

    def member(self, e, name, t):
        args = self.args() if self.at_op("(") else None
        pos = {"line": e.line, "col": e.col}
        if not isinstance(e, Path):
            n = name.text
            if n == "size" and args is None:
                return A.Intrinsic("size", [e], **pos)
            if n == "keys" and args == []:
                return e
            if n in ("get", "has", "delete", "add") and args is not None and len(args) == 1:
                kind = {"get": "map_get", "add": "set_add"}.get(n, n)
                return A.Intrinsic(kind, [e, *args], **pos)
            if n == "set" and args is not None and len(args) == 2:
                return A.Intrinsic("map_put", [e, *args], **pos)
        if isinstance(e, Path):
            path = f"{e.text}.{name.text}"
            if path == "console.log" and args is not None:
                return Log(args, line=e.line, col=e.col)
            if path == "process.stdout" and args is None:
                return Path(path, line=e.line, col=e.col)
            if path == "process.stdout.write" and args is not None and len(args) == 1:
                if isinstance(args[0], A.StrLit) and not args[0].value.strip(" "):
                    node = Log([], line=e.line, col=e.col)
                    node.ending = args[0].value
                    return node
                parts = written(args[0])
                if parts is None:
                    raise self.unsupported("process.stdout.write() text glued to a value without a space", t)
                node = Log(parts, line=e.line, col=e.col)
                node.ending = ""
                return node
            if path == "process.exit" and args is not None and len(args) == 1:
                return A.Intrinsic("exit", args, line=e.line, col=e.col)
            if path == "Math.floor" and args is not None and len(args) == 1 and isinstance(args[0], A.BinOp) \
                    and args[0].op == "/":
                self.divs[id(args[0])] = None
                return args[0]
            if path == "Math.trunc" and args is not None and len(args) == 1:
                return A.Intrinsic("num_int", args, line=e.line, col=e.col)
            if path in ("Math.min", "Math.max") and args and len(args) == 1 and isinstance(args[0], Spread):
                return A.Intrinsic("l" + name.text, [args[0].value], line=e.line, col=e.col)
            if path == "Array.from" and args and len(args) == 2 and isinstance(args[0], Obj) and args[0].key == "length" \
                    and isinstance(args[1], Arrow) and not args[1].params and isinstance(args[1].body, A.Intrinsic) \
                    and args[1].body.name == "list_fill":
                fill = args[1].body
                return A.Intrinsic("grid", [args[0].value, fill.args[1], fill.args[0]], line=e.line, col=e.col)
            if path in ("Math.PI", "Math.E") and args is None:
                return A.Intrinsic("pi" if path == "Math.PI" else "e", [], line=e.line, col=e.col)
            if path == "String.fromCharCode" and args is not None and len(args) == 1:
                return A.Intrinsic("chr", args, line=e.line, col=e.col)
            if e.text == "Math" and name.text in MATH and args is not None:
                return A.Intrinsic(MATH[name.text], args, line=e.line, col=e.col)
            raise self.unsupported(f"library call {path}", t)
        if name.text == "length" and args is None:
            return A.Len(e, line=e.line, col=e.col)
        if isinstance(e, NewArray) and name.text == "fill" and args and len(args) == 1:
            return A.Intrinsic("list_fill", [args[0], e.size], line=e.line, col=e.col)
        if name.text in ARRAY_METHODS and args is not None:
            return A.Intrinsic(ARRAY_METHODS[name.text], [e, *args], line=e.line, col=e.col)
        if name.text in ("toFixed", "padStart", "padEnd") and args is not None and len(args) == 1:
            kind = {"toFixed": "fixed", "padStart": "rjust", "padEnd": "ljust"}[name.text]
            return A.Intrinsic(kind, [e, *args], line=e.line, col=e.col)
        if name.text == "map" and args and len(args) == 1 and isinstance(e, A.Intrinsic) and e.name == "split_ws" \
                and isinstance(args[0], Arrow) and len(args[0].params) == 1 and isinstance(args[0].body, A.Intrinsic) \
                and args[0].body.name == "s2i" and A.same(args[0].body.args[0], A.Name(args[0].params[0])):
            return A.Intrinsic("s2ints", e.args, line=e.line, col=e.col)
        if name.text == "join" and args is not None and len(args) == 1:
            return A.Intrinsic("join", [args[0], e], line=e.line, col=e.col)
        if name.text == "splice" and args is not None:
            return Splice(e, args, line=e.line, col=e.col)
        if name.text == "sort" and args is not None:
            if not args:
                if isinstance(e, A.Intrinsic) and e.name == "lcopy":
                    return A.Intrinsic("jssorted", e.args, line=e.line, col=e.col)
                return A.Intrinsic("jssort", [e], line=e.line, col=e.col)
            cmp = args[0]
            if len(args) == 1 and isinstance(cmp, Arrow) and len(cmp.params) == 2 and isinstance(cmp.body, A.BinOp) \
                    and cmp.body.op == "-" and all(isinstance(x, A.Name) for x in (cmp.body.left, cmp.body.right)):
                order = (cmp.body.left.id, cmp.body.right.id)
                if order == tuple(cmp.params):
                    kind = "sort"
                elif order == tuple(reversed(cmp.params)):
                    kind = "sort_desc"
                else:
                    kind = None
                if kind:
                    if kind == "sort" and isinstance(e, A.Intrinsic) and e.name == "lcopy":
                        return A.Intrinsic("sorted", e.args, line=e.line, col=e.col)
                    return A.Intrinsic(kind, [e], line=e.line, col=e.col)
            raise self.unsupported("this sort() comparator", t)
        if name.text == "reduce" and args and len(args) == 2 and isinstance(args[0], Arrow) \
                and len(args[0].params) == 2 and isinstance(args[0].body, A.BinOp) and args[0].body.op == "+" \
                and isinstance(args[1], A.IntLit) and args[1].value == 0:
            return A.Intrinsic("sum", [e], line=e.line, col=e.col)
        if name.text == "reduce" and args and len(args) == 1 and isinstance(args[0], Arrow)                 and isinstance(args[0].body, Pick) and [args[0].body.a, args[0].body.b] == args[0].params:
            return A.Intrinsic("lmin" if args[0].body.op == "<" else "lmax", [e], line=e.line, col=e.col)
        if name.text == "slice" and args is not None and len(args) in (1, 2):
            stop = args[1] if len(args) == 2 else A.Len(e, line=e.line, col=e.col)
            return A.Intrinsic("slice", [e, args[0], stop], line=e.line, col=e.col)
        if name.text in STRING_METHODS and args is not None:
            return A.Intrinsic(STRING_METHODS[name.text], [e, *args], line=e.line, col=e.col)
        if name.text == "charCodeAt" and args is not None and len(args) == 1:
            i = args[0]
            target = e if isinstance(i, A.IntLit) and i.value == 0 else A.Index(e, i, line=e.line, col=e.col)
            return A.Intrinsic("ord", [target], line=e.line, col=e.col)
        raise self.unsupported(f"member '.{name.text}'", t)

    def assignment(self, lhs, op, value, t):
        if isinstance(lhs, A.ArrayLit):
            if op.text != "=" or not isinstance(value, A.ArrayLit) or len(lhs.items) != len(value.items):
                raise self.unsupported("this destructuring assignment", t)
            return idioms.assign([self.target(x) for x in lhs.items], value.items, self.pos(t))
        if (op.text == "=" and isinstance(value, A.BinOp) and value.op == "/" and self.divs.get(id(value), 0) is None
                and A.same(value.left, lhs)):
            return A.AugAssign(self.target(lhs), "/", value.right, **self.pos(t))
        if op.text == "/=":
            return A.AugAssign(self.target(lhs), "fdiv", value, **self.pos(t))
        return super().assignment(lhs, op, value, t)

    def expr_statement(self, e, t):
        if isinstance(e, Log):
            node = A.Print(e.args, **self.pos(t))
            if hasattr(e, "ending"):
                node.ending = e.ending
            return [node]
        if isinstance(e, A.Intrinsic) and e.name == "reverse" and isinstance(e.args[0], A.Intrinsic) \
                and e.args[0].name == "jssort":
            e = A.Intrinsic("sort_desc", e.args[0].args, line=e.line, col=e.col)
        if isinstance(e, Splice) and len(e.args) == 2 and isinstance(e.args[1], A.IntLit) and e.args[1].value == 1:
            e = A.Intrinsic("remove_at", [e.obj, e.args[0]], line=e.line, col=e.col)
        elif isinstance(e, Splice) and len(e.args) == 3 and isinstance(e.args[1], A.IntLit) and e.args[1].value == 0:
            e = A.Intrinsic("insert", [e.obj, e.args[0], e.args[2]], line=e.line, col=e.col)
        if isinstance(e, A.Intrinsic) and e.name in set(LISTOPS) | set(MAPOPS) | MAP_GENERIC | {"jssort", "exit"}:
            return [A.ExprStmt(e, **self.pos(t))]
        return super().expr_statement(e, t)
