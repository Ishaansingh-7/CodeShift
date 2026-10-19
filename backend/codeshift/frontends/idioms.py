import copy
import re
from collections import Counter

from .. import ast as A


def counts(stmts):
    return Counter(n.id for n in A.walk_all(stmts) if isinstance(n, A.Name))


def written(stmts, name):
    return any(A.writes(s, name) for s in A.walk_all(stmts) if isinstance(s, A.Stmt))


def pos(node, end=None):
    return {"line": node.line, "col": node.col, "end": end if end is not None else node.end}


def assign(targets, values, at):
    if len(targets) == 1 and len(values) == 1:
        return A.Assign(targets[0], values[0], **at)
    if len(targets) == 2 and len(values) == 2 and A.same(targets[0], values[1]) and A.same(targets[1], values[0]):
        return A.Swap(targets[0], targets[1], **at)
    return A.TupleAssign(targets, values, **at)


SPEC = re.compile(r"%(-)?(\d+)?(?:\.(\d+))?(lld|ld|d|f|s|c)")


def spec_value(m, arg, at):
    flag, width, prec, kind = m.groups()
    if (kind == "f") != bool(prec):
        return None
    v = arg
    if kind == "f":
        v = A.Intrinsic("fixed", [v, A.IntLit(int(prec), **at)], **at)
    elif width and kind != "s":
        v = A.Intrinsic("str", [v], **at)
    if width:
        v = A.Intrinsic("ljust" if flag else "rjust", [v, A.IntLit(int(width), **at)], **at)
    return v


def formatted(text, args, at):
    out, k, pos = [], 0, 0
    while pos < len(text):
        j = text.find("%", pos)
        if j < 0:
            out.append(A.StrLit(text[pos:], **at))
            break
        if j > pos:
            out.append(A.StrLit(text[pos:j], **at))
        if text.startswith("%%", j):
            out.append(A.StrLit("%", **at))
            pos = j + 2
            continue
        m = SPEC.match(text, j)
        if not m or k >= len(args):
            return None
        v = spec_value(m, args[k], at)
        if v is None:
            return None
        out.append(v)
        k += 1
        pos = m.end()
    if k != len(args):
        return None
    merged = []
    for x in out:
        if isinstance(x, A.StrLit) and merged and isinstance(merged[-1], A.StrLit):
            merged[-1] = A.StrLit(merged[-1].value + x.value, **at)
        else:
            merged.append(x)
    if not merged:
        return A.StrLit("", **at)
    e = merged[0]
    for x in merged[1:]:
        e = A.BinOp("+", e, x, **at)
    return e


def words(text, mark, exprs, at):
    out, literal = [], []
    for piece in text.split(" "):
        if not piece:
            if out and literal[-1]:
                out[-1] = A.StrLit(out[-1].value + " ", **at)
            else:
                out.append(A.StrLit("", **at))
                literal.append(True)
            continue
        if piece[0] == mark and piece[-1] == mark and piece.count(mark) == 2:
            out.append(exprs[int(piece[1:-1])])
            literal.append(False)
        elif mark in piece:
            out.append(glued(piece, mark, exprs, at))
            literal.append(False)
        elif out and literal[-1] and out[-1].value.strip(" ") == "":
            out[-1] = A.StrLit(out[-1].value + " " + piece if out[-1].value else " " + piece, **at)
        else:
            out.append(A.StrLit(piece, **at))
            literal.append(True)
    return out


def glued(piece, mark, exprs, at):
    out = None
    for k, part in enumerate(piece.split(mark)):
        if not part:
            continue
        x = A.StrLit(part, **at) if k % 2 == 0 else A.Intrinsic("str", [exprs[int(part)]], **at)
        out = x if out is None else A.BinOp("+", out, x, **at)
    return out


def declare(names, values, types, at):
    seen = set()
    for n, v in zip(names, values):
        if A.names(v) & seen:
            out = []
            for name, value, ty in zip(names, values, types):
                out.append(A.Assign(name, value, ty, **at))
            return out
        seen.add(n.id)
    node = assign(names, values, at)
    if isinstance(node, A.Assign):
        node.decl = types[0]
    return [node]


