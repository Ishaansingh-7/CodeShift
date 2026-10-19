from .. import ast as A
from ..linemap import ENTRY
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID
from .c import CBackend, Plan, unsupported
from .java import camel
from ..library import MAPOPS
from ..semantic import elem, is_list, is_map, is_set, mkey, mval, selem

KEYWORDS = {
    "break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough", "for", "func", "go", "goto",
    "if", "import", "interface", "map", "package", "range", "return", "select", "struct", "switch", "type", "var",
    "true", "false", "nil", "iota", "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16", "uint32",
    "uint64", "uintptr", "float32", "float64", "complex64", "complex128", "bool", "string", "rune", "byte", "error",
    "any", "len", "cap", "append", "make", "new", "copy", "delete", "panic", "recover", "print", "println", "close",
    "min", "max", "clear", "fmt", "main", "init",
}
class GoTypes(dict):
    def __missing__(self, key):
        if is_map(key):
            return f"map[{self[mkey(key)]}]{self[mval(key)]}"
        if is_set(key):
            return f"map[{self[selem(key)]}]struct{{}}"
        return "[]" + self[elem(key) or INT]


GT = GoTypes({INT: "int64", IDX: "int", BOOL: "bool", CHAR: "rune", STR: "string", ARR: "[]int64", VOID: "",
              FLOAT: "float64"})
CALLS = {
    "abs_i": "csAbs", "abs_f": "math.Abs", "pow_i": "csIpow", "pow_f": "math.Pow", "sqrt": "math.Sqrt",
    "floor": "math.Floor", "ceil": "math.Ceil", "trunc": "math.Trunc", "round_even": "math.RoundToEven",
    "round_away": "math.Round", "round_js": "csRoundJs", "sin": "math.Sin", "cos": "math.Cos", "tan": "math.Tan",
    "atan2": "math.Atan2", "log": "math.Log", "log10": "math.Log10", "log2": "math.Log2", "exp": "math.Exp",
    "hypot": "math.Hypot", "s2i": "csParseInt", "s2f": "csParseFloat", "b2s": "strconv.FormatBool",
    "b2s_py": "csBoolPy", "upper": "strings.ToUpper", "lower": "strings.ToLower", "trim": "strings.TrimSpace",
    "starts": "strings.HasPrefix", "ends": "strings.HasSuffix", "contains_s": "strings.Contains",
    "contains_c": "strings.ContainsRune", "replace_all": "strings.ReplaceAll", "is_digit": "csIsDigit",
    "is_alpha": "csIsAlpha", "is_space": "csIsSpace", "is_upper": "csIsUpper", "is_lower": "csIsLower",
    "cupper": "csCharUpper", "clower": "csCharLower",
}
HELPERS = {
    "csAbs": ([], """func csAbs(n int64) int64 {
    if n < 0 {
        return -n
    }
    return n
}"""),
    "csIpow": ([], """func csIpow(a, n int64) int64 {
    var r int64 = 1
    for i := int64(0); i < n; i++ {
        r *= a
    }
    return r
}"""),
    "csParseInt": (["strconv", "strings"], """func csParseInt(s string) int64 {
    n, err := strconv.ParseInt(strings.TrimSpace(s), 10, 64)
    if err != nil {
        panic(err)
    }
    return n
}"""),
    "csParseFloat": (["strconv", "strings"], """func csParseFloat(s string) float64 {
    x, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
    if err != nil {
        panic(err)
    }
    return x
}"""),
    "csRoundJs": (["math"], """func csRoundJs(x float64) float64 {
    return math.Floor(x + 0.5)
}"""),
    "csBoolPy": ([], """func csBoolPy(b bool) string {
    if b {
        return "True"
    }
    return "False"
}"""),
    "csIsDigit": ([], """func csIsDigit(c rune) bool {
    return c >= '0' && c <= '9'
}"""),
    "csIsAlpha": ([], """func csIsAlpha(c rune) bool {
    return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z'
}"""),
    "csIsSpace": ([], """func csIsSpace(c rune) bool {
    return c == ' ' || c == '\\t' || c == '\\n' || c == '\\r' || c == '\\v' || c == '\\f'
}"""),
    "csIsUpper": ([], """func csIsUpper(c rune) bool {
    return c >= 'A' && c <= 'Z'
}"""),
    "csIsLower": ([], """func csIsLower(c rune) bool {
    return c >= 'a' && c <= 'z'
}"""),
    "csCharUpper": ([], """func csCharUpper(c rune) rune {
    if c >= 'a' && c <= 'z' {
        return c - 32
    }
    return c
}"""),
    "csCharLower": ([], """func csCharLower(c rune) rune {
    if c >= 'A' && c <= 'Z' {
        return c + 32
    }
    return c
}"""),
    "csPop": ([], """func csPop[T any](xs *[]T) T {
    v := (*xs)[len(*xs)-1]
    *xs = (*xs)[:len(*xs)-1]
    return v
}"""),
    "csPopAt": (["slices"], """func csPopAt[T any](xs *[]T, i int64) T {
    v := (*xs)[i]
    *xs = slices.Delete(*xs, int(i), int(i)+1)
    return v
}"""),
    "csSum": ([], """func csSum[T int64 | float64](xs []T) T {
    var s T
    for _, x := range xs {
        s += x
    }
    return s
}"""),
    "csFill": ([], """func csFill[T any](n int64, v T) []T {
    xs := make([]T, n)
    for i := range xs {
        xs[i] = v
    }
    return xs
}"""),
    "csReadLine": (["bufio", "os", "strings"], """var csIn = bufio.NewReader(os.Stdin)

func csReadLine() string {
    s, _ := csIn.ReadString('\\n')
    return strings.TrimRight(s, "\\r\\n")
}"""),
    "csInts": (["strconv", "strings"], """func csInts(s string) []int64 {
    r := []int64{}
    for _, w := range strings.Fields(s) {
        v, _ := strconv.ParseInt(w, 10, 64)
        r = append(r, v)
    }
    return r
}"""),
    "csGetOr": ([], """func csGetOr[K comparable, V any](m map[K]V, k K, d V) V {
    if v, ok := m[k]; ok {
        return v
    }
    return d
}"""),
    "csHas": ([], """func csHas[K comparable, V any](m map[K]V, k K) bool {
    _, ok := m[k]
    return ok
}"""),
    "csGrid": ([], """func csGrid[T any](r, c int64, v T) [][]T {
    g := make([][]T, r)
    for i := range g {
        g[i] = csFill(c, v)
    }
    return g
}"""),
}
GP = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3, "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}
ESC = {"\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\x00"}


