from .cfg import reachable, split
from .ir import KIND, Const

NAC = "NAC"
PURE = {"copy", "bin", "un", "load"}
INT64 = range(-2 ** 63, 2 ** 63)


def optimize(funcs):
    for code in funcs:
        for _ in range(50):
            if not (fold(code) | cse(code) | copy_prop(code) | dce(code)):
                break
    rows = []
    for code in funcs:
        for ins in code:
            cur = ins.text
            if ins.dead:
                rows.append({"text": ins.orig, "kind": ins.kind, "tag": ins.tag})
            elif cur != ins.orig:
                rows.append({"text": ins.orig, "kind": ins.kind, "tag": ins.tag})
                rows.append({"text": cur, "kind": KIND.get(ins.op, "code"), "tag": "+"})
            else:
                rows.append({"text": ins.orig, "kind": ins.kind, "tag": ""})
    return rows


def count(funcs, live):
    return sum(1 for code in funcs for i in code[1:] if i.op != "label" and not (live and i.dead))


def mark(ins, tag):
    if not ins.tag:
        ins.tag = tag


def kill(ins, tag="dce"):
    ins.dead = True
    if not ins.tag:
        ins.tag = "copy-prop" if ins.op == "copy" and isinstance(ins.args[0], str) else tag


def cfg(code):
    live = [i for i in code[1:] if not i.dead]
    blocks, succ, preds = split(live)
    return blocks, succ, preds, reachable(succ)


def forward(blocks, preds, reach, entry, meet, transfer, init):
    ins_, outs = {}, {b: init for b in reach}
    changed = True
    while changed:
        changed = False
        for b in sorted(reach):
            sources = [outs[p] for p in preds[b] if p in reach]
            state = meet(([entry] if b == 0 else []) + sources)
            ins_[b] = state
            for i in blocks[b]:
                state = transfer(i, state)
            if state != outs[b]:
                outs[b] = state
                changed = True
    return ins_


