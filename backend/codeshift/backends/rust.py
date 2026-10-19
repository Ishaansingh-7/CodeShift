from .. import ast as A
from ..linemap import ENTRY
from ..library import LISTOPS, MAPOPS
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID, elem, is_list, is_map, is_set, mkey, mval, selem
from .c import CBackend, Plan, constant, leftmost, unsupported, values

KEYWORDS = {
    "as", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in",
    "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self", "Self", "static", "struct", "super",
    "trait", "true", "type", "unsafe", "use", "where", "while", "async", "await", "dyn", "abstract", "become", "box",
    "do", "final", "macro", "override", "priv", "typeof", "unsized", "virtual", "yield", "try", "gen", "main",
    "println", "vec", "format", "String", "Vec", "i64", "usize", "char", "bool", "str", "std",
}
METHODS = {
    "abs_i": "abs", "abs_f": "abs", "min": "min", "max": "max", "pow_f": "powf", "sqrt": "sqrt", "floor": "floor",
    "ceil": "ceil", "trunc": "trunc", "round_away": "round", "round_even": "round_ties_even", "sin": "sin",
    "cos": "cos", "tan": "tan", "atan2": "atan2", "log": "ln", "log10": "log10", "log2": "log2", "exp": "exp",
    "hypot": "hypot", "i2s": "to_string", "f2s": "to_string", "b2s": "to_string", "upper": "to_uppercase",
    "lower": "to_lowercase", "is_digit": "is_ascii_digit", "is_alpha": "is_ascii_alphabetic",
    "is_space": "is_ascii_whitespace", "is_upper": "is_ascii_uppercase", "is_lower": "is_ascii_lowercase",
    "cupper": "to_ascii_uppercase", "clower": "to_ascii_lowercase",
}
TEXT = {"starts": "starts_with", "ends": "ends_with", "contains_s": "contains", "replace_all": "replace"}
HELPERS = {
    "cs_round_js": """fn cs_round_js(x: f64) -> f64 {
    (x + 0.5).floor()
}""",
    "cs_sorted": """fn cs_sorted<T: PartialOrd + Clone>(xs: &[T]) -> Vec<T> {
    let mut v = xs.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v
}""",
    "cs_read_line": """fn cs_read_line() -> String {
    let mut s = String::new();
    std::io::stdin().read_line(&mut s).unwrap();
    s.trim_end_matches(['\\r', '\\n']).to_string()
}""",
    "cs_bool_py": """fn cs_bool_py(b: bool) -> String {
    if b {
        "True".to_string()
    } else {
        "False".to_string()
    }
}""",
}
PREC = {"*": 3, "/": 3, "%": 3, "+": 4, "-": 4, "==": 6, "!=": 6, "<": 6, "<=": 6, ">": 6, ">=": 6, "&&": 7, "||": 8}
ESC = {"\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\0"}


def quote(s, q='"'):
    return q + "".join(ESC.get(c, "\\" + c if c == q else c) for c in s) + q


def snake(name):
    from .python import snake as py_snake
    return py_snake(name)


def braces(s):
    return s.replace("{", "{{").replace("}", "}}")


def leaves(e):
    if isinstance(e, A.Name):
        return [e.id]
    if isinstance(e, (A.Index, A.Call, A.Len, A.Intrinsic)):
        return []
    return [x for c in A.children(e) for x in leaves(c)]


def opaque(e):
    if isinstance(e, (A.Call, A.Index, A.Intrinsic)):
        return True
    if isinstance(e, A.Len):
        return False
    return any(opaque(c) for c in A.children(e))


MUTATORS = {"push", "pop", "pop_at", "insert", "remove_at", "sort", "sort_desc", "reverse", "map_put", "map_del",
            "map_incr", "set_add", "set_del"}


