from dataclasses import dataclass

from ... import ast as A
from ...backends import clists, cmaps
from ...errors import CompileError
from ...library import LISTOPS, MAPOPS
from ...semantic import mp, sset
from ...semantic import rewrite
from .. import idioms
from ..cfamily import CFamily

HEADERS = {"stdio.h", "string.h", "stdbool.h", "stdlib.h", "math.h", "ctype.h", "stdarg.h"}
CS_HELPERS = {"cs_f2s": "f2s", "cs_i2s": "i2s", "cs_ipow": "pow_i", "cs_imin": "min", "cs_imax": "max",
              "cs_round_js": "round_js", "cs_substr": "substr", "cs_upper": "upper", "cs_lower": "lower",
              "cs_trim": "trim", "cs_starts": "starts", "cs_ends": "ends", "cs_find": "find", "cs_replace": "replace_all",
              "cs_repeat": "repeat", "cs_concat": "concat", "cs_c2s": "c2s", "cs_append": "append",
              "cs_read_line": "read_line", "cs_format": "format"}
CTYPE = {"isdigit": "is_digit", "isalpha": "is_alpha", "isspace": "is_space", "isupper": "is_upper",
         "islower": "is_lower", "toupper": "cupper", "tolower": "clower"}
MATH = {
    "llabs": "abs", "labs": "abs", "abs": "abs", "fabs": "abs", "fmin": "min", "fmax": "max", "pow": "pow_f",
    "sqrt": "sqrt", "floor": "floor", "ceil": "ceil", "trunc": "trunc", "rint": "round_even", "round": "round_away",
    "sin": "sin", "cos": "cos", "tan": "tan", "atan2": "atan2", "log": "log", "log10": "log10", "log2": "log2",
    "exp": "exp", "hypot": "hypot",
}
DEFINES = {"#define CS_PI 3.14159265358979323846": "pi", "#define CS_E 2.71828182845904523536": "e"}
LIST_TYPES = {k: t for t, k in clists.KIND.items()}
BASE = {k: t for t, k in cmaps.KIND.items()}
MAP_OPS = {"new": "map_new", "put": "map_put", "get": "map_get", "get_or": "map_get_or", "has": "map_has",
           "del": "map_del", "incr": "map_incr", "keys": "sorted"}
SET_OPS = {"new": "set_new", "add": "set_add", "has": "set_has", "del": "set_del", "items": "sorted"}
LIST_OPS = {"push": "push", "insert": "insert", "pop": "pop", "pop_at": "pop_at", "index_of": "index_of",
            "contains": "contains_l", "sort": "sort", "sort_desc": "sort_desc", "reverse": "reverse", "sorted": "sorted",
            "slice": "slice", "sum": "sum", "min": "lmin", "max": "lmax"}


class ListType(str):
    pass


@dataclass(eq=False)
class Null(A.Expr):
    pass
SPECS = {"lld": "int", "ld": "int", "d": "int", "i": "int", "s": "str", "c": "char"}


@dataclass(eq=False)
class Buffer(A.Stmt):
    name: str
    size: int


def parse(tokens):
    return CParser(tokens).module()


def unsupported(what, node):
    return CompileError("parser", f"Unsupported: {what}", node.line, node.col)


