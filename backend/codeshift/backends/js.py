from collections import Counter

from .. import ast as A
from ..linemap import ENTRY
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID, is_list, is_map, is_set, mkey, mval, selem
from .c import CBackend, Plan, unsupported
from .java import camel

KEYWORDS = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do", "else", "export",
    "extends", "finally", "for", "function", "if", "import", "in", "instanceof", "let", "new", "return", "super",
    "switch", "this", "throw", "try", "typeof", "var", "void", "while", "with", "yield", "await", "enum", "null",
    "true", "false", "undefined", "NaN", "Infinity", "Math", "console", "arguments", "eval", "static", "of",
}
CALLS = {
    "abs_i": "Math.abs", "abs_f": "Math.abs", "min": "Math.min", "max": "Math.max", "sqrt": "Math.sqrt",
    "floor": "Math.floor", "ceil": "Math.ceil", "trunc": "Math.trunc", "round_js": "Math.round", "sin": "Math.sin",
    "cos": "Math.cos", "tan": "Math.tan", "atan2": "Math.atan2", "log": "Math.log", "log10": "Math.log10",
    "log2": "Math.log2", "exp": "Math.exp", "hypot": "Math.hypot", "round_even": "csRoundEven",
    "round_away": "csRoundAway", "chr": "String.fromCharCode", "i2s": "String", "f2s": "String", "b2s": "String",
    "s2f": "parseFloat",
}
METHODS = {"upper": "toUpperCase", "lower": "toLowerCase", "cupper": "toUpperCase", "clower": "toLowerCase",
           "trim": "trim", "starts": "startsWith", "ends": "endsWith", "contains_s": "includes", "contains_c": "includes",
           "find": "indexOf", "replace_all": "replaceAll", "repeat": "repeat", "substr": "slice"}
CHECKS = {"is_digit": ("csIsDigit", 'c >= "0" && c <= "9"'), "is_upper": ("csIsUpper", 'c >= "A" && c <= "Z"'),
          "is_lower": ("csIsLower", 'c >= "a" && c <= "z"'),
          "is_alpha": ("csIsAlpha", '(c >= "a" && c <= "z") || (c >= "A" && c <= "Z")'),
          "is_space": ("csIsSpace", 'c === " " || c === "\\t" || c === "\\n" || c === "\\r" || c === "\\v" || c === "\\f"')}
HELPERS = {
    "csRoundEven": """function csRoundEven(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}""",
    "csRoundAway": """function csRoundAway(x) {
  return Math.sign(x) * Math.round(Math.abs(x));
}""",
    "csReadLine": """function csReadLine() {
  if (!csReadLine.lines) {
    csReadLine.lines = require("fs").readFileSync(0, "utf8").split("\\n");
    csReadLine.next = 0;
  }
  const line = csReadLine.lines[csReadLine.next++];
  return line === undefined ? "" : line.replace("\\r", "");
}""",
    "csSplitWs": """function csSplitWs(s) {
  return s.replaceAll("\\t", " ").replaceAll("\\n", " ").split(" ").filter((w) => w !== "");
}""",
    **{name: f"function {name}(c) {{\n  return {body};\n}}" for name, body in CHECKS.values()},
}
LISTS = {"push": "push", "pop": "pop", "reverse": "reverse", "contains_l": "includes", "index_of": "indexOf",
         "lslice": "slice", "split": "split"}
MAPS = {"map_new": "", "set_new": "", "map_get": "get", "map_put": "set", "map_get_or": "", "map_has": "has",
        "map_del": "delete", "map_len": "", "map_incr": "", "map_sorted_keys": "", "set_add": "add", "set_has": "has",
        "set_del": "delete", "set_len": "", "set_sorted": ""}
JSTYPE = {INT: "number", IDX: "number", BOOL: "boolean", CHAR: "string", STR: "string", ARR: "number[]", VOID: "void",
          FLOAT: "number"}


def jstype(t):
    if t in JSTYPE:
        return JSTYPE[t]
    if is_map(t):
        return f"Map<{jstype(mkey(t))}, {jstype(mval(t))}>"
    if is_set(t):
        return f"Set<{jstype(selem(t))}>"
    return jstype(t[5:-1]) + "[]"