class RustBackend(CBackend):
    lang = "rust"
    KEYWORDS = KEYWORDS
    CSTR = False
    CONCAT = True
    ALLMAN = False

    def safe(self, name):
        n = snake(name)
        return n + "_" if n in KEYWORDS else n

    def length_params(self):
        return set()

    def builder_of(self, func):
        return None

    def find_builder(self, f):
        return None

    def loopable(self, stmts, k):
        return False

    def generate(self):
        for f in self.info.all():
            for name in [f.name, *f.vars]:
                if not name.isascii():
                    raise unsupported(f"non-ASCII name '{name}'", f.node or self.m)
        self.need_len = set()
        self.mut_params = self.mutated_params()
        for f in self.info.all():
            self.plans[f] = self.plan(f)
        chunks = [self.function(self.info.funcs[fn.name]) for fn in self.m.functions]
        main = self.main()
        lines = []
        cols = sorted(k for k in self.includes if k in ("BTreeMap", "BTreeSet"))
        uses = []
        if cols:
            names = cols[0] if len(cols) == 1 else "{" + ", ".join(cols) + "}"
            uses = [f"use std::collections::{names};"]
            lines += [(uses[0], self.includes[cols[0]]), ("", None)]
        for name, g in self.helpers.items():
            lines += [(x, g) for x in HELPERS[name].split("\n")] + [("", None)]
        for chunk in chunks:
            lines += chunk + [("", None)]
        self.entry = len(lines)
        lines += main
        self.prelude = uses + [HELPERS[n] for n in self.helpers]
        self.imports = uses + [f"fn {n}() helper" for n in self.helpers]
        return lines

    def rspec(self, e):
        if not isinstance(e, A.Intrinsic):
            return None
        n = e.name
        if n == "fixed" and isinstance(e.args[1], A.IntLit):
            return f":.{e.args[1].value}", e.args[0]
        if n in ("rjust", "ljust") and isinstance(e.args[1], A.IntLit):
            flag, w, inner = ">" if n == "rjust" else "<", e.args[1].value, e.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name == "fixed" and isinstance(inner.args[1], A.IntLit):
                return f":{flag}{w}.{inner.args[1].value}", inner.args[0]
            if isinstance(inner, A.Intrinsic) and inner.name in ("i2s", "f2s"):
                return f":{flag}{w}", inner.args[0]
            return f":{flag}{w}", inner
        return None

    def key_ref(self, e, t):
        if t == STR:
            return self.value(e, "&str")
        k, p = self.num(e, "i64")
        return f"&{f'({k})' if p else k}"

    def map_value(self, e):
        n, args = e.name, e.args
        if n in ("map_new", "set_new"):
            kind = "BTreeMap" if n == "map_new" else "BTreeSet"
            self.include(kind, self.g)
            return f"{kind}::new()", 0
        t = args[0].ty
        k, v = (mkey(t), mval(t)) if is_map(t) else (selem(t), None)
        x, p = self.rx(args[0])
        r = f"({x})" if p else x
        key = self.key_ref(args[1], k) if len(args) > 1 else None
        if n == "map_get":
            return f"{r}[{key}]" + ("" if self.copyable(v) else ".clone()"), 0
        if n == "map_get_or":
            how = "copied" if self.copyable(v) else "cloned"
            return f"{r}.get({key}).{how}().unwrap_or({self.value(args[2], self.scalar(v))})", 0
        if n == "map_has":
            return f"{r}.contains_key({key})", 0
        if n in ("map_del", "set_del"):
            return f"{r}.remove({key})", 0
        if n in ("map_len", "set_len"):
            return f"{r}.len() as i64", 2
        if n == "map_put":
            return f"{r}.insert({self.value(args[1], self.scalar(k))}, {self.value(args[2], self.scalar(v))})", 0
        if n == "map_incr":
            zero = "0.0" if v == FLOAT else "0"
            inc = self.value(args[2], self.scalar(v))
            return f"*{r}.entry({self.value(args[1], self.scalar(k))}).or_insert({zero}) += {inc}", 0
        if n == "map_sorted_keys":
            return f"{r}.keys().cloned().collect::<Vec<{self.scalar(k)}>>()", 0
        if n == "set_add":
            return f"{r}.insert({self.value(args[1], self.scalar(k))})", 0
        if n == "set_has":
            return f"{r}.contains({key})", 0
        if n == "set_sorted":
            return f"{r}.iter().cloned().collect::<Vec<{self.scalar(k)}>>()", 0
        raise unsupported(f"library call @{n} in Rust", e)

    def receiver(self, e):
        if isinstance(e, A.IntLit) and e.ty != FLOAT:
            text = f"{e.value}i64"
            return f"({text})" if e.value < 0 else text
        if isinstance(e, (A.IntLit, A.FloatLit)):
            text = f"{e.value}.0_f64" if isinstance(e, A.IntLit) else f"{e.value!r}_f64"
            return f"({text})" if e.value < 0 else text
        if all(isinstance(n, (A.IntLit, A.FloatLit, A.BinOp, A.UnaryOp)) for n in A.walk(e)):
            first = e
            while not isinstance(first, (A.IntLit, A.FloatLit)):
                first = first.operand if isinstance(first, A.UnaryOp) else first.left
            self.wide.add(id(first))
        text, p = self.num(e, "i64") if e.ty in (INT, IDX) else self.rx(e)
        return f"({text})" if p else text

    def library(self, e):
        n, args = e.name, e.args
        arg = lambda a: self.num(a, "i64")[0] if a.ty in (INT, IDX) else self.rx(a)[0]
        if n == "read_line":
            self.helpers.setdefault("cs_read_line", self.g)
            return "cs_read_line()", 0
        if n == "exit":
            x, p = self.num(args[0], "i64")
            return f"std::process::exit({f'({x})' if p > 2 else x} as i32)", 0
        if n in ("fixed", "rjust", "ljust"):
            got = self.rspec(e)
            if got is None:
                raise unsupported("a format width or precision that is not a constant in Rust", e)
            return f"format!({quote('{' + got[0] + '}')}, {self.rx(got[1])[0]})", 0
        if n in ("pi", "e"):
            return f"std::f64::consts::{'PI' if n == 'pi' else 'E'}", 0
        if n in ("round_js", "b2s_py"):
            name = "cs_round_js" if n == "round_js" else "cs_bool_py"
            self.helpers.setdefault(name, self.g)
            return f"{name}({arg(args[0])})", 0
        if n == "ord":
            x, xp = self.rx(args[0])
            return f"{f'({x})' if xp > 2 else x} as i64", 2
        if n == "chr":
            x, xp = self.num(args[0], "i64")
            return f"({f'({x})' if xp > 2 else x} as u8) as char", 2
        if n == "pow_i":
            x, xp = self.num(args[1], "i64")
            return f"{self.receiver(args[0])}.pow({f'({x})' if xp > 2 else x} as u32)", 0
        if n in ("s2i", "s2f"):
            return f"{self.receiver(args[0])}.trim().parse::<{'i64' if n == 's2i' else 'f64'}>().unwrap()", 0
        if n == "trim":
            return f"{self.receiver(args[0])}.trim().to_string()", 0
        if n in TEXT:
            rest = ", ".join(self.value(a, "&str") for a in args[1:])
            return f"{self.receiver(args[0])}.{TEXT[n]}({rest})", 0
        if n == "contains_c":
            return f"{self.receiver(args[0])}.contains({self.char(args[1])[0]})", 0
        if n == "find":
            return f"{self.receiver(args[0])}.find({self.value(args[1], '&str')}).map(|i| i as i64).unwrap_or(-1)", 0
        if n == "repeat":
            x, xp = self.num(args[1], "i64")
            return f"{self.receiver(args[0])}.repeat({f'({x})' if xp > 2 else x} as usize)", 0
        if n == "substr":
            s, a, b = args
            lo = "" if isinstance(a, A.IntLit) and a.value == 0 else self.index(a)
            hi = "" if isinstance(b, A.Len) and A.same(b.arg, s) else self.index(b)
            return f"{self.receiver(s)}[{lo}..{hi}].to_string()", 0
        return f"{self.receiver(args[0])}.{METHODS[n]}({', '.join(arg(a) for a in args[1:])})", 0

    def element_writes(self, f):
        out = set()
        for s in A.walk_all(f.body):
            targets = []
            if isinstance(s, (A.Assign, A.AugAssign)):
                targets = [s.target]
            elif isinstance(s, A.TupleAssign):
                targets = s.targets
            elif isinstance(s, A.Swap):
                targets = [s.a, s.b]
            for x in targets:
                while isinstance(x, A.Index):
                    x = x.target
                    if isinstance(x, A.Name):
                        out.add(x.id)
            if isinstance(s, A.Intrinsic) and s.name in MUTATORS and isinstance(s.args[0], A.Name):
                out.add(s.args[0].id)
        return out

    def mutated_params(self):
        need = {(f.name, p) for f in self.info.funcs.values() for p in self.element_writes(f) if p in f.params}
        changed = True
        while changed:
            changed = False
            for f in self.info.all():
                for c in A.walk_all(f.body):
                    if isinstance(c, A.Call):
                        g = self.info.funcs[c.func]
                        for a, q in zip(c.args, g.params):
                            if isinstance(a, A.Name) and (g.name, q) in need and a.id in f.params \
                                    and (f.name, a.id) not in need:
                                need.add((f.name, a.id))
                                changed = True
        return need

    def mutated_arrays(self, f):
        out = self.element_writes(f)
        for c in A.walk_all(f.body):
            if isinstance(c, A.Call):
                g = self.info.funcs[c.func]
                out |= {a.id for a, q in zip(c.args, g.params) if isinstance(a, A.Name) and (g.name, q) in self.mut_params}
        return out

    def ptype(self, f, name):
        t = f.vars[name]
        if is_map(t) or is_set(t):
            return f"&{'mut ' if (f.name, name) in self.mut_params else ''}{self.scalar(t)}"
        if is_list(t):
            inner = self.scalar(elem(t) or INT)
            return f"&mut Vec<{inner}>" if (f.name, name) in self.mut_params else f"&[{inner}]"
        return "&str" if t == STR else self.scalar(t)

    def scalar(self, t):
        if is_map(t):
            self.include("BTreeMap", self.g)
            return f"BTreeMap<{self.scalar(mkey(t))}, {self.scalar(mval(t))}>"
        if is_set(t):
            self.include("BTreeSet", self.g)
            return f"BTreeSet<{self.scalar(selem(t))}>"
        if is_list(t):
            return f"Vec<{self.scalar(elem(t) or INT)}>"
        return {INT: "i64", IDX: "i64", BOOL: "bool", CHAR: "char", STR: "String", FLOAT: "f64"}[t]

    def plan(self, f):
        p = Plan(set(f.vars) | set(self.info.funcs))
        if f.node is not None:
            written = {n for s in A.walk_all(f.body) if isinstance(s, A.Stmt) for n in f.params if A.writes(s, n)}
            p.params = [f"{'mut ' if n in written else ''}{self.safe(n)}: {self.ptype(f, n)}" for n in f.params]
            p.ret = "" if f.ret == VOID else self.scalar(f.ret)
            p.sig = f"fn {self.safe(f.name)}({', '.join(p.params)}){' -> ' + p.ret if p.ret else ''}"
        for name, kind in f.kinds.items():
            if kind == "local":
                self.place(name, f.body, p.decl)
        return p

    def start(self, f):
        super().start(f)
        self.usize = set()
        indexed = {n for x in A.walk_all(f.body) if isinstance(x, A.Index) for n in A.names(x.index)}
        for s in A.walk_all(f.body):
            if isinstance(s, A.For) and s.kind == "range" and s.step.value > 0 and self.usize_ok(s.start) \
                    and self.usize_ok(s.stop) and (s.var in indexed or any(isinstance(x, A.Len) for x in A.walk(s.stop))):
                self.usize.add(s.var)
        self.owned = self.owned_strings(f)
        self.mut = self.mutables(f)
        self.anchored = self.anchors(f)
        self.reads = self.read_names(f)
        self.receivers = {x.args[0].id for x in A.walk_all(f.body) if isinstance(x, A.Intrinsic) and x.args
                          and isinstance(x.args[0], A.Name) and (x.name in METHODS or x.name in ("pow_i", "s2i", "s2f"))}

    def usize_ok(self, e):
        if isinstance(e, A.IntLit):
            return e.value >= 0
        if isinstance(e, A.Len):
            return True
        if isinstance(e, A.Name):
            return e.id in self.usize
        return isinstance(e, A.BinOp) and e.op in "+-*" and self.usize_ok(e.left) and self.usize_ok(e.right)

    def owned_strings(self, f):
        strs = {n for n, t in f.vars.items() if t == STR and f.kinds[n] == "local"}
        owned = {s.var for s in A.walk_all(f.body) if isinstance(s, A.For) and s.kind == "each"
                 and (is_list(s.iter.ty) or is_map(s.iter.ty))}
        changed = True
        while changed:
            changed = False
            for s in A.walk_all(f.body):
                if isinstance(s, A.AugAssign) and isinstance(s.target, A.Name) and s.target.id in strs:
                    hit = s.target.id
                elif isinstance(s, A.Assign) and isinstance(s.target, A.Name) and s.target.id in strs:
                    v = s.value
                    borrowed = isinstance(v, A.StrLit) or isinstance(v, A.Name) and v.ty == STR and v.id not in owned
                    hit = None if borrowed else s.target.id
                elif isinstance(s, A.TupleAssign):
                    hits = [t.id for t, v in zip(s.targets, s.values) if isinstance(t, A.Name) and t.id in strs
                            and not (isinstance(v, A.StrLit) or isinstance(v, A.Name) and v.ty == STR and v.id not in owned)]
                    hit = hits[0] if hits else None
                    for h in hits[1:]:
                        if h not in owned:
                            owned.add(h)
                            changed = True
                else:
                    continue
                if hit and hit not in owned:
                    owned.add(hit)
                    changed = True
        return owned

    def mutables(self, f):
        out = set(self.mutated_arrays(f))
        for name, kind in f.kinds.items():
            d = self.p.decl.get(name)
            if kind == "local" and d and self.path_writes(f.body, name, d[1]) > 1:
                out.add(name)
        return out

    def path_writes(self, stmts, name, home):
        n = 0
        for s in stmts:
            if isinstance(s, A.If):
                n += max(self.path_writes(s.body, name, home), self.path_writes(s.orelse, name, home))
            elif isinstance(s, (A.While, A.For)):
                inner = self.path_writes(s.body, name, home)
                n += inner if inner == 0 or self.holds([s], home) else 2
            elif A.writes(s, name):
                n += 1
        return n

    def holds(self, stmts, home):
        return any(s is home or b is home or self.holds(b, home) for s in stmts for b in [*A.blocks(s), []])

    def anchors(self, f):
        parent = {}

        def find(x):
            while parent.setdefault(x, x) != x:
                x = parent[x]
            return x

        anchored = set()

        def group(names, fixed=False):
            names = list(names)
            for n in names[1:]:
                parent[find(n)] = find(names[0])
            if fixed:
                anchored.update(names)

        for n in f.params:
            if f.vars[n] in (INT, IDX):
                anchored.add(n)
        for s in A.walk_all(f.body):
            if isinstance(s, A.Assign) and isinstance(s.target, A.Name) and f.vars[s.target.id] in (INT, IDX):
                group([s.target.id] + leaves(s.value), opaque(s.value))
            elif isinstance(s, A.AugAssign) and isinstance(s.target, A.Name) and f.vars[s.target.id] in (INT, IDX):
                group([s.target.id] + leaves(s.value), opaque(s.value))
            elif isinstance(s, A.TupleAssign):
                for t, v in zip(s.targets, s.values):
                    if isinstance(t, A.Name) and f.vars[t.id] in (INT, IDX):
                        group([t.id] + leaves(v), opaque(v))
            elif isinstance(s, A.For) and s.kind == "range":
                group([s.var] + leaves(s.start) + leaves(s.stop), s.var in self.usize)
            elif isinstance(s, A.Return) and s.value is not None and f.ret in (INT, IDX):
                group(leaves(s.value), True)
            elif isinstance(s, (A.BinOp, A.Compare)) and {s.left.ty, s.right.ty, s.ty} & {INT, IDX}:
                group(leaves(s), opaque(s.left) or opaque(s.right))
            elif isinstance(s, A.Call):
                for a in s.args:
                    group(leaves(a), True)
            elif isinstance(s, A.Index):
                group(leaves(s.target), True)
        roots = {find(n) for n in anchored}
        return {n for n in f.vars if find(n) in roots}

    def read_names(self, f):
        targets = set()
        for s in A.walk_all(f.body):
            if isinstance(s, A.Assign) and isinstance(s.target, A.Name):
                targets.add(id(s.target))
            elif isinstance(s, A.TupleAssign):
                targets |= {id(t) for t in s.targets if isinstance(t, A.Name)}
        return {n.id for n in A.walk_all(f.body) if isinstance(n, A.Name) and id(n) not in targets}

    def vtype(self, name):
        t = self.f.vars[name]
        if self.f.kinds[name] == "parameter":
            return self.ptype(self.f, name)
        if t in (INT, IDX):
            return "usize" if name in self.usize else "i64"
        if t == STR:
            return "String" if name in self.owned else "&str"
        return self.scalar(t)

    def main(self):
        self.start(self.info.main)
        self.tail = None
        self.line("fn main()", ENTRY)
        self.open(ENTRY)
        self.block(self.info.main.body)
        self.close(ENTRY)
        return self.out

    def function(self, f):
        self.start(f)
        g = f.node.group
        self.line(self.p.sig, g)
        self.open(g)
        body = f.body
        self.tail = body[-1] if body and isinstance(body[-1], A.Return) and body[-1].value is not None else None
        self.block(body)
        self.close(g)
        return self.out

    def nat(self, e):
        if isinstance(e, A.IntLit):
            return "lit"
        if isinstance(e, A.Name):
            return self.vtype(e.id)
        if isinstance(e, A.Len):
            return "usize"
        if isinstance(e, A.BinOp) and e.ty in (INT, IDX):
            kinds = {self.nat(e.left), self.nat(e.right)}
            return "i64" if "i64" in kinds else "usize" if "usize" in kinds else "lit"
        if isinstance(e, A.UnaryOp) and e.op == "-":
            return "lit" if self.nat(e.operand) == "lit" else "i64"
        if e.ty in (INT, IDX):
            return "i64"
        return None

    def num(self, e, want):
        have = self.nat(e)
        if isinstance(e, A.BinOp) and want == "i64" and have != "i64":
            have = "i64" if have == "usize" else have
            return self.rx(e, "i64")
        text, p = self.rx(e, have if have in ("i64", "usize") else want)
        if have in ("lit", want) or want is None:
            return text, p
        return f"{f'({text})' if p > 2 else text} as {want}", 2

    def rx(self, e, want=None):
        if isinstance(e, A.IntLit) and e.ty == FLOAT:
            return f"{e.value}.0" + ("_f64" if id(e) in self.wide else ""), 1 if e.value < 0 else 0
        if isinstance(e, A.FloatLit):
            return repr(e.value) + ("_f64" if id(e) in self.wide else ""), 1 if e.value < 0 else 0
        if isinstance(e, A.IntLit):
            text = str(e.value) + ("i64" if id(e) in self.wide else "")
            return text, 1 if e.value < 0 else 0
        if isinstance(e, A.Intrinsic) and e.name in ("i2f", "f2i"):
            x, xp = self.rx(e.args[0])
            return f"{f'({x})' if xp > 2 else x} as {'f64' if e.name == 'i2f' else 'i64'}", 2
        if isinstance(e, A.Intrinsic) and e.name in MAPOPS:
            return self.map_value(e)
        if isinstance(e, A.Intrinsic) and e.name in LISTOPS:
            return self.list_value(e)
        if isinstance(e, A.Intrinsic):
            return self.library(e)
        if isinstance(e, A.BoolLit):
            return ("true" if e.value else "false"), 0
        if isinstance(e, A.StrLit):
            self.ascii(e)
            return quote(e.value), 0
        if isinstance(e, A.CharLit):
            self.ascii(e)
            return quote(e.value, "'"), 0
        if isinstance(e, A.Name):
            return self.safe(e.id), 0
        if isinstance(e, A.Len):
            a = e.arg
            if isinstance(a, A.ArrayLit):
                return f"{self.array(a, '')}.len()", 0
            text, p = self.rx(a)
            return f"{f'({text})' if p else text}.len()", 0
        if isinstance(e, A.Index):
            target = self.rx(e.target)[0]
            i = self.index(e.index)
            if e.target.ty == STR:
                return f"{target}.as_bytes()[{i}] as char", 2
            return f"{target}[{i}]", 0
        if isinstance(e, A.Call):
            return self.call(e), 0
        if isinstance(e, A.ArrayLit):
            return self.array(e, "vec!"), 0
        if isinstance(e, A.UnaryOp):
            if e.op == "!" and e.operand.ty in (INT, IDX):
                x, xp = self.num(e.operand, "i64")
                return f"{f'({x})' if xp >= PREC['=='] else x} == 0", PREC["=="]
            x, xp = self.num(e.operand, "i64") if e.op == "-" and e.operand.ty in (INT, IDX) else self.rx(e.operand)
            if xp > 1 or (e.op == "-" and x.startswith("-")):
                x = f"({x})"
            return e.op + x, 1
        if isinstance(e, A.BoolOp):
            p = PREC[e.op]
            l, lp = self.cond(e.left)
            r, rp = self.cond(e.right)
            return f"{f'({l})' if lp > p else l} {e.op} {f'({r})' if rp >= p else r}", p
        if isinstance(e, A.BinOp) and e.ty in (STR, CHAR):
            return self.format(e), 0
        p = PREC[e.op]
        l, r = e.left, e.right
        if isinstance(e, A.Compare):
            if CHAR in (l.ty, r.ty):
                lt, lp = self.char(l)
                rt, rp = self.char(r)
            elif l.ty in (INT, IDX):
                kinds = {self.nat(l), self.nat(r)}
                want = "i64" if "i64" in kinds else "usize" if "usize" in kinds else None
                (lt, lp), (rt, rp) = self.num(l, want), self.num(r, want)
            else:
                (lt, lp), (rt, rp) = self.rx(l), self.rx(r)
            paren = lp >= p or lp == 2 and e.op in ("<", "<=")
            return f"{f'({lt})' if paren else lt} {e.op} {f'({rt})' if rp >= p else rt}", p
        if constant(e):
            seen = []
            values(e, seen)
            if any(not -2 ** 31 <= v < 2 ** 31 for v in seen):
                self.wide |= {id(leftmost(n)) for n in A.walk(e) if isinstance(n, A.BinOp)}
        want = want if want in ("i64", "usize") else self.nat(e)
        want = want if want in ("i64", "usize") else None
        lt, lp = self.num(l, want)
        rt, rp = self.num(r, want)
        return f"{f'({lt})' if lp > p else lt} {e.op} {f'({rt})' if rp >= p else rt}", p

    def ex(self, e):
        return self.rx(e)[0]

    def cond(self, e):
        if e.ty in (INT, IDX):
            t, p = self.num(e, None)
            return f"{f'({t})' if p >= PREC['!='] else t} != 0", PREC["!="]
        return self.rx(e)

    def index(self, e):
        if self.nat(e) == "i64":
            t, p = self.rx(e, "i64")
            return f"{f'({t})' if p > 2 else t} as usize"
        return self.rx(e, "usize")[0]

    def char(self, e):
        if isinstance(e, A.StrLit) and len(e.value) == 1:
            return quote(e.value, "'"), 0
        return self.rx(e)

    def array(self, e, prefix):
        if not e.items and prefix == "vec!":
            return "Vec::new()"
        inner = self.scalar(elem(e.ty) or INT)
        return f"{prefix}[{', '.join(self.value(x, inner) for x in e.items)}]"

    def copyable(self, t):
        return t in (INT, IDX, FLOAT, BOOL, CHAR)

    def list_value(self, e):
        n, args = e.name, e.args
        xs = args[0] if args else None
        el = elem(xs.ty) if xs is not None and is_list(xs.ty) else None
        inner = self.scalar(el or INT)
        if n == "list_fill":
            return f"vec![{self.value(args[0], self.scalar(elem(e.ty) or INT))}; {self.index(args[1])}]", 0
        if n == "grid":
            v = self.value(args[2], self.scalar(elem(elem(e.ty)) or INT))
            return f"vec![vec![{v}; {self.index(args[1])}]; {self.index(args[0])}]", 0
        if n == "s2ints":
            return f"{self.receiver(xs)}.split_whitespace().map(|t| t.parse::<i64>().unwrap()).collect::<Vec<i64>>()", 0
        if n in ("split", "split_ws"):
            recv = self.receiver(xs)
            how = f"split({self.value(args[1], '&str')})" if n == "split" else "split_whitespace()"
            return f"{recv}.{how}.map(String::from).collect::<Vec<String>>()", 0
        if n == "join":
            return f"{self.receiver(args[1])}.join({self.value(args[0], '&str')})", 0
        if n == "sorted":
            self.helpers.setdefault("cs_sorted", self.g)
            return f"cs_sorted({self.value(xs, '&[' + inner + ']')})", 0
        r = self.receiver(xs)
        if n == "push":
            return f"{r}.push({self.value(args[1], inner)})", 0
        if n == "pop":
            return f"{r}.pop().unwrap()", 0
        if n in ("pop_at", "remove_at"):
            return f"{r}.remove({self.index(args[1])})", 0
        if n == "insert":
            return f"{r}.insert({self.index(args[1])}, {self.value(args[2], inner)})", 0
        if n in ("index_of", "contains_l"):
            v = self.value(args[1], "&str") if el == STR else self.num(args[1], "i64")[0] if el in (INT, IDX) \
                else self.ex(args[1])
            if n == "index_of":
                return f"{r}.iter().position(|e| *e == {v}).map(|i| i as i64).unwrap_or(-1)", 0
            return (f"{r}.iter().any(|e| e == {v})" if el == STR else f"{r}.contains(&{v})"), 0
        if n in ("sort", "sort_desc"):
            a, b = ("a", "b") if n == "sort" else ("b", "a")
            if el == FLOAT:
                return f"{r}.sort_by(|a, b| {a}.partial_cmp({b}).unwrap())", 0
            return (f"{r}.sort()" if n == "sort" else f"{r}.sort_by(|a, b| b.cmp(a))"), 0
        if n == "reverse":
            return f"{r}.reverse()", 0
        if n == "lcopy":
            return f"{r}.to_vec()", 0
        if n == "lslice":
            a, b = args[1], args[2]
            lo = "" if isinstance(a, A.IntLit) and a.value == 0 else self.index(a)
            hi = "" if isinstance(b, A.Len) and A.same(b.arg, xs) else self.index(b)
            return f"{r}[{lo}..{hi}].to_vec()", 0
        if n == "sum":
            return f"{r}.iter().sum::<{inner}>()", 0
        if n in ("lmin", "lmax"):
            if el == FLOAT:
                start = "f64::INFINITY" if n == "lmin" else "f64::NEG_INFINITY"
                return f"{r}.iter().cloned().fold({start}, f64::{n[1:]})", 0
            if el == STR:
                return f"{r}.iter().{n[1:]}().unwrap().clone()", 0
            return f"*{r}.iter().{n[1:]}().unwrap()", 1
        raise unsupported(f"library call @{n} in Rust", e)

    def format(self, e):
        parts = []

        def flat(x):
            if isinstance(x, A.BinOp) and x.ty in (STR, CHAR) and x.op == "+":
                flat(x.left)
                flat(x.right)
            else:
                parts.append(x)

        flat(e)
        fmt, args = "", []
        for x in parts:
            got = self.rspec(x)
            if isinstance(x, (A.StrLit, A.CharLit)):
                self.ascii(x)
                fmt += braces(x.value)
            elif got:
                fmt += "{" + got[0] + "}"
                args.append(self.rx(got[1])[0])
            else:
                fmt += "{}"
                args.append(self.rx(x)[0])
        return f"format!({', '.join([quote(fmt)] + args)})"

    def value(self, e, want):
        if want in ("i64", "usize"):
            return self.num(e, want)[0]
        if want == "String":
            if isinstance(e, A.StrLit):
                self.ascii(e)
                return "String::new()" if not e.value else f"String::from({quote(e.value)})"
            if isinstance(e, A.CharLit) or e.ty == CHAR:
                t, p = self.rx(e)
                return f"{f'({t})' if p else t}.to_string()"
            if isinstance(e, A.Name):
                return f"{self.safe(e.id)}.{'clone' if self.vtype(e.id) == 'String' else 'to_string'}()"
            if isinstance(e, A.Index) and is_list(e.target.ty):
                return f"{self.ex(e)}.clone()"
            return self.ex(e)
        if want == "&str":
            if isinstance(e, A.Name) and self.vtype(e.id) == "&str" or isinstance(e, A.StrLit):
                return self.ex(e)
            if e.ty == CHAR:
                return f"&{self.value(e, 'String')}"
            return f"&{self.ex(e)}"
        if want == "char":
            return self.char(e)[0]
        if want.startswith("&["):
            if isinstance(e, A.ArrayLit):
                return self.array(e, "&")
            if isinstance(e, A.Name):
                return self.safe(e.id) if self.f.kinds.get(e.id) == "parameter" else f"&{self.safe(e.id)}"
            return f"&{self.ex(e)}"
        if want.startswith("&mut Vec<"):
            if isinstance(e, A.ArrayLit):
                return self.array(e, "&mut vec!")
            if isinstance(e, A.Name):
                return self.safe(e.id) if self.f.kinds.get(e.id) == "parameter" else f"&mut {self.safe(e.id)}"
            return f"&mut {self.ex(e)}"
        if want.startswith(("&BTree", "&mut BTree")):
            amp = want[:want.index("BTree")]
            if isinstance(e, A.Name):
                return self.safe(e.id) if self.f.kinds.get(e.id) == "parameter" else f"{amp}{self.safe(e.id)}"
            return f"{amp}{self.ex(e)}"
        if want.startswith("BTree"):
            if isinstance(e, A.Name) and self.f.kinds.get(e.id) == "parameter":
                return f"{self.safe(e.id)}.clone()"
            return self.ex(e)
        if want.startswith("Vec<"):
            if isinstance(e, A.Name) and self.f.kinds.get(e.id) == "parameter":
                return f"{self.safe(e.id)}.to_vec()"
            if isinstance(e, A.Index):
                return f"{self.ex(e)}.clone()"
            return self.ex(e)
        if want == "bool":
            return self.cond(e)[0] if e.ty in (INT, IDX) else self.ex(e)
        return self.ex(e)

    def result(self, e):
        if isinstance(e, A.Name) and self.vtype(e.id) == "String":
            return self.safe(e.id)
        return self.value(e, self.p.ret)

    def call(self, c, extra=()):
        g = self.info.funcs[c.func]
        args = [self.value(a, self.ptype(g, p)) for a, p in zip(c.args, g.params)]
        return f"{self.safe(c.func)}({', '.join(args)})"

    def let(self, names, values, g):
        if len(names) == 1:
            n, v = names[0], values[0]
            ty = self.vtype(n)
            text = self.value(v, ty)
            literal = all(isinstance(x, (A.IntLit, A.FloatLit, A.BinOp, A.UnaryOp)) for x in A.walk(v))
            if ty == "i64" and (n not in self.anchored or n in self.receivers) and constant(v)                     or ty == "f64" and n in self.receivers and literal:
                first = v
                while not isinstance(first, (A.IntLit, A.FloatLit)):
                    first = first.operand if isinstance(first, A.UnaryOp) else first.left
                self.wide.add(id(first))
                text = self.value(v, ty)
            note = f": {ty}" if isinstance(v, A.Intrinsic) and v.name in ("map_new", "set_new") else ""
            self.emit(f"let {'mut ' if n in self.mut else ''}{self.safe(n)}{note} = {text};", g)
        else:
            for v, n in zip(values, names):
                if isinstance(v, A.IntLit) and self.vtype(n) == "i64":
                    self.wide.add(id(v))
            pats = ", ".join(f"{'mut ' if n in self.mut else ''}{self.safe(n)}" for n in names)
            vals = ", ".join(self.value(v, self.vtype(n)) for n, v in zip(names, values))
            self.emit(f"let ({pats}) = ({vals});", g)
        self.declared |= set(names)

    def hoist(self, v, g):
        self.emit(f"let {'mut ' if v in self.mut else ''}{self.safe(v)}: {self.vtype(v)};", g)

    def target_type(self, t):
        return self.vtype(t.id) if isinstance(t, A.Name) else self.scalar(t.ty)

    def place_text(self, t):
        return self.ex(t)

    def stmt(self, s):
        g = self.g = s.group
        if isinstance(s, A.Assign):
            t = s.target
            if isinstance(t, A.Name) and self.p.decl.get(t.id) == ("inline", s) and t.id not in self.declared:
                self.let([t.id], [s.value], g)
            elif isinstance(t, A.Name) and self.vtype(t.id) == "String" and self.build(t.id, s.value, g):
                pass
            else:
                self.emit(f"{self.ex(t)} = {self.value(s.value, self.target_type(t))};", g)
        elif isinstance(s, A.AugAssign):
            t = s.target
            if t.ty == STR:
                self.build(t.id, A.BinOp("+", t, s.value, ty=STR), g)
            else:
                self.emit(f"{self.ex(t)} {s.op}= {self.value(s.value, self.target_type(t))};", g)
        elif isinstance(s, A.TupleAssign):
            names = [t.id for t in s.targets if isinstance(t, A.Name)]
            new = [n for n in names if self.p.decl.get(n) == ("inline", s) and n not in self.declared]
            if new and len(new) == len(s.targets):
                self.let(names, s.values, g)
                return
            for n in new:
                self.declared.add(n)
                self.hoist(n, g)
            lhs = ", ".join(self.ex(t) for t in s.targets)
            rhs = ", ".join(self.value(v, self.target_type(t)) for t, v in zip(s.targets, s.values))
            self.emit(f"({lhs}) = ({rhs});", g)
        elif isinstance(s, A.Swap):
            a, b = s.a, s.b
            if isinstance(a, A.Index) and isinstance(b, A.Index) and A.same(a.target, b.target):
                self.emit(f"{self.ex(a.target)}.swap({self.index(a.index)}, {self.index(b.index)});", g)
            else:
                self.emit(f"({self.ex(a)}, {self.ex(b)}) = ({self.ex(b)}, {self.ex(a)});", g)
        elif isinstance(s, A.If):
            self.emit(f"if {self.cond(s.test)[0]}", g)
            self.body(s.body, g)
            o = s.orelse
            while len(o) == 1 and isinstance(o[0], A.If):
                g = self.g = o[0].group
                self.else_line(f"else if {self.cond(o[0].test)[0]}", g)
                self.body(o[0].body, g)
                o = o[0].orelse
            if o:
                self.else_line("else", g)
                self.body(o, g)
        elif isinstance(s, A.While):
            forever = isinstance(s.test, A.BoolLit) and s.test.value
            self.emit("loop" if forever else f"while {self.cond(s.test)[0]}", g)
            self.body(s.body, g)
        elif isinstance(s, A.For):
            self.for_(s)
        elif isinstance(s, A.Return) and s is self.tail:
            self.emit(self.result(s.value), g)
        elif isinstance(s, A.Return):
            self.emit("return;" if s.value is None else f"return {self.result(s.value)};", g)
        elif isinstance(s, A.ExprStmt):
            self.emit(f"{self.ex(s.expr)};", g)
        elif isinstance(s, A.Break):
            self.emit("break;", g)
        elif isinstance(s, A.Continue):
            self.emit("continue;", g)
        elif isinstance(s, A.Print):
            fmt, args = [], []
            for a in s.args:
                if isinstance(a, (A.StrLit, A.CharLit)):
                    self.ascii(a)
                    fmt.append(braces(a.value))
                    continue
                got = self.rspec(a)
                if got:
                    fmt.append("{" + got[0] + "}")
                    a = got[1]
                else:
                    fmt.append("{:?}" if is_list(a.ty) else "{}")
                if constant(a):
                    self.wide.add(id(leftmost(a)))
                args.append(self.ex(a))
            ending = getattr(s, "ending", "\n")
            if ending == "\n":
                self.emit(f"println!({', '.join([quote(' '.join(fmt))] + args)});" if s.args else "println!();", g)
            else:
                if s.args:
                    self.emit(f"print!({', '.join([quote(' '.join(fmt))] + args)});", g)
                if ending:
                    self.emit(f"print!({quote(braces(ending))});", g)

    def build(self, name, v, g):
        out = self.safe(name)
        if isinstance(v, A.BinOp) and v.op == "+" and v.ty == STR:
            l, r = v.left, v.right
            for other, at_end in ((r, True), (l, False)):
                mine = l if at_end else r
                if isinstance(mine, A.Name) and mine.id == name and name not in A.names(other):
                    if other.ty == CHAR:
                        self.emit(f"{out}.push({self.char(other)[0]});" if at_end
                                  else f"{out}.insert(0, {self.char(other)[0]});", g)
                    else:
                        text = self.value(other, "&str")
                        self.emit(f"{out}.push_str({text});" if at_end else f"{out}.insert_str(0, {text});", g)
                    return True
        self.emit(f"{out} = {self.value(v, 'String')};", g)
        return True

    def for_(self, s):
        g = s.group
        var = self.safe(s.var) if s.var in self.reads else "_"
        keyed = isinstance(s.iter, A.Intrinsic) and s.iter.name == "map_sorted_keys"
        if s.kind == "each" and (is_map(s.iter.ty) or keyed):
            it = s.iter.args[0] if keyed else s.iter
            if isinstance(it, A.Name) and any(isinstance(x, A.Intrinsic) and x.name in MUTATORS and x.args
                                              and A.same(x.args[0], it) for x in A.walk_all(s.body)):
                raise unsupported("changing a dict while looping over it", s)
            if not keyed:
                self.note("order", "Rust's BTreeMap visits keys in sorted order; the source visits them in insertion "
                                   "order.")
            r = self.receiver(it)
            copy = self.copyable(mkey(it.ty))
            src = f"{r}.keys()" if copy else f"{r}.keys().cloned()"
            self.emit(f"for {'&' if copy and var != '_' else ''}{var} in {src}", g)
        elif s.kind == "each" and isinstance(s.iter, A.Intrinsic) and s.iter.name == "set_sorted":
            st = s.iter.args[0]
            copy = self.copyable(selem(st.ty))
            src = f"{self.receiver(st)}.iter()" + ("" if copy else ".cloned()")
            self.emit(f"for {'&' if copy and var != '_' else ''}{var} in {src}", g)
        elif s.kind == "each":
            it = s.iter
            if it.ty == STR:
                src = self.ex(it) if isinstance(it, A.StrLit) else self.receiver(it)
                self.emit(f"for {var} in {src}.chars()", g)
            else:
                if isinstance(it, A.Name) and it.id in self.mutated_arrays(self.f) and any(
                        isinstance(x, A.Stmt) and it.id in A.names(x) for x in A.walk_all(s.body)):
                    raise unsupported("changing a list while looping over it", s)
                copy = self.copyable(elem(it.ty) or INT)
                if isinstance(it, A.ArrayLit):
                    src, amp = self.array(it, "vec!" if not copy else ""), ""
                else:
                    src = f"{self.receiver(it)}.iter()" + ("" if copy else ".cloned()")
                    amp = "&" if copy and var != "_" else ""
                self.emit(f"for {amp}{var} in {src}", g)
        else:
            ty = "usize" if s.var in self.usize else "i64"
            k = s.step.value
            start, stop = self.num(s.start, ty)[0], self.num(s.stop, ty)[0]
            if k == 1:
                rng = f"{start}..{stop}"
            elif k > 0:
                rng = f"({start}..{stop}).step_by({k})"
            else:
                lo, hi = self.num(self.next_int(s.stop), ty)[0], self.num(self.next_int(s.start), ty)[0]
                rng = f"({lo}..{hi}).rev()" + (f".step_by({-k})" if k != -1 else "")
            self.emit(f"for {var} in {rng}", g)
        self.open(g)
        self.scopes[-1].add(s.var)
        self.block(s.body)
        self.close(g)

    def next_int(self, e):
        if isinstance(e, A.IntLit):
            return A.IntLit(e.value + 1, ty=INT)
        return A.BinOp("+", e, A.IntLit(1, ty=INT), ty=e.ty)

    def ctype_of(self, f, name):
        if f.kinds[name] == "parameter":
            return self.ptype(f, name)
        t = f.vars[name]
        if t in (INT, IDX):
            return "i64"
        return "String" if t == STR else self.scalar(t)

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
                notes.append(f"{self.safe(f.name)} → {self.plans[f].ret or '()'}")
        return list(dict.fromkeys(notes))

    def symbols(self):
        out = []
        for f in self.info.all():
            rows = self.rows(f)
            scope = self.safe(f.name) if f.node is not None else "main"
            if f.node is not None:
                params = ", ".join(ct for _, k, ct in rows if k == "parameter")
                out.append({"name": self.safe(f.name), "kind": "function",
                            "type": f"({params}) → {self.plans[f].ret or '()'}", "scope": "crate"})
            for name, kind, ct in rows:
                out.append({"name": name, "kind": kind, "type": ct, "scope": "loop" if kind == "loop var" else scope})
        return out
