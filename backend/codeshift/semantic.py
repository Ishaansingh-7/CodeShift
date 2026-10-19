import copy
from dataclasses import dataclass, field, fields

from . import ast as A
from . import library as L
from .errors import CompileError

INT, IDX, BOOL, STR, CHAR, ARR, VOID, FLOAT = "int", "idx", "bool", "str", "char", "arr", "void", "float"
class Names(dict):
    def __missing__(self, key):
        return "list" if is_list(key) else "dict" if is_map(key) else "set" if is_set(key) else str(key)


NAMES = Names({INT: "int", IDX: "int", BOOL: "bool", STR: "str", CHAR: "character", ARR: "list", VOID: "None",
               FLOAT: "float", None: "unknown"})
ANY = "list<?>"
MAP_ANY, SET_ANY = "map<?,?>", "set<?>"
MAP_ALIAS = {"contains": "map_has", "has": "map_has", "del": "map_del", "delete": "map_del", "remove_at": "map_del",
             "pop_at": "map_del", "size": "map_len", "sorted": "map_sorted_keys", "jssorted": "map_sorted_keys",
             "insert": "map_put", "collect": "map_sorted_keys"}
SET_ALIAS = {"contains": "set_has", "has": "set_has", "del": "set_del", "delete": "set_del", "remove_at": "set_del",
             "pop_at": "set_del", "push": "set_add", "size": "set_len", "sorted": "set_sorted", "lcopy": "set_sorted",
             "jssorted": "set_sorted", "collect": "set_sorted"}


def is_map(t):
    return isinstance(t, str) and t.startswith("map<")


def is_set(t):
    return isinstance(t, str) and t.startswith("set<")


def mp(k, v):
    k, v = (INT if x == IDX else x for x in (k, v))
    return f"map<{k or '?'},{v or '?'}>"


def sset(t):
    t = INT if t == IDX else t
    return f"set<{t or '?'}>"


def part(t, k):
    x = t[4:-1].split(",")[k]
    return None if x == "?" else x


def mkey(t):
    return part(t, 0)


def mval(t):
    return part(t, 1)


def selem(t):
    x = t[4:-1]
    return None if x == "?" else x


def partial(t):
    return (is_map(t) or is_set(t)) and "?" in t


def filled(t):
    return mp(mkey(t) or STR, mval(t) or INT) if is_map(t) else sset(selem(t) or INT)


def alias(n, t):
    return MAP_ALIAS.get(n) if is_map(t) else SET_ALIAS.get(n) if is_set(t) else None


def is_list(t):
    return t == ARR or isinstance(t, str) and t.startswith("list<")


def lst(t):
    return ARR if t in (INT, IDX) else ANY if t is None else f"list<{t}>"


def elem(t):
    if t == ARR:
        return INT
    if is_list(t):
        inner = t[5:-1]
        return None if inner == "?" else inner
    return None
NUM = {INT, IDX, FLOAT}
PY_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod", "enumerate", "filter", "float", "hex", "input",
    "int", "isinstance", "len", "list", "map", "max", "min", "oct", "open", "ord", "pow", "print", "range",
    "reversed", "round", "set", "sorted", "str", "sum", "tuple", "type", "zip",
}


@dataclass(eq=False)
class Func:
    name: str
    node: object
    params: list
    body: list
    vars: dict = field(default_factory=dict)
    kinds: dict = field(default_factory=dict)
    ret: str | None = None
    returns_value: bool = False
    ends: bool = True


class Info:
    def __init__(self, module):
        self.module = module
        self.funcs = {}
        self.main = None

    def all(self):
        return [*self.funcs.values(), self.main]


def error(msg, node):
    return CompileError("semantic", msg, node.line, node.col)


def unsupported(what, node):
    return error(f"Unsupported: {what}", node)


def join(a, b):
    if a is None or a == b:
        return b
    if b is None:
        return a
    if {a, b} == {STR, CHAR}:
        return STR
    if {a, b} == {INT, FLOAT}:
        return FLOAT
    if is_list(a) and is_list(b):
        e = join(elem(a), elem(b))
        return False if e is False else lst(e)
    if is_map(a) and is_map(b):
        k, v = join(mkey(a), mkey(b)), join(mval(a), mval(b))
        return False if False in (k, v) else mp(k, v)
    if is_set(a) and is_set(b):
        e = join(selem(a), selem(b))
        return False if e is False else sset(e)
    return False


def compatible(value, target):
    if is_list(value) and is_list(target):
        return elem(value) is None or compatible(elem(value), elem(target))
    if is_map(value) and is_map(target):
        return all(x is None or compatible(x, y) for x, y in ((mkey(value), mkey(target)), (mval(value), mval(target))))
    if is_set(value) and is_set(target):
        return selem(value) is None or compatible(selem(value), selem(target))
    return value == target or (value == CHAR and target == STR) or {value, target} == {INT, IDX} \
        or value in (INT, IDX) and target == FLOAT


def rewrite(node, fn):
    for fld in fields(node):
        if fld.name in A.META:
            continue
        v = getattr(node, fld.name)
        if isinstance(v, A.Node):
            setattr(node, fld.name, fn(rewrite(v, fn)) if isinstance(v, A.Expr) else rewrite(v, fn))
        elif isinstance(v, list):
            setattr(node, fld.name, [fn(rewrite(x, fn)) if isinstance(x, A.Expr) else rewrite(x, fn)
                                     if isinstance(x, A.Node) else x for x in v])
    return node


def int_lit(e):
    return isinstance(e, A.IntLit)


def one_char(e):
    return isinstance(e, A.StrLit) and len(e.value) == 1


def analyze(module):
    return Analyzer(module).run()


