from .. import ast as A
from ..errors import CompileError
from ..linemap import ENTRY
from ..library import LISTOPS, MAPOPS
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID, elem, is_list, is_map, is_set, mkey, mval, selem
from .c import CBackend, is_arith, unsupported

KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const", "continue", "default",
    "do", "double", "else", "enum", "extends", "final", "finally", "float", "for", "goto", "if", "implements", "import",
    "instanceof", "int", "interface", "long", "native", "new", "package", "private", "protected", "public", "return",
    "short", "static", "strictfp", "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try",
    "void", "volatile", "while", "true", "false", "null", "var", "record", "yield", "Main", "String", "System", "Arrays",
    "Math", "args",
}
CALLS = {
    "abs_i": "Math.abs", "abs_f": "Math.abs", "min": "Math.min", "max": "Math.max", "pow_f": "Math.pow",
    "sqrt": "Math.sqrt", "floor": "Math.floor", "ceil": "Math.ceil", "round_even": "Math.rint", "sin": "Math.sin",
    "cos": "Math.cos", "tan": "Math.tan", "atan2": "Math.atan2", "log": "Math.log", "log10": "Math.log10",
    "exp": "Math.exp", "hypot": "Math.hypot", "i2s": "Long.toString", "f2s": "Double.toString",
    "b2s": "Boolean.toString", "pow_i": "csIpow", "round_away": "csRoundAway",
}
HELPERS = {
    "csIpow": """    static long csIpow(long a, long n)
    {
        long r = 1;
        for (long i = 0; i < n; i++)
        {
            r *= a;
        }
        return r;
    }""",
    "csRoundAway": """    static double csRoundAway(double x)
    {
        return Math.signum(x) * Math.floor(Math.abs(x) + 0.5);
    }""",
    "csSorted": """    static <T extends Comparable<T>> ArrayList<T> csSorted(ArrayList<T> xs)
    {
        ArrayList<T> r = new ArrayList<>(xs);
        Collections.sort(r);
        return r;
    }""",
    "csGrid": """    static <T> ArrayList<ArrayList<T>> csGrid(long r, long c, T v)
    {
        ArrayList<ArrayList<T>> g = new ArrayList<>();
        for (long i = 0; i < r; i++)
        {
            g.add(new ArrayList<>(Collections.nCopies((int)c, v)));
        }
        return g;
    }""",
    "csReadLine": """    static BufferedReader csIn = new BufferedReader(new InputStreamReader(System.in));

    static String csReadLine()
    {
        try
        {
            String s = csIn.readLine();
            return s == null ? "" : s;
        }
        catch (IOException e)
        {
            return "";
        }
    }""",
    "csInts": """    static ArrayList<Long> csInts(String s)
    {
        ArrayList<Long> r = new ArrayList<>();
        for (String w : csSplitWs(s))
        {
            r.add(Long.parseLong(w));
        }
        return r;
    }""",
    "csSplit": """    static ArrayList<String> csSplit(String s, String sep)
    {
        return new ArrayList<>(List.of(s.split(java.util.regex.Pattern.quote(sep), -1)));
    }""",
    "csSplitWs": """    static ArrayList<String> csSplitWs(String s)
    {
        String t = s.strip();
        return t.isEmpty() ? new ArrayList<>() : new ArrayList<>(List.of(t.split("\\\\s+")));
    }""",
}
DEPS = {"csInts": ["csSplitWs"]}
IO = {"csReadLine": ["java.io.BufferedReader", "java.io.IOException", "java.io.InputStreamReader"]}
USES = {"csInts": ["ArrayList"], "csSorted": ["ArrayList", "Collections"], "csGrid": ["ArrayList", "Collections"], "csSplit": ["ArrayList", "List"],
        "csSplitWs": ["ArrayList", "List"]}
BOX = {INT: "Long", IDX: "Long", FLOAT: "Double", STR: "String", BOOL: "Boolean", CHAR: "Character"}
UNBOX = {INT: "(long)", FLOAT: "(double)", BOOL: "(boolean)"}
METHODS = {"upper": "toUpperCase", "lower": "toLowerCase", "trim": "strip", "starts": "startsWith",
           "ends": "endsWith", "contains_s": "contains", "find": "indexOf", "replace_all": "replace"}
