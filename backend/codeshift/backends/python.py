import keyword
import re

from .. import ast as A
from ..semantic import ARR, BOOL, CHAR, FLOAT, IDX, INT, STR, VOID

RESERVED = set(keyword.kwlist) | {"print", "len", "range", "list", "str", "int", "bool", "input", "sum", "min", "max", "abs",
                                   "sorted",
                                   "float", "math", "round", "pow", "ord", "chr", "cs_round_away", "cs_round_js"}
MATHS = {"sqrt", "sin", "cos", "tan", "atan2", "log", "log10", "log2", "exp", "hypot"}
CALLS = {"abs_i": "abs", "abs_f": "abs", "min": "min", "max": "max", "i2s": "str", "f2s": "str", "s2i": "int",
         "s2f": "float", "ord": "ord", "chr": "chr", "b2s_py": "str", "i2f": "float"}
LISTS = {"push": "append", "pop": "pop", "pop_at": "pop", "insert": "insert", "sort": "sort", "reverse": "reverse",
         "split": "split"}
METHODS = {"upper": "upper", "lower": "lower", "trim": "strip", "starts": "startswith", "ends": "endswith",
           "find": "find", "replace_all": "replace", "is_digit": "isdigit", "is_alpha": "isalpha", "is_space": "isspace",
           "is_upper": "isupper", "is_lower": "islower", "cupper": "upper", "clower": "lower"}