def quote(s, q='"'):
    return q + "".join(ESC.get(c, "\\" + c if c == q else c) for c in s) + q


def atom(text):
    return ("atom", text)


def call(fun, *args):
    return ("call", fun, list(args))


def binary(n):
    return n[0] == "bin"


def walk_binary(n):
    _, op, l, r = n
    p = GP[op]
    has4, has5, problem = p == 4, p == 5, 0
    for child, ok in ((l, binary(l) and GP[l[1]] >= p), (r, binary(r) and GP[r[1]] > p)):
        if ok:
            h4, h5, mp = walk_binary(child)
            has4, has5, problem = has4 or h4, has5 or h5, max(problem, mp)
    if r[0] == "un" and op + r[1] in ("--", "++"):
        problem = max(problem, 4)
    return has4, has5, problem


def cutoff(n, depth):
    has4, has5, problem = walk_binary(n)
    if problem:
        return problem + 1
    if has4 and has5:
        return 5 if depth == 1 else 4
    return 6 if depth == 1 else 4


def reduce(depth):
    return max(depth - 1, 1)


def x0(n, depth=1):
    return x1(n, 0, depth)


def operand(n, prec1, depth):
    if binary(n) and GP[n[1]] < prec1:
        return f"({x0(n, reduce(depth))})"
    return x1(n, prec1, depth)


def x1(n, prec1, depth):
    kind = n[0]
    if kind == "atom":
        return n[1]
    if kind == "bin":
        _, op, l, r = n
        p = GP[op]
        gap = " " if p < cutoff(n, depth) else ""
        left = operand(l, p, depth + (0 if binary(l) and GP[l[1]] == p else 1))
        return f"{left}{gap}{op}{gap}{operand(r, p + 1, depth + 1)}"
    if kind == "un":
        x = n[2]
        inner = f"({x0(x, reduce(depth))})" if binary(x) or x[0] == "un" else x1(x, 6, depth)
        return n[1] + inner
    if kind == "call":
        d = depth + 1 if len(n[2]) > 1 else depth
        return f"{n[1]}({', '.join(x0(a, d) for a in n[2])})"
    if kind == "index":
        target = f"({x0(n[1])})" if n[1][0] == "un" else x1(n[1], 7, 1)
        return f"{target}[{x0(n[2], depth + 1)}]"
    if kind == "slice":
        lo, hi = n[2], n[3]
        gap = " " if depth <= 1 and lo and hi and (binary(lo) or binary(hi)) else ""
        parts = [x0(lo, depth + 1) if lo else "", x0(hi, depth + 1) if hi else ""]
        return f"{x1(n[1], 7, 1)}[{parts[0]}{gap}:{gap}{parts[1]}]"
    if kind == "comp":
        return f"{n[1]}{{{', '.join(x0(a, 1) for a in n[2])}}}"
    raise ValueError(n)


