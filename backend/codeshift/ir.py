from dataclasses import dataclass, field

from . import ast as A
from .semantic import VOID, is_map

KIND = {"func": "label", "label": "label", "iffalse": "jump", "goto": "jump", "ret": "jump"}


class Const:
    def __init__(self, value, ty):
        self.value = value
        self.ty = ty

    def __str__(self):
        if self.ty == "bool":
            return "1" if self.value else "0"
        if self.ty == "str":
            return A.quote(self.value)
        if self.ty == "char":
            return A.quote(self.value, "'")
        if self.ty == "float":
            return repr(float(self.value))
        if self.ty == "arr":
            return "[" + ", ".join(map(str, self.value)) + "]"
        return str(self.value)

    def __eq__(self, other):
        return isinstance(other, Const) and self.ty == other.ty and str(self) == str(other)

    def __hash__(self):
        return hash((self.ty, str(self)))

    def vars(self):
        return [x for x in self.value if isinstance(x, str)] if self.ty == "arr" else []


@dataclass(eq=False)
class Ins:
    op: str
    dst: str | None = None
    args: list = field(default_factory=list)
    name: str | None = None
    orig: str = ""
    kind: str = ""
    tag: str = ""
    dead: bool = False

    def uses(self):
        if self.op == "func":
            return []
        out = []
        for a in self.args:
            out += [a] if isinstance(a, str) else a.vars()
        return out

    @property
    def text(self):
        a = [str(x) for x in self.args]
        op = self.op
        if op == "func":
            return f"{self.name}({', '.join(a)}):"
        if op == "label":
            return f"{self.name}:"
        if op == "copy":
            return f"  {self.dst} = {a[0]}"
        if op == "bin":
            return f"  {self.dst} = {a[0]} {self.name} {a[1]}"
        if op == "un":
            return f"  {self.dst} = {self.name} {a[0]}" if self.name.isalpha() else f"  {self.dst} = {self.name}{a[0]}"
        if op == "load":
            return f"  {self.dst} = {a[0]}[{a[1]}]"
        if op == "store":
            return f"  {a[0]}[{a[1]}] = {a[2]}"
        if op == "call":
            rhs = "call " + ", ".join([self.name] + a)
            return f"  {self.dst} = {rhs}" if self.dst else f"  {rhs}"
        if op == "iffalse":
            return f"  ifFalse {a[0]} goto {self.name}"
        if op == "goto":
            return f"  goto {self.name}"
        if op == "ret":
            return f"  return {a[0]}" if a else "  return"
        if op == "print":
            return f"  print {', '.join(a)}" + ("" if self.name is None else f", end={A.quote(self.name)}")
        raise ValueError(op)


def lower(module, info):
    funcs = [Lowerer(info.funcs[fn.name]).run() for fn in module.functions]
    if module.body:
        funcs.append(Lowerer(info.main).run())
    return funcs