def fold_swaps(stmts, uses):
    out = []
    k = 0
    while k < len(stmts):
        s = stmts[k]
        for b in A.blocks(s):
            b[:] = fold_swaps(b, uses)
        if k + 2 < len(stmts):
            a, b, c = stmts[k:k + 3]
            if (isinstance(a, A.Assign) and a.decl and isinstance(a.target, A.Name) and uses[a.target.id] == 2
                    and isinstance(b, A.Assign) and isinstance(c, A.Assign) and isinstance(c.value, A.Name)
                    and c.value.id == a.target.id and a.target.id not in A.names(b) and not A.same(b.target, c.target)):
                x, y = c.target, b.target
                at = {"line": a.line, "col": a.col, "end": c.end}
                if A.same(a.value, y) and A.same(b.value, x):
                    out.append(A.Swap(y, x, **at))
                else:
                    out.append(A.TupleAssign([x, y], [a.value, b.value], **at))
                k += 3
                continue
        out.append(s)
        k += 1
    return out


def make_for(init, cond, update, body, at, scoped):
    step = None
    if isinstance(update, A.AugAssign) and update.op in "+-" and isinstance(update.value, A.IntLit):
        step = update.value.value if update.op == "+" else -update.value.value
    v = init.target.id if isinstance(init, A.Assign) and isinstance(init.target, A.Name) else None
    ok = (scoped and v and step and isinstance(cond, A.Compare) and isinstance(cond.left, A.Name)
          and cond.left.id == v and isinstance(update.target, A.Name) and update.target.id == v)
    if ok:
        stop = cond.right
        if not (cond.op == "<" and step > 0 or cond.op == ">" and step < 0
                or cond.op == "<=" and step > 0 or cond.op == ">=" and step < 0):
            ok = False
        elif cond.op in ("<=", ">="):
            stop = A.BinOp("+" if step > 0 else "-", stop, A.IntLit(1, line=stop.line, col=stop.col), line=stop.line, col=stop.col)
        changing = A.names(cond.right) | {v}
        if ok and (any(written(body, n) for n in changing) or any(isinstance(n, (A.Call, A.Index)) for n in A.walk(cond.right))):
            ok = False
    if ok:
        return [A.For(v, "range", body, init.value, stop, A.IntLit(step, line=update.line, col=update.col), **at)]
    loop = A.While(cond or A.BoolLit(True, line=at["line"], col=at["col"]), body + ([update] if update else []), **at)
    if update is not None:
        for block, c in list(continues(body)):
            again = copy.deepcopy(update)
            again.tie = loop
            block.insert(block.index(c), again)
    out = []
    for s in (init, update):
        if s is not None:
            s.tie = loop
    if init is not None:
        out.append(init)
    out.append(loop)
    return out


def attach(m, spans):
    stmts = sorted((s for s in A.walk_all([*m.functions, *m.body]) if isinstance(s, A.Stmt)), key=lambda s: s.line)
    for names, first, last in spans:
        owner = next((s for s in stmts if any(isinstance(n, A.Intrinsic) and n.name in names
                                              for e in A.heads(s) for n in A.walk(e))), None)
        if owner is not None:
            owner.extra += list(range(first, last + 1))
        elif m.wrap:
            m.wrap.append((first, last))


def continues(stmts):
    for s in stmts:
        if isinstance(s, A.Continue):
            yield stmts, s
        elif not isinstance(s, (A.While, A.For)):
            for b in A.blocks(s):
                yield from continues(b)


def inline_arrays(stmts):
    uses = counts(stmts)
    out = list(stmts)
    for s in list(out):
        if not (isinstance(s, A.Assign) and s.decl and isinstance(s.target, A.Name) and isinstance(s.value, A.ArrayLit)
                and uses[s.target.id] == 2):
            continue
        name = s.target.id
        k = out.index(s)
        for user in out[k + 1:]:
            calls = [c for c in A.walk(user) if isinstance(c, A.Call)]
            hit = next(((c, i) for c in calls for i, a in enumerate(c.args) if isinstance(a, A.Name) and a.id == name), None)
            if hit:
                hit[0].args[hit[1]] = s.value
                user.extra += [s.line, *s.extra]
                out.remove(s)
                break
            if name in A.names(user):
                break
    return out