class CParser(CFamily):
    lang = "c"

    def __init__(self, toks):
        super().__init__(toks)
        self.kinds = {}

    def module(self):
        includes, funcs, main, helpers = [], [], None, []
        while not self.at("EOF"):
            t = self.peek()
            if t.kind == "PRE":
                self.next()
                includes.append(self.include(t))
                continue
            if t.kind == "KEYWORD" and t.text == "static":
                helpers.append(self.helper_def())
                continue
            if t.kind == "KEYWORD" and t.text == "typedef":
                helpers.append(self.typedef())
                continue
            fn = self.function()
            if fn is None:
                continue
            if fn.name == "main":
                main = fn
            else:
                funcs.append(fn)
        body = []
        entry = None
        if main is not None:
            body = main.body
            if body and isinstance(body[-1], A.Return):
                ret = body.pop()
                if not (isinstance(ret.value, A.IntLit) and ret.value.value == 0):
                    raise unsupported("main returning something other than 0", ret)
            for r in A.walk_all(body):
                if isinstance(r, A.Return):
                    raise unsupported("return inside main", r)
            entry = (main.line, main.end)
        m = A.Module(funcs, body, entry=entry, lang="c", wrap=[entry] if entry else [], line=1, col=1)
        for s in [*m.functions, *m.body]:
            rewrite(s, c_idioms)
        for n in A.walk_all([*m.functions, *m.body]):
            if isinstance(n, Null):
                raise unsupported("NULL", n)
            if isinstance(n, A.Intrinsic) and n.name in ("strstr", "strchr", "strcmp"):
                raise unsupported(f"{n.name}() used this way", n)
        Raise(m).run()
        for n in A.walk_all([*m.functions, *m.body]):
            if isinstance(n, A.Index) and getattr(n, "keys", False):
                raise unsupported("->keys[i] outside a loop over the dict", n)
        attach_includes(m, [i for i in includes if i[0] not in ("pi", "e")])
        attach_helpers(m, helpers + [(name, line, line) for name, line in includes if name in ("pi", "e")])
        return m

    def helper_def(self):
        t = self.next()
        name = None
        while not self.at_op("("):
            if self.at("EOF"):
                raise self.error("expected '('")
            tok = self.next()
            if tok.kind == "NAME":
                name = tok
        if name is None or name.text not in CS_HELPERS and not clists.known(name.text) and not cmaps.known(name.text):
            raise self.unsupported("static declarations", t)
        while not self.at_op("{"):
            if self.at("EOF"):
                raise self.error("expected '{'")
            self.next()
        depth = 0
        while True:
            tok = self.next()
            if tok.kind == "EOF":
                raise self.error("expected '}'")
            depth += {"{": 1, "}": -1}.get(tok.text, 0) if tok.kind == "PUNCT" else 0
            if depth == 0:
                return name.text, t.line, tok.line

    def typedef(self):
        t = self.next()
        if not self.at("KEYWORD", "struct"):
            raise self.unsupported("typedef", t)
        self.skip_braced()
        name = self.expect("NAME", what="a type name")
        listy = clists.split(name.text) is not None and name.text.startswith("cs_list_")
        if not listy and not (cmaps.known(name.text) and name.text.startswith(("cs_map_", "cs_set_"))):
            raise self.unsupported("typedef", t)
        end = self.expect_op(";")
        return name.text, t.line, end.line

    def list_type(self):
        t = self.peek()
        if t.kind == "NAME" and t.text.startswith(("cs_map_", "cs_set_")) and self.peek(1).text == "*":
            split = cmaps.split(t.text)
            if split is None:
                raise self.unsupported(f"type {t.text}", t)
            self.next()
            self.next()
            kind, _, k, v = split
            return ListType(mp(BASE[k], BASE[v]) if kind == "map" else sset(BASE[k]))
        if t.kind == "NAME" and t.text.startswith("cs_list_") and self.peek(1).text == "*":
            split = clists.split(t.text)
            if split is None:
                raise self.unsupported(f"type {t.text}", t)
            self.next()
            self.next()
            return ListType(LIST_TYPES[split[1]])
        return None

    def include(self, t):
        text = t.text
        if text in DEFINES:
            return DEFINES[text], t.line
        if not text.startswith("#include"):
            raise self.unsupported(f"preprocessor directive '{text.split()[0]}'", t)
        name = text[len("#include"):].strip().strip("<>\"")
        if name not in HEADERS:
            raise self.unsupported(f"#include <{name}>", t)
        return name, t.line

    def ctype(self):
        t = self.peek()
        listy = self.list_type()
        if listy is not None:
            return listy
        const = bool(self.accept("KEYWORD", "const"))
        if self.at("KEYWORD", "static"):
            raise self.unsupported("static declarations")
        words = []
        while self.at("TYPE"):
            words.append(self.next().text)
        if not words:
            raise self.error("expected a type")
        if "float" in words or words.count("long") and "double" in words:
            raise self.unsupported("float and long double (use double)", t)
        if words == ["double"]:
            if self.at_op("*"):
                raise self.unsupported("pointers", t)
            return "float"
        if any(w in ("unsigned", "short", "signed") for w in words):
            raise self.unsupported(f"'{' '.join(words)}' type", t)
        base = "void" if words == ["void"] else "char" if words == ["char"] else "bool" if words[0] in ("bool", "_Bool") \
            else "int" if set(words) <= {"int", "long"} else None
        if base is None:
            raise self.unsupported(f"'{' '.join(words)}' type", t)
        stars = 0
        while self.accept_op("*"):
            stars += 1
        if stars > 1 or (stars and base not in ("char", "int")):
            raise self.unsupported("pointers", t)
        if stars and base == "char":
            return "str" if const else "outbuf"
        if stars:
            return "arr"
        return base

    def function(self):
        t = self.peek()
        ret = self.ctype()
        name = self.expect("NAME", what="a function name")
        if not self.at_op("("):
            raise self.unsupported("global variables", name)
        self.next()
        params = []
        if self.at("TYPE", "void") and self.peek(1).text == ")":
            self.next()
        while not self.at_op(")"):
            ty = self.ctype()
            p = self.expect("NAME", what="a parameter name")
            if self.accept_op("["):
                self.expect_op("]")
                if ty != "int":
                    raise self.unsupported("arrays of this type", p)
                ty = "arr"
            params.append(A.Param(p.text, ty, line=p.line, col=p.col))
            if not self.accept_op(","):
                break
        self.expect_op(")")
        if self.accept_op(";"):
            return None
        self.kinds = {p.name: p.ty for p in params}
        saved = self.fresh_scopes(p.name for p in params)
        body = self.block()
        self.scopes = saved
        return A.FunctionDef(name.text, params, body, ret, **self.pos(t))

    def decl_start(self):
        return self.at("TYPE") or (self.at("KEYWORD", "const") and self.peek(1).kind == "TYPE") or (
            self.peek().text.startswith(("cs_list_", "cs_map_", "cs_set_")) and self.peek(1).text == "*")

    def arrow(self, e, t):
        self.next()
        name = self.expect("NAME", what="a member name")
        pos = {"line": e.line, "col": e.col}
        if name.text == "len":
            return A.Len(e, **pos)
        if name.text in ("data", "keys") and self.accept_op("["):
            i = self.expr()
            self.expect_op("]")
            node = A.Index(e, i, **pos)
            node.keys = name.text == "keys"
            return node
        raise self.unsupported(f"member '->{name.text}'", name)

    def expr_statement(self, e, t):
        if isinstance(e, A.Intrinsic) and e.name == "pop_at":
            e = A.Intrinsic("remove_at", e.args, line=e.line, col=e.col)
        if isinstance(e, A.Intrinsic) and (e.name in set(LISTOPS) or e.name in MAPOPS or e.name == "exit"):
            return [A.ExprStmt(e, **self.pos(t))]
        return super().expr_statement(e, t)

    def assignment(self, lhs, op, value, t):
        if isinstance(lhs, A.Index) and isinstance(lhs.target, A.Name) and self.kinds.get(lhs.target.id) == "list<bool>":
            value = as_bool(value)
        if op.text == "=" and isinstance(value, A.Intrinsic) and value.name == "append_s" and A.same(value.args[0], lhs):
            return A.AugAssign(self.target(lhs), "+", value.args[1], **self.pos(t))
        return super().assignment(lhs, op, value, t)

    def loop_cond(self, cond):
        if isinstance(cond, A.Compare) and cond.op == "!=" and isinstance(cond.left, A.Index)                 and isinstance(cond.left.index, A.Name) and isinstance(cond.right, A.CharLit) and cond.right.value == "\0":
            pos = {"line": cond.line, "col": cond.col}
            return A.Compare("<", cond.left.index, A.Len(cond.left.target, **pos), **pos)
        return cond

    def declaration(self):
        t = self.peek()
        ty = self.ctype()
        if ty in ("arr", "outbuf") and not isinstance(ty, ListType):
            raise self.unsupported("pointers", t)
        names, values = [], []
        while True:
            n = self.expect("NAME", what="a variable name")
            self.declare_name(n.text, n)
            size = None
            if self.accept_op("["):
                size = None if self.at_op("]") else self.expr()
                self.expect_op("]")
            if self.accept_op("="):
                value = self.array_init() if self.at_op("{") else self.expr()
            elif size is not None and ty == "char":
                if not isinstance(size, A.IntLit):
                    raise self.unsupported("variable-length array", n)
                return [Buffer(n.text, size.value, **self.pos(t))]
            elif size is not None:
                raise self.unsupported("array without an initialiser", n)
            else:
                value = None
            if size is not None and not isinstance(value, A.ArrayLit):
                raise self.unsupported("array initialised from a non-literal", n)
            names.append(A.Name(n.text, line=n.line, col=n.col))
            values.append(value)
            self.kinds[n.text] = "arr" if isinstance(value, A.ArrayLit) and not isinstance(ty, ListType) else ty
            if not self.accept_op(","):
                break
        if all(v is None for v in values):
            return []
        if any(v is None for v in values):
            raise self.unsupported("mixing initialised and uninitialised declarations", t)
        return idioms.declare(names, values, [self.kinds[n.id] for n in names], self.pos(t))

    def array_init(self):
        t = self.expect_op("{")
        items = []
        while not self.at_op("}"):
            items.append(self.expr())
            if not self.accept_op(","):
                break
        self.expect_op("}")
        return A.ArrayLit(items, line=t.line, col=t.col)

    def cast(self):
        k = self.peek(1)
        if self.at_op("(") and (k.kind == "TYPE" or k.text == "const" and self.peek(2).kind == "TYPE"
                                or k.text.startswith("cs_list_") and self.peek(2).text == "*"):
            t = self.next()
            ty = self.ctype()
            if self.accept_op("["):
                self.expect_op("]")
                self.expect_op(")")
                if not self.at_op("{"):
                    raise self.unsupported("casts to an array type", t)
                return self.array_init()
            self.expect_op(")")
            e = self.unary()
            if ty not in ("int", "float", "char"):
                raise self.unsupported("casts to this type", t)
            kind = {"int": "num_int", "float": "num_float", "char": "num_char"}[ty]
            return A.Intrinsic(kind, [e], line=t.line, col=t.col)
        return None

    def call(self, t, args):
        if clists.known(t.text):
            return self.list_call(t, args)
        if cmaps.known(t.text):
            kind, op, _, v = cmaps.split(t.text)
            names = MAP_OPS if kind == "map" else SET_OPS
            if op not in names:
                raise self.unsupported(f"calling {t.text}() directly", t)
            if v == "bool" and len(args) == 3:
                args[2] = as_bool(args[2])
            return A.Intrinsic(names[op], args, line=t.line, col=t.col)
        if t.text == "strlen":
            if len(args) != 1:
                raise self.fail("Syntax error: strlen() takes one argument", t)
            return A.Len(args[0], line=t.line, col=t.col)
        if t.text == "printf":
            raise self.unsupported("printf() used as a value", t)
        if t.text == "cs_format" and args and isinstance(args[0], A.StrLit):
            v = idioms.formatted(args[0].value, args[1:], {"line": t.line, "col": t.col})
            if v is None:
                raise self.unsupported(f"cs_format(\"{args[0].value}\")", t)
            return v
        if t.text == "exit" and len(args) == 1:
            return A.Intrinsic("exit", args, line=t.line, col=t.col)
        if t.text == "cs_concat" and len(args) == 2:
            return A.BinOp("+", args[0], args[1], line=t.line, col=t.col)
        if t.text == "cs_c2s" and len(args) == 1:
            return args[0]
        if t.text == "cs_append" and len(args) == 2:
            return A.Intrinsic("append_s", args, line=t.line, col=t.col)
        if t.text in CS_HELPERS:
            return A.Intrinsic(CS_HELPERS[t.text], args, line=t.line, col=t.col)
        if t.text in CTYPE:
            return A.Intrinsic(CTYPE[t.text], args, line=t.line, col=t.col)
        if t.text in ("strstr", "strchr", "strcmp") and len(args) == 2:
            return A.Intrinsic(t.text, args, line=t.line, col=t.col)
        if t.text in MATH:
            return A.Intrinsic(MATH[t.text], args, line=t.line, col=t.col)
        if t.text in ("strtoll", "strtod"):
            want = 3 if t.text == "strtoll" else 2
            if len(args) != want or not isinstance(args[1], Null) or want == 3 and not (
                    isinstance(args[2], A.IntLit) and args[2].value == 10):
                raise self.unsupported(f"{t.text}() with these arguments", t)
            return A.Intrinsic("s2i" if want == 3 else "s2f", args[:1], line=t.line, col=t.col)
        return super().call(t, args)

    def list_call(self, t, args):
        pos = {"line": t.line, "col": t.col}
        if t.text in clists.SOLO:
            return A.Intrinsic(t.text[3:], args, **pos)
        op, k = clists.split(t.text)
        if k == "bool":
            args = [args[0], *map(as_bool, args[1:])] if op != "from" else args
            if op == "from" and len(args) == 2 and isinstance(args[1], A.ArrayLit):
                args[1].items = [as_bool(x) for x in args[1].items]
        if op == "new" and not args:
            return A.ArrayLit([], **pos)
        if op == "from" and len(args) == 2 and isinstance(args[1], A.ArrayLit) and isinstance(args[0], A.IntLit) \
                and args[0].value == len(args[1].items):
            return args[1]
        if op == "show" and len(args) == 1:
            return args[0]
        if op == "fill" and len(args) == 2:
            return A.Intrinsic("list_fill", [args[1], args[0]], **pos)
        if op in LIST_OPS:
            return A.Intrinsic(LIST_OPS[op], args, **pos)
        raise self.unsupported(f"calling {t.text}() directly", t)

    def primary_extra(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "NULL":
            self.next()
            return Null(line=t.line, col=t.col)
        if t.kind == "KEYWORD" and t.text == "sizeof":
            raise self.unsupported(t.text, t)
        if t.kind == "NAME" and t.text in ("CS_PI", "CS_E"):
            self.next()
            return A.Intrinsic("pi" if t.text == "CS_PI" else "e", [], line=t.line, col=t.col)
        return None

    def simple(self):
        t = self.peek()
        if t.kind == "BUILTIN" and t.text == "printf" and self.peek(1).text == "(":
            self.next()
            self.expect_op("(")
            fmt = self.string()
            args = []
            while self.accept_op(","):
                args.append(self.expr())
            self.expect_op(")")
            return [self.printf(fmt, args, t)]
        return super().simple()

    def printf(self, fmt, args, t):
        text = fmt.value
        newline = text.endswith("\n")
        body = text[:-1] if newline else text.rstrip(" ")
        ending = "\n" if newline else text[len(body):]
        pos = {"line": fmt.line, "col": fmt.col}
        mark, marked, exprs, k, i = chr(0), "", [], 0, 0
        while i < len(body):
            j = body.find("%", i)
            if j < 0:
                marked += body[i:]
                break
            marked += body[i:j]
            if body.startswith("%%", j):
                marked += "%"
                i = j + 2
                continue
            m = idioms.SPEC.match(body, j)
            if not m:
                raise self.unsupported(f"printf format '{body[j:j + 6]}'", t)
            if k >= len(args):
                raise self.fail("Syntax error: printf has fewer arguments than format specifiers", t)
            arg = args[k]
            k += 1
            if m.group(0) == "%s" and isinstance(arg, A.Intrinsic) and arg.name == "f2s":
                arg = arg.args[0]
            v = idioms.spec_value(m, arg, pos)
            if v is None:
                raise self.unsupported(f"printf format '{m.group(0)}'", t)
            marked += f"{mark}{len(exprs)}{mark}"
            exprs.append(v)
            i = m.end()
        if k < len(args):
            raise self.fail("Syntax error: printf has more arguments than format specifiers", t)
        out = idioms.words(marked, mark, exprs, pos) if marked else []
        node = A.Print(out, **self.pos(t))
        node.newline = newline
        node.fmt = fmt.value
        node.ending = ending
        return node


def as_bool(e):
    if isinstance(e, A.IntLit) and e.value in (0, 1):
        return A.BoolLit(bool(e.value), line=e.line, col=e.col)
    return e


def attach_includes(m, includes):
    stmts = sorted((s for s in A.walk_all([*m.functions, *m.body]) if isinstance(s, A.Stmt)), key=lambda s: s.line)
    for name, line in includes:
        if name == "stdio.h":
            owner = next((s for s in stmts if isinstance(s, A.Print)), None)
        elif name == "string.h":
            owner = next((s for s in stmts if getattr(s, "strlen", False) or any(
                isinstance(n, A.Len) for e in A.heads(s) for n in A.walk(e))), None)
        else:
            owner = None
        if owner is not None:
            owner.extra.append(line)
        elif m.wrap:
            m.wrap.append((line, line))


def c_idioms(e):
    if not isinstance(e, A.Compare) or e.op not in ("==", "!=", "<", "<=", ">", ">="):
        return e
    left, right = e.left, e.right
    pos = {"line": e.line, "col": e.col}
    if isinstance(left, A.Intrinsic) and left.name == "strcmp" and isinstance(right, A.IntLit) and right.value == 0:
        return A.Compare(e.op, *left.args, **pos)
    if e.op in ("==", "!=") and isinstance(left, A.Intrinsic):
        hit = None
        if left.name in ("strstr", "strchr") and isinstance(right, Null):
            hit = A.Intrinsic("contains_s" if left.name == "strstr" else "contains_c", left.args, **pos)
        elif left.name in CTYPE.values() and left.name.startswith("is_") and isinstance(right, A.IntLit) \
                and right.value == 0:
            hit = left
        if hit is not None:
            return hit if e.op == "!=" else A.UnaryOp("!", hit, **pos)
    return e


def attach_helpers(m, helpers):
    prints = sorted((s for s in A.walk_all([*m.functions, *m.body]) if isinstance(s, A.Print)), key=lambda s: s.line)
    for _, start, end in helpers:
        if prints:
            prints[0].extra += list(range(start, end + 1))
        elif m.wrap:
            m.wrap.append((start, end))


class Raise:
    def __init__(self, m):
        self.m = m
        self.funcs = {f.name: f for f in m.functions}
        self.lengths = {}
        self.builders = {}

    def run(self):
        m = self.m
        for f in m.functions:
            f.body = idioms.fold_swaps(f.body, idioms.counts(f.body))
            self.length_params(f)
            self.builder(f)
            foreach(f.body)
        m.body = idioms.fold_swaps(m.body, idioms.counts(m.body))
        foreach(m.body)
        for owner in [*m.functions, m]:
            body = owner.body
            self.fix_calls(body)
            body[:] = self.buffers(body)
            body[:] = self.print_arrays(body)
            body[:] = idioms.inline_arrays(body)
        self.bools()
        for n in A.walk_all([*m.functions, *m.body]):
            if isinstance(n, Buffer):
                raise unsupported("char buffer that is not filled by a string-building function", n)

    def length_params(self, f):
        ps = f.params
        for k in range(len(ps) - 1, 0, -1):
            arr, n = ps[k - 1], ps[k]
            if arr.ty == "arr" and not isinstance(arr.ty, ListType) and n.ty == "int" \
                    and not idioms.written(f.body, n.name) \
                    and any(isinstance(x, A.Name) and x.id == n.name for x in A.walk_all(f.body)):
                replace_names(f.body, n.name, lambda x, a=arr.name: A.Len(A.Name(a, line=x.line, col=x.col), line=x.line, col=x.col))
                self.lengths.setdefault(f.name, []).append((k, arr.name))
                del ps[k]

    def builder(self, f):
        if f.ret in ("outbuf", "arr") and not isinstance(f.ret, ListType):
            raise unsupported("returning a pointer", f)
        if not any(p.ty == "outbuf" for p in f.params):
            return
        fail = unsupported("building a string through a char * parameter (supported: reversing or copying)", f)
        if not (f.ret == "void" and f.params[-1].ty == "outbuf" and len(f.body) == 3):
            raise fail
        out = f.params[-1].name
        init, loop, term = f.body
        if not (isinstance(init, A.Assign) and isinstance(init.target, A.Name) and isinstance(init.value, A.Len)
                and isinstance(init.value.arg, A.Name)):
            raise fail
        n, src = init.target.id, init.value.arg.id
        if not (isinstance(loop, A.For) and loop.kind == "range" and isinstance(loop.start, A.IntLit) and loop.start.value == 0
                and isinstance(loop.stop, A.Name) and loop.stop.id == n and loop.step.value == 1 and len(loop.body) == 1):
            raise fail
        i = loop.var
        st = loop.body[0]
        rev = A.BinOp("-", A.BinOp("-", A.Name(n), A.IntLit(1)), A.Name(i))
        if not (isinstance(st, A.Assign) and isinstance(st.target, A.Index) and isinstance(st.target.target, A.Name)
                and st.target.target.id == out and A.same(st.value, A.Index(A.Name(src), A.Name(i)))):
            raise fail
        if A.same(st.target.index, rev):
            mode = "prepend"
        elif A.same(st.target.index, A.Name(i)):
            mode = "append"
        else:
            raise fail
        if not (isinstance(term, A.Assign) and A.same(term.target, A.Index(A.Name(out), A.Name(n)))
                and isinstance(term.value, A.CharLit) and term.value.value == "\0"):
            raise fail
        ch = fresh("ch", f)
        name = lambda x: A.Name(x, line=st.line, col=st.col)
        value = A.BinOp("+", name(ch), name(out)) if mode == "prepend" else A.BinOp("+", name(out), name(ch))
        for e in A.walk(value):
            e.line, e.col = st.line, st.col
        first = A.Assign(A.Name(out, line=init.line, col=init.col), A.StrLit("", line=init.line, col=init.col),
                         line=init.line, col=init.col, end=init.end)
        first.strlen = True
        each = A.For(ch, "each", [A.Assign(name(out), value, line=st.line, col=st.col, end=st.end)],
                     iter=A.Name(src, line=loop.line, col=loop.col), line=loop.line, col=loop.col, end=loop.end)
        f.body = [first, each, A.Return(A.Name(out, line=term.line, col=term.col), line=term.line, col=term.col, end=term.end)]
        f.params = f.params[:-1]
        f.ret = "str"
        self.builders[f.name] = first

    def fix_calls(self, body):
        statics = {s.target.id: len(s.value.items) for s in A.walk_all(body)
                   if isinstance(s, A.Assign) and isinstance(s.target, A.Name) and isinstance(s.value, A.ArrayLit)}
        for c in A.walk_all(body):
            if not isinstance(c, A.Call) or c.func not in self.lengths:
                continue
            for k, arr in self.lengths[c.func]:
                if k >= len(c.args):
                    raise unsupported(f"call to {c.func}() with too few arguments", c)
                a, n = c.args[k - 1], c.args[k]
                size = len(a.items) if isinstance(a, A.ArrayLit) else statics.get(a.id) if isinstance(a, A.Name) else None
                ok = (isinstance(n, A.IntLit) and n.value == size) or (isinstance(n, A.Len) and A.same(n.arg, a))
                if not ok:
                    raise unsupported(f"passing a length to {c.func}() that is not the array's size", n)
                del c.args[k]

    def buffers(self, body):
        out = list(body)
        for buf in [s for s in body if isinstance(s, Buffer)]:
            k = out.index(buf)
            call_stmt = out[k + 1] if k + 1 < len(out) else None
            if not (isinstance(call_stmt, A.ExprStmt) and call_stmt.expr.func in self.builders
                    and call_stmt.expr.args and isinstance(call_stmt.expr.args[-1], A.Name)
                    and call_stmt.expr.args[-1].id == buf.name):
                continue
            call = call_stmt.expr
            call.args.pop()
            self.builders[call.func].extra.append(buf.line)
            rest = out[k + 2:]
            uses = [n for s in rest for n in A.walk(s) if isinstance(n, A.Name) and n.id == buf.name]
            user = next((s for s in rest if buf.name in A.names(s)), None)
            if len(uses) == 1 and user is not None:
                parent, idx = find_parent(user, uses[0])
                setattr(parent, idx[0], call) if idx[1] is None else getattr(parent, idx[0]).__setitem__(idx[1], call)
                user.line, user.col = call_stmt.line, call_stmt.col
                out[k:k + 2] = []
            else:
                out[k:k + 2] = [A.Assign(A.Name(buf.name, line=buf.line, col=buf.col), call, line=call_stmt.line,
                                         col=call_stmt.col, end=call_stmt.end)]
        return out

    def print_arrays(self, body):
        out = []
        for s in body:
            for b in A.blocks(s):
                b[:] = self.print_arrays(b)
            if (isinstance(s, A.For) and s.kind == "range" and len(s.body) == 1 and isinstance(s.body[0], A.Print)
                    and not getattr(s.body[0], "newline", True) and getattr(s.body[0], "fmt", "") in ("%lld ", "%ld ", "%d ")
                    and len(s.body[0].args) == 1 and isinstance(s.body[0].args[0], A.Index)
                    and A.same(s.body[0].args[0].index, A.Name(s.var)) and isinstance(s.start, A.IntLit) and s.start.value == 0
                    and s.step.value == 1):
                arr = s.body[0].args[0].target
                sizes = {x.target.id: len(x.value.items) for x in A.walk_all(body)
                         if isinstance(x, A.Assign) and isinstance(x.target, A.Name) and isinstance(x.value, A.ArrayLit)}
                if (isinstance(s.stop, A.Len) and A.same(s.stop.arg, arr)) or (
                        isinstance(s.stop, A.IntLit) and isinstance(arr, A.Name) and sizes.get(arr.id) == s.stop.value):
                    node = A.Print([arr], line=s.line, col=s.col, end=s.end)
                    out.append(node)
                    continue
            out.append(s)
        return out

    def bools(self):
        calls = {}
        for parent in A.walk_all([*self.m.functions, *self.m.body]):
            for kid in A.children(parent):
                if isinstance(kid, A.Call):
                    calls.setdefault(kid.func, []).append(parent)
        for f in self.m.functions:
            rets = [r for r in A.walk_all(f.body) if isinstance(r, A.Return)]
            if f.ret != "int" or not rets or not all(isinstance(r.value, A.IntLit) and r.value.value in (0, 1) for r in rets):
                continue
            if not all(isinstance(p, (A.Print, A.If, A.While, A.BoolOp)) or (isinstance(p, A.UnaryOp) and p.op == "!")
                       for p in calls.get(f.name, [])):
                continue
            f.ret = "bool"
            for r in rets:
                r.value = A.BoolLit(bool(r.value.value), line=r.value.line, col=r.value.col)
        for f in self.m.functions:
            for k, p in enumerate(f.params):
                if p.ty == "int" and truthy(f.body, p.name) and all(
                        isinstance(c.args[k], (A.Compare, A.BoolOp, A.BoolLit)) or isinstance(c.args[k], A.IntLit)
                        and c.args[k].value in (0, 1) or isinstance(c.args[k], A.UnaryOp) and c.args[k].op == "!"
                        for c in A.walk_all([*self.m.functions, *self.m.body])
                        if isinstance(c, A.Call) and c.func == f.name):
                    p.ty = "bool"
                    for c in A.walk_all([*self.m.functions, *self.m.body]):
                        if isinstance(c, A.Call) and c.func == f.name and isinstance(c.args[k], A.IntLit):
                            c.args[k] = A.BoolLit(bool(c.args[k].value), line=c.args[k].line, col=c.args[k].col)


def truthy(body, name):
    uses = [n for n in A.walk_all(body) if isinstance(n, A.Name) and n.id == name]
    ok = set()
    for parent in A.walk_all(body):
        kids = A.heads(parent)[:1] if isinstance(parent, (A.If, A.While)) else \
            [parent.left, parent.right] if isinstance(parent, A.BoolOp) else \
            [parent.operand] if isinstance(parent, A.UnaryOp) and parent.op == "!" else \
            parent.args if isinstance(parent, A.Intrinsic) and parent.name in ("b2s", "b2s_py") else []
        ok |= {id(k) for k in kids if isinstance(k, A.Name) and k.id == name}
    return bool(uses) and all(id(n) in ok for n in uses) and not any(
        isinstance(s, A.Stmt) and A.writes(s, name) for s in A.walk_all(body))


def blocks_of(stmts):
    yield stmts
    for s in stmts:
        for b in A.blocks(s):
            yield from blocks_of(b)


def foreach(body):
    for s in list(A.walk_all(body)):
        if not (isinstance(s, A.For) and s.kind == "range" and s.body and isinstance(s.start, A.IntLit)
                and s.start.value == 0 and s.step.value == 1):
            continue
        first = s.body[0]
        if not (isinstance(first, A.Assign) and first.decl and isinstance(first.target, A.Name)
                and isinstance(first.value, A.Index) and isinstance(first.value.index, A.Name)
                and first.value.index.id == s.var and isinstance(first.value.target, A.Name)):
            continue
        arr = first.value.target.id
        if any(isinstance(n, A.Name) and n.id == s.var for n in A.walk_all(s.body[1:])):
            continue
        stop, drop = s.stop, None
        if isinstance(stop, A.Name):
            defs = [(b, x) for b in blocks_of(body) for x in b if isinstance(x, A.Assign) and x.decl
                    and isinstance(x.target, A.Name) and x.target.id == stop.id]
            uses = [n for n in A.walk_all(body) if isinstance(n, A.Name) and n.id == stop.id]
            if len(defs) != 1 or len(uses) != 2 or not (isinstance(defs[0][1].value, A.Len)
                                                         and isinstance(defs[0][1].value.arg, A.Name)
                                                         and defs[0][1].value.arg.id == arr):
                continue
            drop = defs[0]
        elif not (isinstance(stop, A.Len) and isinstance(stop.arg, A.Name) and stop.arg.id == arr):
            continue
        if drop:
            drop[0].remove(drop[1])
        s.kind, s.var, s.iter = "each", first.target.id, A.Name(arr, line=first.line, col=first.col)
        s.body, s.start, s.stop, s.step = s.body[1:], None, None, None
        block = next(b for b in blocks_of(body) if any(x is s for x in b))
        k = next(j for j, x in enumerate(block) if x is s)
        prev = block[k - 1] if k else None
        if isinstance(prev, A.Assign) and prev.decl and isinstance(prev.target, A.Name) and prev.target.id == arr \
                and sum(isinstance(n, A.Name) and n.id == arr for n in A.walk_all(body)) == 2:
            s.iter = prev.value
            s.extra += [prev.line, *prev.extra]
            block.remove(prev)


def replace_names(stmts, name, make):
    for parent in list(A.walk_all(stmts)):
        for field in vars(parent):
            v = getattr(parent, field)
            if isinstance(v, A.Name) and v.id == name:
                setattr(parent, field, make(v))
            elif isinstance(v, list):
                for k, x in enumerate(v):
                    if isinstance(x, A.Name) and x.id == name:
                        v[k] = make(x)


def find_parent(root, node):
    for parent in A.walk(root):
        for field in vars(parent):
            v = getattr(parent, field)
            if v is node:
                return parent, (field, None)
            if isinstance(v, list):
                for k, x in enumerate(v):
                    if x is node:
                        return parent, (field, k)
    raise ValueError(node)


def fresh(base, f):
    used = {n.id for n in A.walk_all(f.body) if isinstance(n, A.Name)} | {p.name for p in f.params}
    used |= {s.var for s in A.walk_all(f.body) if isinstance(s, A.For)}
    k = 1
    while (base if k == 1 else f"{base}{k}") in used:
        k += 1
    return base if k == 1 else f"{base}{k}"