class JSBackend(CBackend):
    lang = "js"
    KEYWORDS = KEYWORDS
    CAST = ""
    LONG = ""
    CSTR = False
    CONCAT = True
    INDENT = "  "
    ALLMAN = False

    def safe(self, name):
        n = camel(name)
        return n + "_" if n in KEYWORDS else n

    def ctype(self, t):
        return "let"

    def kw(self, name):
        return "const" if self.writes[name] <= 1 and self.p.decl.get(name, ("inline",))[0] == "inline" else "let"

    def decl_text(self, t, name):
        return f"{self.kw(name)} {self.safe(name)}"

    def length_params(self):
        return set()

    def fixed(self):
        return False

    def builder_of(self, func):
        return None

    def find_builder(self, f):
        return None

    def plan(self, f):
        p = Plan(set(f.vars) | set(self.info.funcs))
        if f.node is not None:
            p.params = [self.safe(n) for n in f.params]
            p.sig = f"function {self.safe(f.name)}({', '.join(p.params)})"
            p.ret = jstype(f.ret)
        for name, kind in f.kinds.items():
            if kind == "local":
                self.place(name, f.body, p.decl)
        return p

    def ex_as(self, e, want):
        return self.ex(e)

    def char_text(self, e):
        return self.ex(e)

    def _ex(self, e, cast=False):
        return super()._ex(e)

    def start(self, f):
        super().start(f)
        self.writes = Counter(n for s in A.walk_all(f.body) if isinstance(s, A.Stmt) for n in A.names(s)
                              if A.writes(s, n) or isinstance(s, A.For) and s.var == n)

    def generate(self):
        self.need_len = set()
        for f in self.info.all():
            self.plans[f] = self.plan(f)
        chunks = []
        for fn in self.m.functions:
            chunks += self.function(self.info.funcs[fn.name]) + [("", None)]
        main = self.main()
        lines = []
        for name, g in self.helpers.items():
            lines += [(x, g) for x in HELPERS[name].split("\n")] + [("", None)]
        lines += chunks
        self.entry = len(lines)
        lines += main
        if self.entry == len(lines) and lines:
            lines.pop()
            self.entry = len(lines)
        self.prelude = [HELPERS[n] for n in self.helpers]
        self.imports = [f"function {n}() helper" for n in self.helpers]
        return lines

    def helper(self, name, g):
        self.helpers.setdefault(name, g)

    def function(self, f):
        self.start(f)
        g = f.node.group
        self.line(self.p.sig, g)
        self.open(g)
        self.block(f.body)
        self.close(g)
        return self.out

    def main(self):
        self.start(self.info.main)
        self.block(self.info.main.body)
        return self.out

    def prototypes(self):
        return []

    def array(self, e):
        return "[" + ", ".join(self.ex(x) for x in e.items) + "]"

    def array_decl(self, name, v):
        return f"{self.kw(name)} {self.safe(name)} = {self.array(v)};"

    def array_arg(self, a, p, sized):
        return [self.array(a) if isinstance(a, A.ArrayLit) else self.ex(a)]

    def float_int(self, v):
        return str(v)

    def intrinsic(self, e):
        n = e.name
        if n == "i2f":
            return self._ex(e.args[0])
        if n == "f2i":
            return f"Math.trunc({self.ex(e.args[0])})", 1
        if n in ("pi", "e"):
            return ("Math.PI" if n == "pi" else "Math.E"), 1
        if n in ("pow_i", "pow_f"):
            (a, ap), (b, bp) = self._ex(e.args[0]), self._ex(e.args[1])
            return f"{f'({a})' if ap > 1 else a} ** {f'({b})' if bp > 2.5 else b}", 2.5
        if n == "ord":
            x, xp = self._ex(e.args[0])
            return f"{f'({x})' if xp > 1 else x}.charCodeAt(0)", 1
        if n == "s2i":
            return f"parseInt({self.ex(e.args[0])}, 10)", 1
        if n in CHECKS:
            self.helper(CHECKS[n][0], self.g)
            return f"{CHECKS[n][0]}({self.ex(e.args[0])})", 1
        if n in MAPS:
            return self.mapop(e)
        if n == "read_line":
            self.helper("csReadLine", self.g)
            return "csReadLine()", 1
        if n == "s2ints":
            self.helper("csSplitWs", self.g)
            return f"csSplitWs({self.ex(e.args[0])}).map((w) => parseInt(w, 10))", 1
        if n == "exit":
            return f"process.exit({self.ex(e.args[0])})", 1
        if n in ("fixed", "rjust", "ljust"):
            x, xp = self._ex(e.args[0])
            how = {"fixed": "toFixed", "rjust": "padStart", "ljust": "padEnd"}[n]
            literal = isinstance(e.args[0], (A.IntLit, A.FloatLit))
            return f"{f'({x})' if xp > 1 or literal else x}.{how}({self.ex(e.args[1])})", 1
        if n in LISTS or n in ("pop_at", "insert", "remove_at", "sort", "sort_desc", "sorted", "lcopy", "sum", "lmin",
                               "lmax", "list_fill", "grid", "split_ws", "join"):
            return self.listop(e)
        if n in METHODS:
            x, xp = self._ex(e.args[0])
            rest = e.args[1:]
            if n == "substr" and isinstance(rest[1], A.Len) and A.same(rest[1].arg, e.args[0]):
                rest = rest[:1]
            return f"{f'({x})' if xp > 1 else x}.{METHODS[n]}({', '.join(self.ex(a) for a in rest)})", 1
        if n in CALLS:
            if CALLS[n].startswith("cs"):
                self.helper(CALLS[n], self.g)
            return f"{CALLS[n]}({', '.join(self.ex(a) for a in e.args)})", 1
        return super().intrinsic(e)

    def mapop(self, e):
        n, args = e.name, e.args
        if n == "map_new":
            return "new Map()", 1
        if n == "set_new":
            return "new Set()", 1
        x, xp = self._ex(args[0])
        r = f"({x})" if xp > 1 else x
        rest = [self.ex(a) for a in args[1:]]
        if n in ("map_len", "set_len"):
            return f"{r}.size", 1
        if n in ("map_sorted_keys", "set_sorted"):
            el = "map" in n and mkey(args[0].ty) or selem(args[0].ty)
            cmp = "(a, b) => a - b" if el == INT else ""
            src = f"{r}.keys()" if n == "map_sorted_keys" else x
            return f"[...{src}].sort({cmp})", 1
        if n == "map_get_or":
            return f"{r}.get({rest[0]}) ?? {self._paren(args[2], A.PREC['||'])}", A.PREC["||"]
        if n == "map_incr":
            v = self._paren(args[2], A.PREC["+"])
            return f"{r}.set({rest[0]}, ({r}.get({rest[0]}) ?? 0) + {v})", 1
        return f"{r}.{MAPS[n]}({', '.join(rest)})", 1

    def listop(self, e):
        n, args = e.name, e.args
        if n == "list_fill":
            return f"new Array({self.ex(args[1])}).fill({self.ex(args[0])})", 1
        if n == "grid":
            r, c, v = (self.ex(a) for a in args)
            return f"Array.from({{ length: {r} }}, () => new Array({c}).fill({v}))", 1
        if n == "join":
            xs, xp = self._ex(args[1])
            return f"{f'({xs})' if xp > 1 else xs}.join({self.ex(args[0])})", 1
        if n == "split_ws":
            self.helper("csSplitWs", self.g)
            return f"csSplitWs({self.ex(args[0])})", 1
        x, xp = self._ex(args[0])
        recv = f"({x})" if xp > 1 else x
        rest = [self.ex(a) for a in args[1:]]
        number = args[0].ty in (ARR,) or args[0].ty == "list<float>"
        cmp = "(a, b) => a - b" if number else ""
        if n in LISTS:
            if n == "lslice" and isinstance(args[2], A.Len) and A.same(args[2].arg, args[0]):
                rest = rest[:1]
            return f"{recv}.{LISTS[n]}({', '.join(rest)})", 1
        if n == "pop_at":
            return f"{recv}.splice({rest[0]}, 1)[0]", 1
        if n == "remove_at":
            return f"{recv}.splice({rest[0]}, 1)", 1
        if n == "insert":
            return f"{recv}.splice({rest[0]}, 0, {rest[1]})", 1
        if n == "sort":
            return f"{recv}.sort({cmp})", 1
        if n == "sort_desc":
            return (f"{recv}.sort((a, b) => b - a)" if number else f"{recv}.sort().reverse()"), 1
        if n == "sorted":
            return f"[...{x}].sort({cmp})", 1
        if n == "lcopy":
            return f"[...{x}]", 1
        if n == "sum":
            return f"{recv}.reduce((a, b) => a + b, 0)", 1
        if not number:
            return f"{recv}.reduce((a, b) => (a {'<' if n == 'lmin' else '>'} b ? a : b))", 1
        return f"Math.{n[1:]}(...{x})", 1

    def aug(self, s):
        if s.op == "/" and s.target.ty != FLOAT:
            t = self.ex(s.target)
            self.emit(f"{t} = Math.floor({t} / {self._paren(s.value, A.PREC['/'])});", s.group)
        else:
            super().aug(s)

    def _paren(self, e, p):
        text, q = self._ex(e)
        return f"({text})" if q >= p else text

    def swap(self, s):
        a, b = self.ex(s.a), self.ex(s.b)
        self.emit(f"[{a}, {b}] = [{b}, {a}];", s.group)

    def tuple_assign(self, s):
        g = s.group
        names = [t.id for t in s.targets if isinstance(t, A.Name)]
        new = [n for n in names if self.p.decl.get(n) == ("inline", s) and n not in self.declared]
        reads = set().union(*(A.names(v) for v in s.values))
        if len(new) == len(s.targets) and not set(names) & reads:
            self.declared |= set(names)
            kw = "const" if all(self.writes[n] <= 1 for n in names) else "let"
            parts = [f"{self.safe(n)} = {self.ex(v)}" for n, v in zip(names, s.values)]
            self.emit(f"{kw} {', '.join(parts)};", g)
            return
        for n in new:
            self.declared.add(n)
            self.emit(f"let {self.safe(n)};", g)
        self.emit(f"[{', '.join(map(self.ex, s.targets))}] = [{', '.join(map(self.ex, s.values))}];", g)

    def for_head(self, ctype, v, start, cond, step):
        return f"for (let {self.safe(v)} = {start}; {cond}; {step})"

    def for_each(self, s):
        g = s.group
        it = self.ex(s.iter) + (".keys()" if is_map(s.iter.ty) else "")
        self.emit(f"for (const {self.safe(s.var)} of {it})", g)
        self.open(g)
        self.scopes[-1].add(s.var)
        self.block(s.body)
        self.close(g)

    def print_(self, s):
        end = getattr(s, "ending", "\n")
        if end == "\n":
            self.emit(f"console.log({', '.join(self.ex(a) for a in s.args)});", s.group)
            return
        pieces = []
        for k, a in enumerate(s.args):
            if is_list(a.ty):
                raise unsupported("printing a list without a newline", a)
            if k:
                pieces.append(["lit", " "])
            if isinstance(a, A.StrLit):
                pieces.append(["lit", a.value])
            else:
                pieces.append(["expr", self._paren(a, A.PREC["+"]) if a.ty == STR else f"String({self.ex(a)})"])
        merged = []
        for p in pieces:
            if p[0] == "lit" and merged and merged[-1][0] == "lit":
                merged[-1][1] += p[1]
            else:
                merged.append(p)
        text = " + ".join(A.quote(v) if kind == "lit" else v for kind, v in merged)
        if text:
            self.emit(f"process.stdout.write({text});", s.group)
        if end:
            self.emit(f"process.stdout.write({A.quote(end)});", s.group)

    def bool_text(self, v):
        return "true" if v else "false"

    def len_text(self, e):
        a = e.arg
        return f"{self.array(a) if isinstance(a, A.ArrayLit) else self._ex(a)[0]}.length"

    def str_compare(self, e):
        p = A.PREC[e.op]
        op = {"==": "===", "!=": "!=="}.get(e.op, e.op)
        return f"{self._paren(e.left, p + 1)} {op} {self._paren(e.right, p)}", p

    def concat(self, e):
        p = A.PREC["+"]
        return f"{self._paren(e.left, p + 1)} + {self._paren(e.right, p)}", p

    def binary(self, e, lt, rt, p):
        if isinstance(e, A.BinOp) and e.op == "/" and e.ty != FLOAT:
            return f"Math.floor({lt} / {rt})", 1
        return f"{lt} {({'==': '===', '!=': '!=='}).get(e.op, e.op)} {rt}", p

    def literal(self, e):
        return A.quote(e.value)

    def ctype_of(self, f, name):
        return jstype(f.vars[name])

    def rows(self, f):
        return [(self.safe(n), "parameter", self.ctype_of(f, n)) for n in f.params] + \
            [(self.safe(n), k, self.ctype_of(f, n)) for n, k in f.kinds.items() if k != "parameter"]

    def types(self):
        return []

    def symbols(self):
        out = []
        for f in self.info.all():
            rows = self.rows(f)
            scope = self.safe(f.name) if f.node is not None else "global"
            if f.node is not None:
                params = ", ".join(ct for _, k, ct in rows if k == "parameter")
                out.append({"name": self.safe(f.name), "kind": "function", "type": f"({params}) → {jstype(f.ret)}",
                            "scope": "global"})
            for name, kind, ct in rows:
                out.append({"name": name, "kind": kind, "type": ct, "scope": "loop" if kind == "loop var" else scope})
        return out
