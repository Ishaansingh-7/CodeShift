from dataclasses import dataclass

from ... import ast as A
from ...library import LISTOPS, MAP_GENERIC, MAPOPS
from ...semantic import mp, sset
from .. import idioms
import copy

from ..cfamily import ASSIGN, BINARY_GO, CFamily
from ...desugar import LITERALS, pure

PACKAGES = {"fmt", "math", "strconv", "strings", "slices", "maps", "os", "sort"}
SLICES = {"Index": "index", "Contains": "contains", "Sort": "sort", "Reverse": "reverse", "Clone": "clone",
          "Min": "lmin", "Max": "lmax", "Sorted": "sorted", "Values": "values", "Insert": "go_insert",
          "Delete": "go_delete"}
HELPERS = {"csAbs": "abs_i", "csIpow": "pow_i", "csParseInt": "s2i", "csParseFloat": "s2f", "csRoundJs": "round_js",
           "csBoolPy": "b2s_py", "csIsDigit": "is_digit", "csIsAlpha": "is_alpha", "csIsSpace": "is_space",
           "csIsUpper": "is_upper", "csIsLower": "is_lower", "csCharUpper": "cupper", "csCharLower": "clower",
           "csPop": "pop", "csPopAt": "pop_at", "csSum": "sum", "csFill": "go_fill", "csGrid": "go_grid",
           "csGetOr": "map_get_or", "csHas": "has", "csReadLine": "read_line", "csInts": "s2ints"}
STRINGS = {"ToUpper": "to_upper", "ToLower": "to_lower", "TrimSpace": "trim", "HasPrefix": "starts",
           "HasSuffix": "ends", "Contains": "contains", "ContainsRune": "contains", "Index": "find",
           "ReplaceAll": "replace_all", "Repeat": "repeat", "Split": "split", "Fields": "split_ws", "Join": "go_join"}
MATH = {
    "Abs": "abs", "Pow": "pow_f", "Sqrt": "sqrt", "Floor": "floor", "Ceil": "ceil", "Trunc": "trunc",
    "Round": "round_away", "RoundToEven": "round_even", "Sin": "sin", "Cos": "cos", "Tan": "tan", "Atan2": "atan2",
    "Log": "log", "Log10": "log10", "Log2": "log2", "Exp": "exp", "Hypot": "hypot",
}
USERS = {
    "math": {"abs", "pow_f", "sqrt", "floor", "ceil", "trunc", "round_away", "round_even", "sin", "cos", "tan", "atan2",
             "log", "log10", "log2", "exp", "hypot", "pi", "e", "round_js"},
    "strconv": {"i2s", "f2s", "b2s", "s2i", "s2f"},
    "strings": {"upper", "lower", "trim", "starts", "ends", "contains_s", "contains_c", "find", "replace_all", "repeat",
                "to_upper", "to_lower", "contains", "s2i", "s2f", "split", "split_ws", "join"},
    "slices": {"index", "contains", "sort", "reverse", "lcopy", "lslice", "lmin", "lmax", "sorted", "insert",
               "remove_at", "sort_desc", "pop_at"},
    "maps": {"sorted"},
    "os": {"exit"},
    "sort": {"sort"},
}


@dataclass(eq=False)
class StructVal(A.Expr):
    pass
GTYPE = {"int": "int", "int64": "int", "bool": "bool", "string": "str", "rune": "char", "byte": "char", "float64": "float"}
ZERO = {"int": 0, "bool": False, "str": ""}


@dataclass(eq=False)
class Path(A.Expr):
    text: str


@dataclass(eq=False)
class Log(A.Expr):
    args: list


def sort_desc(stmts):
    k = 0
    while k < len(stmts):
        s = stmts[k]
        for b in A.blocks(s):
            sort_desc(b)
        nxt = stmts[k + 1] if k + 1 < len(stmts) else None
        if isinstance(s, A.ExprStmt) and isinstance(nxt, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) \
                and isinstance(nxt.expr, A.Intrinsic) and s.expr.name == "sort" and nxt.expr.name == "reverse" \
                and A.same(s.expr.args, nxt.expr.args):
            s.expr.name = "sort_desc"
            s.extra.append(nxt.line)
            del stmts[k + 1]
        k += 1


def parse(tokens):
    return GoParser(tokens).module()


