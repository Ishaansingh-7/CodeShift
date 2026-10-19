import re
from dataclasses import dataclass

from ... import ast as A
from ...library import LISTOPS, MAPOPS
from ...semantic import mp, rewrite, sset
from ...tokens import Token
from .. import idioms
from ..cfamily import CFamily

IMPORTS = {"java.io.BufferedReader", "java.io.IOException", "java.io.InputStreamReader", "java.util.Arrays", "java.util.ArrayList", "java.util.Collections", "java.util.List",
           "java.util.LinkedHashMap", "java.util.HashMap", "java.util.Map", "java.util.TreeSet", "java.util.HashSet",
           "java.util.Set"}
MAPS = {"LinkedHashMap", "HashMap", "Map"}
SETS = {"TreeSet", "HashSet", "Set"}
HELPERS = {"csIpow": "pow_i", "csRoundAway": "round_away", "csSorted": "sorted", "csGrid": "grid", "csSplit": "split",
           "csSplitWs": "split_ws", "csReadLine": "read_line", "csInts": "s2ints"}
FORMAT = re.compile(r"%(-)?(\d+)?(?:\.(\d+))?([dfs])$")
BOXES = {"Long": "int", "Integer": "int", "Double": "float", "Boolean": "bool", "String": "str"}
COLLECTIONS = {"Collections.sort": "sort", "Collections.reverse": "reverse", "Collections.min": "lmin",
               "Collections.max": "lmax"}
LIB = {
    "Math.abs": "abs", "Math.min": "min", "Math.max": "max", "Math.pow": "pow_f", "Math.sqrt": "sqrt",
    "Math.floor": "floor", "Math.ceil": "ceil", "Math.rint": "round_even", "Math.sin": "sin", "Math.cos": "cos",
    "Math.tan": "tan", "Math.atan2": "atan2", "Math.log": "log", "Math.log10": "log10", "Math.exp": "exp",
    "Math.hypot": "hypot", "Long.toString": "i2s", "Long.parseLong": "s2i", "Double.toString": "f2s",
    "Double.parseDouble": "s2f", "Boolean.toString": "b2s", "String.valueOf": "str",
}
CONSTS = {"Math.PI": "pi", "Math.E": "e"}
STRING_METHODS = {"toUpperCase": "to_upper", "toLowerCase": "to_lower", "strip": "trim", "trim": "trim",
                  "startsWith": "starts", "endsWith": "ends", "contains": "contains", "indexOf": "index",
                  "replace": "replace_all", "repeat": "repeat", "compareTo": "compare"}
CHARACTER = {"Character.isDigit": "is_digit", "Character.isLetter": "is_alpha", "Character.isWhitespace": "is_space",
             "Character.isUpperCase": "is_upper", "Character.isLowerCase": "is_lower",
             "Character.toUpperCase": "cupper", "Character.toLowerCase": "clower"}


def java_idioms(e):
    e = log2(e)
    if not isinstance(e, A.Compare) or not isinstance(e.left, A.Intrinsic) or not isinstance(e.right, A.IntLit) \
            or e.right.value != 0:
        return e
    pos = {"line": e.line, "col": e.col}
    if e.left.name == "compare":
        return A.Compare(e.op, *e.left.args, **pos)
    if e.left.name in ("find", "index") and e.op == ">=":
        return A.Intrinsic("contains", e.left.args, **pos)
    return e


def log2(e):
    if isinstance(e, A.BinOp) and e.op == "/" and all(isinstance(x, A.Intrinsic) and x.name == "log"
                                                       for x in (e.left, e.right)):
        base = e.right.args[0]
        if isinstance(base, A.IntLit) and base.value == 2:
            return A.Intrinsic("log2", e.left.args, line=e.line, col=e.col)
    return e
PRIMS = {"int": "int", "long": "int", "boolean": "bool", "char": "char", "String": "str", "StringBuilder": "sb",
         "void": "void", "double": "float"}


@dataclass(eq=False)
class Path(A.Expr):
    text: str


@dataclass(eq=False)
class Method(A.Expr):
    obj: object
    name: str
    args: list


def parse(tokens):
    return JavaParser(tokens).module()


