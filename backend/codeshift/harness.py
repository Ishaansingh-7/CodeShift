import copy

from . import ast as A
from .errors import CompileError
from .pipeline import emit, front
from .semantic import ARR, BOOL, IDX, INT, VOID, analyze

MARK = "@@CS@@"
AUTO = [(0, 0), (1, 1), (7, 3), (25, 4), (100, 30)]


def subject(module):
    for n in A.walk_all(module.body):
        if isinstance(n, A.Call):
            return n.func
    return module.functions[0].name if len(module.functions) == 1 else None


def show(value, spread):
    if isinstance(value, str):
        return A.quote(value)
    if isinstance(value, list):
        text = ", ".join(map(str, value))
        return text if spread else f"[{text}]"
    return str(value)


class Harness:
    def __init__(self, src, tgt, code, inputs=None):
        self.src, self.tgt, self.code = src, tgt, code
        _, self.module, self.info = front(src, code)
        self.fn = subject(self.module)
        if self.fn is None or self.fn not in self.info.funcs:
            raise CompileError("harness", "Unsupported: no function to test")
        self.cases = self.from_samples(inputs) if inputs else self.automatic()
        self.divides = any(isinstance(n, (A.BinOp, A.AugAssign)) and n.op in ("/", "%")
                           for n in A.walk_all(self.module.functions))

    def from_samples(self, inputs):
        f = self.info.funcs[self.fn]
        cases = []
        for value in inputs:
            body = copy.deepcopy(self.module.body)
            call = next((n for n in A.walk_all(body) if isinstance(n, A.Call) and n.func == self.fn), None)
            if call is None:
                raise CompileError("harness", f"Unsupported: the entry point does not call {self.fn}()")
            slots = self.slots(body, call, f)
            used = self.fill(slots, value)
            if used is None:
                raise CompileError("harness", "Unsupported: the sample inputs do not fit this code")
            spread = isinstance(value, list) and len(used) > 1
            cases.append({"value": value, "label": show(value, spread), "body": body, "params": used})
        self.label = "Input " + ", ".join(cases[0]["params"]) if cases else "Input"
        return cases

    def slots(self, body, call, f):
        assigned = {s.target.id: s.value for s in body if isinstance(s, A.Assign) and isinstance(s.target, A.Name)}
        out = []
        for a, p in zip(call.args, f.params):
            node = assigned.get(a.id, a) if isinstance(a, A.Name) else a
            if isinstance(node, (A.IntLit, A.ArrayLit, A.StrLit)):
                out.append((node, p))
        return out

    def fill(self, slots, value):
        kinds = lambda t: [(n, p) for n, p in slots if isinstance(n, t)]
        ints, arrs, strs = kinds(A.IntLit), kinds(A.ArrayLit), kinds(A.StrLit)
        if isinstance(value, str) and len(strs) == 1:
            strs[0][0].value = value
            return [strs[0][1]]
        if isinstance(value, list) and len(arrs) == 1 and (not ints or len(ints) != len(value)):
            node = arrs[0][0]
            node.items = [A.IntLit(v, line=node.line, col=node.col) for v in value]
            return [arrs[0][1]]
        if isinstance(value, list) and value and len(ints) == len(value) and all(isinstance(v, int) for v in value):
            for (node, _), v in zip(ints, value):
                node.value = v
            return [p for _, p in ints]
        if isinstance(value, int) and len(ints) == 1:
            ints[0][0].value = value
            return [ints[0][1]]
        return None

    def automatic(self):
        f = self.info.funcs[self.fn]
        if not f.params or f.ret == VOID or any(f.vars[p] not in (INT, IDX) for p in f.params):
            raise CompileError("harness", f"Unsupported: auto inputs need {self.fn}() to take ints and return a value")
        node = f.node
        self.label = "Input " + ", ".join(f.params)
        cases = []
        for first, rest in AUTO:
            values = [first] + [rest] * (len(f.params) - 1)
            call = A.Call(self.fn, [A.IntLit(v, line=node.line, col=node.col) for v in values], line=node.line, col=node.col)
            body = [A.Print([call], line=node.line, col=node.col, end=node.line)]
            cases.append({"value": values, "label": show(values, True), "body": body, "params": f.params})
        return cases

    def body(self, indices, marks=True):
        out = []
        for k in indices:
            body = copy.deepcopy(self.cases[k]["body"])
            if k:
                rename(body, f"_{k}")
            out += body
            if marks:
                out.append(A.Print([A.StrLit(MARK)], line=1, col=1, end=1))
        return out

    def programs(self, indices, marks=True):
        module = A.Module(self.module.functions, self.body(indices, marks), entry=self.module.entry,
                          lang=self.module.lang, line=1, col=1)
        info = analyze(module)
        self.printed = next((p.args[0].ty for p in A.walk_all(module.body) if isinstance(p, A.Print) and p.args
                             and not isinstance(p.args[0], A.StrLit)), None)
        tgt = "\n".join(t for t, _ in emit(self.tgt, module, info)[1]) + "\n"
        backend, lines = emit(self.src, module, info)
        entry = [t for t, _ in lines[backend.entry:getattr(backend, "entry_end", None)]]
        return splice(self.code, self.module, entry, backend.prelude), tgt


def rename(body, suffix):
    names = {t.id for s in A.walk_all(body) if isinstance(s, (A.Assign, A.TupleAssign))
             for t in ([s.target] if isinstance(s, A.Assign) else s.targets) if isinstance(t, A.Name)}
    for n in A.walk_all(body):
        if isinstance(n, A.Name) and n.id in names:
            n.id += suffix


def splice(code, module, entry, prelude):
    lines = code.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if module.entry:
        start, end = module.entry
        drop = set(range(start, end + 1))
    else:
        start = len(lines) + 1
        drop = {n for s in module.body for n in range(s.line, s.end + 1)}
    before = [t for n, t in enumerate(lines, 1) if n < start and n not in drop]
    after = [t for n, t in enumerate(lines, 1) if n > start and n not in drop]
    while before and not before[-1].strip():
        before.pop()
    present = {x.strip() for x in lines}
    head = [p for p in prelude if p.split("\n")[0] not in present and p.removeprefix("import ") not in present]
    at = 1 if before and before[0].startswith("package ") else 0
    before = before[:at] + ([""] if at and head else []) + head + before[at:]
    return "\n".join(before + ([""] if before else []) + entry + after) + "\n"


def number(x):
    try:
        return float(x)
    except ValueError:
        return None


BOOLS = {"True": "1", "true": "1", "False": "0", "false": "0"}


def words(text):
    for ch in "[](),'\"":
        text = text.replace(ch, " ")
    return [[BOOLS.get(w, w) for w in line.split()] for line in text.strip().splitlines()]


def same(a, b, ty=None):
    if ty in (BOOL, ARR):
        return canon(a, ty) == canon(b, ty)
    wa, wb = words(a), words(b)
    if len(wa) != len(wb) or any(len(x) != len(y) for x, y in zip(wa, wb)):
        return False
    for x, y in zip(sum(wa, []), sum(wb, [])):
        if x == y:
            continue
        if not any(c in x + y for c in ".eEin"):
            return False
        fx, fy = number(x), number(y)
        if fx is None or fy is None or abs(fx - fy) > 1e-9 * max(1.0, abs(fx), abs(fy)):
            return False
    return True


def canon(text, ty):
    text = text.strip()
    if ty == BOOL:
        return {"true": "T", "1": "T", "false": "F", "0": "F"}.get(text.lower(), text)
    if ty == ARR:
        return tuple(int(x) for x in "".join(c if c in "-0123456789" else " " for c in text).split() if x != "-")
    return text