def type_kind(ty):
    if ty is None:
        return None
    if ty.startswith("map<"):
        return "map"
    if ty.startswith("set<"):
        return "set"
    if ty == "arr" or ty.startswith("list<"):
        return "list"
    return "str" if ty == "str" else "scalar"


LISTY = {"list_fill", "grid", "go_append", "lcopy", "slice", "sorted", "split", "split_ws", "s2ints", "go_keys"}


class GoParser(CFamily):
    lang = "go"
    SLICE = ":"
    BINARY = BINARY_GO

    def value_kind(self, v):
        if isinstance(v, A.Intrinsic):
            return "map" if v.name == "map_new" else "set" if v.name == "set_new" else "list" if v.name in LISTY \
                else None
        if isinstance(v, A.ArrayLit):
            return "list"
        if isinstance(v, A.StrLit):
            return "str"
        if isinstance(v, (A.IntLit, A.FloatLit, A.BoolLit)):
            return "scalar"
        if isinstance(v, A.Name):
            return getattr(self, "kinds", {}).get(v.id)
        return None

    def zero_of(self, ty, at):
        pos = {"line": at.line, "col": at.col}
        z = {"arr": A.IntLit(0, **pos), "int": A.IntLit(0, **pos), "list<float>": A.FloatLit(0.0, **pos),
             "float": A.FloatLit(0.0, **pos), "list<bool>": A.BoolLit(False, **pos), "bool": A.BoolLit(False, **pos),
             "list<str>": A.StrLit("", **pos), "str": A.StrLit("", **pos)}.get(ty)
        if z is None:
            raise self.unsupported("a zero value of this type", at)
        return z

    def fixed_ahead(self):
        return self.at_op("[") and self.peek(1).kind in ("NUMBER", "NAME") and self.peek(2).text == "]"

    def fixed(self):
        t = self.next()
        size = self.expr()
        self.expect_op("]")
        el = self.gtype()
        if el not in ("int", "float", "bool", "str"):
            raise self.unsupported("fixed-size arrays of this type", t)
        return size, el

    def module(self):
        self.skip()
        pkg = self.expect("KEYWORD", "package", "'package'")
        name = self.expect("NAME", what="a package name")
        if name.text != "main":
            raise self.unsupported(f"package {name.text} (only package main)", name)
        self.end()
        imports, frame = [], []
        while self.at("KEYWORD", "import"):
            t = self.next()
            group = bool(self.accept_op("("))
            if group:
                frame.append(t.line)
            while True:
                self.skip()
                if group and self.at_op(")"):
                    frame.append(self.next().line)
                    break
                path = self.expect("STRING", what="an import path")
                if path.text[1:-1] not in PACKAGES | {"bufio"}:
                    raise self.unsupported(f"import {path.text}", path)
                imports.append((path.text[1:-1], path.line))
                if not group:
                    break
                self.end()
            self.end()
        funcs, main, helpers = [], None, []
        while not self.at("EOF"):
            if self.accept_op(";"):
                continue
            t = self.peek()
            if self.at("KEYWORD", "var") and self.peek(1).text == "csIn":
                while not self.at_op(";") and not self.at("EOF"):
                    self.next()
                helpers.append(({"read_line"}, t.line, t.line))
                continue
            if self.at("KEYWORD", "const") or self.at("KEYWORD", "var"):
                self.top_decl()
                continue
            if not self.at("KEYWORD", "func"):
                raise self.unsupported(f"top-level '{t.text}' (only functions)", t)
            if self.peek(1).text in HELPERS:
                self.next()
                name = self.next()
                helpers.append(({HELPERS[name.text]}, t.line, self.skip_braced().line))
                continue
            fn = self.function()
            if fn.name == "main":
                main = fn
            else:
                funcs.append(fn)
        if main is None:
            raise self.unsupported("a program without func main", pkg)
        body = idioms.fold_swaps(main.body, idioms.counts(main.body))
        for f in funcs:
            f.body = idioms.fold_swaps(f.body, idioms.counts(f.body))
        for block in [*(f.body for f in funcs), body]:
            sort_desc(block)
        wrap = [(pkg.line, pkg.line), (main.line, main.end)]
        m = A.Module(funcs, body, entry=(main.line, main.end), lang="go", wrap=wrap, line=1, col=1)
        m.consts = dict(self.consts)
        prints = sorted((s for s in A.walk_all([*funcs, *body]) if isinstance(s, A.Print)), key=lambda s: s.line)
        for pkg, line in imports:
            if pkg == "fmt" and prints:
                prints[0].extra.append(line)
            elif pkg in USERS:
                helpers.append((USERS[pkg], line, line))
            else:
                m.wrap.append((line, line))
        m.wrap += [(line, line) for line in frame]
        idioms.attach(m, helpers)
        return m

    def skip(self):
        while self.accept_op(";"):
            pass

    def top_decl(self):
        kw = self.next()
        group = bool(self.accept_op("("))
        k, iota, last = 0, False, None
        while True:
            self.skip()
            if group and self.accept_op(")"):
                break
            name = self.expect("NAME", what="a name")
            ty = None if self.at_op("=", ";", ")") else self.gtype()
            if self.accept_op("="):
                if self.at("NAME", "iota") and self.peek(1).text in (";", ")"):
                    self.next()
                    iota, value = True, A.IntLit(k)
                else:
                    iota, value = False, self.expr()
            elif iota:
                value = A.IntLit(k)
            elif kw.text == "const" and last is not None:
                value = copy.deepcopy(last)
            else:
                value = self.zero_of(ty, name)
            if ty == "float" and isinstance(value, A.IntLit):
                value = A.FloatLit(float(value.value))
            if not isinstance(value, LITERALS):
                raise self.unsupported(f"a top-level {kw.text} that is not a plain value", name)
            value.line, value.col = name.line, name.col
            self.consts[name.text] = value
            last, k = value, k + 1
            if not group:
                break
        self.end()

    def end(self):
        if not self.at_op("}", ")"):
            self.expect_op(";")

    def function(self):
        t = self.next()
        name = self.expect("NAME", what="a function name")
        self.expect_op("(")
        params, pending = [], []
        while not self.at_op(")"):
            p = self.expect("NAME", what="a parameter name")
            pending.append(p)
            if self.accept_op(","):
                continue
            ty = self.gtype()
            params += [A.Param(q.text, ty, line=q.line, col=q.col) for q in pending]
            pending = []
            if not self.accept_op(","):
                break
        if pending:
            raise self.error("expected a parameter type")
        self.expect_op(")")
        ret = None if self.at_op("{") else self.gtype()
        if name.text == "main" and (params or ret):
            raise self.unsupported("main with parameters or a result", name)
        saved = self.fresh_scopes(p.name for p in params)
        self.kinds = {p.name: type_kind(p.ty) for p in params}
        body = self.block()
        self.scopes = saved
        self.end()
        return A.FunctionDef(name.text, params, body, ret or "void", **self.pos(t))

    def gtype(self):
        t = self.peek()
        if self.at("KEYWORD", "map"):
            self.next()
            self.expect_op("[")
            k = self.gtype()
            self.expect_op("]")
            if self.at("KEYWORD", "struct"):
                self.next()
                self.expect_op("{")
                self.expect_op("}")
                return sset(k)
            return mp(k, self.gtype())
        if self.at_op("("):
            raise self.unsupported("multiple results", t)
        if self.accept_op("["):
            if not self.accept_op("]"):
                raise self.unsupported("fixed-size arrays (use a slice)", t)
            el = self.gtype()
            if el == "char":
                raise self.unsupported("slices of runes or bytes", t)
            return "arr" if el == "int" else f"list<{el}>"
        if self.at_op("*") and self.peek(1).text == "[":
            self.next()
            return self.gtype()
        if self.at_op("*", "&"):
            raise self.unsupported("pointers", t)
        tt = self.expect("TYPE", what="a type")
        if tt.text in ("float32", "complex64", "complex128"):
            raise self.unsupported(f"{tt.text} (use float64)", tt)
        if tt.text not in GTYPE:
            raise self.unsupported(f"type {tt.text}", tt)
        return GTYPE[tt.text]

    def statement(self):
        t = self.peek()
        if t.kind == "KEYWORD":
            if t.text == "if":
                r = self.if_stmt()
                return r if isinstance(r, list) else [r]
            if t.text == "switch":
                return self.go_switch()
            if t.text in ("select", "defer", "go", "goto", "fallthrough", "const", "type"):
                raise self.unsupported(f"'{t.text}' statement", t)
            if t.text == "func":
                raise self.unsupported("nested functions", t)
        return super().statement()

    def init_ahead(self):
        depth, k = 0, 0
        while True:
            tok = self.peek(k)
            if tok.kind == "EOF":
                return False
            if tok.text in ("(", "["):
                depth += 1
            elif tok.text in (")", "]"):
                depth -= 1
            elif depth == 0 and tok.text == "{":
                return False
            elif depth == 0 and tok.text == ";":
                return True
            k += 1

    def if_stmt(self, nested=False):
        t = self.next()
        pre = []
        if self.init_ahead():
            pre = self.simple()
            self.expect_op(";")
        test = self.cond()
        body = self.block()
        orelse = []
        if self.accept("KEYWORD", "else"):
            if self.at("KEYWORD", "if"):
                r = self.if_stmt(True)
                orelse = r if isinstance(r, list) else [r]
            else:
                orelse = self.block()
        if not nested:
            self.end()
        node = A.If(test, body, orelse, **self.pos(t))
        return pre + [node] if pre else node

    def go_switch(self):
        t = self.next()
        if self.init_ahead():
            raise self.unsupported("switch with an init statement", t)
        subject = None if self.at_op("{") else self.expr()
        self.expect_op("{")
        self.scopes.append(set())
        groups = []
        while True:
            self.skip()
            if self.at_op("}"):
                break
            start = self.next()
            labels, default = [], False
            if start.text == "default":
                default = True
            elif start.text == "case":
                labels.append(self.expr())
                while self.accept_op(","):
                    labels.append(self.expr())
            else:
                raise self.error("expected 'case' or 'default'", start)
            self.expect_op(":")
            body = []
            while not (self.at("KEYWORD", "case") or self.at("KEYWORD", "default") or self.at_op("}")):
                if self.at("EOF"):
                    raise self.error("expected '}'")
                body += self.statement()
            groups.append((labels, default, body, start, self.last.line))
        self.next()
        self.scopes.pop()
        self.end()
        return self.case_chain(subject, groups, t, False)

    def cond(self):
        return self.expr()

    def decl_start(self):
        return self.at("KEYWORD", "var")

    def declaration(self):
        t = self.next()
        if self.at_op("("):
            raise self.unsupported("grouped var declarations", t)
        names = [self.expect("NAME", what="a variable name")]
        while self.accept_op(","):
            names.append(self.expect("NAME", what="a variable name"))
        if self.fixed_ahead():
            size, el = self.fixed()
            if self.at_op("="):
                raise self.unsupported("a fixed-size array declared with values (use a slice)", t)
            targets = [A.Name(n.text, line=n.line, col=n.col) for n in names]
            for n in names:
                self.declare_name(n.text, n)
                self.kinds[n.text] = "list"
            fills = [A.Intrinsic("list_fill", [self.zero_of(el, n), copy.deepcopy(size)], line=n.line, col=n.col)
                     for n in names]
            return idioms.declare(targets, fills, [None] * len(names), self.pos(t))
        ty = None if self.at_op("=") else self.gtype()
        for n in names:
            self.kinds[n.text] = type_kind(ty)
        if self.accept_op("="):
            values = [self.expr()]
            while self.accept_op(","):
                values.append(self.expr())
            if len(values) != len(names):
                raise self.fail("Syntax error: assignment count mismatch", t)
        else:
            if ty not in ZERO:
                raise self.unsupported("a zero-valued variable of this type", t)
            values = [self.zero(ty, n) for n in names]
        targets = [A.Name(n.text, line=n.line, col=n.col) for n in names]
        for n in names:
            self.declare_name(n.text, n)
        return idioms.declare(targets, values, [ty] * len(names), self.pos(t))

    def zero(self, ty, at):
        v = ZERO[ty]
        if ty == "bool":
            return A.BoolLit(v, line=at.line, col=at.col)
        if ty == "str":
            return A.StrLit(v, line=at.line, col=at.col)
        return A.IntLit(v, line=at.line, col=at.col)

    def for_clauses(self):
        t = self.next()
        if self.at_op("{"):
            body = self.block()
            self.end()
            return [A.While(A.BoolLit(True, line=t.line, col=t.col), body, **self.pos(t))]
        form = self.header()
        if form == "range":
            return self.range_for(t)
        if form == "cond":
            test = self.expr()
            body = self.block()
            self.end()
            return [A.While(test, body, **self.pos(t))]
        init = scoped = None
        if not self.at_op(";"):
            init = self.simple()
            scoped = isinstance(init[0], (A.Assign, A.TupleAssign)) and self.declared
            if len(init) != 1:
                raise self.unsupported("for-loop header with several declarations", t)
            init = init[0]
        self.expect_op(";")
        cond = None if self.at_op(";") else self.expr()
        self.expect_op(";")
        update = None
        if not self.at_op("{"):
            ups = self.simple()
            if len(ups) != 1:
                raise self.unsupported("for-loop update with several statements", t)
            update = ups[0]
        body = self.block()
        self.end()
        at = self.pos(t)
        for s in (init, update):
            if s is not None:
                s.line, s.col, s.end = t.line, t.col, t.line
        if cond is None:
            raise self.unsupported("a for loop without a condition", t)
        return idioms.make_for(init, cond, update, body, at, scoped)

    def header(self):
        depth, k = 0, 0
        while True:
            tok = self.peek(k)
            if tok.kind == "EOF":
                raise self.error("expected '{'")
            if tok.text in ("(", "["):
                depth += 1
            elif tok.text in (")", "]"):
                depth -= 1
            elif depth == 0:
                if tok.kind == "KEYWORD" and tok.text == "range":
                    return "range"
                if tok.text == ";":
                    return "clauses"
                if tok.text == "{":
                    return "cond"
            k += 1

    def range_for(self, t):
        if self.at("KEYWORD", "range"):
            raise self.unsupported("for range without a loop variable", t)
        first = self.expect("NAME", what="a loop variable")
        second = None
        if self.accept_op(","):
            second = self.expect("NAME", what="a loop variable")
        if not self.accept_op(":="):
            raise self.unsupported("range loop that assigns existing variables", t)
        self.expect("KEYWORD", "range", "'range'")
        it = self.expr()
        for v in (first, second):
            if v is not None and v.text != "_":
                self.declare_name(v.text, v)
        body = self.block()
        self.end()
        kind = self.value_kind(it)
        at = {"line": t.line, "col": t.col}
        zero, one = A.IntLit(0, **at), A.IntLit(1, **at)
        if second is None:
            if first.text == "_":
                raise self.unsupported("for range without a loop variable", t)
            if kind in ("list", "str"):
                return [A.For(first.text, "range", body, start=zero, stop=A.Len(it, **at), step=one, **self.pos(t))]
            if kind in ("map", "set"):
                return [A.For(first.text, "each", body, iter=it, **self.pos(t))]
            return [A.For(first.text, "range", body, start=zero, stop=it, step=one, **self.pos(t))]
        if kind == "map":
            key = first.text if first.text != "_" else self.fresh("key")
            pre = [] if second.text == "_" else [
                A.Assign(A.Name(second.text, **at), A.Index(copy.deepcopy(it), A.Name(key, **at), **at), **self.pos(t))]
            for x in pre:
                x.bound = True
            return [A.For(key, "each", pre + body, iter=it, **self.pos(t))]
        if first.text == "_":
            return [A.For(second.text, "each", body, iter=it, **self.pos(t))]
        if not pure(it):
            raise self.unsupported("a range loop with an index over a computed value", first)
        pre = [] if second.text == "_" else [
            A.Assign(A.Name(second.text, **at), A.Index(copy.deepcopy(it), A.Name(first.text, **at), **at), **self.pos(t))]
        for x in pre:
            x.bound = True
        return [A.For(first.text, "range", pre + body, start=zero, stop=A.Len(copy.deepcopy(it), **at), step=one,
                      **self.pos(t))]

    def simple(self):
        t = self.peek()
        self.declared = False
        lhs = [self.expr()]
        while self.accept_op(","):
            lhs.append(self.expr())
        if self.at_op(":=", "="):
            op = self.next()
            values = [self.expr()]
            while self.accept_op(","):
                values.append(self.expr())
            v0 = values[0]
            if len(lhs) == 2 and len(values) == 1 and isinstance(v0, A.Intrinsic) and v0.name in ("@atoi", "@atof"):
                if not (isinstance(lhs[1], A.Name) and lhs[1].id == "_"):
                    raise self.unsupported("using the error result of strconv (use _)", lhs[1])
                lhs, values = lhs[:1], [A.Intrinsic("s2i" if v0.name == "@atoi" else "s2f", v0.args, line=v0.line,
                                                    col=v0.col)]
            if len(values) != len(lhs):
                raise self.fail("Syntax error: assignment count mismatch", op)
            targets = [self.target(x) for x in lhs]
            if op.text == ":=":
                if not all(isinstance(x, A.Name) for x in targets):
                    raise self.fail("Syntax error: non-name on left side of :=", t)
                self.declared = True
                for x, v in zip(targets, values):
                    self.declare_name(x.id, x)
                    self.kinds[x.id] = self.value_kind(v)
                return idioms.declare(targets, values, [None] * len(targets), self.pos(t))
            if len(values) == 1 and isinstance(values[0], StructVal) and isinstance(targets[0], A.Index):
                x = targets[0]
                return [A.ExprStmt(A.Intrinsic("set_add", [x.target, x.index], line=x.line, col=x.col), **self.pos(t))]
            if len(values) == 1 and isinstance(values[0], A.Intrinsic) and values[0].args \
                    and A.same(values[0].args[0], targets[0]):
                v = values[0]
                if v.name == "go_append" and len(v.args) >= 2:
                    return [A.ExprStmt(A.Intrinsic("push", [copy.deepcopy(v.args[0]), x], line=v.line, col=v.col),
                                       **self.pos(t)) for x in v.args[1:]]
                if v.name == "go_insert" and len(v.args) == 3:
                    return [A.ExprStmt(A.Intrinsic("insert", v.args, line=v.line, col=v.col), **self.pos(t))]
                if v.name == "go_delete" and len(v.args) == 3:
                    return [A.ExprStmt(A.Intrinsic("remove_at", v.args[:2], line=v.line, col=v.col), **self.pos(t))]
            return [idioms.assign(targets, values, self.pos(t))]
        if len(lhs) > 1:
            raise self.error("expected ':=' or '='")
        if self.at_op(*ASSIGN):
            op = self.next()
            return [self.assignment(lhs[0], op, self.expr(), t)]
        if self.at_op("++", "--"):
            op = self.next()
            return [A.AugAssign(self.target(lhs[0]), op.text[0], A.IntLit(1, line=t.line, col=t.col), **self.pos(t))]
        return self.expr_statement(lhs[0], t)

    def return_stmt(self):
        t = self.next()
        value = None if self.at_op(";", "}") else self.expr()
        if self.at_op(","):
            raise self.unsupported("returning several values", t)
        self.end()
        return A.Return(value, **self.pos(t))

    def expr_statement(self, e, t):
        if isinstance(e, Log):
            node = A.Print(e.args, **self.pos(t))
            if hasattr(e, "ending"):
                node.ending = e.ending
            return [node]
        if isinstance(e, A.Intrinsic) and (e.name in set(LISTOPS) or e.name in MAPOPS or e.name in MAP_GENERIC
                                           or e.name == "exit"):
            return [A.ExprStmt(e, **self.pos(t))]
        return super().expr_statement(e, t)

    def primary_extra(self):
        t = self.peek()
        if t.kind == "BUILTIN" and t.text == "make" and self.peek(1).text == "(":
            return self.make(t)
        if self.fixed_ahead():
            size, el = self.fixed()
            lit = self.composite(t)
            if isinstance(size, A.IntLit) and len(lit.items) < size.value:
                lit.items += [self.zero_of(el, t) for _ in range(size.value - len(lit.items))]
            return lit
        if self.at_op("["):
            self.gtype()
            return self.composite(t)
        if self.at_op("&", "*") and self.peek(1).kind == "NAME":
            argument = self.toks[self.i - 1].text in ("(", ",") and self.peek(2).text in (",", ")")
            if t.text == "&" and not argument:
                raise self.unsupported("pointers (only passing a slice to a function with &name)", t)
            self.next()
            return self.unary()
        if t.kind == "TYPE":
            self.next()
            if not self.at_op("("):
                raise self.unsupported(f"using type {t.text} as a value", t)
            args = self.args()
            if len(args) != 1:
                raise self.fail(f"Syntax error: conversion to {t.text} takes one value", t)
            if t.text not in ("int", "int64", "string", "rune", "byte", "float64"):
                raise self.unsupported(f"conversion to {t.text}", t)
            kind = {"int": "num_int", "int64": "num_int", "float64": "num_float", "rune": "num_char"}.get(t.text)
            return A.Intrinsic(kind, args, line=t.line, col=t.col) if kind else args[0]
        if self.at_op("^"):
            self.next()
            return A.UnaryOp("~", self.unary(), line=t.line, col=t.col)
        if self.at_op("&", "*", "<-"):
            raise self.unsupported(f"operator '{t.text}'", t)
        if t.kind == "KEYWORD" and t.text == "map":
            ty = self.gtype()
            return self.map_literal(ty, t)
        if t.kind == "KEYWORD" and t.text == "struct" and [self.peek(k).text for k in range(1, 5)] == ["{", "}", "{", "}"]:
            for _ in range(5):
                self.next()
            return StructVal(line=t.line, col=t.col)
        if t.kind == "KEYWORD" and t.text in ("nil", "func", "map", "struct", "chan", "interface"):
            raise self.unsupported(t.text, t)
        if t.kind == "NAME" and t.text in PACKAGES and self.peek(1).text == ".":
            self.next()
            return Path(t.text, line=t.line, col=t.col)
        return None

    def map_literal(self, ty, t):
        pos = {"line": t.line, "col": t.col}
        self.expect_op("{")
        keys, values = [], []
        while not self.at_op("}"):
            keys.append(self.expr())
            self.expect_op(":")
            if self.at_op("{") and self.peek(1).text == "}":
                self.next()
                self.next()
                values.append(A.BoolLit(True, **pos))
            else:
                values.append(self.expr())
            if not self.accept_op(","):
                break
        self.expect_op("}")
        if ty.startswith("set<"):
            if not all(isinstance(v, A.BoolLit) and v.value for v in values):
                raise self.unsupported("a map[T]bool literal with false values", t)
            return A.SetLit(keys, **pos) if keys else A.Intrinsic("set_new", [], **pos)
        return A.DictLit(keys, values, **pos) if keys else A.Intrinsic("map_new", [], **pos)

    def composite(self, t):
        self.expect_op("{")
        items = []
        while not self.at_op("}"):
            items.append(self.composite(self.peek()) if self.at_op("{") else self.expr())
            if not self.accept_op(","):
                break
        self.expect_op("}")
        return A.ArrayLit(items, line=t.line, col=t.col)

    def make(self, t):
        self.next()
        self.next()
        ty = self.gtype()
        size = None
        if self.accept_op(","):
            size = self.expr()
            if self.accept_op(","):
                self.expr()
        self.expect_op(")")
        kind = type_kind(ty)
        pos = {"line": t.line, "col": t.col}
        if kind in ("map", "set"):
            return A.Intrinsic("map_new" if kind == "map" else "set_new", [], **pos)
        if kind != "list" or size is None:
            raise self.unsupported("make() of this type", t)
        if isinstance(size, A.IntLit) and size.value == 0:
            return A.ArrayLit([], **pos)
        if ty.startswith("list<list") or ty.startswith("list<arr"):
            raise self.unsupported("make() of a slice of slices (fill each row with a loop instead)", t)
        return A.Intrinsic("list_fill", [self.zero_of(ty, t), size], **pos)

    def member(self, e, name, t):
        if isinstance(e, Path) and e.text == "fmt" and name.text == "Println" and self.at_op("("):
            return Log(self.args(), line=e.line, col=e.col)
        if isinstance(e, Path) and e.text == "fmt" and name.text == "Print" and self.at_op("("):
            args = self.args()
            node = Log(args, line=e.line, col=e.col)
            node.ending = ""
            if len(args) == 1 and isinstance(args[0], A.StrLit) and not args[0].value.strip(" "):
                node.args, node.ending = [], args[0].value
            elif len(args) % 2 and all(isinstance(x, A.StrLit) and x.value == " " for x in args[1::2]):
                node.args = args[::2]
            return node
        if isinstance(e, Path) and e.text == "fmt" and name.text == "Printf" and self.at_op("("):
            args = self.args()
            if not args or not isinstance(args[0], A.StrLit):
                raise self.unsupported("fmt.Printf without a literal format", t)
            text = args[0].value
            newline = text.endswith("\n")
            v = idioms.formatted(text[:-1] if newline else text, args[1:], {"line": e.line, "col": e.col})
            if v is None:
                raise self.unsupported(f"fmt.Printf(\"{text}\")", t)
            node = Log([v], line=e.line, col=e.col)
            if not newline:
                node.ending = ""
            return node
        if isinstance(e, Path) and e.text == "math" and name.text in ("Pi", "E") and not self.at_op("("):
            return A.Intrinsic("pi" if name.text == "Pi" else "e", [], line=e.line, col=e.col)
        if isinstance(e, Path) and self.at_op("("):
            args = self.args()
            pos = {"line": e.line, "col": e.col}
            if e.text == "math" and name.text in MATH:
                return A.Intrinsic(MATH[name.text], args, **pos)
            if e.text == "strings" and name.text in STRINGS:
                if name.text == "Join" and len(args) == 2:
                    return A.Intrinsic("join", [args[1], args[0]], **pos)
                return A.Intrinsic(STRINGS[name.text], args, **pos)
            if e.text == "sort" and name.text in ("Ints", "Strings", "Float64s") and len(args) == 1:
                return A.Intrinsic("sort", args, **pos)
            if e.text == "maps" and name.text == "Keys" and len(args) == 1:
                return A.Intrinsic("go_keys", args, **pos)
            if e.text == "slices" and name.text in SLICES:
                kind = SLICES[name.text]
                if kind == "clone" and len(args) == 1:
                    x = args[0]
                    return x if isinstance(x, A.Intrinsic) and x.name == "slice" else A.Intrinsic("lcopy", args, **pos)
                if kind == "sorted" and len(args) == 1 and isinstance(args[0], A.Intrinsic) \
                        and args[0].name in ("values", "go_keys"):
                    return A.Intrinsic("sorted", args[0].args, **pos)
                return A.Intrinsic(kind, args, **pos)
            if e.text == "strconv" and name.text == "FormatInt" and len(args) == 2 and isinstance(args[1], A.IntLit) \
                    and args[1].value == 10:
                return A.Intrinsic("i2s", args[:1], **pos)
            if e.text == "strconv" and name.text in ("Atoi", "ParseFloat") and args:
                return A.Intrinsic("@atoi" if name.text == "Atoi" else "@atof", args[:1], **pos)
            if e.text == "strconv" and name.text == "Itoa" and len(args) == 1:
                return A.Intrinsic("i2s", args, **pos)
            if e.text == "fmt" and name.text == "Sprint" and len(args) == 1:
                return A.Intrinsic("str", args, **pos)
            if e.text == "os" and name.text == "Exit" and len(args) == 1:
                return A.Intrinsic("exit", args, **pos)
            if e.text == "fmt" and name.text == "Sprintf" and args and isinstance(args[0], A.StrLit):
                v = idioms.formatted(args[0].value, args[1:], pos)
                if v is None:
                    raise self.unsupported(f"fmt.Sprintf(\"{args[0].value}\")", t)
                return v
            if e.text == "strconv" and name.text == "FormatFloat" and len(args) == 4 and isinstance(args[1], A.CharLit) \
                    and args[1].value == "f" and isinstance(args[2], A.IntLit):
                return A.Intrinsic("fixed", [args[0], args[2]], **pos)
            if e.text == "strconv" and name.text == "FormatFloat" and len(args) == 4:
                return A.Intrinsic("f2s", args[:1], **pos)
            if e.text == "strconv" and name.text == "FormatBool" and len(args) == 1:
                return A.Intrinsic("b2s", args, **pos)
        path = f"{e.text}.{name.text}" if isinstance(e, Path) else f".{name.text}"
        raise self.unsupported(f"library call {path}" if isinstance(e, Path) else f"selector '{path}'", t)

    def call(self, t, args):
        if t.text == "csFill" and len(args) == 2:
            return A.Intrinsic("list_fill", [args[1], args[0]], line=t.line, col=t.col)
        if t.text == "csGrid" and len(args) == 3:
            return A.Intrinsic("grid", args, line=t.line, col=t.col)
        if t.text in HELPERS:
            return A.Intrinsic(HELPERS[t.text], args, line=t.line, col=t.col)
        if t.text == "append" and len(args) >= 2:
            return A.Intrinsic("go_append", args, line=t.line, col=t.col)
        if t.text == "delete" and len(args) == 2:
            return A.Intrinsic("delete", args, line=t.line, col=t.col)
        if t.text in ("min", "max"):
            if len(args) != 2:
                raise self.unsupported(f"{t.text}() with {len(args)} arguments", t)
            return A.Intrinsic(t.text, args, line=t.line, col=t.col)
        if t.text == "len":
            if len(args) != 1:
                raise self.fail("Syntax error: len takes one argument", t)
            return A.Len(args[0], line=t.line, col=t.col)
        return super().call(t, args)
