from dataclasses import dataclass

from .. import ast as A
from ..errors import CompileError
from ..linemap import ENTRY
from ..library import LISTOPS, MAPOPS
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID, elem, is_list, is_map, is_set, mkey, mval, selem
from . import clists, cmaps
from .python import snake

KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern",
    "float", "for", "goto", "if", "inline", "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while", "main",
    "printf", "strlen", "strcmp", "bool", "true", "false", "NULL",
}
CTYPE = {INT: "long long", IDX: "int", BOOL: "int", CHAR: "char", VOID: "void", FLOAT: "double"}
FMT = {INT: "%lld", IDX: "%d", BOOL: "%d", CHAR: "%c", STR: "%s"}
HEADERS = ["stdarg.h", "stdio.h", "stdlib.h", "string.h", "ctype.h", "math.h"]
HELPERS = {
    "cs_read_line": (["stdio.h", "stdlib.h", "string.h"], """static const char *cs_read_line(void)
{
    char buf[4096];
    if (fgets(buf, sizeof buf, stdin) == NULL)
    {
        buf[0] = '\\0';
    }
    buf[strcspn(buf, "\\r\\n")] = '\\0';
    char *s = malloc(strlen(buf) + 1);
    strcpy(s, buf);
    return s;
}"""),
    "cs_format": (["stdarg.h", "stdio.h", "stdlib.h"], """static const char *cs_format(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    char *s = malloc(n + 1);
    va_start(ap, fmt);
    vsnprintf(s, n + 1, fmt, ap);
    va_end(ap);
    return s;
}"""),
    "cs_f2s": (["stdio.h", "stdlib.h", "string.h"], """static const char *cs_f2s(double x)
{
    static char buf[8][48];
    static int k = 0;
    char *s = buf[k++ % 8];
    double a = x < 0 ? -x : x;
    int sci = a != 0 && (a < 1e-4 || a >= 1e16);
    for (int p = 0; p <= 25; p++)
    {
        snprintf(s, 48, sci ? "%.*e" : "%.*f", p, x);
        if (strtod(s, NULL) == x)
        {
            break;
        }
    }
    if (strspn(s, "-0123456789") == strlen(s))
    {
        strcat(s, ".0");
    }
    return s;
}"""),
    "CS_PI": ([], "#define CS_PI 3.14159265358979323846"),
    "CS_E": ([], "#define CS_E 2.71828182845904523536"),
    "cs_i2s": (["stdio.h"], """static const char *cs_i2s(long long n)
{
    static char buf[8][24];
    static int k = 0;
    char *s = buf[k++ % 8];
    snprintf(s, 24, "%lld", n);
    return s;
}"""),
    "cs_ipow": ([], """static long long cs_ipow(long long a, long long n)
{
    long long r = 1;
    for (long long i = 0; i < n; i++)
    {
        r *= a;
    }
    return r;
}"""),
    "cs_imin": ([], """static long long cs_imin(long long a, long long b)
{
    return a < b ? a : b;
}"""),
    "cs_imax": ([], """static long long cs_imax(long long a, long long b)
{
    return a > b ? a : b;
}"""),
    "cs_round_js": (["math.h"], """static double cs_round_js(double x)
{
    return floor(x + 0.5);
}"""),
    "cs_concat": (["stdlib.h", "string.h"], """static const char *cs_concat(const char *a, const char *b)
{
    char *s = malloc(strlen(a) + strlen(b) + 1);
    strcpy(s, a);
    strcat(s, b);
    return s;
}"""),
    "cs_append": (["stdlib.h", "string.h"], """static const char *cs_append(const char *a, const char *b)
{
    char *s = malloc(strlen(a) + strlen(b) + 1);
    strcpy(s, a);
    strcat(s, b);
    return s;
}"""),
    "cs_c2s": (["stdlib.h"], """static const char *cs_c2s(char c)
{
    char *s = malloc(2);
    s[0] = c;
    s[1] = '\\0';
    return s;
}"""),
    "cs_substr": (["stdlib.h", "string.h"], """static const char *cs_substr(const char *s, long long a, long long b)
{
    long long n = (long long)strlen(s);
    a = a < 0 ? 0 : a > n ? n : a;
    b = b < a ? a : b > n ? n : b;
    char *out = malloc(b - a + 1);
    memcpy(out, s + a, b - a);
    out[b - a] = '\\0';
    return out;
}"""),
    "cs_upper": (["ctype.h", "stdlib.h", "string.h"], """static const char *cs_upper(const char *s)
{
    size_t n = strlen(s);
    char *out = malloc(n + 1);
    for (size_t i = 0; i <= n; i++)
    {
        out[i] = (char)toupper((unsigned char)s[i]);
    }
    return out;
}"""),
    "cs_lower": (["ctype.h", "stdlib.h", "string.h"], """static const char *cs_lower(const char *s)
{
    size_t n = strlen(s);
    char *out = malloc(n + 1);
    for (size_t i = 0; i <= n; i++)
    {
        out[i] = (char)tolower((unsigned char)s[i]);
    }
    return out;
}"""),
    "cs_trim": (["ctype.h", "stdlib.h", "string.h"], """static const char *cs_trim(const char *s)
{
    while (isspace((unsigned char)*s))
    {
        s++;
    }
    size_t n = strlen(s);
    while (n > 0 && isspace((unsigned char)s[n - 1]))
    {
        n--;
    }
    char *out = malloc(n + 1);
    memcpy(out, s, n);
    out[n] = '\\0';
    return out;
}"""),
    "cs_starts": (["string.h"], """static int cs_starts(const char *s, const char *t)
{
    return strncmp(s, t, strlen(t)) == 0;
}"""),
    "cs_ends": (["string.h"], """static int cs_ends(const char *s, const char *t)
{
    size_t n = strlen(s);
    size_t m = strlen(t);
    return n >= m && strcmp(s + n - m, t) == 0;
}"""),
    "cs_find": (["string.h"], """static long long cs_find(const char *s, const char *t)
{
    const char *p = strstr(s, t);
    return p ? (long long)(p - s) : -1;
}"""),
    "cs_replace": (["stdlib.h", "string.h"], """static const char *cs_replace(const char *s, const char *a, const char *b)
{
    size_t na = strlen(a);
    size_t nb = strlen(b);
    size_t n = 0;
    if (na == 0)
    {
        return s;
    }
    for (const char *p = strstr(s, a); p; p = strstr(p + na, a))
    {
        n++;
    }
    char *out = malloc(strlen(s) + n * nb + 1);
    char *o = out;
    for (const char *p = strstr(s, a); p; p = strstr(s, a))
    {
        memcpy(o, s, p - s);
        o += p - s;
        memcpy(o, b, nb);
        o += nb;
        s = p + na;
    }
    strcpy(o, s);
    return out;
}"""),
    "cs_repeat": (["stdlib.h", "string.h"], """static const char *cs_repeat(const char *s, long long n)
{
    char *out = malloc(strlen(s) * (n > 0 ? n : 0) + 1);
    out[0] = '\\0';
    for (long long i = 0; i < n; i++)
    {
        strcat(out, s);
    }
    return out;
}"""),
}
ORDER = ["CS_PI", "CS_E", "cs_f2s", "cs_i2s", "cs_ipow", "cs_imin", "cs_imax", "cs_round_js", "cs_concat", "cs_append", "cs_c2s",
         "cs_substr", "cs_upper", "cs_lower", "cs_trim", "cs_starts", "cs_ends", "cs_find", "cs_replace", "cs_repeat",
         "cs_read_line", "cs_format"]