class Analyzer:
    def __init__(self, module):
        self.m = module
        self.info = Info(module)
        self.changed = False
        self.char_args = set()
        self.breaks = []

    def run(self):
        self.collect()
        for f in self.info.all():
            self.resolve(f)
            self.loops(f.body, False)
        for f in self.info.all():
            f.ends = self.assigned(f.body, set(f.params)) is not None
        if self.m.lang == "python":
            self.check_order()
        self.infer()
        for f in self.info.all():
            self.mapify_block(f, f.body)
            for s in f.body:
                rewrite(s, lambda e, f=f: self.mapify(f, e))
        for f in self.info.all():
            self.check_block(f, f.body)
            if f.node is not None and f.ret != VOID and f.ends:
                raise unsupported(f"function '{f.name}' can reach its end without returning a value", f.node)
        for f in self.info.all():
            for s in f.body:
                rewrite(s, self.generic)
        self.widths()
        for f in self.info.all():
            self.fix_block(f, f.body)
        return self.info

    def generic(self, e):
        if isinstance(e, A.Intrinsic) and e.args and alias(e.name, e.args[0].ty):
            return A.Intrinsic(alias(e.name, e.args[0].ty), e.args, ty=e.ty, line=e.line, col=e.col)
        if isinstance(e, A.Intrinsic) and e.name in ("del", "collect"):
            return A.Intrinsic("remove_at" if e.name == "del" else "lcopy", e.args, ty=e.ty, line=e.line, col=e.col)
        if isinstance(e, A.BinOp) and getattr(e, "fill", False):
            return A.Intrinsic("list_fill", [e.left.items[0], e.right], ty=e.ty, line=e.line, col=e.col)
        if isinstance(e, A.BinOp) and getattr(e, "repeat", False):
            s, k = (e.left, e.right) if e.left.ty in (STR, CHAR) else (e.right, e.left)
            return A.Intrinsic("repeat", [s, k], ty=STR, line=e.line, col=e.col)
        if isinstance(e, A.BinOp) and getattr(e, "floor", False):
            e.floor, e.true_div = False, True
            return A.Intrinsic("floor", [e], ty=FLOAT, line=e.line, col=e.col)
        if not isinstance(e, A.Intrinsic) or e.name not in L.GENERIC:
            return e
        n, x = e.name, e.args[0]
        t = INT if x.ty == IDX else x.ty
        make = lambda name, ty: A.Intrinsic(name, e.args, ty=ty, line=e.line, col=e.col)
        if n == "num_int":
            return {FLOAT: make("f2i", INT), CHAR: make("ord", INT), STR: make("s2i", INT)}.get(t, x)
        if n == "num_float":
            return make("s2f", FLOAT) if t == STR else self.conv(x, FLOAT)
        if n == "num_char":
            return make("chr", CHAR) if t == INT else x
        if n == "str":
            if t == BOOL:
                return make("b2s_py" if self.m.lang == "python" else "b2s", STR)
            return {INT: make("i2s", STR), FLOAT: make("f2s", STR)}.get(t, x)
        if n == "abs":
            return make("abs_i" if t == INT else "abs_f", t)
        if n == "pad":
            if t in (STR, CHAR):
                return make("ljust", STR)
            text = {INT: "i2s", FLOAT: "f2s", BOOL: "b2s_py" if self.m.lang == "python" else "b2s"}[t]
            inner = A.Intrinsic(text, [x], ty=STR, line=e.line, col=e.col)
            return A.Intrinsic("rjust", [inner, e.args[1]], ty=STR, line=e.line, col=e.col)
        if n == "index":
            return make("index_of" if is_list(t) else "find", INT)
        if n == "jssort":
            return make("sort", VOID)
        if n == "jssorted":
            return make("sorted", t)
        if n == "to_lower" and isinstance(x, A.Intrinsic) and x.name == "b2s_py":
            return A.Intrinsic("b2s", x.args, ty=STR, line=e.line, col=e.col)
        if n in ("to_upper", "to_lower"):
            word = n[3:]
            return make(word if t == STR else f"c{word}", t)
        if n == "contains":
            if is_list(t):
                return make("contains_l", BOOL)
            return make("contains_c" if e.args[1].ty == CHAR else "contains_s", BOOL)
        if n == "slice":
            if is_list(t):
                s, a, b = e.args
                whole = isinstance(a, A.IntLit) and a.value == 0 and isinstance(b, A.Len) and A.same(b.arg, s)
                return A.Intrinsic("lcopy", [s], ty=t, line=e.line, col=e.col) if whole else make("lslice", t)
            return make("substr", STR)
        if n == "pow":
            return make("pow_i" if e.ty == INT else "pow_f", e.ty)
        return e

    def loops(self, stmts, inside):
        for s in stmts:
            if isinstance(s, (A.Break, A.Continue)) and not inside:
                raise error(f"'{'break' if isinstance(s, A.Break) else 'continue'}' outside a loop", s)
            for b in A.blocks(s):
                self.loops(b, inside or isinstance(s, (A.While, A.For)))

    def collect(self):
        for fn in self.m.functions:
            if fn.name in self.info.funcs:
                raise unsupported(f"redefining function '{fn.name}'", fn)
            if fn.name in PY_BUILTINS and self.m.lang == "python":
                raise unsupported(f"redefining built-in '{fn.name}'", fn)
            f = Func(fn.name, fn, [p.name for p in fn.params], fn.body)
            for p in fn.params:
                if p.name in f.kinds:
                    raise error(f"Duplicate parameter '{p.name}'", p)
                f.kinds[p.name] = "parameter"
                f.vars[p.name] = p.ty
            f.ret = fn.ret
            self.info.funcs[fn.name] = f
        self.info.main = Func("main", None, [], self.m.body)
        for f in self.info.all():
            for s in A.walk_all(f.body):
                if isinstance(s, A.For):
                    self.declare(f, s.var, "loop var", None, s)
                elif isinstance(s, A.Assign) and isinstance(s.target, A.Name):
                    self.declare(f, s.target.id, "local", s.decl, s)
                elif isinstance(s, A.TupleAssign):
                    for t in s.targets:
                        if isinstance(t, A.Name):
                            self.declare(f, t.id, "local", None, s)
                elif isinstance(s, A.AugAssign) and isinstance(s.target, A.Name):
                    self.declare(f, s.target.id, "local", None, s)
                elif isinstance(s, A.Return) and s.value is not None:
                    f.returns_value = True

    def declare(self, f, name, kind, ty, node):
        if name in self.info.funcs:
            raise unsupported(f"using function name '{name}' as a variable", node)
        old = f.kinds.get(name)
        if old is None:
            f.kinds[name] = kind
            f.vars[name] = ty
        elif (old == "loop var") != (kind == "loop var"):
            raise unsupported(f"'{name}' used both as a loop variable and as an ordinary variable", node)
        elif ty:
            self.set_var(f, name, ty, node)

    def resolve(self, f):
        for n in A.walk_all(f.body):
            if isinstance(n, A.Name) and n.id not in f.vars:
                if n.id in self.info.funcs:
                    raise unsupported(f"using function '{n.id}' as a value", n)
                if f.node is not None and n.id in self.info.main.vars:
                    raise unsupported(f"global variable '{n.id}' used inside function '{f.name}'", n)
                raise error(f"Undefined name '{n.id}'", n)
            if isinstance(n, A.Call):
                if n.func == "print":
                    raise unsupported("print() used as a value", n)
                g = self.info.funcs.get(n.func)
                if g is None:
                    if n.func in PY_BUILTINS and self.m.lang == "python":
                        raise unsupported(f"built-in function {n.func}()", n)
                    raise error(f"Undefined function '{n.func}'", n)
                if len(n.args) != len(g.params):
                    raise error(f"{n.func}() takes {len(g.params)} argument(s) but {len(n.args)} were given", n)

    def uses(self, e, da):
        for n in A.walk(e):
            if isinstance(n, A.Name) and n.id not in da:
                raise error(f"Variable '{n.id}' may be used before it is assigned", n)

    def assigned(self, stmts, da):
        for s in stmts:
            if da is None:
                return None
            da = self.assigned_stmt(s, da)
        return da

    def assigned_stmt(self, s, da):
        if isinstance(s, A.Assign):
            self.uses(s.value, da)
            if isinstance(s.target, A.Name):
                return da | {s.target.id}
            self.uses(s.target, da)
        elif isinstance(s, A.AugAssign):
            self.uses(s.target, da)
            self.uses(s.value, da)
        elif isinstance(s, A.TupleAssign):
            for v in s.values:
                self.uses(v, da)
            for t in s.targets:
                if isinstance(t, A.Index):
                    self.uses(t, da)
            return da | {t.id for t in s.targets if isinstance(t, A.Name)}
        elif isinstance(s, A.Swap):
            self.uses(s.a, da)
            self.uses(s.b, da)
        elif isinstance(s, A.If):
            self.uses(s.test, da)
            a = self.assigned(s.body, set(da))
            b = self.assigned(s.orelse, set(da))
            return b if a is None else a if b is None else a & b
        elif isinstance(s, A.While):
            self.uses(s.test, da)
            self.breaks.append([])
            self.assigned(s.body, set(da))
            exits = self.breaks.pop()
            if isinstance(s.test, A.BoolLit) and s.test.value:
                return set.intersection(*exits) if exits else None
            return da
        elif isinstance(s, A.For):
            for e in A.heads(s):
                self.uses(e, da)
            self.breaks.append([])
            self.assigned(s.body, da | {s.var})
            self.breaks.pop()
        elif isinstance(s, A.Break):
            self.breaks[-1].append(set(da))
            return None
        elif isinstance(s, A.Continue):
            return None
        elif isinstance(s, A.Return):
            if s.value is not None:
                self.uses(s.value, da)
            return None
        elif isinstance(s, A.ExprStmt):
            self.uses(s.expr, da)
        elif isinstance(s, A.Print):
            for a in s.args:
                self.uses(a, da)
        return da

    def check_order(self):
        calls = {n: {c.func for c in A.walk_all(f.body) if isinstance(c, A.Call)} for n, f in self.info.funcs.items()}

        def closure(name, seen):
            if name not in seen:
                seen.add(name)
                for c in calls[name]:
                    closure(c, seen)
            return seen

        defined = set()
        for item in sorted([*self.m.functions, *self.m.body], key=lambda n: n.line):
            if isinstance(item, A.FunctionDef):
                defined.add(item.name)
                continue
            for c in A.walk(item):
                if isinstance(c, A.Call):
                    for g in sorted(closure(c.func, set())):
                        if g not in defined:
                            raise error(f"Function '{g}' is called before it is defined", c)

    def set_var(self, f, name, ty, node):
        if ty is None:
            return
        old = f.vars[name]
        new = join(old, ty)
        if new is False:
            raise unsupported(f"'{name}' holds both {NAMES[old]} and {NAMES[ty]} values", node)
        if new != old:
            f.vars[name] = new
            self.changed = True

    def set_ret(self, f, ty, node):
        if ty is None:
            return
        new = join(f.ret, ty)
        if new is False:
            raise unsupported(f"function '{f.name}' returns both {NAMES[f.ret]} and {NAMES[ty]}", node)
        if new != f.ret:
            f.ret = new
            self.changed = True

    def hint(self, f, e, ty):
        if isinstance(e, A.Name) and f.vars.get(e.id) is None and f.kinds.get(e.id) != "loop var":
            self.set_var(f, e.id, ty, e)

    def infer(self):
        while True:
            self.changed = True
            while self.changed:
                self.changed = False
                for f in self.info.all():
                    self.infer_block(f, f.body)
            missing = [(f, n) for f in self.info.all() for n, t in f.vars.items() if t is None or t == ANY or partial(t)]
            if missing:
                f, n = missing[0]
                t = f.vars[n]
                f.vars[n] = ARR if t == ANY else filled(t) if partial(t) else self.default(f, n)
                continue
            for f in self.info.all():
                if f.ret == ANY:
                    f.ret = ARR
                elif partial(f.ret):
                    f.ret = filled(f.ret)
            rets = [f for f in self.info.funcs.values() if f.ret is None]
            if rets:
                rets[0].ret = INT if rets[0].returns_value else VOID
                continue
            return

    def default(self, f, name):
        nodes = list(A.walk_all(f.body))
        named = lambda e: isinstance(e, A.Name) and e.id == name
        char = (f.name, name) in self.char_args
        if any(isinstance(n, A.For) and named(n.iter) for n in nodes):
            return STR
        if any(isinstance(n, A.Index) and named(n.target) or isinstance(n, A.Len) and named(n.arg) for n in nodes):
            return STR if char else ARR
        return CHAR if char else INT

    def typeof(self, f, e):
        if isinstance(e, A.IntLit):
            return INT
        if isinstance(e, A.BoolLit):
            return BOOL
        if isinstance(e, A.FloatLit):
            return FLOAT
        if isinstance(e, A.StrLit):
            return STR
        if isinstance(e, A.CharLit):
            return CHAR
        if isinstance(e, A.Intrinsic):
            ts = [self.typeof(f, a) for a in e.args]
            return self.intrinsic(f, e, ts)
        if isinstance(e, A.ArrayLit):
            t = None
            for x in e.items:
                tx = self.typeof(f, x)
                t = join(t, tx) if tx is not None and t is not False else t
            if t is False:
                t = None
            for x in e.items:
                self.hint(f, x, t or INT)
            return lst(t) if e.items else ANY
        if isinstance(e, A.Name):
            return f.vars[e.id]
        if isinstance(e, A.BinOp) and e.op == "*" and isinstance(e.left, A.ArrayLit) and len(e.left.items) == 1:
            self.typeof(f, e.right)
            self.hint(f, e.right, INT)
            return self.typeof(f, e.left)
        if isinstance(e, A.BinOp):
            l, r = self.typeof(f, e.left), self.typeof(f, e.right)
            if e.op == "+" and (l in (STR, CHAR) or r in (STR, CHAR)):
                self.hint(f, e.left, STR)
                self.hint(f, e.right, STR)
                return STR
            if e.op == "*" and (l in (STR, CHAR) or r in (STR, CHAR)):
                self.hint(f, e.right if l in (STR, CHAR) else e.left, INT)
                return STR
            if e.op == "*" and None in (l, r):
                return None
            if e.op == "fdiv":
                return FLOAT
            if FLOAT in (l, r):
                self.hint(f, e.left, FLOAT)
                self.hint(f, e.right, FLOAT)
                return FLOAT
            if e.op != "+" or INT in (l, r):
                self.hint(f, e.left, INT)
                self.hint(f, e.right, INT)
                return INT
            return None
        if isinstance(e, A.Compare):
            l, r = self.typeof(f, e.left), self.typeof(f, e.right)
            self.hint(f, e.right, CHAR if one_char(e.left) else l)
            self.hint(f, e.left, CHAR if one_char(e.right) else r)
            return BOOL
        if isinstance(e, A.BoolOp):
            for x in (e.left, e.right):
                self.typeof(f, x)
                self.hint(f, x, BOOL)
            return BOOL
        if isinstance(e, A.UnaryOp):
            t = self.typeof(f, e.operand)
            if e.op == "-":
                if t == FLOAT:
                    return FLOAT
                self.hint(f, e.operand, INT)
                return INT
            return BOOL
        if isinstance(e, A.Index):
            t = self.typeof(f, e.target)
            ti = self.typeof(f, e.index)
            if is_map(t):
                if isinstance(e.target, A.Name):
                    self.set_var(f, e.target.id, mp(ti, None), e)
                    t = f.vars[e.target.id]
                if mkey(t):
                    self.hint(f, e.index, mkey(t))
                return mval(t)
            if t is not None:
                self.hint(f, e.index, INT)
            return elem(t) if is_list(t) else CHAR if t == STR else None
        if isinstance(e, A.Len):
            self.typeof(f, e.arg)
            return INT
        if isinstance(e, A.Call):
            g = self.info.funcs[e.func]
            for a, p in zip(e.args, g.params):
                if one_char(a) and g.vars[p] in (None, CHAR):
                    self.char_args.add((g.name, p))
                    continue
                ta = self.typeof(f, a)
                self.set_var(g, p, ta, a)
                if ta is None:
                    self.hint(f, a, g.vars[p])
            return g.ret
        raise TypeError(e)

    def infer_assign(self, f, target, value, node):
        tv = self.typeof(f, value)
        if isinstance(target, A.Name):
            self.set_var(f, target.id, tv, node)
            self.hint(f, value, f.vars[target.id])
        else:
            tt = self.typeof(f, target.target)
            if is_map(tt):
                if isinstance(target.target, A.Name):
                    self.set_var(f, target.target.id, mp(self.typeof(f, target.index), tv), node)
                tt = self.typeof(f, target.target)
                if mkey(tt):
                    self.hint(f, target.index, mkey(tt))
                if mval(tt):
                    self.hint(f, value, mval(tt))
                return
            if tt is None and isinstance(target.target, A.Name) and f.kinds.get(target.target.id) == "parameter":
                return
            if isinstance(target.target, A.Name) and tv is not None:
                self.set_var(f, target.target.id, lst(tv), node)
            self.hint(f, target.target, ARR)
            self.typeof(f, target)
            self.hint(f, value, elem(self.typeof(f, target.target)) or INT)

    def infer_block(self, f, stmts):
        for s in stmts:
            if isinstance(s, A.Assign):
                self.infer_assign(f, s.target, s.value, s)
            elif isinstance(s, A.TupleAssign):
                for t, v in zip(s.targets, s.values):
                    self.infer_assign(f, t, v, s)
            elif isinstance(s, A.AugAssign):
                tv = self.typeof(f, s.value)
                if isinstance(s.target, A.Name):
                    tx = f.vars[s.target.id]
                    if s.op == "+" and (tx in (STR, CHAR) or tv in (STR, CHAR)):
                        self.set_var(f, s.target.id, STR, s)
                    elif tv == FLOAT or s.op == "fdiv":
                        self.set_var(f, s.target.id, FLOAT, s)
                    else:
                        self.set_var(f, s.target.id, INT, s)
                        self.hint(f, s.value, INT)
                else:
                    tt = self.typeof(f, s.target.target)
                    if is_map(tt):
                        if isinstance(s.target.target, A.Name):
                            self.set_var(f, s.target.target.id, mp(self.typeof(f, s.target.index), tv or INT), s)
                        self.typeof(f, s.target)
                        continue
                    self.hint(f, s.target.target, ARR)
                    self.typeof(f, s.target)
                    self.hint(f, s.value, INT)
            elif isinstance(s, A.Swap):
                ta, tb = self.typeof(f, s.a), self.typeof(f, s.b)
                if isinstance(s.a, A.Name):
                    self.set_var(f, s.a.id, tb, s)
                if isinstance(s.b, A.Name):
                    self.set_var(f, s.b.id, ta, s)
            elif isinstance(s, A.If):
                self.typeof(f, s.test)
                self.infer_block(f, s.body)
                self.infer_block(f, s.orelse)
            elif isinstance(s, A.While):
                self.typeof(f, s.test)
                self.infer_block(f, s.body)
            elif isinstance(s, A.For):
                if s.kind == "range":
                    self.set_var(f, s.var, INT, s)
                    for e in (s.start, s.stop, s.step):
                        self.hint(f, e, INT)
                        self.typeof(f, e)
                else:
                    t = self.typeof(f, s.iter)
                    self.set_var(f, s.var, CHAR if t == STR else elem(t) if is_list(t) else mkey(t) if is_map(t)
                                 else selem(t) if is_set(t) else None, s)
                self.infer_block(f, s.body)
            elif isinstance(s, A.Return):
                if s.value is None:
                    self.set_ret(f, VOID, s)
                else:
                    t = self.typeof(f, s.value)
                    self.set_ret(f, t, s)
                    if t is None and f.ret:
                        self.hint(f, s.value, f.ret)
            elif isinstance(s, A.ExprStmt):
                self.typeof(f, s.expr)
            elif isinstance(s, A.Print):
                for a in s.args:
                    self.typeof(f, a)

    def ty(self, f, e):
        for c in A.children(e):
            if isinstance(c, A.Expr):
                self.ty(f, c)
        e.ty = self.compute(f, e)
        return e.ty

    def compute(self, f, e):
        if isinstance(e, A.IntLit):
            if not -2 ** 63 <= e.value < 2 ** 63:
                raise unsupported("integer literal beyond 64 bits", e)
            return INT
        if isinstance(e, A.BoolLit):
            return BOOL
        if isinstance(e, A.FloatLit):
            return FLOAT
        if isinstance(e, A.StrLit):
            return STR
        if isinstance(e, A.CharLit):
            return CHAR
        if isinstance(e, A.Intrinsic):
            return self.intrinsic(f, e, [a.ty for a in e.args], check=True)
        if isinstance(e, A.ArrayLit):
            t = None
            for x in e.items:
                t = join(t, x.ty)
                if t is False or t in (VOID, CHAR):
                    raise unsupported("list elements of different or unsupported types", x)
            return lst(t) if e.items else ANY
        if isinstance(e, A.Name):
            return f.vars[e.id]
        if isinstance(e, A.BinOp):
            l, r = e.left.ty, e.right.ty
            if e.op == "+" and l in (STR, CHAR) and r in (STR, CHAR):
                return STR
            if e.op == "*" and {l, r} in ({STR, INT}, {CHAR, INT}):
                e.repeat = True
                return STR
            if e.op == "*" and is_list(l) and r in (INT, IDX) and isinstance(e.left, A.ArrayLit) and len(e.left.items) == 1:
                e.fill = True
                return l
            if l in NUM and r in NUM and (FLOAT in (l, r) or e.op == "fdiv"):
                if e.op == "%":
                    raise unsupported("'%' on floats", e)
                if e.op == "/" and self.m.lang in ("python", "js") and not getattr(e, "true_div", False):
                    e.floor = True
                return FLOAT
            if l == r == INT:
                return INT
            raise unsupported(f"'{e.op}' between {NAMES[l]} and {NAMES[r]}", e)
        if isinstance(e, A.Compare):
            l, r = e.left.ty, e.right.ty
            if l == r == INT or l in NUM and r in NUM:
                return BOOL
            if {l, r} <= {STR, CHAR}:
                if l != r and not any(isinstance(x, A.StrLit) and len(x.value) == 1 for x in (e.left, e.right)):
                    raise unsupported("comparing a character with a longer string", e)
                return BOOL
            if l == r == BOOL and e.op in ("==", "!="):
                return BOOL
            raise unsupported(f"comparing {NAMES[l]} with {NAMES[r]}", e)
        if isinstance(e, A.BoolOp):
            if e.left.ty != BOOL or e.right.ty != BOOL:
                raise unsupported("'and' / 'or' on values that are not booleans", e)
            return BOOL
        if isinstance(e, A.UnaryOp):
            t = e.operand.ty
            if e.op == "-" and t in (INT, FLOAT):
                return t
            if e.op == "!" and t == INT and self.m.lang == "rust":
                raise unsupported("'!' on an integer (bitwise not in Rust)", e)
            if e.op == "!" and t in (BOOL, INT):
                return BOOL
            raise unsupported(f"'{'not' if e.op == '!' else e.op}' on {NAMES[t]}", e)
        if isinstance(e, A.Index):
            t = e.target.ty
            if e.index.ty != INT:
                raise unsupported("index that is not an integer", e.index)
            if int_lit(e.index) and e.index.value < 0:
                raise unsupported("negative index", e.index)
            if is_list(t):
                return elem(t)
            if t == STR:
                return CHAR
            raise unsupported(f"indexing a {NAMES[t]}", e)
        if isinstance(e, A.Len):
            if not is_list(e.arg.ty) and e.arg.ty != STR:
                raise unsupported(f"len() of a {NAMES[e.arg.ty]}", e)
            return INT
        if isinstance(e, A.Call):
            g = self.info.funcs[e.func]
            for k, (a, p) in enumerate(zip(e.args, g.params)):
                if one_char(a) and g.vars[p] == CHAR:
                    a = e.args[k] = A.CharLit(a.value, line=a.line, col=a.col, ty=CHAR)
                if isinstance(a, A.ArrayLit) and not a.items and is_list(g.vars[p]) or partial(a.ty) \
                        and compatible(a.ty, g.vars[p]):
                    a.ty = g.vars[p]
                if a.ty != g.vars[p] and {a.ty, g.vars[p]} != {INT, IDX} and not (a.ty == INT and g.vars[p] == FLOAT):
                    raise unsupported(f"passing a {NAMES[a.ty]} to parameter '{p}' of {g.name}()", a)
            return g.ret
        raise TypeError(e)

    def check_assign(self, f, target, value, node):
        self.ty(f, value)
        if value.ty == VOID:
            raise unsupported(f"using the result of {value.func}(), which returns nothing", value)
        if isinstance(target, A.Name):
            if not compatible(value.ty, f.vars[target.id]):
                raise unsupported(f"assigning a {NAMES[value.ty]} to '{target.id}'", node)
            if (is_list(value.ty) or is_map(value.ty) or is_set(value.ty)) and isinstance(value, A.Name):
                raise unsupported(f"two names for the same {NAMES[value.ty]} ('{target.id}' = '{value.id}'); copy it "
                                  f"instead", node)
            if partial(value.ty):
                value.ty = f.vars[target.id]
            target.ty = f.vars[target.id]
            return
        self.ty(f, target)
        if target.target.ty == STR:
            raise unsupported("changing a character inside a string", target)
        if not compatible(value.ty, target.ty):
            raise unsupported(f"storing a {NAMES[value.ty]} in a list of {NAMES[target.ty]}", value)

    def check_block(self, f, stmts):
        for s in stmts:
            if isinstance(s, A.Assign):
                self.check_assign(f, s.target, s.value, s)
            elif isinstance(s, A.TupleAssign):
                for t, v in zip(s.targets, s.values):
                    self.check_assign(f, t, v, s)
            elif isinstance(s, A.Swap):
                self.ty(f, s.a)
                self.ty(f, s.b)
                if s.a.ty != s.b.ty:
                    raise unsupported(f"swapping a {NAMES[s.a.ty]} with a {NAMES[s.b.ty]}", s)
                for x in (s.a, s.b):
                    if isinstance(x, A.Index) and x.target.ty == STR:
                        raise unsupported("changing a character inside a string", x)
            elif isinstance(s, A.AugAssign):
                t, v = self.ty(f, s.target), self.ty(f, s.value)
                if isinstance(s.target, A.Index) and s.target.target.ty == STR:
                    raise unsupported("changing a character inside a string", s.target)
                floor = s.op == "/" and self.m.lang in ("python", "js")
                numeric = t == FLOAT and v in (INT, FLOAT) and s.op in ("+", "-", "*", "/", "fdiv") and not floor
                if not (t == v == INT and s.op != "fdiv" or numeric or (t == STR and v in (STR, CHAR) and s.op == "+")):
                    op = "//" if s.op == "/" and self.m.lang == "python" else "/" if s.op == "fdiv" else s.op
                    raise unsupported(f"'{op}=' between {NAMES[t]} and {NAMES[v]}", s)
            elif isinstance(s, (A.If, A.While)):
                t = self.ty(f, s.test)
                if t not in (BOOL, INT):
                    raise unsupported(f"condition of type {NAMES[t]}", s.test)
                self.check_block(f, s.body)
                if isinstance(s, A.If):
                    self.check_block(f, s.orelse)
            elif isinstance(s, A.For):
                if s.kind == "range":
                    for e in (s.start, s.stop, s.step):
                        if self.ty(f, e) != INT:
                            raise unsupported(f"range() argument of type {NAMES[e.ty]}", e)
                    if not int_lit(s.step):
                        raise unsupported("range() step that is not a constant", s.step)
                    if s.step.value == 0:
                        raise error("range() step must not be zero", s.step)
                elif self.ty(f, s.iter) != STR and not is_list(s.iter.ty) and not is_map(s.iter.ty):
                    raise unsupported(f"looping over a {NAMES[s.iter.ty]}", s.iter)
                self.check_block(f, s.body)
            elif isinstance(s, A.Return):
                if s.value is None:
                    if f.ret != VOID:
                        raise unsupported("'return' without a value in a function that returns a value", s)
                elif not compatible(self.ty(f, s.value), f.ret):
                    raise unsupported(f"returning a {NAMES[s.value.ty]} from a function that returns {NAMES[f.ret]}", s)
                elif partial(s.value.ty):
                    s.value.ty = f.ret
            elif isinstance(s, A.ExprStmt):
                self.ty(f, s.expr)
            elif isinstance(s, A.Print):
                for a in s.args:
                    if self.ty(f, a) == VOID:
                        raise unsupported(f"printing the result of {a.func}(), which returns nothing", a)
                    if is_map(a.ty) or is_set(a.ty):
                        raise unsupported(f"printing a whole {NAMES[a.ty]} (its order and format differ by language)", a)

    def intrinsic(self, f, e, ts, check=False):
        n = e.name
        if e.args and alias(n, ts[0]):
            return self.map_type(f, e, ts, check, alias(n, ts[0]))
        if n in L.MAPOPS:
            return self.map_type(f, e, ts, check, n)
        if n == "del" and is_list(ts[0]):
            return self.list_type(f, e, ts, check, "remove_at")
        if n == "del" and ts[0] is None and not check:
            return VOID
        if n == "collect":
            if is_list(ts[0]):
                return self.list_type(f, e, ts, check, "lcopy")
            if check:
                raise unsupported(f"collect() of a {NAMES[ts[0]]}", e)
            return None
        if n in L.MAP_GENERIC:
            if check:
                raise unsupported(f"{n}() of a {NAMES[ts[0]]}", e)
            return BOOL if n == "has" else INT if n == "size" else VOID
        if n in L.GENERIC:
            return self.generic_type(f, e, ts, check)
        if n in L.LISTOPS:
            return self.list_type(f, e, ts, check)
        if n not in L.SIGS:
            raise unsupported(f"library call @{n}", e)
        params, ret = L.SIGS[n]
        if len(params) != len(e.args):
            raise error(f"@{n} takes {len(params)} argument(s) but {len(e.args)} were given", e)
        for a, want, have in zip(e.args, params, ts):
            if check and not compatible(have, want) and not (want == CHAR and one_char(a)):
                raise unsupported(f"passing a {NAMES[have]} to @{n}", a)
            if not check and have is None:
                self.hint(f, a, want)
        return ret

    def generic_type(self, f, e, ts, check):
        n = e.name
        if n in ("to_upper", "to_lower", "contains", "slice"):
            return self.text_type(f, e, ts, check)
        if n == "index":
            if check and not (ts[0] == STR and ts[1] in (STR, CHAR) or is_list(ts[0]) and compatible(ts[1], elem(ts[0]))):
                raise unsupported(f"indexOf() on a {NAMES[ts[0]]}", e)
            return INT
        if n == "jssort":
            if check and elem(ts[0]) != STR:
                raise unsupported("sort() without a comparator (JavaScript would sort numbers as text)", e)
            return VOID
        if n == "jssorted":
            if check and elem(ts[0]) != STR:
                raise unsupported("sort() without a comparator (JavaScript would sort numbers as text)", e)
            return ts[0]
        if n == "pad":
            if len(e.args) != 2:
                raise error(f"pad() takes 2 argument(s) but {len(e.args)} were given", e)
            if check and (ts[0] not in NUM | {STR, CHAR, BOOL} or not int_lit(e.args[1])):
                raise unsupported("this format width", e)
            return STR
        want = {"num_int": NUM | {STR, CHAR}, "num_float": NUM | {STR}, "num_char": {INT, IDX, CHAR},
                "str": NUM | {STR, CHAR, BOOL}}.get(n, NUM)
        arity = 2 if n in ("min", "max", "pow") else 1
        if len(e.args) != arity:
            raise error(f"{n}() takes {arity} argument(s) but {len(e.args)} were given", e)
        if check:
            for a, t in zip(e.args, ts):
                if t not in want:
                    raise unsupported(f"{n}() of a {NAMES[t]}", a)
        if n == "num_int":
            return INT
        if n == "num_float":
            return FLOAT
        if n == "num_char":
            return CHAR
        if n == "str":
            return STR
        if not check:
            for a in e.args:
                self.hint(f, a, INT)
        ts = [INT if t == IDX else t for t in ts]
        if n == "abs":
            return ts[0]
        if n == "pow":
            return None if None in ts else INT if ts == [INT, INT] else FLOAT
        out = None
        for t in ts:
            out = join(out, t)
        return out or None

    def text_type(self, f, e, ts, check):
        n = e.name
        arity = {"contains": 2, "slice": 3}.get(n, 1)
        if len(e.args) != arity:
            raise error(f"{n}() takes {arity} argument(s) but {len(e.args)} were given", e)
        if not check:
            if n == "slice":
                self.hint(f, e.args[1], INT)
                self.hint(f, e.args[2], INT)
            if n == "contains" and is_list(ts[0]):
                self.hint(f, e.args[1], elem(ts[0]))
            return BOOL if n == "contains" else ts[0]
        t = ts[0]
        if n == "contains" and is_list(t):
            if not compatible(ts[1], elem(t)):
                raise unsupported(f"looking for a {NAMES[ts[1]]} in a list of {NAMES[elem(t)]}", e)
            return BOOL
        if n == "slice" and is_list(t):
            if any(x not in (INT, IDX) for x in ts[1:]):
                raise unsupported("slice bounds that are not integers", e)
            return t
        if n in ("to_upper", "to_lower"):
            if t not in (STR, CHAR):
                raise unsupported(f"{n[3:]}() of a {NAMES[t]}", e)
            return t
        if n == "contains":
            if t != STR or ts[1] not in (STR, CHAR):
                raise unsupported(f"'in' on a {NAMES[t]}", e)
            return BOOL
        if t != STR or any(x not in (INT, IDX) for x in ts[1:]):
            raise unsupported(f"slicing a {NAMES[t]}", e)
        return STR

    def map_type(self, f, e, ts, check, n):
        args = e.args
        if len(args) != L.MAPOPS[n]:
            raise error(f"{n}() takes {L.MAPOPS[n]} argument(s) but {len(args)} were given", e)
        if n == "map_new":
            return MAP_ANY
        if n == "set_new":
            return SET_ANY
        m, t = args[0], ts[0]
        if n.startswith("map_"):
            if not check:
                k = ts[1] if len(ts) > 1 else None
                v = ts[2] if n in ("map_put", "map_get_or") else (INT if ts[2] in (None, IDX) else ts[2]) \
                    if n == "map_incr" else None
                if isinstance(m, A.Name) and (f.vars.get(m.id) is None or is_map(f.vars[m.id])):
                    self.set_var(f, m.id, mp(k, v), e)
                    t = f.vars[m.id]
                if is_map(t) and mkey(t) and len(args) > 1:
                    self.hint(f, args[1], mkey(t))
                if is_map(t) and mval(t) and n in ("map_put", "map_get_or", "map_incr"):
                    self.hint(f, args[2], mval(t))
                if n in ("map_get", "map_get_or"):
                    return (mval(t) if is_map(t) else None) or (ts[2] if n == "map_get_or" else None)
                if n in ("map_keys", "map_sorted_keys"):
                    return lst(mkey(t)) if is_map(t) and mkey(t) else None
                return BOOL if n == "map_has" else INT if n == "map_len" else VOID
            if not is_map(t):
                raise unsupported(f"{n}() of a {NAMES[t]}", e)
            k, v = mkey(t), mval(t)
            if k not in (INT, STR):
                raise unsupported(f"dict keys of type {NAMES[k]} (use int or str)", e)
            if v not in (INT, FLOAT, BOOL, STR):
                raise unsupported(f"dict values of type {NAMES[v]}", e)
            if n not in ("map_len", "map_keys", "map_sorted_keys") and not compatible(ts[1], k):
                raise unsupported(f"a {NAMES[ts[1]]} key in a dict with {NAMES[k]} keys", args[1])
            if n in ("map_put", "map_get_or") and not compatible(ts[2], v):
                raise unsupported(f"a {NAMES[ts[2]]} value in a dict of {NAMES[v]} values", args[2])
            if n == "map_incr" and (v not in (INT, FLOAT) or not compatible(ts[2], v)):
                raise unsupported("adding to a dict value that is not a number", e)
            return v if n in ("map_get", "map_get_or") else BOOL if n == "map_has" else INT if n == "map_len" \
                else lst(k) if n in ("map_keys", "map_sorted_keys") else VOID
        if not check:
            if n == "set_add" and isinstance(m, A.Name) and (f.vars.get(m.id) is None or is_set(f.vars[m.id])):
                self.set_var(f, m.id, sset(ts[1]), e)
                t = f.vars[m.id]
            if is_set(t) and selem(t) and len(args) > 1:
                self.hint(f, args[1], selem(t))
            if n == "set_sorted":
                return lst(selem(t)) if is_set(t) and selem(t) else None
            return BOOL if n == "set_has" else INT if n == "set_len" else VOID
        if not is_set(t):
            raise unsupported(f"{n}() of a {NAMES[t]}", e)
        el = selem(t)
        if el not in (INT, STR):
            raise unsupported(f"sets of {NAMES[el]} (use int or str)", e)
        if len(args) > 1 and not compatible(ts[1], el):
            raise unsupported(f"a {NAMES[ts[1]]} in a set of {NAMES[el]}", args[1])
        return BOOL if n == "set_has" else INT if n == "set_len" else lst(el) if n == "set_sorted" else VOID

    def mapify_block(self, f, stmts):
        for k, s in enumerate(stmts):
            pos = {"line": s.line, "col": s.col, "end": s.end, "group": s.group, "extra": s.extra, "tie": s.tie}
            t = s.target if isinstance(s, (A.Assign, A.AugAssign)) else None
            if isinstance(t, A.Index) and is_map(self.typeof(f, t.target)):
                m, key = t.target, t.index
                at = {"line": t.line, "col": t.col}
                if isinstance(s, A.Assign):
                    node = A.Intrinsic("map_put", [m, key, s.value], **at)
                elif self.m.lang == "go" and s.op in ("+", "-"):
                    v = s.value if s.op == "+" else A.UnaryOp("-", s.value, line=s.value.line, col=s.value.col)
                    node = A.Intrinsic("map_incr", [m, key, v], **at)
                else:
                    get = A.Intrinsic("map_get", [copy.deepcopy(m), copy.deepcopy(key)], **at)
                    node = A.Intrinsic("map_put", [m, key, A.BinOp(s.op, get, s.value, **at)], **at)
                s = stmts[k] = A.ExprStmt(node, **pos)
            if isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name == "map_put":
                m, key, v = s.expr.args
                if isinstance(v, A.BinOp) and v.op == "+" and isinstance(v.left, A.Intrinsic) \
                        and v.left.name == "map_get_or" and A.same(v.left.args[0], m) and A.same(v.left.args[1], key) \
                        and isinstance(v.left.args[2], (A.IntLit, A.FloatLit)) and v.left.args[2].value == 0:
                    s.expr = A.Intrinsic("map_incr", [m, key, v.right], line=s.expr.line, col=s.expr.col)
            if isinstance(s, A.For) and s.kind == "each" and is_set(self.typeof(f, s.iter)):
                s.iter = A.Intrinsic("set_sorted", [s.iter], line=s.iter.line, col=s.iter.col)
            for b in A.blocks(s):
                self.mapify_block(f, b)

    def mapify(self, f, e):
        pos = {"line": e.line, "col": e.col}
        if isinstance(e, A.Index) and is_map(self.typeof(f, e.target)):
            return A.Intrinsic("map_get", [e.target, e.index], **pos)
        if isinstance(e, A.Len):
            t = self.typeof(f, e.arg)
            if is_map(t) or is_set(t):
                return A.Intrinsic("map_len" if is_map(t) else "set_len", [e.arg], **pos)
        return e

    def list_type(self, f, e, ts, check, n=None):
        n, args = n or e.name, e.args
        if len(args) != L.LISTOPS[n]:
            raise error(f"{n}() takes {L.LISTOPS[n]} argument(s) but {len(args)} were given", e)
        if n == "list_fill":
            self.hint(f, args[1], INT)
            if check and ts[1] not in (INT, IDX):
                raise unsupported("repeating a list a non-integer number of times", e)
            return lst(ts[0]) if ts[0] else None
        if n == "grid":
            self.hint(f, args[0], INT)
            self.hint(f, args[1], INT)
            return lst(lst(ts[2])) if ts[2] else None
        if n == "s2ints":
            self.hint(f, args[0], STR)
            if check and ts[0] != STR:
                raise unsupported(f"reading numbers from a {NAMES[ts[0]]}", e)
            return ARR
        if n in ("split", "split_ws"):
            for a in args:
                self.hint(f, a, STR)
            if check and any(t != STR for t in ts):
                raise unsupported(f"{n}() of a {NAMES[ts[0]]}", e)
            return lst(STR)
        if n == "join":
            self.hint(f, args[0], STR)
            self.hint(f, args[1], lst(STR))
            if check and (ts[0] != STR or ts[1] != lst(STR)):
                raise unsupported("join() needs a separator string and a list of strings", e)
            return STR
        xs, el = ts[0], elem(ts[0])
        if n in ("push", "insert") and xs == STR:
            if check and ts[-1] not in (STR, CHAR):
                raise unsupported(f"adding a {NAMES[ts[-1]]} to a string", e)
            if check and n == "insert" and not (int_lit(args[1]) and args[1].value == 0):
                raise unsupported("inserting into a string anywhere but the start", e)
            return VOID
        if not check:
            if n in ("push", "insert") and isinstance(args[0], A.Name) and ts[-1] is not None:
                self.set_var(f, args[0].id, lst(ts[-1]), e)
            if n in ("pop_at", "insert", "remove_at"):
                self.hint(f, args[1], INT)
            if n == "index_of" and el:
                self.hint(f, args[1], el)
            if n in ("pop", "pop_at", "sum", "lmin", "lmax"):
                return el
            return xs if n in ("sorted", "lcopy", "lslice") else INT if n == "index_of" else BOOL \
                if n == "contains_l" else VOID
        if not is_list(xs):
            raise unsupported(f"{n}() of a {NAMES[xs]}", e)
        if n in ("push", "insert", "index_of") and not compatible(ts[-1], el):
            raise unsupported(f"putting a {NAMES[ts[-1]]} in a list of {NAMES[el]}", args[-1])
        if n in ("sum", "lmin", "lmax") and el not in (INT, FLOAT) and not (n != "sum" and el == STR):
            raise unsupported(f"{n}() of a list of {NAMES[el]}", e)
        if n in ("pop", "pop_at", "sum", "lmin", "lmax"):
            return el
        return xs if n in ("sorted", "lcopy", "lslice") else INT if n == "index_of" else BOOL if n == "contains_l" \
            else VOID

    def wants(self, e):
        n, args = e.name, e.args
        if n in L.SIGS:
            return L.SIGS[n][0]
        if n in L.MAPOPS:
            t = args[0].ty if args else None
            if is_map(t):
                return {"map_put": [t, mkey(t), mval(t)], "map_get": [t, mkey(t)], "map_get_or": [t, mkey(t), mval(t)],
                        "map_has": [t, mkey(t)], "map_del": [t, mkey(t)],
                        "map_incr": [t, mkey(t), mval(t)]}.get(n, [None] * len(args))
            if is_set(t):
                return [t, selem(t)] if len(args) == 2 else [None] * len(args)
            return [None] * len(args)
        if n in L.LISTOPS:
            xs = args[0].ty if args else None
            return {"push": [xs, elem(xs)], "insert": [xs, INT, elem(xs)], "index_of": [xs, elem(xs)],
                    "contains_l": [xs, elem(xs)], "list_fill": [elem(e.ty), INT],
                    "grid": [INT, INT, elem(elem(e.ty))], "join": [STR, lst(STR)]}.get(n, [None] * len(args))
        return [e.ty] * len(args)

    def conv(self, e, want):
        if is_list(want) and isinstance(e, A.ArrayLit) and e.ty != want:
            e.ty = want
            e.items = [self.conv(x, elem(want)) for x in e.items]
            return e
        if is_list(want) and is_list(e.ty) and elem(e.ty) == INT and elem(want) == FLOAT:
            raise unsupported("using a list of ints where a list of floats is needed (write the values as floats)", e)
        if want == CHAR and one_char(e):
            return A.CharLit(e.value, ty=CHAR, line=e.line, col=e.col)
        if want == FLOAT and e.ty in (INT, IDX):
            if isinstance(e, A.IntLit):
                e.ty = FLOAT
                return e
            return A.Intrinsic("i2f", [e], ty=FLOAT, line=e.line, col=e.col)
        return e

    def fix(self, f, e):
        if isinstance(e, (A.BinOp, A.Compare, A.BoolOp)):
            e.left, e.right = self.fix(f, e.left), self.fix(f, e.right)
            if isinstance(e, A.BinOp) and e.ty == FLOAT or isinstance(e, A.Compare) and FLOAT in (e.left.ty, e.right.ty):
                e.left, e.right = self.conv(e.left, FLOAT), self.conv(e.right, FLOAT)
                e.true_div = e.op in ("/", "fdiv")
            if e.op == "fdiv":
                e.op, e.true_div = "/", True
        elif isinstance(e, A.UnaryOp):
            e.operand = self.fix(f, e.operand)
        elif isinstance(e, A.Index):
            e.target, e.index = self.fix(f, e.target), self.fix(f, e.index)
        elif isinstance(e, A.Len):
            e.arg = self.fix(f, e.arg)
        elif isinstance(e, A.ArrayLit):
            e.items = [self.fix(f, x) for x in e.items]
            if e.ty == ANY:
                e.ty = ARR
        elif isinstance(e, A.Call):
            g = self.info.funcs[e.func]
            e.args = [self.conv(self.fix(f, a), g.vars[p]) for a, p in zip(e.args, g.params)]
        elif isinstance(e, A.Intrinsic):
            e.args = [self.conv(self.fix(f, a), want) for a, want in zip(e.args, self.wants(e))]
            if partial(e.ty):
                e.ty = filled(e.ty)
        return e

    def fix_block(self, f, stmts):
        for k, s in enumerate(stmts):
            if isinstance(s, A.ExprStmt) and isinstance(s.expr, A.Intrinsic) and s.expr.name in ("push", "insert")                     and s.expr.args[0].ty == STR:
                x, v = s.expr.args[0], s.expr.args[-1]
                pos = {"line": s.line, "col": s.col, "end": s.end, "group": s.group, "extra": s.extra, "tie": s.tie}
                if s.expr.name == "push":
                    s = stmts[k] = A.AugAssign(x, "+", v, **pos)
                else:
                    other = A.Name(x.id, ty=STR, line=x.line, col=x.col)
                    s = stmts[k] = A.Assign(x, A.BinOp("+", v, other, ty=STR, line=v.line, col=v.col), **pos)
            if isinstance(s, (A.Assign, A.AugAssign)):
                s.value = self.fix(f, s.value)
                s.target = self.fix(f, s.target)
                s.value = self.conv(s.value, f.vars[s.target.id] if isinstance(s.target, A.Name) else s.target.ty)
                if isinstance(s, A.AugAssign) and s.op == "fdiv":
                    s.op = "/"
            elif isinstance(s, A.TupleAssign):
                s.values = [self.fix(f, v) for v in s.values]
                s.values = [self.conv(v, f.vars[t.id]) if isinstance(t, A.Name) else v for t, v in zip(s.targets, s.values)]
            elif isinstance(s, (A.If, A.While)):
                s.test = self.fix(f, s.test)
            elif isinstance(s, A.For):
                for k in ("start", "stop", "step", "iter"):
                    if getattr(s, k) is not None:
                        setattr(s, k, self.fix(f, getattr(s, k)))
            elif isinstance(s, A.Return) and s.value is not None:
                s.value = self.conv(self.fix(f, s.value), f.ret)
            elif isinstance(s, A.ExprStmt):
                s.expr = self.fix(f, s.expr)
            elif isinstance(s, A.Print):
                s.args = [self.fix(f, a) for a in s.args]
            for b in A.blocks(s):
                self.fix_block(f, b)

    def widths(self):
        for f in self.info.all():
            idx, defs = set(), {}
            for n in A.walk_all(f.body):
                if isinstance(n, A.For) and n.kind == "range":
                    idx.add(n.var)
                    idx |= {e.id for e in (n.start, n.stop) if isinstance(e, A.Name)}
                elif isinstance(n, A.Assign) and isinstance(n.target, A.Name):
                    defs.setdefault(n.target.id, []).append(n.value)
                elif isinstance(n, A.TupleAssign):
                    for t, v in zip(n.targets, n.values):
                        if isinstance(t, A.Name):
                            defs.setdefault(t.id, []).append(v)
                elif isinstance(n, A.Index):
                    idx |= arith_names(n.index)
            work = list(idx)
            while work:
                for e in defs.get(work.pop(), []):
                    for x in arith_names(e) - idx:
                        idx.add(x)
                        work.append(x)
            for n in idx:
                if f.vars.get(n) == INT:
                    f.vars[n] = IDX
        for f in self.info.funcs.values():
            vals = [s.value for s in A.walk_all(f.body) if isinstance(s, A.Return) and s.value is not None]
            is_idx = [isinstance(v, A.Len) or (isinstance(v, A.Name) and f.vars[v.id] == IDX) for v in vals]
            if f.ret == INT and vals and any(is_idx) and all(i or int_lit(v) for i, v in zip(is_idx, vals)):
                f.ret = IDX
        for f in self.info.all():
            for e in reversed([n for n in A.walk_all(f.body) if isinstance(n, A.Expr)]):
                self.refine(f, e)

    def refine(self, f, e):
        if e.ty != INT:
            return
        if isinstance(e, A.Name) and f.vars[e.id] == IDX:
            e.ty = IDX
        elif isinstance(e, A.Len) or (isinstance(e, A.Call) and self.info.funcs[e.func].ret == IDX) \
                or isinstance(e, A.Intrinsic) and e.name in ("map_len", "set_len"):
            e.ty = IDX
        elif isinstance(e, A.BinOp):
            sides = (e.left, e.right)
            if all(x.ty == IDX or int_lit(x) for x in sides) and any(x.ty == IDX for x in sides):
                e.ty = IDX
        elif isinstance(e, A.UnaryOp) and e.operand.ty == IDX:
            e.ty = IDX


def arith_names(e):
    if isinstance(e, A.Name):
        return {e.id}
    if isinstance(e, A.BinOp) and e.op in "+-*/%":
        return arith_names(e.left) | arith_names(e.right)
    if isinstance(e, A.UnaryOp) and e.op == "-":
        return arith_names(e.operand)
    return set()
