from . import ast as A

ENTRY = -1


def absorbs(s):
    for b in (s.body, s.orelse):
        if len(b) > 1 or (b and isinstance(b[0], (A.While, A.For))):
            return False
        if b and isinstance(b[0], A.If) and not (b is s.orelse and absorbs(b[0])):
            return False
    return True


class Grouper:
    def __init__(self):
        self.names = []

    def new(self, name):
        self.names.append(name)
        return len(self.names) - 1

    def run(self, module):
        for n in A.walk_all([*module.functions, *module.body]):
            if isinstance(n, A.Stmt):
                n.group = None
        seen_main = set()
        for item in sorted([*module.functions, *module.body], key=lambda n: n.line):
            if isinstance(item, A.FunctionDef):
                item.group = self.new(f"Function {item.name}")
                self.visit(item.body, {p.name for p in item.params}, 0)
            else:
                self.visit([item], seen_main, 0)
        return self.names

    def visit(self, stmts, seen, depth):
        for s in stmts:
            owner = s.tie or s
            if owner.group is None:
                owner.group = self.new(self.name(owner, seen, depth))
            if s.tie:
                s.group = owner.group
                self.name(s, seen, depth)
                continue
            if isinstance(s, A.If):
                if absorbs(s):
                    for c in A.walk_all(s.body + s.orelse):
                        if isinstance(c, A.Stmt):
                            c.group = s.group
                            self.name(c, seen, depth)
                else:
                    self.visit(s.body, seen, depth)
                    self.visit(s.orelse, seen, depth)
            elif isinstance(s, (A.While, A.For)):
                self.visit(s.body, seen, depth + 1)

    def name(self, s, seen, depth):
        if isinstance(s, (A.Assign, A.TupleAssign)):
            targets = [s.target] if isinstance(s, A.Assign) else s.targets
            names = [t.id for t in targets if isinstance(t, A.Name)]
            fresh = names and all(n not in seen for n in names)
            seen.update(names)
            text = ", ".join(A.show(t) for t in targets)
            if isinstance(s, A.TupleAssign) and not fresh:
                return "Parallel assignment"
            return f"Initialise {text}" if fresh else f"Assign {text}"
        if isinstance(s, A.AugAssign):
            return f"Update {A.show(s.target)}"
        if isinstance(s, A.Swap):
            return "Swap"
        if isinstance(s, A.If):
            return "Condition"
        if isinstance(s, (A.While, A.For)):
            nested = any(isinstance(x, (A.While, A.For)) for x in A.walk_all(s.body))
            return "Inner loop" if depth else "Outer loop" if nested else "Loop"
        if isinstance(s, A.Return):
            return "Return"
        if isinstance(s, A.Print):
            return "Output"
        if isinstance(s, A.ExprStmt):
            return f"Call {s.expr.func}" if isinstance(s.expr, A.Call) else f"Call @{s.expr.name}"
        return type(s).__name__


def assign_groups(module):
    return Grouper().run(module)


def finalize(code, comment, module, names, tgt, merges):
    parent = list(range(len(names) + 1))
    idx = lambda g: len(names) if g == ENTRY else g

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for keep, absorbed in merges:
        parent[find(idx(absorbed))] = find(idx(keep))
    labels = names + ["Entry point"]
    lines = code.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    prov = [None] * len(lines)

    def mark(s):
        for n in range(s.line, s.end + 1):
            if 0 < n <= len(prov):
                prov[n - 1] = s.group
        for b in A.blocks(s):
            for c in b:
                mark(c)

    for start, end in module.wrap:
        for n in range(start, end + 1):
            if 0 < n <= len(prov):
                prov[n - 1] = ENTRY
    for s in [*module.functions, *module.body]:
        mark(s)
    for s in A.walk_all([*module.functions, *module.body]):
        if isinstance(s, A.Stmt):
            for n in s.extra:
                if 0 < n <= len(prov):
                    prov[n - 1] = s.group
    for k, text in enumerate(lines):
        if not text.strip() or text.strip().startswith(comment):
            prov[k] = None
    final = {}

    def fid(g):
        if g is None:
            return None
        r = find(idx(g))
        return final.setdefault(r, len(final))

    src = [{"text": t, "group": fid(g)} for t, g in zip(lines, prov)]
    out = [{"text": t, "group": fid(g)} for t, g in tgt]
    groups = [labels[r] for r in sorted(final, key=final.get)]
    return src, out, groups, fid