STRINGS = {"substr": "cs_substr", "upper": "cs_upper", "lower": "cs_lower", "trim": "cs_trim", "starts": "cs_starts",
           "ends": "cs_ends", "find": "cs_find", "replace_all": "cs_replace", "repeat": "cs_repeat"}
CHECKS = {"is_digit": "isdigit", "is_alpha": "isalpha", "is_space": "isspace", "is_upper": "isupper",
          "is_lower": "islower", "cupper": "toupper", "clower": "tolower"}
MATH_H = {
    "abs_f": "fabs", "pow_f": "pow", "sqrt": "sqrt", "floor": "floor", "ceil": "ceil", "trunc": "trunc",
    "round_even": "rint", "round_away": "round", "sin": "sin", "cos": "cos", "tan": "tan", "atan2": "atan2",
    "log": "log", "log10": "log10", "log2": "log2", "exp": "exp", "hypot": "hypot",
}
CALLS = {"abs_i": ("llabs", "stdlib.h"), "pow_i": ("cs_ipow", None), "round_js": ("cs_round_js", None),
         "i2s": ("cs_i2s", None), "f2s": ("cs_f2s", None)}


def concat_parts(e):
    if isinstance(e, A.BinOp) and e.op == "+" and e.ty in (STR, CHAR):
        return concat_parts(e.left) + concat_parts(e.right)
    return [e]


def unsupported(what, node):
    return CompileError("codegen", f"Unsupported: {what}", node.line, node.col)


def safe(name):
    name = snake(name)
    return name + "_" if name in KEYWORDS else name


def is_arith(e):
    return isinstance(e, A.BinOp) and e.op in ("+", "-", "*")


def written(f, name):
    return any(A.writes(s, name) for s in A.walk_all(f.body) if isinstance(s, A.Stmt))


def constant(e):
    return e.ty == INT and all(isinstance(n, A.IntLit) or isinstance(n, (A.BinOp, A.UnaryOp)) and n.op in "+-*/%"
                               for n in A.walk(e))


def values(e, out):
    if isinstance(e, A.IntLit):
        v = e.value
    elif isinstance(e, A.UnaryOp):
        v = -values(e.operand, out)
    else:
        l, r = values(e.left, out), values(e.right, out)
        v = l + r if e.op == "+" else l - r if e.op == "-" else l * r if e.op == "*" else 0 if r == 0             else abs(l) // abs(r) * (1 if (l < 0) == (r < 0) else -1) if e.op == "/" else l - r * int(l / r)
    out.append(v)
    return v


def leftmost(e):
    while not isinstance(e, A.IntLit):
        e = e.operand if isinstance(e, A.UnaryOp) else e.left
    return e


def continues(stmts):
    for s in stmts:
        if isinstance(s, A.Continue):
            yield s
        elif not isinstance(s, (A.While, A.For)):
            for b in A.blocks(s):
                yield from continues(b)


def char_lit(e):
    return A.CharLit(e.value, ty=CHAR) if isinstance(e, A.StrLit) and len(e.value) == 1 else e


@dataclass(eq=False)
class Builder:
    out: str
    init: object
    loop: object
    update: object
    mode: str
    src: str
    ret: object


class Plan:
    def __init__(self, taken):
        self.taken = taken
        self.params = []
        self.ret = "int"
        self.sig = ""
        self.lens = {}
        self.strlen_at = {}
        self.builder = None
        self.decl = {}