CHARS = {"is_digit": "isDigit", "is_alpha": "isLetter", "is_space": "isWhitespace", "is_upper": "isUpperCase",
         "is_lower": "isLowerCase", "cupper": "toUpperCase", "clower": "toLowerCase"}
JTYPE = {INT: "long", IDX: "int", BOOL: "boolean", CHAR: "char", STR: "String", VOID: "void", ARR: "long[]", FLOAT: "double"}


def camel(name):
    core = name.strip("_")
    parts = [p for p in core.split("_") if p]
    if not parts:
        return name
    return name[:len(name) - len(name.lstrip("_"))] + parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class JavaBackend(CBackend):
    lang = "java"
    KEYWORDS = KEYWORDS
    CAST = "(long)"
    CONV = {"i2f": "(double)", "f2i": "(long)"}
    LONG = "L"
    BIG = True
    CSTR = False
    CONCAT = True

    def safe(self, name):
        n = camel(name)
        return n + "_" if n in KEYWORDS else n

    def ctype(self, t):
        return self.jt(t)

    def jt(self, t):
        if is_map(t):
            self.include("java.util.LinkedHashMap", self.g)
            return f"LinkedHashMap<{self.boxed(mkey(t))}, {self.boxed(mval(t))}>"
        if is_set(t):
            self.include("java.util.TreeSet", self.g)
            return f"TreeSet<{self.boxed(selem(t))}>"
        if is_list(t) and self.dyn:
            self.include("java.util.ArrayList", self.g)
            return f"ArrayList<{self.boxed(elem(t) or INT)}>"
        return JTYPE[t]

    def boxed(self, t):
        return self.jt(t) if is_list(t) else BOX[t]

    def decl_text(self, t, name):
        return f"{self.jt(t)} {self.safe(name)}"

    def length_params(self):
        return set()

    def builder_of(self, func):
        return None

    def find_builder(self, f):
        try:
            return super().find_builder(f)
        except CompileError:
            return None

    def plan(self, f):
        p = super().plan(f)
        if f.node is not None:
            p.ret = self.jt(f.ret)
            p.params = [self.decl_text(f.vars[n], n) for n in f.params]
            p.sig = f"static {p.ret} {self.safe(f.name)}({', '.join(p.params)})"
        return p

    def generate(self):
        self.dyn = self.dynamic()
        self.need_len = set()
        for f in self.info.all():
            self.g = f.node.group if f.node is not None else ENTRY
            self.plans[f] = self.plan(f)
        chunks = [self.function(self.info.funcs[fn.name]) for fn in self.m.functions]
        main = self.main()
        head = [(f"import {h};", g) for h, g in sorted(self.includes.items())]
        lines = head + ([("", None)] if head else []) + [("public class Main", ENTRY), ("{", ENTRY)]
        for name, g in self.helpers.items():
            lines += [(x, g if x else None) for x in HELPERS[name].split("\n")] + [("", None)]
        for chunk in chunks:
            lines += chunk + [("", None)]
        self.entry = len(lines)
        lines += main
        self.entry_end = len(lines)
        lines.append(("}", ENTRY))
        self.prelude = [t for t, _ in head]
        self.imports = self.prelude + [f"static {n}() helper" for n in self.helpers]
        return lines

    def helper(self, name, g):
        for d in DEPS.get(name, []):
            self.helper(d, g)
        for u in USES.get(name, []):
            self.include(f"java.util.{u}", g)
        for u in IO.get(name, []):
            self.include(u, g)
        self.helpers.setdefault(name, g)

    def spec(self, e):
        n = e.name
        if n == "fixed" and isinstance(e.args[1], A.IntLit):
            return f"%.{e.args[1].value}f", e.args[0]
        if n in ("rjust", "ljust") and isinstance(e.args[1], A.IntLit):
            flag, w, inner = "" if n == "rjust" else "-", e.args[1].value, e.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name == "fixed" and isinstance(inner.args[1], A.IntLit):
                return f"%{flag}{w}.{inner.args[1].value}f", inner.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name == "i2s":
                return f"%{flag}{w}d", inner.args[0]
            return f"%{flag}{w}s", inner
        return None

    def item(self, x, el):
        if el in (INT, IDX) and isinstance(x, A.IntLit):
            return f"{x.value}L"
        if el in (INT, IDX) and x.ty == IDX:
            return self._ex(x, cast=True)[0]
        return self.ex(x)

    def boxed_val(self, e):
        return e.ty in UNBOX and (isinstance(e, A.Index) and is_list(e.target.ty) or isinstance(e, A.Intrinsic)
                                  and e.name in ("pop", "pop_at", "lmin", "lmax", "map_get", "map_get_or"))

    def _ex(self, e, cast=False):
        if self.dyn:
            if isinstance(e, A.ArrayLit):
                return self.new_list(e), 1
            if isinstance(e, A.Intrinsic) and e.name in LISTOPS:
                return self.listop(e)
            if isinstance(e, A.Intrinsic) and e.name in MAPOPS:
                return self.mapop(e)
            if isinstance(e, A.Compare) and e.op in ("==", "!=") and self.boxed_val(e.left) and self.boxed_val(e.right):
                p = A.PREC[e.op]
                return f"{UNBOX[e.left.ty]}{self.ex(e.left)} {e.op} {self.ex(e.right)}", p
        return super()._ex(e, cast)

    def new_list(self, e):
        self.include("java.util.ArrayList", self.g)
        if not e.items:
            return "new ArrayList<>()"
        self.include("java.util.List", self.g)
        el = elem(e.ty) or INT
        return f"new ArrayList<>(List.of({', '.join(self.item(x, el) for x in e.items)}))"

    def mapop(self, e):
        n, args, g = e.name, e.args, self.g
        if n == "map_new":
            self.include("java.util.LinkedHashMap", g)
            return "new LinkedHashMap<>()", 1
        if n == "set_new":
            self.include("java.util.TreeSet", g)
            return "new TreeSet<>()", 1
        x, xp = self._ex(args[0])
        r = f"({x})" if xp > 1 else x
        t = args[0].ty
        k, v = (mkey(t), mval(t)) if is_map(t) else (selem(t), None)
        key = self.item(args[1], k) if len(args) > 1 else None
        if n in ("map_len", "set_len"):
            return f"{r}.size()", 1
        if n == "map_get":
            return f"{r}.get({key})", 1
        if n == "map_put":
            return f"{r}.put({key}, {self.item(args[2], v)})", 1
        if n == "map_get_or":
            return f"{r}.getOrDefault({key}, {self.item(args[2], v)})", 1
        if n == "map_has":
            return f"{r}.containsKey({key})", 1
        if n in ("map_del", "set_del"):
            return f"{r}.remove({key})", 1
        if n == "map_incr":
            box = "Long" if v == INT else "Double"
            return f"{r}.merge({key}, {self.item(args[2], v)}, {box}::sum)", 1
        if n == "map_sorted_keys":
            self.include("java.util.ArrayList", g)
            self.include("java.util.TreeSet", g)
            return f"new ArrayList<>(new TreeSet<>({r}.keySet()))", 1
        if n == "set_add":
            return f"{r}.add({key})", 1
        if n == "set_has":
            return f"{r}.contains({key})", 1
        if n == "set_sorted":
            self.include("java.util.ArrayList", g)
            return f"new ArrayList<>({x})", 1
        raise unsupported(f"library call @{n} in Java", e)

    def listop(self, e):
        n, args, g = e.name, e.args, self.g
        xs = args[0]
        el = elem(xs.ty) if is_list(xs.ty) else None
        x, xp = self._ex(xs)
        r = f"({x})" if xp > 1 else x
        if n in ("sort", "sort_desc", "reverse", "lmin", "lmax", "list_fill"):
            self.include("java.util.Collections", g)
        if n == "push":
            return f"{r}.add({self.item(args[1], el)})", 1
        if n == "insert":
            return f"{r}.add({self.ex_as(args[1], IDX)}, {self.item(args[2], el)})", 1
        if n == "pop":
            return f"{r}.remove({r}.size() - 1)", 1
        if n in ("pop_at", "remove_at"):
            return f"{r}.remove({self.ex_as(args[1], IDX)})", 1
        if n == "index_of":
            return f"{r}.indexOf({self.item(args[1], el)})", 1
        if n == "contains_l":
            return f"{r}.contains({self.item(args[1], el)})", 1
        if n == "sort":
            return f"Collections.sort({x})", 1
        if n == "sort_desc":
            return f"{r}.sort(Collections.reverseOrder())", 1
        if n == "reverse":
            return f"Collections.reverse({x})", 1
        if n in ("lmin", "lmax"):
            return f"Collections.{n[1:]}({x})", 1
        if n == "sorted":
            self.helper("csSorted", g)
            return f"csSorted({x})", 1
        if n == "lcopy":
            self.include("java.util.ArrayList", g)
            return f"new ArrayList<>({x})", 1
        if n == "lslice":
            self.include("java.util.ArrayList", g)
            return f"new ArrayList<>({r}.subList({self.ex_as(args[1], IDX)}, {self.ex_as(args[2], IDX)}))", 1
        if n == "sum":
            box, prim = ("Long", "long") if el in (INT, IDX) else ("Double", "double")
            return f"{r}.stream().mapTo{box}({box}::{prim}Value).sum()", 1
        if n == "list_fill":
            self.include("java.util.ArrayList", g)
            v = self.item(args[0], elem(e.ty) or INT)
            return f"new ArrayList<>(Collections.nCopies({self.ex_as(args[1], IDX)}, {v}))", 1
        if n == "grid":
            self.helper("csGrid", g)
            v = self.item(args[2], elem(elem(e.ty)) or INT)
            return f"csGrid({self.ex_as(args[0], INT)}, {self.ex_as(args[1], INT)}, {v})", 1
        if n == "split":
            self.helper("csSplit", g)
            return f"csSplit({self.ex(args[0])}, {self.ex(args[1])})", 1
        if n == "split_ws":
            self.helper("csSplitWs", g)
            return f"csSplitWs({x})", 1
        if n == "s2ints":
            self.helper("csInts", g)
            return f"csInts({x})", 1
        if n == "join":
            return f"String.join({x}, {self.ex(args[1])})", 1
        raise unsupported(f"library call @{n} in Java", e)

    def assign(self, s):
        t = s.target
        if self.dyn and isinstance(t, A.Index) and is_list(t.target.ty):
            self.emit(f"{self.ex(t.target)}.set({self.ex_as(t.index, IDX)}, {self.item(s.value, t.ty)});", s.group)
            return
        super().assign(s)

    def swap(self, s):
        a, b = s.a, s.b
        lists = [isinstance(x, A.Index) and is_list(x.target.ty) for x in (a, b)]
        if self.dyn and all(lists) and A.same(a.target, b.target):
            self.include("java.util.Collections", s.group)
            i, j = self.ex_as(a.index, IDX), self.ex_as(b.index, IDX)
            self.emit(f"Collections.swap({self.ex(a.target)}, {i}, {j});", s.group)
            return
        if self.dyn and any(lists):
            raise unsupported("swapping elements of two different lists", s)
        super().swap(s)

    def intrinsic(self, e):
        n = e.name
        if n == "read_line":
            self.helper("csReadLine", self.g)
            return "csReadLine()", 1
        if n == "exit":
            return f"System.exit({self.ex_as(e.args[0], IDX)})", 1
        if n in ("fixed", "rjust", "ljust"):
            got = self.spec(e)
            if got is None:
                raise unsupported("a format width or precision that is not a constant in Java", e)
            return f"String.format({A.quote(got[0])}, {self.ex(got[1])})", 1
        if n == "f2i" and isinstance(e.args[0], A.Intrinsic) and e.args[0].name == "round_js":
            return f"Math.round({self.ex(e.args[0].args[0])})", 1
        if n in ("pi", "e"):
            return ("Math.PI" if n == "pi" else "Math.E"), 1
        x, xp = self._ex(e.args[0]) if e.args else ("", 0)
        if n == "round_js":
            return f"(double)Math.round({x})", 2
        if n == "trunc":
            return f"(double)(long){f'({x})' if xp > 1 else x}", 2
        if n == "log2":
            return f"Math.log({x}) / Math.log(2)", A.PREC["/"]
        if n in ("s2i", "s2f"):
            fn = "Long.parseLong" if n == "s2i" else "Double.parseDouble"
            return f"{fn}({f'({x})' if xp > 1 else x}.trim())", 1
        if n in CALLS:
            if CALLS[n].startswith("cs"):
                self.helper(CALLS[n], self.g)
            return f"{CALLS[n]}({', '.join(self.ex(a) for a in e.args)})", 1
        if n in CHARS:
            return f"Character.{CHARS[n]}({x})", 1
        recv = f"({x})" if xp > 1 else x
        if n in METHODS:
            return f"{recv}.{METHODS[n]}({', '.join(self.ex(a) for a in e.args[1:])})", 1
        if n == "contains_c":
            return f"{recv}.indexOf({self.ex(e.args[1])}) >= 0", A.PREC[">="]
        if n == "substr":
            a, b = e.args[1], e.args[2]
            whole = isinstance(b, A.Len) and A.same(b.arg, e.args[0])
            bounds = [self.ex_as(a, IDX)] + ([] if whole else [self.ex_as(b, IDX)])
            return f"{recv}.substring({', '.join(bounds)})", 1
        if n == "repeat":
            return f"{recv}.repeat({self.ex_as(e.args[1], IDX)})", 1
        return super().intrinsic(e)

    def function(self, f):
        self.start(f)
        self.depth = 1
        g = f.node.group
        self.line(self.p.sig, g)
        self.open(g)
        self.block(f.body)
        self.close(g)
        return self.out

    def main(self):
        self.start(self.info.main)
        self.depth = 1
        self.line("public static void main(String[] args)", ENTRY)
        self.open(ENTRY)
        self.block(self.info.main.body)
        self.close(ENTRY)
        return self.out

    def prototypes(self):
        return []

    def aug(self, s):
        t = s.target
        if self.dyn and isinstance(t, A.Index) and is_list(t.target.ty):
            v, vp = self._ex(s.value)
            if vp >= A.PREC[s.op]:
                v = f"({v})"
            i = self.ex_as(t.index, IDX)
            self.emit(f"{self.ex(t.target)}.set({i}, {self.ex(t)} {s.op} {v});", s.group)
            return
        if s.target.ty == STR:
            self.emit(f"{self.ex(s.target)} += {self.ex(s.value)};", s.group)
            return
        super().aug(s)

    def builder_stmt(self, s, b):
        out = self.safe(b.out)
        self.declared.add(b.out)
        if s is b.init:
            self.emit(f"StringBuilder {out} = new StringBuilder();", s.group)
        elif b.mode == "prepend":
            self.emit(f"{out}.insert(0, {self.ex(A.Name(b.loop.var))});", s.group)
        else:
            self.emit(f"{out}.append({self.ex(A.Name(b.loop.var))});", s.group)

    def builder_ret(self, b, s):
        self.emit(f"return {self.safe(b.out)}.toString();", s.group)

    def array_decl(self, name, v):
        return f"long[] {self.safe(name)} = {self.array(v)};"

    def array_arg(self, a, p, sized):
        if isinstance(a, A.ArrayLit):
            return [f"new long[]{self.array(a)}"]
        return [self.ex(a)]

    def for_each(self, s):
        g = s.group
        it = self.ex(s.iter)
        if s.iter.ty == STR:
            it += ".toCharArray()"
        if is_map(s.iter.ty):
            it += ".keySet()"
        if isinstance(s.iter, A.Intrinsic) and s.iter.name == "set_sorted":
            it = self.ex(s.iter.args[0])
        self.emit(f"for ({self.jt(self.f.vars[s.var])} {self.safe(s.var)} : {it})", g)
        self.open(g)
        self.scopes[-1].add(s.var)
        self.block(s.body)
        self.close(g)

    def print_(self, s):
        end = getattr(s, "ending", "\n")
        if end == "\n":
            return self.print_line(s, "println")
        if s.args:
            self.print_line(s, "print")
        if end:
            self.emit(f"System.out.print({A.quote(end)});", s.group)

    def print_line(self, s, method):
        g = s.group
        if self.dyn and len(s.args) == 1 and is_list(s.args[0].ty):
            self.emit(f"System.out.{method}({self.ex(s.args[0])});", g)
            return
        if len(s.args) == 1 and s.args[0].ty == ARR:
            self.include("java.util.Arrays", g)
            a = s.args[0]
            text = f"new long[]{self.array(a)}" if isinstance(a, A.ArrayLit) else self.ex(a)
            self.emit(f"System.out.{method}(Arrays.toString({text}));", g)
            return
        if not self.dyn and any(a.ty == ARR for a in s.args):
            raise unsupported("printing a list together with other values", s)
        parts = []
        for k, a in enumerate(s.args):
            if k:
                parts.append(("lit", " "))
            if isinstance(a, A.StrLit):
                parts.append(("lit", a.value))
            else:
                parts.append(("expr", a))
        merged = []
        for kind, v in parts:
            if kind == "lit" and merged and merged[-1][0] == "lit":
                merged[-1] = ("lit", merged[-1][1] + v)
            else:
                merged.append((kind, v))
        if len(merged) == 1 and merged[0][0] == "expr":
            text = self.ex_as(merged[0][1], INT)
        else:
            pieces = []
            for k, (kind, v) in enumerate(merged):
                if kind == "lit":
                    pieces.append(A.quote(v))
                    continue
                code, prec = self._ex(v, cast=v.ty == IDX and is_arith(v))
                if prec >= A.PREC["+"]:
                    code = f"({code})"
                pieces.append(code)
            text = " + ".join(pieces)
        self.emit(f"System.out.{method}({text});", g)

    def test_text(self, e):
        text, p = self._ex(e)
        return f"{f'({text})' if p >= A.PREC['!='] else text} != 0" if e.ty in (INT, IDX) else text

    def not_int(self, e):
        x, xp = self._ex(e.operand)
        return f"{f'({x})' if xp >= A.PREC['=='] else x} == 0", A.PREC["=="]

    def char_text(self, e):
        return f"String.valueOf({self.ex(e)})"

    def bool_text(self, v):
        return "true" if v else "false"

    def index_text(self, e):
        t = self._ex(e.target)[0]
        i = self.ex_as(e.index, IDX)
        if self.dyn and is_list(e.target.ty):
            return f"{t}.get({i})"
        return f"{t}.charAt({i})" if e.target.ty == STR else f"{t}[{i}]"

    def narrow(self, e):
        t, p = self._ex(e)
        if self.boxed_val(e):
            return f"(int)(long){t}"
        return f"(int){t}" if p <= 1 else f"(int)({t})"

    def len_text(self, e):
        a = e.arg
        if self.dyn and is_list(a.ty):
            return f"{self._ex(a)[0]}.size()"
        t = f"new long[]{self.array(a)}" if isinstance(a, A.ArrayLit) else self._ex(a)[0]
        return f"{t}.length" if a.ty == ARR else f"{t}.length()"

    def str_compare(self, e):
        (l, lp), r = self._ex(e.left), self.ex(e.right)
        l = f"({l})" if lp > 1 else l
        if e.op in ("==", "!="):
            return (f"{l}.equals({r})", 1) if e.op == "==" else (f"!{l}.equals({r})", 2)
        return f"{l}.compareTo({r}) {e.op} 0", A.PREC[e.op]

    def concat(self, e):
        l, lp = self._ex(e.left)
        r, rp = self._ex(e.right)
        if e.left.ty == CHAR and e.right.ty == CHAR:
            l = f"String.valueOf({l})"
            lp = 1
        p = A.PREC["+"]
        return f"{f'({l})' if lp > p else l} + {f'({r})' if rp >= p else r}", p

    def ctype_of(self, f, name):
        p = self.plans[f]
        if p.builder and name == p.builder.out:
            return "StringBuilder"
        return self.jt(f.vars[name])

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
                notes.append(f"{self.safe(f.name)} → {self.plans[f].ret}")
        return list(dict.fromkeys(notes))

    def symbols(self):
        out = []
        for f in self.info.all():
            rows = self.rows(f)
            scope = self.safe(f.name) if f.node is not None else "main"
            if f.node is not None:
                params = ", ".join(ct for _, k, ct in rows if k == "parameter")
                out.append({"name": self.safe(f.name), "kind": "function", "type": f"({params}) → {self.plans[f].ret}",
                            "scope": "Main"})
            for name, kind, ct in rows:
                out.append({"name": name, "kind": kind, "type": ct, "scope": "loop" if kind == "loop var" else scope})
        return out