class GoBackend(CBackend):
    lang = "go"
    KEYWORDS = KEYWORDS
    CSTR = False
    CONCAT = True
    ALLMAN = False

    def safe(self, name):
        n = camel(name)
        return n + "_" if n in KEYWORDS else n

    def ctype(self, t):
        return GT[t]

    def decl_text(self, t, name):
        return f"var {self.safe(name)} {GT[t]}"

    def length_params(self):
        return set()

    def builder_of(self, func):
        return None

    def find_builder(self, f):
        return None

    def plan(self, f):
        p = Plan(set(f.vars) | set(self.info.funcs))
        if f.node is not None:
            groups = []
            for n in f.params:
                t = ("*" if (f.name, n) in self.ptrs else "") + GT[f.vars[n]]
                if groups and groups[-1][1] == t:
                    groups[-1][0].append(self.safe(n))
                else:
                    groups.append(([self.safe(n)], t))
            p.params = [f"{', '.join(ns)} {t}" for ns, t in groups]
            p.ret = GT[f.ret]
            p.sig = f"func {self.safe(f.name)}({', '.join(p.params)}){' ' + p.ret if p.ret else ''}"
        for name, kind in f.kinds.items():
            if kind == "local":
                self.place(name, f.body, p.decl)
        return p

    def start(self, f):
        super().start(f)
        targets = set()
        for s in A.walk_all(f.body):
            if isinstance(s, (A.Assign, A.AugAssign)) and isinstance(s.target, A.Name):
                targets.add(id(s.target))
            elif isinstance(s, A.TupleAssign):
                targets |= {id(t) for t in s.targets if isinstance(t, A.Name)}
        self.reads = {n.id for n in A.walk_all(f.body) if isinstance(n, A.Name) and id(n) not in targets}

    def generate(self):
        for f in self.info.all():
            for name in [f.name, *f.vars]:
                if not name.isascii():
                    raise unsupported(f"non-ASCII name '{name}'", f.node or self.m)
        self.need_len = set()
        self.ptrs = self.grown()
        for f in self.info.all():
            self.plans[f] = self.plan(f)
        chunks = [self.function(self.info.funcs[fn.name]) for fn in self.m.functions]
        main = self.main()
        lines = [("package main", ENTRY), ("", None)]
        pkgs = sorted(self.includes)
        if len(pkgs) == 1:
            head = [(f'import "{pkgs[0]}"', self.includes[pkgs[0]])]
        elif pkgs:
            head = [("import (", ENTRY)] + [(f'    "{p}"', self.includes[p]) for p in pkgs] + [(")", ENTRY)]
        else:
            head = []
        if head:
            lines += head + [("", None)]
        for name, g in self.helpers.items():
            lines += [(x, g if x else None) for x in HELPERS[name][1].split("\n")] + [("", None)]
        for chunk in chunks:
            lines += chunk + [("", None)]
        self.entry = len(lines)
        lines += main
        self.entry_end = len(lines)
        self.prelude = [f'import "{p}"' for p in pkgs] + [HELPERS[n][1] for n in self.helpers]
        self.imports = [f'import "{p}"' for p in pkgs] + [f"func {n}() helper" for n in self.helpers]
        return lines

    def helper(self, name, g):
        for pkg in HELPERS[name][0]:
            self.include(pkg, g)
        if name == "csGrid":
            self.helper("csFill", g)
        self.helpers.setdefault(name, g)

    def typed(self, e, ty):
        x, have = self.lower(e)
        return call(ty, x) if have == "const" and ty in ("int64", "float64") else self.as_(e, ty)

    def ptr(self, e):
        return isinstance(e, A.Name) and (self.f.name, e.id) in self.ptrs

    def grown(self):
        ops = {"push", "pop", "pop_at", "insert", "remove_at"}
        need = set()
        changed = True
        while changed:
            changed = False
            for f in self.info.funcs.values():
                for n in A.walk_all(f.body):
                    hits = []
                    if isinstance(n, A.Intrinsic) and n.name in ops and isinstance(n.args[0], A.Name):
                        hits.append(n.args[0].id)
                    if isinstance(n, A.Call):
                        g = self.info.funcs[n.func]
                        hits += [a.id for a, q in zip(n.args, g.params) if isinstance(a, A.Name) and (g.name, q) in need]
                    for h in hits:
                        if h in f.params and (f.name, h) not in need:
                            need.add((f.name, h))
                            changed = True
        return need

    def place_of(self, e):
        return ("un", "*", atom(self.safe(e.id))) if self.ptr(e) else self.lower(e)[0]

    def key_type(self, t):
        return GT[mkey(t)] if is_map(t) else GT[selem(t)]

    def map_value(self, e):
        n, args, g = e.name, e.args, self.g
        if n in ("map_new", "set_new"):
            return ("comp", GT[e.ty], []), GT[e.ty]
        t = args[0].ty
        src = self.lower(args[0])[0]
        key = self.as_(args[1], self.key_type(t)) if len(args) > 1 else None
        if n == "map_get":
            return ("index", src, key), GT[e.ty]
        if n == "map_get_or":
            self.helper("csGetOr", g)
            return call("csGetOr", src, key, self.as_(args[2], GT[mval(t)])), GT[e.ty]
        if n in ("map_has", "set_has"):
            self.helper("csHas", g)
            return call("csHas", src, key), "bool"
        if n in ("map_len", "set_len"):
            return call("len", src), "int"
        if n in ("map_sorted_keys", "set_sorted"):
            self.include("maps", g)
            self.include("slices", g)
            return call("slices.Sorted", call("maps.Keys", src)), GT[e.ty]
        raise unsupported(f"library call @{n} in Go", e)

    def map_stmt(self, e, g):
        n, args = e.name, e.args
        t = args[0].ty
        src = self.lower(args[0])[0]
        key = self.as_(args[1], self.key_type(t))
        place = x0(("index", src, key))
        if n == "map_put":
            self.emit(f"{place} = {x0(self.as_(args[2], GT[mval(t)]))}", g)
        elif n == "map_incr":
            v = args[2]
            one = isinstance(v, A.IntLit) and v.value == 1
            self.emit(f"{place}++" if one else f"{place} += {x0(self.as_(v, GT[mval(t)]))}", g)
        elif n in ("map_del", "set_del"):
            self.emit(x0(call("delete", src, key)), g)
        elif n == "set_add":
            self.emit(f"{place} = struct{{}}{{}}", g)
        else:
            self.emit(x0(self.lower(e)[0]), g)

    def list_stmt(self, e, g):
        if e.name in MAPOPS:
            return self.map_stmt(e, g)
        n, args = e.name, e.args
        xs = args[0]
        target = x0(self.place_of(xs))
        el = GT[elem(xs.ty) or INT]
        if n == "push":
            self.emit(f"{target} = {x0(call('append', self.place_of(xs), self.as_(args[1], el)))}", g)
        elif n == "insert":
            self.include("slices", g)
            node = call("slices.Insert", self.place_of(xs), self.as_(args[1], "int"), self.as_(args[2], el))
            self.emit(f"{target} = {x0(node)}", g)
        elif n == "remove_at":
            self.include("slices", g)
            i = self.as_(args[1], "int")
            j = atom(str(args[1].value + 1)) if isinstance(args[1], A.IntLit) else ("bin", "+", i, atom("1"))
            self.emit(f"{target} = {x0(call('slices.Delete', self.place_of(xs), i, j))}", g)
        elif n in ("sort", "reverse", "sort_desc"):
            self.include("slices", g)
            fn = "slices.Reverse" if n == "reverse" else "slices.Sort"
            self.emit(x0(call(fn, self.place_of(xs))), g)
            if n == "sort_desc":
                self.emit(x0(call("slices.Reverse", self.place_of(xs))), g)
        else:
            self.emit(x0(self.lower(e)[0]), g)

    def list_value(self, e):
        n, args, g = e.name, e.args, self.g
        ret = GT[e.ty]
        xs = args[0] if args else None
        if n in ("pop", "pop_at"):
            name = "csPop" if n == "pop" else "csPopAt"
            self.helper(name, g)
            ref = atom(self.safe(xs.id)) if self.ptr(xs) else ("un", "&", self.lower(xs)[0])
            rest = [self.as_(args[1], "int64")] if n == "pop_at" else []
            return call(name, ref, *rest), ret
        if n in ("index_of", "contains_l", "sorted", "lcopy", "lmin", "lmax"):
            self.include("slices", g)
            src = self.place_of(xs)
            if n == "index_of":
                return call("slices.Index", src, self.as_(args[1], GT[elem(xs.ty) or INT])), "int"
            if n == "contains_l":
                return call("slices.Contains", src, self.as_(args[1], GT[elem(xs.ty) or INT])), ret
            if n == "sorted":
                return call("slices.Sorted", call("slices.Values", src)), ret
            return call({"lcopy": "slices.Clone", "lmin": "slices.Min", "lmax": "slices.Max"}[n], src), ret
        if n == "lslice":
            self.include("slices", g)
            a, b = args[1], args[2]
            lo = None if isinstance(a, A.IntLit) and a.value == 0 else self.lower(a)[0]
            hi = None if isinstance(b, A.Len) and A.same(b.arg, xs) else self.lower(b)[0]
            return call("slices.Clone", ("slice", self.place_of(xs), lo, hi)), ret
        if n == "sum":
            self.helper("csSum", g)
            return call("csSum", self.place_of(xs)), ret
        if n == "list_fill":
            self.helper("csFill", g)
            return call("csFill", self.as_(args[1], "int64"), self.typed(args[0], GT[elem(e.ty)])), ret
        if n == "grid":
            self.helper("csGrid", g)
            return call("csGrid", self.as_(args[0], "int64"), self.as_(args[1], "int64"),
                        self.typed(args[2], GT[elem(elem(e.ty))])), ret
        self.include("strings", g)
        if n == "split":
            return call("strings.Split", self.as_(args[0], "string"), self.as_(args[1], "string")), ret
        if n == "split_ws":
            return call("strings.Fields", self.as_(args[0], "string")), ret
        if n == "s2ints":
            self.helper("csInts", g)
            return call("csInts", self.as_(args[0], "string")), ret
        if n == "join":
            return call("strings.Join", self.lower(args[1])[0], self.as_(args[0], "string")), ret
        raise unsupported(f"library call @{n} in Go", e)

    def gspec(self, e):
        n = e.name
        if n == "fixed" and isinstance(e.args[1], A.IntLit):
            return f"%.{e.args[1].value}f", e.args[0], "float64"
        if n in ("rjust", "ljust") and isinstance(e.args[1], A.IntLit):
            flag, w, inner = "" if n == "rjust" else "-", e.args[1].value, e.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name == "fixed" and isinstance(inner.args[1], A.IntLit):
                return f"%{flag}{w}.{inner.args[1].value}f", inner.args[0], "float64"
            if isinstance(inner, A.Intrinsic) and inner.name == "i2s":
                return f"%{flag}{w}d", inner.args[0], "int64"
            return f"%{flag}{w}s", inner, "string"
        return None

    def library(self, e):
        n, g = e.name, self.g
        ret = GT[e.ty]
        args = e.args
        if n == "read_line":
            self.helper("csReadLine", g)
            return call("csReadLine"), "string"
        if n == "exit":
            self.include("os", g)
            return call("os.Exit", self.as_(args[0], "int")), ""
        if n == "fixed" and isinstance(args[1], A.IntLit):
            self.include("strconv", g)
            return call("strconv.FormatFloat", self.as_(args[0], "float64"), atom("'f'"), atom(str(args[1].value)),
                        atom("64")), "string"
        if n in ("rjust", "ljust", "fixed"):
            got = self.gspec(e)
            if got is None:
                raise unsupported("a format width or precision that is not a constant in Go", e)
            self.include("fmt", g)
            return call("fmt.Sprintf", atom(quote(got[0])), self.as_(got[1], got[2])), "string"
        if n in ("pi", "e"):
            self.include("math", g)
            return atom("math.Pi" if n == "pi" else "math.E"), ret
        if n == "i2s":
            self.include("strconv", g)
            return call("strconv.FormatInt", self.as_(args[0], "int64"), atom("10")), ret
        if n == "f2s":
            self.include("strconv", g)
            return call("strconv.FormatFloat", self.as_(args[0], "float64"), atom("'g'"), ("un", "-", atom("1")),
                        atom("64")), ret
        if n == "ord":
            return call("int64", self.as_(args[0], "rune")), ret
        if n == "chr":
            return call("rune", self.as_(args[0], "int64")), ret
        if n in ("min", "max"):
            return call(n, *[self.as_(a, ret) for a in args]), ret
        if n == "substr":
            s, a, b = args
            lo = None if isinstance(a, A.IntLit) and a.value == 0 else self.lower(a)[0]
            hi = None if isinstance(b, A.Len) and A.same(b.arg, s) else self.lower(b)[0]
            return ("slice", self.lower(s)[0], lo, hi), ret
        if n == "find":
            self.include("strings", g)
            return call("strings.Index", self.as_(args[0], "string"), self.as_(args[1], "string")), "int"
        if n == "repeat":
            self.include("strings", g)
            return call("strings.Repeat", self.as_(args[0], "string"), self.as_(args[1], "int")), ret
        from ..library import SIGS
        fn = CALLS[n]
        if fn.startswith("cs"):
            self.helper(fn, g)
        else:
            self.include(fn.split(".")[0], g)
        return call(fn, *[self.as_(a, GT[p]) for a, p in zip(args, SIGS[n][0])]), ret

    def main(self):
        self.start(self.info.main)
        self.line("func main()", ENTRY)
        self.open(ENTRY)
        self.block(self.info.main.body)
        self.close(ENTRY)
        return self.out

    def prototypes(self):
        return []

    def as_(self, e, want):
        if isinstance(e, A.CharLit) and want == "string":
            return atom(quote(e.value))
        if isinstance(e, A.StrLit) and len(e.value) == 1 and want == "rune":
            return atom(quote(e.value, "'"))
        n, have = self.lower(e)
        if want is None or have in ("const", want):
            return n
        if want == "string" and have in ("rune", "byte"):
            return call("string", n)
        if want == "rune" and have == "byte":
            return call("rune", n)
        if want in ("int64", "int") and have in ("int64", "int"):
            return call(want, n)
        return n

    def lower(self, e):
        if isinstance(e, (A.StrLit, A.CharLit)):
            self.ascii(e)
        if isinstance(e, (A.IntLit, A.FloatLit)):
            v = abs(e.value)
            n = atom(repr(v) if isinstance(e, A.FloatLit) else f"{v}.0" if e.ty == FLOAT else str(v))
            return (("un", "-", n) if e.value < 0 else n), "const"
        if isinstance(e, A.Intrinsic) and e.name in ("i2f", "f2i"):
            kind = "float64" if e.name == "i2f" else "int64"
            x, have = self.lower(e.args[0])
            if kind == "int64" and have == "const":
                self.include("math", self.g)
                x = call("math.Trunc", x)
            return call(kind, x), kind
        from ..library import LISTOPS
        if isinstance(e, A.Intrinsic) and e.name in MAPOPS:
            return self.map_value(e)
        if isinstance(e, A.Intrinsic) and e.name in LISTOPS:
            return self.list_value(e)
        if isinstance(e, A.Intrinsic):
            return self.library(e)
        if isinstance(e, A.BoolLit):
            return atom("true" if e.value else "false"), "const"
        if isinstance(e, A.StrLit):
            return atom(quote(e.value)), "const"
        if isinstance(e, A.CharLit):
            return atom(quote(e.value, "'")), "const"
        if isinstance(e, A.Name):
            if self.ptr(e):
                return ("un", "*", atom(self.safe(e.id))), GT[self.f.vars[e.id]]
            return atom(self.subst.get(e.id) or self.safe(e.id)), GT[self.f.vars[e.id]]
        if isinstance(e, A.ArrayLit):
            el = GT[elem(e.ty) or INT]
            return ("comp", GT[e.ty], [self.as_(x, el) for x in e.items]), GT[e.ty]
        if isinstance(e, A.Index):
            n = ("index", self.lower(e.target)[0], self.lower(e.index)[0])
            return n, "byte" if e.target.ty == STR else GT[e.ty]
        if isinstance(e, A.Len):
            return call("len", self.lower(e.arg)[0]), "int"
        if isinstance(e, A.Call):
            g = self.info.funcs[e.func]
            args = []
            for a, p in zip(e.args, g.params):
                if (g.name, p) in self.ptrs:
                    args.append(atom(self.safe(a.id)) if self.ptr(a) else ("un", "&", self.lower(a)[0]))
                else:
                    args.append(self.as_(a, GT[g.vars[p]]))
            return call(self.safe(e.func), *args), GT[g.ret]
        if isinstance(e, A.UnaryOp):
            x, t = self.lower(e.operand)
            if e.op == "!" and e.operand.ty in (INT, IDX):
                return ("bin", "==", x, atom("0")), "bool"
            return ("un", e.op, x), "bool" if e.op == "!" else t
        if isinstance(e, A.BoolOp):
            return ("bin", e.op, self.cond(e.left), self.cond(e.right)), "bool"
        if isinstance(e, A.Compare):
            return ("bin", e.op, *self.pair(e.left, e.right)), "bool"
        if e.ty in (STR, CHAR):
            return ("bin", "+", self.as_(e.left, "string"), self.as_(e.right, "string")), "string"
        want = GT[e.ty]
        l, lt = self.lower(e.left)
        r, rt = self.lower(e.right)
        n = ("bin", e.op, self.as_(e.left, want), self.as_(e.right, want))
        return n, "const" if lt == rt == "const" else want

    def pair(self, l, r):
        lt, rt = self.lower(l)[1], self.lower(r)[1]
        if lt == rt:
            return self.lower(l)[0], self.lower(r)[0]
        if {lt, rt} == {"int", "int64"}:
            return self.as_(l, "int64"), self.as_(r, "int64")
        if CHAR in (l.ty, r.ty):
            return self.as_(l, "rune"), self.as_(r, "rune")
        return self.lower(l)[0], self.lower(r)[0]

    def cond(self, e):
        n = self.lower(e)[0]
        return ("bin", "!=", n, atom("0")) if e.ty in (INT, IDX) else n

    def ex(self, e):
        return x0(self.lower(e)[0])

    def unused(self, name, g):
        if name not in self.reads:
            self.emit(f"_ = {self.safe(name)}", g)

    def hoist(self, v, g):
        self.emit(self.decl_text(self.f.vars[v], v), g)
        self.unused(v, g)

    def declare(self, names, values, g):
        tys = [GT[self.f.vars[n]] for n in names]
        consts = [self.lower(v)[1] == "const" for v in values]
        lhs = ", ".join(map(self.safe, names))
        if len(set(tys)) == 1 and tys[0] == "int64" and any(consts):
            self.emit(f"var {lhs} int64 = {', '.join(x0(self.as_(v, 'int64')) for v in values)}", g)
        else:
            depth = 2 if len(names) > 1 else 1
            vals = [call("int64", self.lower(v)[0]) if c and t == "int64" else self.as_(v, t)
                    for v, t, c in zip(values, tys, consts)]
            self.emit(f"{lhs} := {', '.join(x0(v, depth) for v in vals)}", g)
        self.declared |= set(names)
        for n in names:
            self.unused(n, g)

    def target_type(self, t):
        return GT[self.f.vars[t.id]] if isinstance(t, A.Name) else "int64"

    def stmt(self, s):
        g = self.g = s.group
        if isinstance(s, A.Assign):
            t = s.target
            if isinstance(t, A.Name) and self.p.decl.get(t.id) == ("inline", s) and t.id not in self.declared:
                self.declare([t.id], [s.value], g)
            else:
                self.emit(f"{self.ex(t)} = {x0(self.as_(s.value, self.target_type(t)))}", g)
        elif isinstance(s, A.AugAssign):
            self.emit(f"{self.ex(s.target)} {s.op}= {x0(self.as_(s.value, self.target_type(s.target)))}", g)
        elif isinstance(s, A.TupleAssign):
            names = [t.id for t in s.targets if isinstance(t, A.Name)]
            new = [n for n in names if self.p.decl.get(n) == ("inline", s) and n not in self.declared]
            if new and len(new) == len(s.targets):
                self.declare(names, s.values, g)
                return
            for n in new:
                self.declared.add(n)
                self.hoist(n, g)
            lhs = ", ".join(x0(self.lower(t)[0], 2) for t in s.targets)
            rhs = ", ".join(x0(self.as_(v, self.target_type(t)), 2) for t, v in zip(s.targets, s.values))
            self.emit(f"{lhs} = {rhs}", g)
        elif isinstance(s, A.Swap):
            a, b = x0(self.lower(s.a)[0], 2), x0(self.lower(s.b)[0], 2)
            self.emit(f"{a}, {b} = {b}, {a}", g)
        elif isinstance(s, A.If):
            self.emit(f"if {x0(self.cond(s.test))}", g)
            self.body(s.body, g)
            o = s.orelse
            while len(o) == 1 and isinstance(o[0], A.If):
                g = self.g = o[0].group
                self.else_line(f"else if {x0(self.cond(o[0].test))}", g)
                self.body(o[0].body, g)
                o = o[0].orelse
            if o:
                self.else_line("else", g)
                self.body(o, g)
        elif isinstance(s, A.While):
            forever = isinstance(s.test, A.BoolLit) and s.test.value
            self.emit("for" if forever else f"for {x0(self.cond(s.test))}", g)
            self.body(s.body, g)
        elif isinstance(s, A.For):
            self.for_(s)
        elif isinstance(s, A.Return):
            self.emit("return" if s.value is None else f"return {x0(self.as_(s.value, GT[self.f.ret]))}", g)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic):
            self.list_stmt(s.expr, g)
        elif isinstance(s, A.ExprStmt):
            self.emit(self.ex(s.expr), g)
        elif isinstance(s, A.Break):
            self.emit("break", g)
        elif isinstance(s, A.Continue):
            self.emit("continue", g)
        elif isinstance(s, A.Print):
            self.include("fmt", g)
            args = [self.as_(a, "string" if a.ty == CHAR else None) for a in s.args]
            ending = getattr(s, "ending", "\n")
            if ending == "\n":
                self.emit(x0(call("fmt.Println", *args)), g)
                return
            spaced = []
            for k, a in enumerate(args):
                spaced += [atom('" "'), a] if k else [a]
            if spaced:
                self.emit(x0(call("fmt.Print", *spaced)), g)
            if ending:
                self.emit(x0(call("fmt.Print", atom(quote(ending)))), g)

    def step(self, v, k):
        return f"{v}++" if k == 1 else f"{v}--" if k == -1 else f"{v} += {k}" if k > 0 else f"{v} -= {-k}"

    def while_for(self, a, w):
        v, inc, g = a.target.id, w.body[-1], w.group
        self.merges += [(g, a.group), (g, inc.group)]
        self.g = g
        t = GT[self.f.vars[v]]
        init = self.lower(a.value)
        start = call("int64", init[0]) if init[1] == "const" and t == "int64" else self.as_(a.value, t)
        k = inc.value.value * (1 if inc.op == "+" else -1)
        name = self.safe(v)
        self.emit(f"for {name} := {x0(start)}; {x0(self.cond(w.test))}; {self.step(name, k)}", g)
        self.declared.add(v)
        self.body(w.body[:-1], g)

    def for_(self, s):
        g = s.group
        if s.kind == "each" and is_map(s.iter.ty):
            self.include("maps", g)
            self.include("slices", g)
            self.note("order", "Go maps have no order, so the Go version visits keys in sorted order; the source visits "
                               "them in insertion order.")
            it = x0(call("slices.Sorted", call("maps.Keys", self.lower(s.iter)[0])))
            self.emit(f"for _, {self.safe(s.var)} := range {it}" if s.var in self.reads else f"for range {it}", g)
        elif s.kind == "each":
            it = x0(self.lower(s.iter)[0])
            self.emit(f"for _, {self.safe(s.var)} := range {it}" if s.var in self.reads else f"for range {it}", g)
        else:
            v, k = self.safe(s.var), s.step.value
            stop = self.as_(s.stop, "int")
            changed = {n for x in A.walk_all(s.body) if isinstance(x, A.Stmt) for n in A.names(x) if A.writes(x, n)}
            if A.names(s.stop) & changed or any(isinstance(x, (A.Call, A.Index)) for x in A.walk(s.stop)):
                end = self.temp("end")
                self.emit(f"{end} := {x0(stop)}", g)
                stop = atom(end)
            test = ("bin", "<" if k > 0 else ">", atom(v), stop)
            self.emit(f"for {v} := {x0(self.as_(s.start, 'int'))}; {x0(test)}; {self.step(v, k)}", g)
        self.open(g)
        self.scopes[-1].add(s.var)
        self.block(s.body)
        self.close(g)

    def ctype_of(self, f, name):
        return GT[f.vars[name]]

    def rows(self, f):
        return [(self.safe(n), "parameter", self.ctype_of(f, n)) for n in f.params] + \
            [(self.safe(n), k, self.ctype_of(f, n)) for n, k in f.kinds.items() if k != "parameter"]

    def types(self):
        notes = []
        for f in self.info.all():
            by = {}
            for name, _, ct in self.rows(f):
                by.setdefault(ct, []).append(name)
            notes += [f"{', '.join(ns)}: {ct}" for ct, ns in by.items()]
            if f.node is not None:
                notes.append(f"{self.safe(f.name)} → {GT[f.ret] or 'no result'}")
        return list(dict.fromkeys(notes))

    def symbols(self):
        out = []
        for f in self.info.all():
            rows = self.rows(f)
            scope = self.safe(f.name) if f.node is not None else "main"
            if f.node is not None:
                params = ", ".join(ct for _, k, ct in rows if k == "parameter")
                ret = GT[f.ret] or "()"
                out.append({"name": self.safe(f.name), "kind": "function", "type": f"({params}) → {ret}",
                            "scope": "package"})
            for name, kind, ct in rows:
                out.append({"name": name, "kind": kind, "type": ct, "scope": "loop" if kind == "loop var" else scope})
        return out