class JavaParser(CFamily):
    lang = "java"

    def module(self):
        imports = []
        while self.at("KEYWORD", "import"):
            t = self.next()
            parts = [self.expect("NAME", what="a package name").text]
            while self.accept_op("."):
                parts.append(self.next().text)
            self.expect_op(";")
            name = ".".join(parts)
            if name not in IMPORTS:
                raise self.unsupported(f"import {name}", t)
            imports.append(t.line)
        start = self.peek()
        self.accept("KEYWORD", "public")
        self.expect("KEYWORD", "class", "'class'")
        self.expect("NAME", what="a class name")
        self.expect_op("{")
        funcs, main, helpers = [], None, []
        while not self.at_op("}"):
            if self.at("EOF"):
                raise self.error("expected '}'")
            if self.helper_ahead():
                helpers.append(self.skip_helper())
                continue
            if [self.peek(k).text for k in range(3)] == ["static", "BufferedReader", "csIn"]:
                first = self.peek()
                while not self.at_op(";"):
                    self.next()
                helpers.append(("csReadLine", first.line, self.next().line))
                continue
            fn = self.method()
            if fn.name == "main":
                main = fn
            else:
                funcs.append(fn)
        end = self.next()
        if not self.at("EOF"):
            raise self.unsupported("code after the class", self.peek())
        if main is None:
            raise self.unsupported("a program without main", start)
        body = idioms.fold_swaps(main.body, idioms.counts(main.body))
        for f in funcs:
            f.body = idioms.fold_swaps(f.body, idioms.counts(f.body))
        for s in [*funcs, *body]:
            rewrite(s, java_idioms)
        for n in A.walk_all([*funcs, *body]):
            if isinstance(n, A.Intrinsic) and n.name == "compare":
                raise self.unsupported("compareTo() used this way", n)
        m = A.Module(funcs, body, entry=(main.line, main.end), lang="java", wrap=[(start.line, end.line)], line=1, col=1)
        stmts = sorted((s for s in A.walk_all([*funcs, *body]) if isinstance(s, A.Stmt)), key=lambda s: s.line)
        for name, first, last in helpers:
            owner = next((s for s in stmts if any(isinstance(n, A.Intrinsic) and n.name == HELPERS[name]
                                                  for e in A.heads(s) for n in A.walk(e))), None)
            if owner is not None:
                owner.extra += list(range(first, last + 1))
        prints = sorted((s for s in A.walk_all([*funcs, *body]) if isinstance(s, A.Print)), key=lambda s: s.line)
        for line in imports:
            if prints:
                prints[0].extra.append(line)
            else:
                m.wrap.append((line, line))
        return m

    def helper_ahead(self):
        k = 0
        while k < 40 and self.peek(k).text not in ("(", "{", ";", "}") and self.peek(k).kind != "EOF":
            k += 1
        return k > 0 and self.peek(k).text == "(" and self.peek(k - 1).text in HELPERS

    def skip_helper(self):
        t = self.peek()
        while self.peek().text not in HELPERS:
            self.next()
        name = self.next()
        while not self.at_op("{"):
            self.next()
        depth = 0
        while True:
            tok = self.next()
            if tok.kind == "EOF":
                raise self.error("expected '}'")
            depth += {"{": 1, "}": -1}.get(tok.text, 0) if tok.kind == "PUNCT" else 0
            if depth == 0:
                return name.text, t.line, tok.line

    def call(self, t, args):
        if t.text in HELPERS:
            return A.Intrinsic(HELPERS[t.text], args, line=t.line, col=t.col)
        return super().call(t, args)

    def method(self):
        t = self.peek()
        mods = []
        while self.at("KEYWORD") and self.peek().text in ("public", "private", "protected", "static", "final"):
            mods.append(self.next().text)
        if "static" not in mods:
            raise self.unsupported("instance members (only static methods are supported)", t)
        ret = self.jtype()
        name = self.expect("NAME", what="a method name")
        if not self.at_op("("):
            raise self.unsupported("fields", name)
        self.next()
        params = []
        while not self.at_op(")"):
            ty = self.jtype()
            p = self.expect("NAME", what="a parameter name")
            params.append(A.Param(p.text, ty, line=p.line, col=p.col))
            if not self.accept_op(","):
                break
        self.expect_op(")")
        if name.text == "main":
            if not (ret == "void" and len(params) == 1 and params[0].ty == "strs"):
                raise self.unsupported("main with an unusual signature", name)
            params = []
        saved = self.fresh_scopes(p.name for p in params)
        body = self.block()
        self.scopes = saved
        return A.FunctionDef(name.text, params, body, ret, **self.pos(t))

    def jtype(self):
        t = self.peek()
        self.accept("KEYWORD", "final")
        if self.at("KEYWORD", "var"):
            self.next()
            return None
        tt = self.expect("TYPE", what="a type")
        if tt.text in MAPS or tt.text in SETS:
            self.expect_op("<")
            k = self.box()
            v = None
            if tt.text in MAPS:
                self.expect_op(",")
                v = self.box()
            self.close_angle()
            return mp(k, v) if tt.text in MAPS else sset(k)
        if tt.text in ("ArrayList", "List"):
            self.expect_op("<")
            el = self.box()
            self.close_angle()
            if el == "char":
                raise self.unsupported("lists of characters", tt)
            return "arr" if el == "int" else f"list<{el}>"
        if tt.text == "float":
            raise self.unsupported("32-bit float (use double)", tt)
        if tt.text in ("short", "byte"):
            raise self.unsupported(f"'{tt.text}' type", tt)
        ty = PRIMS[tt.text]
        if self.accept_op("["):
            self.expect_op("]")
            if self.at_op("["):
                raise self.unsupported("multi-dimensional arrays", t)
            if tt.text == "String":
                return "strs"
            if ty != "int":
                raise self.unsupported(f"arrays of {tt.text}", t)
            return "arr"
        return ty

    def box(self):
        if self.peek().text in ("ArrayList", "List"):
            return self.jtype()
        t = self.next()
        if t.text not in BOXES:
            raise self.unsupported(f"lists of {t.text}", t)
        return BOXES[t.text]

    def close_angle(self):
        tok = self.peek()
        if tok.text == ">>":
            self.toks[self.i] = Token("OP", ">", tok.line, tok.col + 1)
            return
        self.expect_op(">")

    def generic_ahead(self, k):
        if self.peek(k).text != "<":
            return k
        depth = 0
        while True:
            x = self.peek(k).text
            depth += {"<": 1, ">": -1, ">>": -2}.get(x, 0)
            k += 1
            if depth <= 0 or self.peek(k).kind == "EOF":
                return k

    def decl_start(self):
        return self.at("TYPE") or self.at("KEYWORD", "final") or (self.at("KEYWORD", "var") and self.peek(1).kind == "NAME")

    def declaration(self):
        t = self.peek()
        ty = self.jtype()
        names, values, types = [], [], []
        while True:
            n = self.expect("NAME", what="a variable name")
            self.declare_name(n.text, n)
            if self.accept_op("["):
                raise self.unsupported("C-style array declarators", n)
            if not self.accept_op("="):
                value = None
            else:
                value = self.array_init() if self.at_op("{") else self.expr()
            if ty == "sb" and not (isinstance(value, A.StrLit) and value.value == ""):
                raise self.unsupported("a StringBuilder that does not start empty", n)
            names.append(A.Name(n.text, line=n.line, col=n.col))
            values.append(value)
            types.append("str" if ty == "sb" else ty)
            if not self.accept_op(","):
                break
        if all(v is None for v in values):
            return []
        if any(v is None for v in values):
            raise self.unsupported("mixing initialised and uninitialised declarations", t)
        return idioms.declare(names, values, types, self.pos(t))

    def array_init(self):
        t = self.expect_op("{")
        items = []
        while not self.at_op("}"):
            items.append(self.expr())
            if not self.accept_op(","):
                break
        self.expect_op("}")
        return A.ArrayLit(items, line=t.line, col=t.col)

    def for_each(self, t):
        k = self.generic_ahead(1) if self.peek().kind == "TYPE" else 0
        if not (k and self.peek(k).kind == "NAME" and self.peek(k + 1).text == ":"):
            return None
        self.jtype()
        var = self.next()
        self.declare_name(var.text, var)
        self.expect_op(":")
        it = self.expr()
        if isinstance(it, Method) and it.name in ("toCharArray", "keySet"):
            it = it.obj
        self.expect_op(")")
        body = self.body()
        return [A.For(var.text, "each", body, iter=it, **self.pos(t))]

    def cast(self):
        if self.at_op("(") and self.peek(1).kind == "TYPE" and self.peek(2).text == ")":
            t = self.next()
            ty = self.next()
            self.next()
            e = self.unary()
            if ty.text not in ("int", "long", "double", "char"):
                raise self.unsupported(f"casts to {ty.text}", t)
            kind = {"double": "num_float", "char": "num_char"}.get(ty.text, "num_int")
            return A.Intrinsic(kind, [e], line=t.line, col=t.col)
        return None

    def primary_extra(self):
        t = self.peek()
        if self.at("KEYWORD", "new"):
            self.next()
            ty = self.expect("TYPE", what="a type")
            if ty.text == "StringBuilder":
                if self.args():
                    raise self.unsupported("new StringBuilder(...) with arguments", ty)
                return A.StrLit("", line=t.line, col=t.col)
            if ty.text in MAPS or ty.text in SETS:
                self.expect_op("<")
                self.expect_op(">")
                args = self.args()
                if ty.text in ("TreeSet", "HashSet") and len(args) == 1 and isinstance(args[0], Method) \
                        and args[0].name == "keySet":
                    return A.Intrinsic("sorted", [args[0].obj], line=t.line, col=t.col)
                if args:
                    raise self.unsupported(f"new {ty.text}<>(...) with arguments", ty)
                return A.Intrinsic("map_new" if ty.text in MAPS else "set_new", [], line=t.line, col=t.col)
            if ty.text == "ArrayList":
                self.expect_op("<")
                self.expect_op(">")
                args = self.args()
                if not args:
                    return A.ArrayLit([], line=t.line, col=t.col)
                x = args[0]
                if len(args) != 1:
                    raise self.unsupported("new ArrayList<>(...) with these arguments", ty)
                if isinstance(x, A.ArrayLit) or isinstance(x, A.Intrinsic) and x.name in ("list_fill", "slice", "sorted"):
                    return x
                return A.Intrinsic("lcopy", [x], line=t.line, col=t.col)
            self.expect_op("[")
            if not self.at_op("]"):
                raise self.unsupported("new arrays of a given size", t)
            self.next()
            if ty.text not in ("long", "int"):
                raise self.unsupported(f"arrays of {ty.text}", ty)
            return self.array_init()
        if t.kind == "KEYWORD" and t.text in ("null", "this"):
            raise self.unsupported(t.text, t)
        if t.kind in ("NAME", "TYPE") and t.text in ("System", "Arrays", "Math", "Integer", "Long", "String", "Character",
                                                     "Double", "Boolean", "List", "Collections") \
                and self.peek(1).text == ".":
            self.next()
            return Path(t.text, line=t.line, col=t.col)
        return None

    def member(self, e, name, t):
        n = name.text
        pos = {"line": e.line, "col": e.col}
        if n == "merge" and self.at_op("("):
            self.next()
            key = self.expr()
            self.expect_op(",")
            value = self.expr()
            for want in (",", None, ":", ":", "sum", ")"):
                tok = self.next()
                if want is not None and tok.text != want or want is None and tok.text not in ("Long", "Double"):
                    raise self.unsupported("merge() other than merge(k, v, Long::sum)", tok)
            return A.Intrinsic("map_incr", [e, key, value], **pos)
        if n in ("mapToLong", "mapToDouble") and isinstance(e, Method) and e.name == "stream":
            self.expect_op("(")
            box = self.next().text
            for want in (":", ":", box.lower() + "Value", ")", ".", "sum", "(", ")"):
                if self.peek().text != want:
                    raise self.unsupported("this stream() chain", self.peek())
                self.next()
            return A.Intrinsic("sum", [e.obj], **pos)
        args = self.args() if self.at_op("(") else None
        if isinstance(e, Path):
            path = f"{e.text}.{n}"
            if path == "List.of" and args is not None:
                return A.ArrayLit(args, **pos)
            if path in COLLECTIONS and args is not None and len(args) == 1:
                return A.Intrinsic(COLLECTIONS[path], args, **pos)
            if path == "Collections.nCopies" and args is not None and len(args) == 2:
                return A.Intrinsic("list_fill", [args[1], args[0]], **pos)
            if path == "Collections.reverseOrder" and args == []:
                return Path(path, **pos)
            if path == "Collections.swap" and args is not None and len(args) == 3:
                return Method(e, path, args, **pos)
            if path == "String.join" and args is not None and len(args) == 2:
                return A.Intrinsic("join", args, **pos)
            if args is None and path == "System.out":
                return Path(path, line=e.line, col=e.col)
            if path == "System.exit" and args is not None and len(args) == 1:
                return A.Intrinsic("exit", args, line=e.line, col=e.col)
            if path == "String.format" and args and isinstance(args[0], A.StrLit):
                m = FORMAT.match(args[0].value)
                if not m or len(args) != 2 or m.group(4) != "f" and m.group(3) or m.group(4) == "f" and not m.group(3):
                    raise self.unsupported(f"String.format(\"{args[0].value}\")", t)
                flag, width, prec, kind = m.groups()
                pos = {"line": e.line, "col": e.col}
                v = args[1]
                if kind == "f":
                    v = A.Intrinsic("fixed", [v, A.IntLit(int(prec), **pos)], **pos)
                elif kind == "d":
                    v = A.Intrinsic("str", [v], **pos)
                if width:
                    v = A.Intrinsic("ljust" if flag else "rjust", [v, A.IntLit(int(width), **pos)], **pos)
                return v
            if path in ("System.out.println", "System.out.print", "Arrays.toString") and args is not None:
                return Method(e, path, args, line=e.line, col=e.col)
            if path in CONSTS and args is None:
                return A.Intrinsic(CONSTS[path], [], line=e.line, col=e.col)
            if path == "Math.round" and args is not None and len(args) == 1:
                inner = A.Intrinsic("round_js", args, line=e.line, col=e.col)
                return A.Intrinsic("f2i", [inner], line=e.line, col=e.col)
            if path in LIB and args is not None:
                if path in ("Long.parseLong", "Double.parseDouble") and len(args) == 1 \
                        and isinstance(args[0], A.Intrinsic) and args[0].name == "trim":
                    args = args[0].args
                return A.Intrinsic(LIB[path], args, line=e.line, col=e.col)
            if path in CHARACTER and args is not None and len(args) == 1:
                return A.Intrinsic(CHARACTER[path], args, line=e.line, col=e.col)
            raise self.unsupported(f"library call {path}", t)
        if args is None:
            if n == "length":
                return A.Len(e, line=e.line, col=e.col)
            raise self.unsupported(f"field '.{n}'", t)
        if n == "length" and not args:
            return A.Len(e, line=e.line, col=e.col)
        if n == "charAt" and len(args) == 1:
            return A.Index(e, args[0], line=e.line, col=e.col)
        if n == "get" and len(args) == 1:
            return A.Index(e, args[0], **pos)
        if n in ("put", "getOrDefault", "containsKey") and len(args) == (1 if n == "containsKey" else 2):
            return A.Intrinsic({"put": "map_put", "getOrDefault": "map_get_or", "containsKey": "map_has"}[n],
                               [e, *args], **pos)
        if n == "keySet" and not args:
            return Method(e, n, args, **pos)
        if n == "size" and not args:
            return A.Len(e, **pos)
        if n == "add" and len(args) in (1, 2):
            return A.Intrinsic("push" if len(args) == 1 else "insert", [e, *args], **pos)
        if n == "remove" and len(args) == 1:
            i = args[0]
            last = isinstance(i, A.BinOp) and i.op == "-" and isinstance(i.left, A.Len) and A.same(i.left.arg, e) \
                and isinstance(i.right, A.IntLit) and i.right.value == 1
            return A.Intrinsic("pop", [e], **pos) if last else A.Intrinsic("pop_at", [e, i], **pos)
        if n == "subList" and len(args) == 2:
            return A.Intrinsic("slice", [e, *args], **pos)
        if n == "sort" and len(args) == 1 and isinstance(args[0], Path) and args[0].text == "Collections.reverseOrder":
            return A.Intrinsic("sort_desc", [e], **pos)
        if n in ("set", "stream") and len(args) == (2 if n == "set" else 0):
            return Method(e, n, args, **pos)
        if n == "equals" and len(args) == 1:
            return A.Compare("==", e, args[0], line=e.line, col=e.col)
        if n == "toString" and not args:
            return e
        if n == "substring" and len(args) in (1, 2):
            stop = args[1] if len(args) == 2 else A.Len(e, line=e.line, col=e.col)
            return A.Intrinsic("slice", [e, args[0], stop], line=e.line, col=e.col)
        if n in STRING_METHODS:
            return A.Intrinsic(STRING_METHODS[n], [e, *args], line=e.line, col=e.col)
        if n in ("toCharArray", "insert", "append"):
            return Method(e, n, args, line=e.line, col=e.col)
        raise self.unsupported(f"method '.{n}()'", t)

    def expr_statement(self, e, t):
        if isinstance(e, Method) and e.name == "set":
            return [A.Assign(A.Index(e.obj, e.args[0], line=e.line, col=e.col), e.args[1], **self.pos(t))]
        if isinstance(e, Method) and e.name == "Collections.swap":
            xs, i, j = e.args
            pos = {"line": e.line, "col": e.col}
            return [A.Swap(A.Index(xs, i, **pos), A.Index(A.Name(xs.id, **pos) if isinstance(xs, A.Name) else xs, j, **pos),
                           **self.pos(t))]
        if isinstance(e, A.Intrinsic) and e.name == "pop_at":
            e = A.Intrinsic("remove_at", e.args, line=e.line, col=e.col)
        if isinstance(e, A.Intrinsic) and (e.name in set(LISTOPS) or e.name in MAPOPS or e.name == "exit"):
            return [A.ExprStmt(e, **self.pos(t))]
        if isinstance(e, Method) and e.name in ("System.out.println", "System.out.print"):
            if len(e.args) > 1:
                raise self.fail(f"Syntax error: {e.name[11:]} takes one argument", t)
            node = A.Print(self.print_args(e.args[0]) if e.args else [], **self.pos(t))
            if e.name == "System.out.print":
                x = e.args[0] if e.args else None
                if isinstance(x, A.StrLit) and not x.value.strip(" "):
                    node.args = []
                    node.ending = x.value
                else:
                    node.ending = ""
            return [node]
        if isinstance(e, Method) and e.name in ("insert", "append") and isinstance(e.obj, A.Name):
            sb = A.Name(e.obj.id, line=e.line, col=e.col)
            if e.name == "insert":
                if len(e.args) != 2 or not (isinstance(e.args[0], A.IntLit) and e.args[0].value == 0):
                    raise self.unsupported("StringBuilder.insert at a position other than 0", t)
                value = A.BinOp("+", e.args[1], A.Name(sb.id, line=e.line, col=e.col), line=e.line, col=e.col)
            else:
                if len(e.args) != 1:
                    raise self.fail("Syntax error: append takes one argument", t)
                value = A.BinOp("+", A.Name(sb.id, line=e.line, col=e.col), e.args[0], line=e.line, col=e.col)
            return [A.Assign(sb, value, **self.pos(t))]
        return super().expr_statement(e, t)

    def print_args(self, e):
        if isinstance(e, Method) and e.name == "Arrays.toString" and len(e.args) == 1:
            return [e.args[0]]
        spine = []
        x = e
        while isinstance(x, A.BinOp) and x.op == "+":
            spine.append(x.right)
            x = x.left
        spine.append(x)
        spine.reverse()
        k = next((i for i, s in enumerate(spine) if isinstance(s, A.StrLit)), None)
        if k is None or len(spine) == 1:
            return [e]
        head = spine[0]
        for s in spine[1:k]:
            head = A.BinOp("+", head, s, line=s.line, col=s.col)
        items = ([head] if k > 0 else []) + spine[k:]
        mark = chr(0)
        text, exprs = "", []
        for s in items:
            if isinstance(s, A.StrLit):
                text += s.value
            else:
                text += f"{mark}{len(exprs)}{mark}"
                exprs.append(s)
        return idioms.words(text, mark, exprs, {"line": e.line, "col": e.col})