HELPERS = {
    "cs_round_away": """def cs_round_away(x):
    r = math.floor(abs(x) + 0.5)
    return float(r if x >= 0 else -r)""",
    "cs_round_js": """def cs_round_js(x):
    return float(math.floor(x + 0.5))""",
}
STRENGTH = {"||": 1, "&&": 2, "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4, "+": 6, "-": 6, "*": 7, "/": 7, "%": 7}
SPELL = {"||": "or", "&&": "and", "/": "//"}
PYTYPE = {INT: "int", IDX: "int", BOOL: "bool", STR: "str", CHAR: "str", ARR: "list[int]", VOID: "None", FLOAT: "float"}


def pytype(t):
    if t in PYTYPE:
        return PYTYPE[t]
    if t.startswith("map<"):
        k, v = t[4:-1].split(",")
        return f"dict[{pytype(k)}, {pytype(v)}]"
    if t.startswith("set<"):
        return f"set[{pytype(t[4:-1])}]"
    return f"list[{pytype(t[5:-1])}]"


def flatten(e):
    if isinstance(e, A.BinOp) and e.op == "+" and e.ty == "str":
        return flatten(e.left) + flatten(e.right)
    return [e]


def snake(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def safe(name):
    name = snake(name)
    return name + "_" if name in RESERVED else name


class PythonBackend:
    lang = "python"

    def __init__(self, module, info):
        self.m = module
        self.info = info
        self.merges = []
        self.notes = {}
        self.entry = 0
        self.prelude = []
        self.need = {}
        self.g = None

    def generate(self):
        self.out = []
        self.depth = 0
        for fn in self.m.functions:
            self.function(fn)
            self.out.append(("", None))
        self.entry = len(self.out)
        self.block(self.m.body)
        if self.entry == len(self.out) and self.out:
            self.out.pop()
            self.entry = len(self.out)
        head, texts = [], []
        mods = [m for m in ("math", "sys") if m in self.need]
        if mods:
            texts.append(("\n".join(f"import {m}" for m in mods), self.need[mods[0]]))
        texts += [(HELPERS[n], g) for n, g in self.need.items() if n in HELPERS]
        for text, g in texts:
            head += [(x, g) for x in text.split("\n")] + [("", None)]
        self.out = head + self.out
        self.entry += len(head)
        self.prelude = [text for text, _ in texts]
        self.imports = [text if text.startswith("import") else f"def {text[4:text.index('(')]}() helper" for text, _ in texts]
        return self.out

    def uses(self, name):
        self.need.setdefault(name, self.g)

    def intrinsic(self, e):
        n, args = e.name, e.args
        if n == "f2i":
            x = args[0]
            if isinstance(x, A.Intrinsic) and x.name in ("floor", "ceil", "trunc"):
                self.uses("math")
                return f"math.{x.name}({self.ex(x.args[0])})", 9
            if isinstance(x, A.Intrinsic) and x.name == "round_even":
                return f"round({self.ex(x.args[0])})", 9
            return f"int({self.ex(x)})", 9
        if n in ("floor", "ceil", "trunc"):
            self.uses("math")
            return f"float(math.{n}({self.ex(args[0])}))", 9
        if n == "round_even":
            return f"float(round({self.ex(args[0])}))", 9
        if n in ("round_away", "round_js"):
            self.uses("math")
            self.uses(f"cs_{n}")
            return f"cs_{n}({self.ex(args[0])})", 9
        if n in ("pow_i", "pow_f"):
            return f"{self.paren(args[0], 9)} ** {self.paren(args[1], 8)}", 8.5
        if n in MATHS or n in ("pi", "e"):
            self.uses("math")
            return (f"math.{n}" if n in ("pi", "e") else f"math.{n}({', '.join(map(self.ex, args))})"), 9
        if n == "b2s":
            return f"str({self.ex(args[0])}).lower()", 9
        if n in LISTS:
            return f"{self.paren(args[0], 9)}.{LISTS[n]}({', '.join(map(self.ex, args[1:]))})", 9
        if n in ("sum", "sorted", "lmin", "lmax"):
            return f"{n.lstrip('l') if n != 'sorted' else n}({self.ex(args[0])})", 9
        if n == "read_line":
            return "input()", 9
        if n == "s2ints":
            return f"list(map(int, {self.paren(args[0], 9)}.split()))", 9
        if n == "exit":
            self.uses("sys")
            return f"sys.exit({self.ex(args[0])})", 9
        if n in ("fixed", "rjust", "ljust"):
            text = self.fstring([e])
            if text:
                return text, 9
            if n == "fixed":
                return f"format({self.ex(args[0])}, \".{args[1].value}f\")", 9
            return f"{self.paren(args[0], 9)}.{n}({self.ex(args[1])})", 9
        if n in ("contains_l", "map_has", "set_has"):
            return f"{self.paren(args[1], 5)} in {self.paren(args[0], 5)}", 4
        if n == "map_new":
            return "{}", 9
        if n == "set_new":
            return "set()", 9
        if n == "map_get":
            return f"{self.paren(args[0], 9)}[{self.ex(args[1])}]", 9
        if n == "map_get_or":
            return f"{self.paren(args[0], 9)}.get({self.ex(args[1])}, {self.ex(args[2])})", 9
        if n in ("map_len", "set_len"):
            return f"len({self.ex(args[0])})", 9
        if n in ("map_sorted_keys", "set_sorted"):
            return f"sorted({self.ex(args[0])})", 9
        if n in ("set_add", "set_del"):
            return f"{self.paren(args[0], 9)}.{'add' if n == 'set_add' else 'discard'}({self.ex(args[1])})", 9
        if n == "index_of":
            xs, v = self.paren(args[0], 9), self.paren(args[1], 5)
            return f"{xs}.index({self.ex(args[1])}) if {v} in {self.paren(args[0], 5)} else -1", 0
        if n == "lcopy":
            return f"{self.paren(args[0], 9)}[:]", 9
        if n == "lslice":
            s, a, b = args
            lo = "" if isinstance(a, A.IntLit) and a.value == 0 else self.ex(a)
            hi = "" if isinstance(b, A.Len) and A.same(b.arg, s) else self.ex(b)
            return f"{self.paren(s, 9)}[{lo}:{hi}]", 9
        if n == "list_fill":
            return f"[{self.ex(args[0])}] * {self.paren(args[1], 8)}", 7
        if n == "grid":
            return f"[[{self.ex(args[2])}] * {self.paren(args[1], 8)} for _ in range({self.ex(args[0])})]", 9
        if n == "split_ws":
            return f"{self.paren(args[0], 9)}.split()", 9
        if n == "join":
            return f"{self.paren(args[0], 9)}.join({self.ex(args[1])})", 9
        if n in METHODS:
            return f"{self.paren(args[0], 9)}.{METHODS[n]}({', '.join(map(self.ex, args[1:]))})", 9
        if n in ("contains_s", "contains_c"):
            return f"{self.paren(args[1], 5)} in {self.paren(args[0], 5)}", 4
        if n == "repeat":
            return f"{self.paren(args[0], 7)} * {self.paren(args[1], 8)}", 7
        if n == "substr":
            s, a, b = args
            lo = "" if isinstance(a, A.IntLit) and a.value == 0 else self.ex(a)
            hi = "" if isinstance(b, A.Len) and A.same(b.arg, s) else self.ex(b)
            return f"{self.paren(s, 9)}[{lo}:{hi}]", 9
        if n in CALLS:
            return f"{CALLS[n]}({', '.join(map(self.ex, args))})", 9
        raise ValueError(n)

    def line(self, text, g):
        self.out.append(("    " * self.depth + text, g))

    def function(self, fn):
        self.line(f"def {safe(fn.name)}({', '.join(safe(p.name) for p in fn.params)}):", fn.group)
        self.suite(fn.body)

    def suite(self, stmts):
        self.depth += 1
        if stmts:
            self.block(stmts)
        else:
            self.line("pass", None)
        self.depth -= 1

    def block(self, stmts):
        for s in stmts:
            self.stmt(s)

    def stmt(self, s):
        g = self.g = s.group
        if isinstance(s, A.Assign):
            self.line(f"{self.ex(s.target)} = {self.ex(s.value)}", g)
        elif isinstance(s, A.AugAssign):
            op = "/" if s.op == "/" and s.target.ty == FLOAT else SPELL.get(s.op, s.op)
            self.line(f"{self.ex(s.target)} {op}= {self.ex(s.value, s.target.ty == FLOAT)}", g)
        elif isinstance(s, A.TupleAssign):
            self.line(f"{', '.join(map(self.ex, s.targets))} = {', '.join(map(self.ex, s.values))}", g)
        elif isinstance(s, A.Swap):
            a, b = self.ex(s.a), self.ex(s.b)
            self.line(f"{a}, {b} = {b}, {a}", g)
        elif isinstance(s, A.If):
            self.line(f"if {self.ex(s.test)}:", g)
            self.suite(s.body)
            o = s.orelse
            while len(o) == 1 and isinstance(o[0], A.If):
                self.line(f"elif {self.ex(o[0].test)}:", o[0].group)
                self.suite(o[0].body)
                o = o[0].orelse
            if o:
                self.line("else:", g)
                self.suite(o)
        elif isinstance(s, A.While):
            self.line(f"while {self.ex(s.test)}:", g)
            self.suite(s.body)
        elif isinstance(s, A.For):
            if s.kind == "each":
                head = self.ex(s.iter)
            else:
                start, stop = self.ex(s.start), self.ex(s.stop)
                one = isinstance(s.step, A.IntLit) and s.step.value == 1
                zero = isinstance(s.start, A.IntLit) and s.start.value == 0
                args = [stop] if zero and one else [start, stop] if one else [start, stop, self.ex(s.step)]
                head = f"range({', '.join(args)})"
            self.line(f"for {safe(s.var)} in {head}:", g)
            self.suite(s.body)
        elif isinstance(s, A.Return):
            self.line("return" if s.value is None else f"return {self.ex(s.value)}", g)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name in ("remove_at", "map_del"):
            self.line(f"del {self.paren(s.expr.args[0], 9)}[{self.ex(s.expr.args[1])}]", g)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name == "map_put":
            m, k, v = s.expr.args
            self.line(f"{self.paren(m, 9)}[{self.ex(k)}] = {self.ex(v)}", g)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name == "map_incr":
            m, k, v = s.expr.args
            zero = "0.0" if v.ty == "float" else "0"
            self.line(f"{self.paren(m, 9)}[{self.ex(k)}] = {self.paren(m, 9)}.get({self.ex(k)}, {zero}) + "
                      f"{self.paren(v, 7)}", g)
        elif isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name == "sort_desc":
            self.line(f"{self.paren(s.expr.args[0], 9)}.sort(reverse=True)", g)
        elif isinstance(s, A.ExprStmt):
            self.line(self.ex(s.expr), g)
        elif isinstance(s, A.Break):
            self.line("break", g)
        elif isinstance(s, A.Continue):
            self.line("continue", g)
        elif isinstance(s, A.Print):
            end = [] if getattr(s, "ending", "\n") == "\n" else [f"end={A.quote(s.ending)}"]
            self.line(f"print({', '.join([*map(self.ex, s.args), *end])})", g)

    def ex(self, e, arith=False):
        return self._ex(e, arith)[0]

    def _ex(self, e, arith=False):
        if isinstance(e, A.Intrinsic) and e.name == "i2f" and arith:
            return self._ex(e.args[0])
        if isinstance(e, A.IntLit):
            return str(e.value), 8 if e.value < 0 else 9
        if isinstance(e, A.FloatLit):
            return repr(e.value), 8 if e.value < 0 else 9
        if isinstance(e, A.Intrinsic):
            return self.intrinsic(e)
        if isinstance(e, A.BoolLit):
            return ("True" if e.value else "False"), 9
        if isinstance(e, (A.StrLit, A.CharLit)):
            return A.quote(e.value), 9
        if isinstance(e, A.ArrayLit):
            return "[" + ", ".join(map(self.ex, e.items)) + "]", 9
        if isinstance(e, A.Name):
            return safe(e.id), 9
        if isinstance(e, A.Index):
            return f"{self.paren(e.target, 9)}[{self.ex(e.index)}]", 9
        if isinstance(e, A.Len):
            return f"len({self.ex(e.arg)})", 9
        if isinstance(e, A.Call):
            return f"{safe(e.func)}({', '.join(map(self.ex, e.args))})", 9
        if isinstance(e, A.UnaryOp):
            if e.op == "!":
                return f"not {self.paren(e.operand, 3)}", 3
            return f"-{self.paren(e.operand, 8)}", 8
        if isinstance(e, A.BinOp) and e.op == "+" and e.ty == "str":
            parts = flatten(e)
            if any(isinstance(x, A.Intrinsic) and x.name in ("fixed", "rjust", "ljust") for x in parts):
                text = self.fstring(parts)
                if text:
                    return text, 9
        p = STRENGTH[e.op]
        num = not isinstance(e, A.BoolOp)
        left = self.paren(e.left, p, cmp=isinstance(e, A.Compare), arith=num)
        right = self.paren(e.right, p + 1, arith=num)
        op = "/" if e.op == "/" and e.ty == FLOAT else SPELL.get(e.op, e.op)
        return f"{left} {op} {right}", p

    def fstring(self, parts):
        out = []
        for x in parts:
            if isinstance(x, (A.StrLit, A.CharLit)):
                out.append(A.quote(x.value)[1:-1].replace("{", "{{").replace("}", "}}"))
                continue
            spec, v = "", x
            if isinstance(v, A.Intrinsic) and v.name in ("rjust", "ljust"):
                width = v.args[1]
                if not isinstance(width, A.IntLit):
                    return None
                inner = v.args[0]
                fixed = isinstance(inner, A.Intrinsic) and inner.name == "fixed"
                spec = ("" if fixed and v.name == "rjust" else ">" if v.name == "rjust" else "<") + str(width.value)
                v = inner
            if isinstance(v, A.Intrinsic) and v.name == "fixed":
                if not isinstance(v.args[1], A.IntLit):
                    return None
                spec += f".{v.args[1].value}f"
                v = v.args[0]
            elif isinstance(v, A.Intrinsic) and v.name in ("i2s", "f2s", "b2s_py"):
                v = v.args[0]
            text = self.ex(v, True)
            if any(c in text for c in "\"\\{}"):
                return None
            out.append("{" + text + (":" + spec if spec else "") + "}")
        return 'f"' + "".join(out) + '"'

    def paren(self, e, need, cmp=False, arith=False):
        text, p = self._ex(e, arith)
        return f"({text})" if p < need or (cmp and p == need) else text



    def types(self):
        notes = []
        for f in self.info.all():
            by = {}
            for name in f.vars:
                by.setdefault(pytype(f.vars[name]), []).append(safe(name))
            notes += [f"{', '.join(ns)}: {t}" for t, ns in by.items()]
            if f.node is not None:
                notes.append(f"{safe(f.name)} → {pytype(f.ret)}")
        return list(dict.fromkeys(notes))

    def symbols(self):
        out = []
        for f in self.info.all():
            scope = safe(f.name) if f.node is not None else "global"
            if f.node is not None:
                params = ", ".join(pytype(f.vars[p]) for p in f.params)
                out.append({"name": safe(f.name), "kind": "function", "type": f"({params}) → {pytype(f.ret)}",
                            "scope": "global"})
            for name, kind in f.kinds.items():
                out.append({"name": safe(name), "kind": kind, "type": pytype(f.vars[name]),
                            "scope": "loop" if kind == "loop var" else scope})
        return out