def evaluate(op, name, vals):
    if op == "un":
        (a,) = vals
        if name == "-" and a.ty == "int" and -a.value in INT64:
            return Const(-a.value, "int")
        if name == "!" and a.ty in ("bool", "int"):
            return Const(not a.value, "bool")
        if name == "len" and a.ty == "str":
            return Const(len(a.value), "int")
        return None
    a, b = vals
    x, y = a.value, b.value
    cmp = {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y, "==": x == y, "!=": x != y} if a.ty == b.ty else {}
    if a.ty == b.ty == "int":
        if name in ("+", "-", "*"):
            r = x + y if name == "+" else x - y if name == "-" else x * y
            return Const(r, "int") if r in INT64 else None
        if name in ("/", "%"):
            return Const(x // y if name == "/" else x % y, "int") if x >= 0 and y > 0 else None
        if name in cmp:
            return Const(cmp[name], "bool")
    if a.ty in ("str", "char") and b.ty in ("str", "char"):
        if name == "+":
            return Const(x + y, "str")
        if name in ("==", "!="):
            return Const(cmp.get(name, name == "!="), "bool")
    if a.ty == b.ty and a.ty in ("bool", "char") and name in cmp:
        return Const(cmp[name], "bool")
    return None


def fold(code):
    blocks, succ, preds, reach = cfg(code)

    def value(a, st):
        if isinstance(a, Const):
            return NAC if a.ty == "arr" else a
        return st.get(a)

    def transfer(i, st):
        if i.dst is None:
            return st
        st = dict(st)
        if i.op == "copy":
            v = value(i.args[0], st)
        elif i.op in ("bin", "un"):
            vals = [value(a, st) for a in i.args]
            v = NAC if NAC in vals else None if None in vals else evaluate(i.op, i.name, vals) or NAC
        else:
            v = NAC
        if v is None:
            st.pop(i.dst, None)
        else:
            st[i.dst] = v
        return st

    def meet(states):
        out = {}
        for st in states:
            for k, v in st.items():
                out[k] = v if k not in out or out[k] == v else NAC
        return out

    entry = {p: NAC for p in code[0].args}
    ins_ = forward(blocks, preds, reach, entry, meet, transfer, {})
    changed = False
    for b in sorted(reach):
        st = ins_[b]
        for i in blocks[b]:
            if i.op not in ("label", "goto"):
                args = [st[a] if isinstance(a, str) and isinstance(st.get(a), Const) else a for a in i.args]
                if args != i.args:
                    i.args = args
                    mark(i, "fold")
                    changed = True
                if i.op in ("bin", "un") and all(isinstance(a, Const) and a.ty != "arr" for a in i.args):
                    r = evaluate(i.op, i.name, i.args)
                    if r is not None:
                        i.op, i.args, i.name = "copy", [r], None
                        mark(i, "fold")
                        changed = True
                if i.op == "iffalse" and isinstance(i.args[0], Const):
                    if i.args[0].value:
                        kill(i, "fold")
                    else:
                        i.op, i.args = "goto", []
                        mark(i, "fold")
                    changed = True
            st = transfer(i, st)
    return changed


def operand(a):
    return a if isinstance(a, str) else ("const", a.ty, str(a))


def ekey(i):
    if i.op in ("bin", "un", "load") and all(not isinstance(a, Const) or a.ty != "arr" for a in i.args):
        return (i.op, i.name, *map(operand, i.args))
    return None


def cse(code):
    blocks, succ, preds, reach = cfg(code)

    def transfer(i, st):
        if i.dst is None and i.op not in ("store", "call"):
            return st
        out = {f for f in st if f[1] != i.dst and i.dst not in f[0][2:]}
        if i.op in ("store", "call"):
            out = {f for f in out if f[0][0] != "load" and f[0][:2] != ("un", "len")}
        k = ekey(i)
        if k and i.dst and i.dst not in k[2:]:
            out.add((k, i.dst))
        return frozenset(out)

    universe = frozenset((ekey(i), i.dst) for blk in blocks for i in blk if ekey(i) and i.dst)
    ins_ = forward(blocks, preds, reach, frozenset(), lambda sts: frozenset.intersection(*sts) if sts else frozenset(),
                   transfer, universe)
    changed = False
    for b in sorted(reach):
        st = ins_[b]
        for i in blocks[b]:
            k = ekey(i)
            if k and i.dst:
                holders = sorted(h for kk, h in st if kk == k and h != i.dst)
                if holders:
                    i.op, i.args, i.name = "copy", [holders[0]], None
                    mark(i, "cse")
                    changed = True
            st = transfer(i, st)
    return changed


def copy_prop(code):
    blocks, succ, preds, reach = cfg(code)

    def transfer(i, st):
        if i.dst is None:
            return st
        out = {(x, y) for x, y in st if i.dst not in (x, y)}
        if i.op == "copy" and isinstance(i.args[0], str) and i.args[0] != i.dst:
            out.add((i.dst, i.args[0]))
        return frozenset(out)

    universe = frozenset((i.dst, i.args[0]) for blk in blocks for i in blk
                         if i.op == "copy" and isinstance(i.args[0], str) and i.args[0] != i.dst)
    ins_ = forward(blocks, preds, reach, frozenset(), lambda sts: frozenset.intersection(*sts) if sts else frozenset(),
                   transfer, universe)
    changed = False
    for b in sorted(reach):
        st = ins_[b]
        for i in blocks[b]:
            if i.op not in ("label", "goto"):
                copies = dict(st)
                args = [copies.get(a, a) if isinstance(a, str) else a for a in i.args]
                if args != i.args:
                    i.args = args
                    mark(i, "copy-prop")
                    changed = True
            st = transfer(i, st)
    return changed


def dce(code):
    blocks, succ, preds, reach = cfg(code)
    changed = False
    for b, blk in enumerate(blocks):
        if b not in reach:
            for i in blk:
                kill(i)
            changed = True
    live_in = {b: frozenset() for b in reach}
    stable = False
    while not stable:
        stable = True
        for b in sorted(reach, reverse=True):
            live = set().union(*(live_in[s] for s in succ[b] if s in reach))
            for i in reversed(blocks[b]):
                if i.dst:
                    live.discard(i.dst)
                live |= set(i.uses())
            if frozenset(live) != live_in[b]:
                live_in[b] = frozenset(live)
                stable = False
    for b in sorted(reach):
        live = set().union(*(live_in[s] for s in succ[b] if s in reach))
        for i in reversed(blocks[b]):
            if i.dst and i.op in PURE and i.dst not in live:
                kill(i)
                changed = True
                continue
            if i.dst:
                live.discard(i.dst)
            live |= set(i.uses())
    live = [i for i in code[1:] if not i.dead]
    for a, b in zip(live, live[1:]):
        if a.op == "goto" and b.op == "label" and a.name == b.name:
            kill(a)
            changed = True
    return changed