class CBackend:
    lang = "c"
    KEYWORDS = KEYWORDS
    CAST = "(long long)"
    CSTR = True
    CONCAT = True
    INDENT = "    "
    ALLMAN = True
    END = ";"
    LONG = "LL"
    BIG = False

    def safe(self, name):
        return safe(name)

    def ctype(self, t):
        if is_map(t) or is_set(t):
            k = cmaps.map_kind(t) if is_map(t) else cmaps.set_kind(t)
            if k is None:
                raise unsupported("a dict or set of this type in C", self.m)
            name = f"cs_{'map' if is_map(t) else 'set'}_{k}"
            self.helper(name, self.g)
            return name + " *"
        if is_list(t) and self.dyn:
            k = self.kind(t, self.m)
            self.helper(f"cs_list_{k}", self.g)
            return f"cs_list_{k} *"
        return CTYPE[t]

    def __init__(self, module, info):
        self.m = module
        self.info = info
        self.merges = []
        self.includes = {}
        self.helpers = {}
        self.raw = set()
        self.notes = {}
        self.plans = {}
        self.wide = set()
        self.dyn = False
        self.g = None

    def dynamic(self):
        for f in self.info.all():
            if is_list(f.ret):
                return True
            for name, t in f.vars.items():
                if is_list(t) and t != ARR:
                    return True
                if t == ARR and f.kinds[name] != "parameter":
                    ws = [s for s in A.walk_all(f.body) if isinstance(s, A.Stmt) and A.writes(s, name)]
                    if len(ws) != 1 or not isinstance(ws[0], A.Assign) or not isinstance(ws[0].value, A.ArrayLit):
                        return True
            for n in A.walk_all(f.body):
                if isinstance(n, A.Intrinsic) and (n.name in LISTOPS or n.name in MAPOPS):
                    return True
                if isinstance(n, A.Print) and len(n.args) > 1 and any(is_list(a.ty) for a in n.args):
                    return True
        return False

    def generate(self):
        for f in self.info.all():
            for name in [f.name, *f.vars]:
                if not name.isascii():
                    raise unsupported(f"non-ASCII name '{name}'", f.node or self.m)
        self.dyn = self.dynamic()
        if self.dyn:
            self.check_lists()
        self.need_len = set() if self.dyn else self.length_params()
        for f in self.info.all():
            self.g = f.node.group if f.node is not None else ENTRY
            self.plans[f] = self.plan(f)
        chunks = [self.function(self.info.funcs[fn.name]) for fn in self.m.functions]
        chunks.append(self.main())
        head = [(f"#include <{h}>", self.includes[h]) for h in HEADERS if h in self.includes]
        names = sorted(self.helpers, key=lambda n: (0, ORDER.index(n), 0) if n in ORDER else cmaps.rank(n)
                       if cmaps.known(n) else clists.rank(n))
        defines = [(HELPERS[n][1], self.helpers[n]) for n in names if n.startswith("CS_")]
        helpers = ([defines] if defines else []) + [[(x, self.helpers[n]) for x in self.helper_text(n).split("\n")]
                                                   for n in names if not n.startswith("CS_")]
        lines = []
        for chunk in [c for c in (head, *helpers, self.prototypes()) if c] + chunks:
            if lines:
                lines.append(("", None))
            lines += chunk
        self.entry = len(lines) - len(chunks[-1])
        self.prelude = [text for text, _ in head] + [self.helper_text(n) for n in names]
        self.imports = [text for text, _ in head] + [HELPERS[n][1] if n.startswith("CS_") else f"typedef {n}"
                                                     if n.startswith(("cs_list_", "cs_map_", "cs_set_"))
                                                     else f"static {n}() helper" for n in names]
        return lines

    def helper_text(self, n):
        return HELPERS[n][1] if n in HELPERS else self.runtime(n)[2]

    def runtime(self, name):
        return cmaps.helper(name) if cmaps.known(name) else clists.helper(name)

    def helper(self, name, g):
        if name in self.helpers:
            return
        heads, deps = (HELPERS[name][0], []) if name in HELPERS else self.runtime(name)[:2]
        for h in heads:
            self.include(h, g)
        for d in deps:
            self.helper(d, g)
        self.helpers.setdefault(name, g)

    def check_lists(self):
        for f in self.info.all():
            if is_list(f.ret) and f.ret not in clists.KIND:
                ret = next(s for s in A.walk_all(f.body) if isinstance(s, A.Return) and s.value is not None)
                raise unsupported("returning a list of this type in C", ret)
            for name, t in f.vars.items():
                bad = is_map(t) and cmaps.map_kind(t) is None or is_set(t) and cmaps.set_kind(t) is None
                if bad:
                    at = next((s for s in A.walk_all(f.body) if isinstance(s, A.Stmt) and A.writes(s, name)), None)
                    raise unsupported(f"a {'dict' if is_map(t) else 'set'} of this type in C ('{name}')",
                                      at or f.node or self.m)
                if is_list(t) and t not in clists.KIND:
                    at = next((s for s in A.walk_all(f.body) if isinstance(s, A.Stmt) and A.writes(s, name)), None)
                    raise unsupported(f"a list of this type in C ('{name}')", at or f.node or self.m)

    def kind(self, t, node):
        if t not in clists.KIND:
            raise unsupported("a list of this type in C", node)
        return clists.KIND[t]

    def list_fn(self, op, k, node):
        if not clists.supports(op, k):
            raise unsupported(f"this list operation on a list of {'lists' if k == 'grid' else 'these values'} in C", node)
        name = f"cs_{op}_{k}"
        self.helper(name, self.g)
        return name

    def new_list(self, e):
        k = self.kind(e.ty, e)
        if not e.items:
            return f"{self.list_fn('new', k, e)}()"
        el = elem(e.ty)
        items = ", ".join(self.ex_as(x, el) for x in e.items)
        return f"{self.list_fn('from', k, e)}({len(e.items)}, ({clists.ELEM[k]}[]){{{items}}})"

    def cspec(self, e):
        if not isinstance(e, A.Intrinsic):
            return None
        n = e.name
        if n == "fixed" and isinstance(e.args[1], A.IntLit):
            return f"%.{e.args[1].value}f", [self.ex(e.args[0])]
        if n in ("rjust", "ljust") and isinstance(e.args[1], A.IntLit):
            flag, w, inner = "" if n == "rjust" else "-", e.args[1].value, e.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name == "fixed" and isinstance(inner.args[1], A.IntLit):
                return f"%{flag}{w}.{inner.args[1].value}f", [self.ex(inner.args[0])]
            if isinstance(inner, A.Intrinsic) and inner.name == "i2s":
                return f"%{flag}{w}lld", [self.wide_int(inner.args[0])]
            return f"%{flag}{w}s", [self.as_text(inner)]
        return None

    def wide_int(self, e):
        return self._ex(e, cast=e.ty == IDX)[0]

    def formatting(self, e):
        return isinstance(e, A.Intrinsic) and e.name in ("fixed", "rjust", "ljust") or isinstance(e, A.BinOp) \
            and e.op == "+" and e.ty == STR and any(self.cspec(x) for x in concat_parts(e))

    def layout(self, e):
        fmt, vals = "", []
        for x in concat_parts(e):
            got = self.cspec(x)
            if isinstance(x, (A.StrLit, A.CharLit)):
                self.ascii(x)
                fmt += x.value.replace("%", "%%")
            elif got:
                fmt += got[0]
                vals += got[1]
            elif isinstance(x, A.Intrinsic) and x.name == "i2s":
                fmt += "%lld"
                vals.append(self.wide_int(x.args[0]))
            elif x.ty == CHAR:
                fmt += "%c"
                vals.append(self.ex(x))
            else:
                fmt += "%s"
                vals.append(self.as_text(x))
        return fmt, vals

    def mapop(self, e):
        n, args, g = e.name, e.args, self.g
        if n in ("map_new", "set_new"):
            k = cmaps.map_kind(e.ty) if n == "map_new" else cmaps.set_kind(e.ty)
            fn = f"cs_{'m' if n == 'map_new' else 's'}new_{k}"
            self.helper(fn, g)
            return f"{fn}()", 1
        t = args[0].ty
        x = self.ex(args[0])
        if n in ("map_len", "set_len"):
            return f"{x}->len", 1
        if is_map(t):
            kt, vt = mkey(t), mval(t)
            op = {"map_get": "get", "map_put": "put", "map_get_or": "get_or", "map_has": "has", "map_del": "del",
                  "map_incr": "incr", "map_sorted_keys": "keys"}[n]
            fn = f"cs_m{op}_{cmaps.map_kind(t)}"
            vals = [x] + [self.ex_as(a, w) for a, w in zip(args[1:], (kt, vt))]
        else:
            op = {"set_add": "add", "set_has": "has", "set_del": "del", "set_sorted": "items"}[n]
            fn = f"cs_s{op}_{cmaps.set_kind(t)}"
            vals = [x] + [self.ex_as(a, selem(t)) for a in args[1:]]
        self.helper(fn, g)
        return f"{fn}({', '.join(vals)})", 1

    def listop(self, e):
        n, args, g = e.name, e.args, self.g
        if n in ("split", "split_ws", "join", "grid", "s2ints"):
            if n == "grid" and e.ty != "list<arr>":
                raise unsupported("a grid of this type in C", e)
            name = "cs_" + n
            self.helper(name, g)
            vals = [self.ex_as(a, INT) for a in args] if n == "grid" else [self.as_text(args[0]), self.ex(args[1])] \
                if n == "join" else [self.as_text(a) for a in args]
            return f"{name}({', '.join(vals)})", 1
        if n == "list_fill":
            fn = self.list_fn("fill", self.kind(e.ty, e), e)
            return f"{fn}({self.ex_as(args[1], INT)}, {self.ex_as(args[0], elem(e.ty))})", 1
        xs = args[0]
        k, el = self.kind(xs.ty, e), elem(xs.ty)
        op = {"lcopy": "slice", "lslice": "slice", "contains_l": "contains", "remove_at": "pop_at", "lmin": "min",
              "lmax": "max"}.get(n, n)
        fn = self.list_fn(op, k, e)
        x = self.ex(xs)
        rest = []
        if n == "lcopy":
            rest = ["0", f"{x}->len"]
        elif n == "lslice":
            rest = [self.ex_as(args[1], INT), self.ex_as(args[2], INT)]
        elif n in ("push", "index_of", "contains_l"):
            rest = [self.ex_as(args[1], el)]
        elif n == "insert":
            rest = [self.ex_as(args[1], INT), self.ex_as(args[2], el)]
        elif n in ("pop_at", "remove_at"):
            rest = [self.ex_as(args[1], INT)]
        return f"{fn}({', '.join([x, *rest])})", 1

    def length_params(self):
        need = set()
        arrays = [(f, p) for f in self.info.funcs.values() for p in f.params if f.vars[p] == ARR]

        def uses(f, p):
            for n in A.walk_all(f.body):
                if isinstance(n, A.Len) and isinstance(n.arg, A.Name) and n.arg.id == p \
                        or isinstance(n, A.For) and isinstance(n.iter, A.Name) and n.iter.id == p \
                        or isinstance(n, A.Print) and any(isinstance(a, A.Name) and a.id == p for a in n.args):
                    return True
                if isinstance(n, A.Call):
                    g = self.info.funcs[n.func]
                    if any(isinstance(a, A.Name) and a.id == p and (g.name, q) in need for a, q in zip(n.args, g.params)):
                        return True
            return False

        changed = True
        while changed:
            changed = False
            for f, p in arrays:
                if (f.name, p) not in need and uses(f, p):
                    need.add((f.name, p))
                    changed = True
        return need

    def fresh(self, base, taken):
        k = 1
        while True:
            name = base if k == 1 else f"{base}{k}"
            if name not in taken and name not in self.KEYWORDS:
                taken.add(name)
                return name
            k += 1

    def plan(self, f):
        p = Plan(set(f.vars) | set(self.info.funcs))
        if f.node is not None:
            p.builder = self.find_builder(f) if f.ret == STR else None
            p.ret = "void" if p.builder or f.ret == VOID else "const char *" if f.ret == STR else self.ctype(f.ret)
            first = True
            for name in f.params:
                if f.vars[name] == ARR and not self.dyn:
                    p.params.append(f"long long {self.safe(name)}[]")
                    if (f.name, name) in self.need_len:
                        n = self.fresh("n" if first else f"{name}_len", p.taken)
                        first = False
                        p.params.append(f"int {n}")
                        p.lens[name] = n
                else:
                    p.params.append(self.decl_text(f.vars[name], name))
            if p.builder:
                p.params.append(f"char *{self.safe(p.builder.out)}")
            sep = "" if p.ret.endswith("*") else " "
            p.sig = f"{p.ret}{sep}{self.safe(f.name)}({', '.join(p.params) or 'void'})"
        for name, t in f.vars.items():
            if t == ARR and f.kinds[name] != "parameter" and not self.dyn:
                ws = [s for s in A.walk_all(f.body) if isinstance(s, A.Stmt) and A.writes(s, name)]
                if len(ws) != 1 or not isinstance(ws[0], A.Assign) or not isinstance(ws[0].value, A.ArrayLit):
                    raise unsupported(f"list '{name}' must be created exactly once from a literal", ws[-1] if ws else f.node)
                p.lens[name] = str(len(ws[0].value.items))
        for name in f.params if self.CSTR else []:
            if f.vars[name] == STR and not written(f, name):
                for s in f.body:
                    if self.needs_len(s, name, p.builder):
                        n = self.fresh("n" if "n" not in p.taken else f"{name}_len", p.taken)
                        p.lens[name] = n
                        p.strlen_at.setdefault(s, []).append((name, n))
                        break
        for name, kind in f.kinds.items():
            if kind == "local":
                self.place(name, f.body, p.decl)
        return p

    def needs_len(self, s, name, b):
        if b and s is b.init and b.src == name:
            return True
        return any(isinstance(n, A.Len) and isinstance(n.arg, A.Name) and n.arg.id == name
                   or isinstance(n, A.For) and isinstance(n.iter, A.Name) and n.iter.id == name for n in A.walk(s))

    def place(self, v, stmts, decl):
        hits = [k for k, s in enumerate(stmts) if v in A.names(s)]
        if not hits:
            return
        if len(hits) == 1:
            s = stmts[hits[0]]
            if v not in A.own_names(s):
                subs = [b for b in A.blocks(s) if any(v in A.names(x) for x in b)]
                if len(subs) == 1:
                    return self.place(v, subs[0], decl)
        first = stmts[hits[0]]
        if isinstance(first, (A.Assign, A.TupleAssign)) and A.writes(first, v):
            decl[v] = ("inline", first)
        else:
            decl[v] = ("hoist", stmts, hits[0])

    def find_builder(self, f):
        rets = [s for s in A.walk_all(f.body) if isinstance(s, A.Return)]
        if all(isinstance(r.value, (A.StrLit, A.Intrinsic)) or isinstance(r.value, A.Name)
               and f.kinds[r.value.id] == "parameter" and not written(f, r.value.id) for r in rets):
            return None
        last = f.body[-1]
        if not (isinstance(last, A.Return) and isinstance(last.value, A.Name) and rets == [last]):
            return None
        out = last.value.id
        init = loop = update = mode = None
        for s in f.body:
            if init is None and isinstance(s, A.Assign) and A.writes(s, out) and isinstance(s.value, A.StrLit) \
                    and s.value.value == "":
                init = s
            elif init and not loop and isinstance(s, A.For) and isinstance(s.iter, A.Name) \
                    and f.kinds.get(s.iter.id) == "parameter" and f.vars[s.iter.id] == STR:
                for x in s.body:
                    if isinstance(x, A.Assign) and A.writes(x, out) and isinstance(x.value, A.BinOp) and x.value.op == "+":
                        pair = tuple(getattr(y, "id", None) for y in (x.value.left, x.value.right))
                        mode = {(s.var, out): "prepend", (out, s.var): "append"}.get(pair)
                        if mode:
                            loop, update = s, x
                            break
        if not (init and update) or f.kinds[out] != "local" or written(f, loop.iter.id):
            return None
        used = update.value.right if mode == "prepend" else update.value.left
        allowed = {id(init.target), id(update.target), id(used), id(last.value)}
        if any(isinstance(n, A.Name) and n.id == out and id(n) not in allowed for n in A.walk_all(f.body)):
            return None
        return Builder(out, init, loop, update, mode, loop.iter.id, last)

    def start(self, f):
        self.f, self.p = f, self.plans[f]
        self.out, self.pre, self.subst = [], [], {}
        self.depth, self.scopes = 0, [set()]
        self.declared = set(f.params)
        self.loop_index = {}
        self.g = None

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
        self.line("int main(void)", ENTRY)
        self.open(ENTRY)
        self.block(self.info.main.body)
        self.line("return 0;", ENTRY)
        self.close(ENTRY)
        return self.out

    def prototypes(self):
        pos = {fn.name: k for k, fn in enumerate(self.m.functions)}
        need = []
        for k, fn in enumerate(self.m.functions):
            for c in A.walk_all(fn.body):
                if isinstance(c, A.Call) and pos[c.func] > k and c.func not in need:
                    need.append(c.func)
        return [(self.plans[self.info.funcs[n]].sig + ";", self.info.funcs[n].node.group) for n in sorted(need, key=pos.get)]

    def line(self, text, g):
        self.out.append((self.INDENT * self.depth + text, g))

    def emit(self, text, g):
        pre, self.pre = self.pre, []
        for t, pg in pre:
            self.line(t, pg)
        self.line(text, g)

    def open(self, g):
        if self.ALLMAN or not self.out:
            self.line("{", g)
        else:
            text, lg = self.out[-1]
            self.out[-1] = (text + " {", lg)
        self.depth += 1
        self.scopes.append(set())

    def close(self, g):
        self.depth -= 1
        self.scopes.pop()
        self.line("}", g)

    def body(self, stmts, g):
        self.open(g)
        self.block(stmts)
        self.close(g)

    def temp(self, base, add=True):
        k = 1
        while True:
            name = base if k == 1 else f"{base}{k}"
            if name not in self.p.taken and name not in self.KEYWORDS and not any(name in s for s in self.scopes):
                if add:
                    self.scopes[-1].add(name)
                return name
            k += 1

    def include(self, header, g):
        self.includes.setdefault(header, g)

    def note(self, key, text):
        self.notes.setdefault(key, text)

    def decl_text(self, t, name):
        return f"const char *{self.safe(name)}" if t == STR else clists.decl(self.ctype(t), self.safe(name))

    def fixed(self):
        return not self.dyn

    def builder_of(self, func):
        g = self.info.funcs.get(func)
        return self.plans[g].builder if g else None

    def block(self, stmts):
        k = 0
        while k < len(stmts):
            s = stmts[k]
            self.g = s.group
            for v, d in self.p.decl.items():
                if d[0] == "hoist" and d[1] is stmts and d[2] == k and v not in self.declared:
                    if self.f.vars[v] == ARR and not self.dyn:
                        raise unsupported(f"list '{v}' declared inside a branch", s)
                    self.declared.add(v)
                    self.hoist(v, s.group)
            for name, n in self.p.strlen_at.get(s, []):
                self.include("string.h", s.group)
                self.emit(f"int {n} = strlen({self.safe(name)});", s.group)
            if self.loopable(stmts, k):
                self.while_for(stmts[k], stmts[k + 1])
                k += 2
            else:
                self.stmt(s)
                k += 1

    def hoist(self, v, g):
        self.emit(self.decl_text(self.f.vars[v], v) + ";", g)

    def stmt(self, s):
        g = self.g = s.group
        if isinstance(s, A.Assign):
            self.assign(s)
        elif isinstance(s, A.AugAssign):
            if s.target.ty in (STR, CHAR) and not self.CONCAT:
                raise unsupported("string concatenation", s)
            self.aug(s)
        elif isinstance(s, A.TupleAssign):
            self.tuple_assign(s)
        elif isinstance(s, A.Swap):
            self.swap(s)
        elif isinstance(s, A.If):
            self.if_(s)
        elif isinstance(s, A.While):
            self.emit(f"while ({self.test_text(s.test)})", g)
            self.body(s.body, g)
        elif isinstance(s, A.For):
            self.for_(s)
        elif isinstance(s, A.Return):
            self.ret(s)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic):
            self.emit(f"{self.ex(s.expr)};", g)
        elif isinstance(s, A.ExprStmt):
            if self.builder_of(s.expr.func):
                raise unsupported(f"calling {s.expr.func}() without using its result", s)
            self.emit(f"{self.call(s.expr)};", g)
        elif isinstance(s, A.Print):
            self.print_(s)
        elif isinstance(s, A.Break):
            self.emit("break" + self.END, g)
        elif isinstance(s, A.Continue):
            self.emit("continue" + self.END, g)

    def assign(self, s):
        g, t, v, b = s.group, s.target, s.value, self.p.builder
        if b and s in (b.init, b.update):
            return self.builder_stmt(s, b)
        if isinstance(t, A.Index):
            self.emit(f"{self.ex(t)} = {self.ex_as(v, t.ty)};", g)
            return
        name, ty = t.id, self.f.vars[t.id]
        inline = self.p.decl.get(name) == ("inline", s) and name not in self.declared
        if ty == ARR and self.fixed():
            if not (inline and isinstance(v, A.ArrayLit)):
                raise unsupported(f"reassigning list '{name}'", s)
            self.declared.add(name)
            self.emit(self.array_decl(name, v), g)
            return
        if isinstance(v, A.Call) and self.builder_of(v.func):
            if not inline:
                raise unsupported(f"reassigning the string result of {v.func}()", s)
            self.declared.add(name)
            self.buffer(v, self.safe(name), g)
            return
        if ty == STR and isinstance(v, A.BinOp) and not self.CONCAT:
            raise unsupported("building a string by concatenation", v)
        rhs = self.ex_as(v, ty)
        if inline:
            self.declared.add(name)
            self.emit(f"{self.decl_text(ty, name)} = {rhs};", g)
        else:
            self.emit(f"{self.safe(name)} = {rhs};", g)

    def aug(self, s):
        if s.target.ty == STR and self.CSTR:
            t = self.ex(s.target)
            self.helper("cs_append", s.group)
            self.emit(f"{t} = cs_append({t}, {self.as_text(s.value)});", s.group)
            return
        self.emit(f"{self.ex(s.target)} {s.op}= {self.ex_as(s.value, s.target.ty)};", s.group)

    def swap(self, s):
        a, b = self.ex(s.a), self.ex(s.b)
        t = self.temp("t")
        self.emit(f"{self.decl_text(s.a.ty, t)} = {a};", s.group)
        self.emit(f"{a} = {b};", s.group)
        self.emit(f"{b} = {t};", s.group)

    def else_line(self, text, g):
        if self.ALLMAN:
            self.emit(text, g)
        else:
            last = self.out.pop()[0]
            self.out.append((f"{last.rstrip()} {text}", g))

    def builder_stmt(self, s, b):
        if s is b.update:
            i = self.loop_index[b.loop]
            index = f"{self.p.lens[b.src]} - 1 - {i}" if b.mode == "prepend" else i
            self.emit(f"{self.safe(b.out)}[{index}] = {self.ex(A.Name(b.loop.var))};", s.group)

    def builder_ret(self, b, s):
        self.emit(f"{self.safe(b.out)}[{self.p.lens[b.src]}] = '\\0';", s.group)

    def array_decl(self, name, v):
        if not v.items:
            return f"long long {self.safe(name)}[1] = {{0}};"
        return f"long long {self.safe(name)}[] = {self.array(v)};"

    def tuple_assign(self, s):
        g = s.group
        if any(isinstance(t, A.Index) for t in s.targets):
            raise unsupported("parallel assignment to list elements", s)
        names = [t.id for t in s.targets]
        tys = [self.f.vars[n] for n in names]
        if any(is_list(t) for t in tys):
            raise unsupported("parallel assignment of lists", s)
        new = [n for n in names if self.p.decl.get(n) == ("inline", s) and n not in self.declared]
        reads = set().union(*(A.names(v) for v in s.values))
        if len(new) == len(names) and not set(names) & reads and len(set(tys)) == 1 and STR not in tys:
            self.declared |= set(names)
            parts = [f"{self.safe(n)} = {self.ex_as(v, t)}" for n, v, t in zip(names, s.values, tys)]
            self.emit(f"{self.ctype(tys[0])} {', '.join(parts)};", g)
            return
        for n in new:
            self.declared.add(n)
            self.emit(self.decl_text(self.f.vars[n], n) + ";", g)
        pending = list(zip(names, s.values))
        while pending:
            for k, (n, v) in enumerate(pending):
                if not any(n in A.names(w) for j, (_, w) in enumerate(pending) if j != k):
                    break
            else:
                n, v = pending[0]
                t = self.temp("t")
                self.emit(f"{self.decl_text(self.f.vars[n], t)} = {self.ex(v)};", g)
                pending[0] = (n, A.Name(t, ty=self.f.vars[n]))
                continue
            self.emit(f"{self.safe(n)} = {self.ex_as(v, self.f.vars[n])};", g)
            pending.pop(k)

    def if_(self, s):
        g = s.group
        self.emit(f"if ({self.test_text(s.test)})", g)
        self.body(s.body, g)
        o = s.orelse
        while len(o) == 1 and isinstance(o[0], A.If):
            e = o[0]
            g = self.g = e.group
            cond = self.test_text(e.test)
            if self.pre:
                raise unsupported("this condition in an elif branch", e.test)
            self.else_line(f"else if ({cond})", g)
            self.body(e.body, g)
            o = e.orelse
        if o:
            self.else_line("else", g)
            self.body(o, g)

    def loopable(self, stmts, k):
        if k + 1 >= len(stmts):
            return False
        a, w = stmts[k], stmts[k + 1]
        if not (isinstance(a, A.Assign) and isinstance(a.target, A.Name) and isinstance(w, A.While) and w.body):
            return False
        v, inc = a.target.id, w.body[-1]
        return (isinstance(inc, A.AugAssign) and isinstance(inc.target, A.Name) and inc.target.id == v
                and inc.op in ("+", "-") and isinstance(inc.value, A.IntLit) and inc.value.value > 0
                and self.p.decl.get(v) == ("inline", a) and v not in self.declared
                and self.f.vars[v] in (INT, IDX) and v in A.names(w.test)
                and not any(v in A.names(x) for x in stmts[k + 2:])
                and not any(A.writes(x, v) for x in A.walk_all(w.body[:-1]) if isinstance(x, A.Stmt))
                and not any(True for _ in continues(w.body)))

    def while_for(self, a, w):
        v, inc, g = a.target.id, w.body[-1], w.group
        self.merges += [(g, a.group), (g, inc.group)]
        self.g = g
        k = inc.value.value
        step = f"{self.safe(v)}{inc.op * 2}" if k == 1 else f"{self.safe(v)} {inc.op}= {k}"
        init = self.ex_as(a.value, self.f.vars[v])
        self.emit(self.for_head(None, v, init, self.test_text(w.test), step), g)
        self.declared.add(v)
        self.body(w.body[:-1], g)

    def for_(self, s):
        g = s.group
        if s.kind == "range":
            v = self.safe(s.var)
            start, stop = self.ex_as(s.start, IDX), self.stop(s)
            k = s.step.value
            step = f"{v}++" if k == 1 else f"{v}--" if k == -1 else f"{v} += {k}" if k > 0 else f"{v} -= {-k}"
            self.emit(self.for_head(self.ctype(self.f.vars[s.var]), v, start, f"{v} {'<' if k > 0 else '>'} {stop}", step), g)
            self.open(g)
            self.scopes[-1].add(s.var)
            self.block(s.body)
            self.close(g)
            return
        self.for_each(s)

    def for_each(self, s):
        g = s.group
        it = s.iter
        if self.dyn and (is_list(it.ty) or is_map(it.ty)):
            if isinstance(it, A.Name):
                src = self.safe(it.id)
            else:
                src = self.temp("items")
                self.emit(f"{clists.decl(self.ctype(it.ty), src)} = {self.ex(it)};", g)
            n = f"{src}->len"
        elif not isinstance(it, A.Name) and it.ty == STR:
            src = self.temp("text")
            self.emit(f"const char *{src} = {self.as_text(it)};", g)
            n = None
        elif not isinstance(it, A.Name):
            raise unsupported("looping over a literal", it)
        else:
            src, n = self.safe(it.id), self.length(it)
        i = self.temp("i", add=False)
        elem = f"{src}->keys[{i}]" if is_map(it.ty) else f"{src}->data[{i}]" if self.dyn and is_list(it.ty) \
            else f"{src}[{i}]"
        self.emit(f"for (int {i} = 0; {i} < {n}; {i}++)" if n else f"for (int {i} = 0; {elem} != '\\0'; {i}++)", g)
        self.open(g)
        self.scopes[-1].add(i)
        self.loop_index[s] = i
        b = self.p.builder
        if b and s is b.loop:
            self.subst[s.var] = elem
        else:
            self.emit(f"{self.decl_text(self.f.vars[s.var], s.var)} = {elem};", g)
        self.block(s.body)
        self.subst.pop(s.var, None)
        self.close(g)

    def for_head(self, ctype, v, start, cond, step):
        decl = f"{ctype} {self.safe(v)}" if ctype else self.decl_text(self.f.vars[v], v)
        return f"for ({decl} = {start}; {cond}; {step})"

    def stop(self, s):
        text = self.ex_as(s.stop, IDX)
        changed = {n for x in A.walk_all(s.body) if isinstance(x, A.Stmt) for n in A.names(x) if A.writes(x, n)}
        if not (A.names(s.stop) & changed or any(isinstance(x, (A.Call, A.Index)) for x in A.walk(s.stop))):
            return text
        end = self.temp("end")
        self.emit(f"{self.ctype(s.stop.ty)} {end} = {text};", s.group)
        return end

    def ret(self, s):
        b = self.p.builder
        if b and s is b.ret:
            self.builder_ret(b, s)
        elif s.value is None:
            self.emit("return;", s.group)
        else:
            self.emit(f"return {self.ex_as(s.value, self.f.ret)};", s.group)

    def print_(self, s):
        g = s.group
        self.include("stdio.h", g)
        if len(s.args) == 1 and s.args[0].ty == ARR and not self.dyn:
            a = s.args[0]
            if not isinstance(a, A.Name):
                raise unsupported("printing a list literal", a)
            n = self.length(a)
            i = self.temp("i", add=False)
            self.emit(f"for (int {i} = 0; {i} < {n}; {i}++)", g)
            self.open(g)
            self.scopes[-1].add(i)
            self.emit(f'printf("%lld ", {self.safe(a.id)}[{i}]);', g)
            self.close(g)
            return
        fmt, vals = [], []
        for a in s.args:
            if self.formatting(a):
                part, more = self.layout(a)
                fmt.append(part)
                vals += more
                continue
            if self.dyn and is_list(a.ty):
                fmt.append("%s")
                vals.append(f"{self.list_fn('show', self.kind(a.ty, a), a)}({self.ex(a)})")
                continue
            if a.ty == ARR:
                raise unsupported("printing a list together with other values", a)
            if isinstance(a, A.StrLit):
                self.ascii(a)
                fmt.append(a.value.replace("%", "%%"))
            elif isinstance(a, A.Call) and self.builder_of(a.func):
                buf = self.temp(self.builder_of(a.func).out)
                self.buffer(a, buf, g, pre=True)
                fmt.append("%s")
                vals.append(buf)
            elif constant(a):
                self.wide.add(id(leftmost(a)))
                fmt.append("%lld")
                vals.append(self.ex(a))
            elif a.ty == IDX and is_arith(a):
                fmt.append("%lld")
                vals.append(self.ex_as(a, INT))
            elif a.ty == FLOAT:
                self.helper("cs_f2s", g)
                fmt.append("%s")
                vals.append(f"cs_f2s({self.ex(a)})")
            else:
                fmt.append(FMT[a.ty])
                vals.append(self.ex(a))
        ending = getattr(s, "ending", "\n").replace("%", "%%")
        self.emit(f"printf({', '.join([A.quote(' '.join(fmt) + ending)] + vals)});", g)

    def buffer(self, call, name, g, pre=False):
        b = self.builder_of(call.func)
        size = self.size(call)
        text = self.call(call, [name])
        lines = [(f"char {name}[{size}];", b.init.group), (f"{text};", g)]
        self.note("buffer", f"{call.func}() returns a new string in Python; in C it writes into a buffer the caller "
                            f"declares (char {name}[{size}]).")
        if pre:
            self.pre += lines
        else:
            for t, lg in lines:
                self.emit(t, lg)

    def size(self, call):
        g = self.info.funcs[call.func]
        arg = call.args[g.params.index(self.plans[g].builder.src)]
        text = arg.value if isinstance(arg, A.StrLit) else None
        if isinstance(arg, A.Name):
            ws = [s for s in A.walk_all(self.f.body) if isinstance(s, A.Stmt) and A.writes(s, arg.id)]
            if len(ws) == 1 and isinstance(ws[0], A.Assign) and isinstance(ws[0].value, A.StrLit):
                text = ws[0].value.value
        if text is None:
            raise unsupported(f"sizing the output buffer of {call.func}() for a string that is not a literal", arg)
        return max(32, len(text) + 1)

    def call(self, c, extra=()):
        g = self.info.funcs[c.func]
        args = []
        for a, p in zip(c.args, g.params):
            sized = (g.name, p) in self.need_len
            if g.vars[p] != ARR or self.dyn:
                args.append(self.ex_as(a, g.vars[p]))
            else:
                args += self.array_arg(a, p, sized)
        return f"{self.safe(c.func)}({', '.join(args + list(extra))})"

    def array_arg(self, a, p, sized):
        if isinstance(a, A.ArrayLit):
            name = self.temp(p)
            self.pre.append((self.array_decl(name, a), self.g))
            return [name, str(len(a.items))] if sized else [name]
        if isinstance(a, A.Name):
            return [self.safe(a.id), self.length(a)] if sized else [self.safe(a.id)]
        raise unsupported("passing this list expression", a)

    def array(self, e):
        return "{" + ", ".join(self.ex(x) for x in e.items) + "}"

    def length(self, e):
        if isinstance(e, A.Name):
            if e.id in self.p.lens:
                return self.p.lens[e.id]
            if self.f.vars[e.id] == STR:
                return None
        if isinstance(e, A.StrLit):
            return str(len(e.value))
        raise unsupported("taking the length of this value", e)

    def ascii(self, e):
        if not e.value.isascii():
            raise unsupported("non-ASCII text", e)

    def ex(self, e):
        return self._ex(e)[0]

    def test_text(self, e):
        stack = [e]
        while stack:
            x = stack.pop()
            if isinstance(x, A.BoolOp):
                stack += [x.left, x.right]
            elif isinstance(x, A.UnaryOp) and x.op == "!":
                stack.append(x.operand)
            elif isinstance(x, A.Intrinsic) and x.name in CHECKS:
                self.raw.add(id(x))
        return self.ex(e)

    def char_text(self, e):
        return self.as_text(e)

    def ex_as(self, e, want):
        if want == STR and e.ty == CHAR:
            return self.char_text(e)
        if want == IDX and e.ty == INT and not isinstance(e, A.IntLit):
            return self.narrow(e)
        return self._ex(e, cast=want == INT and e.ty == IDX and is_arith(e))[0]

    def narrow(self, e):
        return self.ex(e)

    def _ex(self, e, cast=False):
        if cast and not isinstance(e, A.BinOp):
            t, p = self._ex(e)
            return (f"{self.CAST}{t}" if p <= 1 else f"{self.CAST}({t})"), 2
        if isinstance(e, A.IntLit):
            if e.ty == FLOAT:
                return self.float_int(e.value), 2 if e.value < 0 else 1
            wide = id(e) in self.wide or self.BIG and not -2 ** 31 <= e.value < 2 ** 31
            return str(e.value) + (self.LONG if wide else ""), 2 if e.value < 0 else 1
        if isinstance(e, A.FloatLit):
            return repr(e.value), 2 if e.value < 0 else 1
        if isinstance(e, A.Intrinsic):
            return self.intrinsic(e)
        if isinstance(e, A.ArrayLit):
            return (self.new_list(e) if self.dyn else self.array(e)), 1
        if isinstance(e, A.BoolLit):
            return self.bool_text(e.value), 1
        if isinstance(e, (A.StrLit, A.CharLit)):
            self.ascii(e)
            return self.literal(e), 1
        if isinstance(e, A.Name):
            return self.subst.get(e.id) or self.safe(e.id), 1
        if isinstance(e, A.Index):
            return self.index_text(e), 1
        if isinstance(e, A.Len):
            return self.len_text(e), 1
        if isinstance(e, A.Call):
            if self.builder_of(e.func):
                raise unsupported(f"using the string result of {e.func}() inside an expression", e)
            return self.call(e), 1
        if isinstance(e, A.UnaryOp):
            if e.op == "!" and e.operand.ty in (INT, IDX):
                return self.not_int(e)
            x, xp = self._ex(e.operand)
            if xp > 2 or (e.op == "-" and x.startswith("-")):
                x = f"({x})"
            return e.op + x, 2
        l, r = e.left, e.right
        if isinstance(e, A.Compare) and l.ty == r.ty == STR:
            return self.str_compare(e)
        if isinstance(e, A.Compare) and CHAR in (l.ty, r.ty):
            l, r = char_lit(l), char_lit(r)
        if isinstance(e, A.BinOp) and constant(e):
            seen = []
            values(e, seen)
            if any(not -2 ** 31 <= v < 2 ** 31 for v in seen):
                self.wide |= {id(leftmost(n)) for n in A.walk(e) if isinstance(n, A.BinOp)}
        if isinstance(e, A.BinOp) and e.ty in (STR, CHAR):
            return self.concat(e)
        p = A.PREC[e.op]
        wide = (isinstance(e, A.BinOp) and e.ty == INT) or (isinstance(e, A.Compare) and INT in (l.ty, r.ty))
        lt, lp = self._ex(l, cast or (wide and l.ty == IDX and is_arith(l)))
        rt, rp = self._ex(r, wide and r.ty == IDX and is_arith(r))
        return self.binary(e, f"{f'({lt})' if lp > p else lt}", f"{f'({rt})' if rp >= p else rt}", p)

    def not_int(self, e):
        x, xp = self._ex(e.operand)
        return "!" + (f"({x})" if xp > 2 else x), 2

    def float_int(self, v):
        return f"{v}.0"

    CONV = {"i2f": "(double)", "f2i": "(long long)"}

    def intrinsic(self, e):
        n, g = e.name, self.g
        if n == "read_line":
            self.helper("cs_read_line", g)
            return "cs_read_line()", 1
        if n == "exit":
            self.include("stdlib.h", g)
            return f"exit({self.ex_as(e.args[0], IDX)})", 1
        if n in ("fixed", "rjust", "ljust"):
            if self.cspec(e) is None:
                raise unsupported("a format width or precision that is not a constant in C", e)
            fmt, vals = self.layout(e)
            self.helper("cs_format", g)
            return f"cs_format({', '.join([A.quote(fmt), *vals])})", 1
        if self.dyn and n in LISTOPS:
            return self.listop(e)
        if n in MAPOPS:
            return self.mapop(e)
        if n in ("i2f", "f2i", "ord", "chr"):
            x, xp = self._ex(e.args[0])
            cast = {"ord": self.CONV["f2i"], "chr": "(char)"}.get(n) or self.CONV[n]
            return f"{cast}{f'({x})' if xp > 1 else x}", 2
        if n in ("b2s", "b2s_py"):
            x, xp = self._ex(e.args[0])
            words = ("true", "false") if n == "b2s" else ("True", "False")
            return f'{f"({x})" if xp > 12 else x} ? "{words[0]}" : "{words[1]}"', 13
        if n in ("pi", "e"):
            name = "CS_PI" if n == "pi" else "CS_E"
            self.helper(name, g)
            return name, 1
        if n in ("min", "max"):
            if e.ty == FLOAT:
                self.include("math.h", g)
                fn = "fmin" if n == "min" else "fmax"
            else:
                fn = f"cs_i{n}"
                self.helper(fn, g)
            return f"{fn}({', '.join(self.ex(a) for a in e.args)})", 1
        if n in STRINGS:
            self.helper(STRINGS[n], g)
            return f"{STRINGS[n]}({', '.join(self.as_text(a) for a in e.args)})", 1
        if n in ("contains_s", "contains_c"):
            self.include("string.h", g)
            fn = "strstr" if n == "contains_s" else "strchr"
            return f"{fn}({self.ex(e.args[0])}, {self.ex(e.args[1])}) != NULL", A.PREC["!="]
        if n in CHECKS:
            self.include("ctype.h", g)
            text = f"{CHECKS[n]}({self.ex(e.args[0])})"
            if n in ("cupper", "clower"):
                return f"(char){text}", 2
            return (text, 1) if id(e) in self.raw else (f"{text} != 0", A.PREC["!="])
        if n in ("s2i", "s2f"):
            self.include("stdlib.h", g)
            s = self.ex(e.args[0])
            return (f"strtoll({s}, NULL, 10)" if n == "s2i" else f"strtod({s}, NULL)"), 1
        if n in MATH_H:
            self.include("math.h", g)
            fn = MATH_H[n]
        elif n in CALLS:
            fn, header = CALLS[n]
            if header:
                self.include(header, g)
            else:
                self.helper(fn, g)
        else:
            raise unsupported(f"library call @{n} in {self.lang}", e)
        return f"{fn}({', '.join(self.ex(a) for a in e.args)})", 1

    def binary(self, e, lt, rt, p):
        return f"{lt} {e.op} {rt}", p

    def literal(self, e):
        return A.quote(e.value, "'" if isinstance(e, A.CharLit) else '"')

    def bool_text(self, v):
        return "1" if v else "0"

    def index_text(self, e):
        if self.dyn and is_list(e.target.ty):
            return f"{self._ex(e.target)[0]}->data[{self.ex(e.index)}]"
        return f"{self._ex(e.target)[0]}[{self.ex(e.index)}]"

    def len_text(self, e):
        if self.dyn and is_list(e.arg.ty):
            return f"{self._ex(e.arg)[0]}->len"
        n = self.length(e.arg)
        if n is None:
            self.include("string.h", self.g)
            n = f"strlen({self.ex(e.arg)})"
        return n

    def str_compare(self, e):
        self.include("string.h", self.g)
        return f"strcmp({self.ex(e.left)}, {self.ex(e.right)}) {e.op} 0", A.PREC[e.op]

    def concat(self, e):
        if self.CSTR and self.formatting(e):
            fmt, vals = self.layout(e)
            self.helper("cs_format", self.g)
            return f"cs_format({', '.join([A.quote(fmt), *vals])})", 1
        self.helper("cs_concat", self.g)
        return f"cs_concat({self.as_text(e.left)}, {self.as_text(e.right)})", 1

    def as_text(self, e):
        if e.ty == CHAR and not isinstance(e, A.CharLit):
            self.helper("cs_c2s", self.g)
            return f"cs_c2s({self.ex(e)})"
        if isinstance(e, A.CharLit):
            return A.quote(e.value)
        return self.ex(e)

    def ctype_of(self, f, name):
        p, t = self.plans[f], f.vars[name]
        if p.builder and name == p.builder.out:
            return "char *"
        if t == ARR and not self.dyn:
            return "long long[]"
        return "const char *" if t == STR else self.ctype(t)

    def rows(self, f):
        p = self.plans[f]
        out = []
        for name in f.params:
            out.append((name, "parameter", self.ctype_of(f, name)))
            if f.vars[name] == ARR and name in p.lens:
                out.append((p.lens[name], "parameter", "int"))
        if p.builder:
            out.append((p.builder.out, "parameter", "char *"))
        for name, kind in f.kinds.items():
            if kind != "parameter" and not (p.builder and name == p.builder.out):
                out.append((name, kind, self.ctype_of(f, name)))
        for pairs in p.strlen_at.values():
            out += [(n, "local", "int") for _, n in pairs]
        return out

    def types(self):
        notes = []
        for f in self.info.all():
            by = {}
            for name, _, ct in self.rows(f):
                by.setdefault(ct, []).append(name)
            notes += [f"{', '.join(ns)}: {ct}" for ct, ns in by.items()]
            if f.node is not None:
                notes.append(f"{f.name} → {self.plans[f].ret}")
        return list(dict.fromkeys(notes))

    def symbols(self):
        out = []
        for f in self.info.all():
            rows = self.rows(f)
            scope = f.name if f.node is not None else "global"
            if f.node is not None:
                params = ", ".join(ct for _, k, ct in rows if k == "parameter")
                out.append({"name": f.name, "kind": "function", "type": f"({params}) → {self.plans[f].ret}", "scope": "global"})
            for name, kind, ct in rows:
                out.append({"name": name, "kind": kind, "type": ct, "scope": "loop" if kind == "loop var" else scope})
        return out