class Lowerer:
    def __init__(self, f):
        self.f = f
        self.code = []
        self.nt = 0
        self.nl = 0
        self.temps = set()
        self.loops = []

    def run(self):
        f = self.f
        self.emit("func", args=list(f.params), name=f.name)
        self.block(f.body, None)
        if f.node is not None and f.ret == VOID and self.code[-1].op != "ret":
            self.emit("ret")
        labels = {}
        for ins in self.code:
            if ins.op == "label":
                labels[ins.name] = f"L{len(labels) + 1}"
        self.nt = 0
        temps = {}
        for ins in self.code:
            if ins.dst in self.temps and ins.dst not in temps:
                temps[ins.dst] = self.temp()
        rename = lambda a: temps.get(a, a) if isinstance(a, str) else \
            Const([rename(x) for x in a.value], "arr") if a.ty == "arr" else a
        for ins in self.code:
            if ins.op in ("label", "goto", "iffalse"):
                ins.name = labels[ins.name]
            if ins.op != "func":
                ins.dst = temps.get(ins.dst, ins.dst)
                ins.args = [rename(a) for a in ins.args]
            ins.orig = ins.text
            ins.kind = KIND.get(ins.op, "code")
        return self.code

    def emit(self, op, dst=None, args=(), name=None):
        self.code.append(Ins(op, dst, list(args), name))

    def temp(self):
        while True:
            name = f"t{self.nt}"
            self.nt += 1
            if name not in self.f.vars:
                self.temps.add(name)
                return name

    def label(self):
        self.nl += 1
        return f"@{self.nl}"

    def jumped(self):
        return self.code[-1].op in ("goto", "ret")

    def block(self, stmts, nxt):
        for k, s in enumerate(stmts):
            self.stmt(s, nxt if k == len(stmts) - 1 else None)

    def stmt(self, s, nxt):
        if isinstance(s, A.Assign):
            self.assign(s.target, s.value)
        elif isinstance(s, A.AugAssign):
            if isinstance(s.target, A.Name):
                v = self.atom(s.value)
                self.emit("bin", s.target.id, [s.target.id, v], s.op)
            else:
                a, i = self.atom(s.target.target), self.atom(s.target.index)
                t = self.temp()
                self.emit("load", t, [a, i])
                v = self.atom(s.value)
                u = self.temp()
                self.emit("bin", u, [t, v], s.op)
                self.emit("store", args=[a, i, u])
        elif isinstance(s, A.TupleAssign):
            targets = {t.id for t in s.targets if isinstance(t, A.Name)}
            reads = set().union(*(A.names(v) for v in s.values))
            if all(isinstance(t, A.Name) for t in s.targets) and not targets & reads:
                for t, v in zip(s.targets, s.values):
                    self.assign(t, v)
            else:
                temps = [self.fresh(v) for v in s.values]
                for t, v in zip(s.targets, temps):
                    self.store(t, v)
        elif isinstance(s, A.Swap):
            ta, tb = self.fresh(s.a), self.fresh(s.b)
            self.store(s.a, tb)
            self.store(s.b, ta)
        elif isinstance(s, A.If):
            self.if_(s, nxt)
        elif isinstance(s, A.While):
            head, end = self.label(), self.label()
            self.emit("label", name=head)
            self.emit("iffalse", args=[self.atom(s.test)], name=end)
            self.loops.append({"break": end, "cont": head})
            self.block(s.body, head)
            self.loops.pop()
            if not self.jumped():
                self.emit("goto", name=head)
            self.emit("label", name=end)
        elif isinstance(s, A.For):
            self.for_(s)
        elif isinstance(s, A.Return):
            self.emit("ret", args=[self.atom(s.value)] if s.value is not None else [])
        elif isinstance(s, A.Break):
            self.emit("goto", name=self.loops[-1]["break"])
        elif isinstance(s, A.Continue):
            loop = self.loops[-1]
            if loop["cont"] is None:
                loop["cont"] = self.label()
            self.emit("goto", name=loop["cont"])
        elif isinstance(s, A.ExprStmt):
            self.call(s.expr, None)
        elif isinstance(s, A.Print):
            end = getattr(s, "ending", "\n")
            self.emit("print", args=[self.atom(a) for a in s.args], name=None if end == "\n" else end)

    def if_(self, s, nxt):
        other = self.label()
        self.emit("iffalse", args=[self.atom(s.test)], name=other)
        self.block(s.body, nxt)
        if not s.orelse:
            self.emit("label", name=other)
            return
        end = None
        if not self.jumped():
            end = nxt or self.label()
            self.emit("goto", name=end)
        self.emit("label", name=other)
        self.block(s.orelse, nxt)
        if end is not None and end != nxt:
            self.emit("label", name=end)

    def for_(self, s):
        head, end = self.label(), self.label()
        if s.kind == "range":
            start = self.atom(s.start)
            stop, step = self.snapshot(s.stop), self.snapshot(s.step)
            self.emit("copy", s.var, [start])
            self.emit("label", name=head)
            t = self.temp()
            self.emit("bin", t, [s.var, stop], "<" if s.step.value > 0 else ">")
            self.emit("iffalse", args=[t], name=end)
            self.body(s.body, end)
            self.emit("bin", s.var, [s.var, step], "+")
        else:
            it = self.atom(s.iter)
            if is_map(s.iter.ty):
                keys = self.temp()
                self.emit("call", keys, [it], "@map_keys")
                it = keys
            n, k = self.temp(), self.temp()
            self.emit("un", n, [it], "len")
            self.emit("copy", k, [Const(0, "int")])
            self.emit("label", name=head)
            t = self.temp()
            self.emit("bin", t, [k, n], "<")
            self.emit("iffalse", args=[t], name=end)
            self.emit("load", s.var, [it, k])
            self.body(s.body, end)
            self.emit("bin", k, [k, Const(1, "int")], "+")
        self.emit("goto", name=head)
        self.emit("label", name=end)

    def body(self, stmts, end):
        self.loops.append({"break": end, "cont": None})
        self.block(stmts, None)
        loop = self.loops.pop()
        if loop["cont"] is not None:
            self.emit("label", name=loop["cont"])

    def snapshot(self, e):
        a = self.atom(e)
        if isinstance(a, str) and a not in self.f.vars:
            return a
        t = self.temp()
        self.emit("copy", t, [a])
        return t

    def fresh(self, e):
        t = self.temp()
        self.into(e, t)
        return t

    def assign(self, target, value):
        if isinstance(target, A.Name):
            self.into(value, target.id)
        else:
            v = self.atom(value)
            self.emit("store", args=[self.atom(target.target), self.atom(target.index), v])

    def store(self, target, v):
        if isinstance(target, A.Name):
            self.emit("copy", target.id, [v])
        else:
            self.emit("store", args=[self.atom(target.target), self.atom(target.index), v])

    def into(self, e, dst):
        if isinstance(e, (A.BinOp, A.Compare)):
            l, r = self.atom(e.left), self.atom(e.right)
            self.emit("bin", dst, [l, r], e.op)
        elif isinstance(e, A.BoolOp):
            if dst in self.f.vars:
                t = self.fresh(e)
                self.emit("copy", dst, [t])
                return
            end = self.label()
            self.into(e.left, dst)
            if e.op == "&&":
                self.emit("iffalse", args=[dst], name=end)
            else:
                other = self.label()
                self.emit("iffalse", args=[dst], name=other)
                self.emit("goto", name=end)
                self.emit("label", name=other)
            self.into(e.right, dst)
            self.emit("label", name=end)
        elif isinstance(e, A.UnaryOp):
            self.emit("un", dst, [self.atom(e.operand)], e.op)
        elif isinstance(e, A.Index):
            a, i = self.atom(e.target), self.atom(e.index)
            self.emit("load", dst, [a, i])
        elif isinstance(e, A.Len):
            self.emit("un", dst, [self.atom(e.arg)], "len")
        elif isinstance(e, (A.Call, A.Intrinsic)):
            self.call(e, dst)
        else:
            self.emit("copy", dst, [self.atom(e)])

    def call(self, e, dst):
        args = [self.atom(a) for a in e.args]
        self.emit("call", dst, args, "@" + e.name if isinstance(e, A.Intrinsic) else e.func)

    def atom(self, e):
        if isinstance(e, A.IntLit):
            return Const(float(e.value), "float") if e.ty == "float" else Const(e.value, "int")
        if isinstance(e, A.BoolLit):
            return Const(e.value, "bool")
        if isinstance(e, A.FloatLit):
            return Const(e.value, "float")
        if isinstance(e, A.StrLit):
            return Const(e.value, "str")
        if isinstance(e, A.CharLit):
            return Const(e.value, "char")
        if isinstance(e, A.ArrayLit):
            return Const([self.atom(x) for x in e.items], "arr")
        if isinstance(e, A.Name):
            return e.id
        return self.fresh(e)
