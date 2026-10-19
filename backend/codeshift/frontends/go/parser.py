from dataclasses import dataclass

from ... import ast as A
from ...library import LISTOPS, MAP_GENERIC, MAPOPS
from ...semantic import mp, sset
from .. import idioms
from ..cfamily import ASSIGN, CFamily

PACKAGES = {"fmt", "math", "strconv", "strings", "slices", "maps", "os"}
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


class GoParser(CFamily):
    lang = "go"
    SLICE = ":"

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
            if t.text in ("switch", "select", "defer", "go", "goto", "fallthrough", "const", "type"):
                raise self.unsupported(f"'{t.text}' statement", t)
            if t.text == "func":
                raise self.unsupported("nested functions", t)
        return super().statement()

    def if_stmt(self, nested=False):
        t = self.next()
        test = self.cond()
        if self.at_op(";", ":=", "="):
            raise self.unsupported("if with an init statement", t)
        body = self.block()
        orelse = []
        if self.accept("KEYWORD", "else"):
            orelse = [self.if_stmt(True)] if self.at("KEYWORD", "if") else self.block()
        if not nested:
            self.end()
        return A.If(test, body, orelse, **self.pos(t))

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
        ty = None if self.at_op("=") else self.gtype()
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
        if second is None:
            if first.text == "_":
                raise self.unsupported("for range without a loop variable", t)
            zero = A.IntLit(0, line=t.line, col=t.col)
            return [A.For(first.text, "range", body, start=zero, stop=it, step=A.IntLit(1, line=t.line, col=t.col),
                          **self.pos(t))]
        if first.text != "_":
            raise self.unsupported("range loop that uses the index", first)
        return [A.For(second.text, "each", body, iter=it, **self.pos(t))]

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
            if len(values) != len(lhs):
                raise self.fail("Syntax error: assignment count mismatch", op)
            targets = [self.target(x) for x in lhs]
            if op.text == ":=":
                if not all(isinstance(x, A.Name) for x in targets):
                    raise self.fail("Syntax error: non-name on left side of :=", t)
                self.declared = True
                for x in targets:
                    self.declare_name(x.id, x)
                return idioms.declare(targets, values, [None] * len(targets), self.pos(t))
            if len(values) == 1 and isinstance(values[0], StructVal) and isinstance(targets[0], A.Index):
                x = targets[0]
                return [A.ExprStmt(A.Intrinsic("set_add", [x.target, x.index], line=x.line, col=x.col), **self.pos(t))]
            if len(values) == 1 and isinstance(values[0], A.Intrinsic) and values[0].args \
                    and A.same(values[0].args[0], targets[0]):
                v = values[0]
                if v.name == "go_append" and len(v.args) == 2:
                    return [A.ExprStmt(A.Intrinsic("push", v.args, line=v.line, col=v.col), **self.pos(t))]
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
        if self.at_op("["):
            self.gtype()
            return self.composite(t)
        if self.at_op("&", "*") and self.peek(1).kind == "NAME":
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
        if self.at_op("&", "*", "<-", "^"):
            raise self.unsupported(f"operator '{t.text}'", t)
        if t.kind == "KEYWORD" and t.text == "map":
            ty = self.gtype()
            self.expect_op("{")
            self.expect_op("}")
            return A.Intrinsic("set_new" if ty.startswith("set<") else "map_new", [], line=t.line, col=t.col)
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

    def composite(self, t):
        self.expect_op("{")
        items = []
        while not self.at_op("}"):
            items.append(self.composite(self.peek()) if self.at_op("{") else self.expr())
            if not self.accept_op(","):
                break
        self.expect_op("}")
        return A.ArrayLit(items, line=t.line, col=t.col)

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
        if t.text == "append" and len(args) == 2:
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
