from dataclasses import dataclass, field, fields


@dataclass(eq=False)
class Node:
    line: int = field(default=0, kw_only=True)
    col: int = field(default=0, kw_only=True)


@dataclass(eq=False)
class Expr(Node):
    ty: str | None = field(default=None, kw_only=True)


@dataclass(eq=False)
class IntLit(Expr):
    value: int


@dataclass(eq=False)
class FloatLit(Expr):
    value: float


@dataclass(eq=False)
class BoolLit(Expr):
    value: bool


@dataclass(eq=False)
class StrLit(Expr):
    value: str


@dataclass(eq=False)
class CharLit(Expr):
    value: str


@dataclass(eq=False)
class ArrayLit(Expr):
    items: list


@dataclass(eq=False)
class Name(Expr):
    id: str


@dataclass(eq=False)
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(eq=False)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(eq=False)
class Compare(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(eq=False)
class BoolOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(eq=False)
class Index(Expr):
    target: Expr
    index: Expr


@dataclass(eq=False)
class Call(Expr):
    func: str
    args: list


@dataclass(eq=False)
class Len(Expr):
    arg: Expr


@dataclass(eq=False)
class Intrinsic(Expr):
    name: str
    args: list


@dataclass(eq=False)
class Stmt(Node):
    end: int = field(default=0, kw_only=True)
    group: int | None = field(default=None, kw_only=True)
    extra: list = field(default_factory=list, kw_only=True)
    tie: object = field(default=None, kw_only=True)


@dataclass(eq=False)
class Param(Node):
    name: str
    ty: str | None = None


@dataclass(eq=False)
class FunctionDef(Stmt):
    name: str
    params: list
    body: list
    ret: str | None = None


@dataclass(eq=False)
class Assign(Stmt):
    target: Expr
    value: Expr
    decl: str | None = None


@dataclass(eq=False)
class AugAssign(Stmt):
    target: Expr
    op: str
    value: Expr


@dataclass(eq=False)
class TupleAssign(Stmt):
    targets: list
    values: list


@dataclass(eq=False)
class Swap(Stmt):
    a: Expr
    b: Expr


@dataclass(eq=False)
class If(Stmt):
    test: Expr
    body: list
    orelse: list = field(default_factory=list)


@dataclass(eq=False)
class While(Stmt):
    test: Expr
    body: list


@dataclass(eq=False)
class For(Stmt):
    var: str
    kind: str
    body: list
    start: Expr | None = None
    stop: Expr | None = None
    step: Expr | None = None
    iter: Expr | None = None


@dataclass(eq=False)
class Return(Stmt):
    value: Expr | None = None


@dataclass(eq=False)
class Break(Stmt):
    pass


@dataclass(eq=False)
class Continue(Stmt):
    pass


@dataclass(eq=False)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(eq=False)
class Print(Stmt):
    args: list


@dataclass(eq=False)
class Module(Node):
    functions: list
    body: list
    entry: tuple | None = None
    lang: str = "python"
    wrap: list = field(default_factory=list)


META = {"line", "col", "ty", "end", "group", "extra", "tie"}


def children(node):
    for f in fields(node):
        if f.name in META:
            continue
        v = getattr(node, f.name)
        if isinstance(v, Node):
            yield v
        elif isinstance(v, list):
            yield from (x for x in v if isinstance(x, Node))


def walk(node):
    yield node
    for c in children(node):
        yield from walk(c)


def walk_all(nodes):
    for n in nodes:
        yield from walk(n)


def blocks(s):
    if isinstance(s, If):
        return [s.body, s.orelse]
    if isinstance(s, (While, For, FunctionDef)):
        return [s.body]
    return []


def heads(s):
    if isinstance(s, (If, While)):
        return [s.test]
    if isinstance(s, For):
        return [e for e in (s.start, s.stop, s.step, s.iter) if e is not None]
    return [s]


def names(node):
    out = set()
    for n in walk(node):
        if isinstance(n, Name):
            out.add(n.id)
        elif isinstance(n, For):
            out.add(n.var)
    return out


def own_names(s):
    out = {s.var} if isinstance(s, For) else set()
    for e in heads(s):
        out |= names(e)
    return out


def writes(s, name):
    if isinstance(s, (Assign, AugAssign)):
        return isinstance(s.target, Name) and s.target.id == name
    if isinstance(s, TupleAssign):
        return any(isinstance(t, Name) and t.id == name for t in s.targets)
    if isinstance(s, Swap):
        return any(isinstance(t, Name) and t.id == name for t in (s.a, s.b))
    return False


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, Node):
        return all(same(getattr(a, f.name), getattr(b, f.name)) for f in fields(a) if f.name not in META)
    if isinstance(a, list):
        return len(a) == len(b) and all(map(same, a, b))
    return a == b


ESC = {"\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\0"}


def quote(s, q='"'):
    return q + "".join(ESC.get(c, "\\" + c if c == q else c) for c in s) + q


PREC = {"||": 12, "&&": 11, "==": 7, "!=": 7, "<": 6, "<=": 6, ">": 6, ">=": 6, "+": 4, "-": 4, "*": 3, "/": 3, "%": 3,
        "fdiv": 3}


def show(e):
    return _show(e)[0]


def _show(e):
    if isinstance(e, IntLit):
        return str(e.value), 2 if e.value < 0 else 1
    if isinstance(e, BoolLit):
        return ("true" if e.value else "false"), 1
    if isinstance(e, FloatLit):
        return repr(e.value), 2 if e.value < 0 else 1
    if isinstance(e, StrLit):
        return quote(e.value), 1
    if isinstance(e, CharLit):
        return quote(e.value, "'"), 1
    if isinstance(e, ArrayLit):
        return "[" + ", ".join(map(show, e.items)) + "]", 1
    if isinstance(e, Name):
        return e.id, 1
    if isinstance(e, (BinOp, Compare, BoolOp)):
        p = PREC[e.op]
        l, lp = _show(e.left)
        r, rp = _show(e.right)
        return f"{f'({l})' if lp > p else l} {'/' if e.op == 'fdiv' else e.op} {f'({r})' if rp >= p else r}", p
    if isinstance(e, UnaryOp):
        x, xp = _show(e.operand)
        return e.op + (f"({x})" if xp > 2 else x), 2
    if isinstance(e, Index):
        return f"{show(e.target)}[{show(e.index)}]", 1
    if isinstance(e, Call):
        return f"{e.func}({', '.join(map(show, e.args))})", 1
    if isinstance(e, Len):
        return f"len({show(e.arg)})", 1
    if isinstance(e, Intrinsic):
        return f"@{e.name}({', '.join(map(show, e.args))})", 1
    raise TypeError(e)
