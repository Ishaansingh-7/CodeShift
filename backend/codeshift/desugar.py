import copy
from dataclasses import fields

from . import ast as A
from .errors import CompileError

LITERALS = (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit, A.CharLit)
PLACEHOLDERS = (A.Comp, A.DictLit, A.SetLit)
EXPR_FIELDS = {A.If: ("test",), A.While: ("test",), A.For: ("start", "stop", "step", "iter")}


def unsupported(what, node):
    return CompileError("semantic", f"Unsupported: {what}", node.line, node.col)


def pure(e):
    return all(isinstance(n, (A.Name, A.BinOp, A.UnaryOp, A.Len, A.Index, A.Compare, A.BoolOp) + LITERALS)
               for n in A.walk(e))


def subst(node, target, repl):
    if node is target:
        return copy.deepcopy(repl)
    if isinstance(node, list):
        return [subst(x, target, repl) for x in node]
    if isinstance(node, A.Node):
        new = copy.copy(node)
        for f in fields(node):
            v = getattr(node, f.name)
            if isinstance(v, (A.Node, list)):
                setattr(new, f.name, subst(v, target, repl))
        return new
    return node


def map_expr(e, fn):
    if isinstance(e, list):
        return [map_expr(x, fn) for x in e]
    if not isinstance(e, A.Node):
        return e
    for f in fields(e):
        v = getattr(e, f.name)
        if isinstance(v, (A.Node, list)) and f.name not in A.META:
            setattr(e, f.name, map_expr(v, fn))
    return fn(e)


def own_exprs(s):
    if type(s) in EXPR_FIELDS:
        return [getattr(s, n) for n in EXPR_FIELDS[type(s)] if getattr(s, n) is not None]
    if isinstance(s, A.FunctionDef):
        return []
    return [s]


def first(s, kinds):
    for e in own_exprs(s):
        for n in A.walk(e):
            if isinstance(n, kinds):
                return n
    return None


def at(node, **kw):
    return {"line": node.line, "col": node.col, **kw}


def desugar(module):
    Desugar(module).run()
    return module


class Desugar:
    def __init__(self, m):
        self.m = m
        self.taken = set()
        for n in A.walk_all([*m.functions, *m.body]):
            if isinstance(n, A.Name):
                self.taken.add(n.id)
            elif isinstance(n, A.For):
                self.taken.add(n.var)
            elif isinstance(n, A.FunctionDef):
                self.taken.add(n.name)
                self.taken.update(p.name for p in n.params)
        self.taken.update(m.consts)

    def fresh(self, base):
        name, k = base, 2
        while name in self.taken:
            name, k = f"{base}{k}", k + 1
        self.taken.add(name)
        return name

    def run(self):
        self.constants()
        self.calls()
        self.char_loops()
        for f in self.m.functions:
            self.scope = f.body
            self.loop_scopes(f.body, f.body)
            f.body = self.block(f.body)
            self.untangle(f.body)
        self.scope = self.m.body
        self.loop_scopes(self.m.body, self.m.body)
        self.m.body = self.block(self.m.body)
        self.untangle(self.m.body)
        for n in A.walk_all([*self.m.functions, *self.m.body]):
            if isinstance(n, A.Cond):
                raise unsupported("a conditional expression here", n)
            if isinstance(n, PLACEHOLDERS):
                raise unsupported("a comprehension or literal here", n)
            if isinstance(n, A.Intrinsic) and n.name.startswith("@"):
                raise unsupported(f"{n.name[1:]} here", n)

    def char_loops(self):
        """for (char c = 'a'; c <= 'z'; c++) counts over character codes: c becomes chr(code) in the body."""
        for loop in A.walk_all([*self.m.functions, *self.m.body]):
            if not (isinstance(loop, A.For) and loop.kind == "range" and isinstance(loop.start, A.CharLit)):
                continue
            if any(A.writes(s, loop.var) for s in A.walk_all(loop.body) if isinstance(s, A.Stmt)):
                raise unsupported(f"changing the character loop variable '{loop.var}' inside the loop", loop)
            code = lambda e: A.Intrinsic("ord", [e], line=e.line, col=e.col) if isinstance(e, A.CharLit) else e
            loop.start = code(loop.start)
            loop.stop = map_expr(loop.stop, code)
            var = loop.var

            def char(e):
                if isinstance(e, A.Name) and e.id == var:
                    return A.Intrinsic("chr", [e], line=e.line, col=e.col)
                return e
            loop.body = map_expr(loop.body, char)

    def loop_scopes(self, stmts, whole):
        """A for-loop header variable lives only in its loop; when the loop became a while loop, give it its own name
        if the same name is used elsewhere in the function."""
        def count(nodes, name):
            return sum(1 for n in A.walk_all(nodes) if isinstance(n, A.Name) and n.id == name
                       or isinstance(n, A.For) and n.var == name)

        for k, s in enumerate(stmts):
            for b in A.blocks(s):
                self.loop_scopes(b, whole)
            init = stmts[k - 1] if k and getattr(stmts[k - 1], "tie", None) is s else None
            if not (isinstance(s, A.While) and getattr(s, "owns", None) and init is not None):
                continue
            mine = [init, s]
            for name in s.owns:
                if count(whole, name) == count(mine, name):
                    continue
                new = self.fresh(name)
                for n in A.walk_all(mine):
                    if isinstance(n, A.Name) and n.id == name:
                        n.id = new
                    elif isinstance(n, A.For) and n.var == name:
                        n.var = new

    def untangle(self, stmts):
        loops = [n for n in A.walk_all(stmts) if isinstance(n, A.For)]
        loop_vars = {n.var for n in loops}
        for loop in loops:
            for s in loop.body:
                if not getattr(s, "bound", False):
                    break
                old = s.target.id
                if old in loop_vars:
                    new = self.fresh(old)
                    for n in A.walk_all(loop.body):
                        if isinstance(n, A.Name) and n.id == old:
                            n.id = new
                        elif isinstance(n, A.For) and n.var == old:
                            n.var = new

    def constants(self):
        typed = dict(self.m.consts)
        loose = self.top_level_constants() if self.m.lang in ("python", "js") else {}
        if not typed and not loose:
            return
        for name, s in self.writers(self.m.body).items():
            if name in typed:
                raise unsupported(f"changing the global variable '{name}'", s)
        for f in self.m.functions:
            params = {p.name for p in f.params}
            written = self.writers(f.body)
            live = {}
            for name, lit in typed.items():
                if name in params:
                    continue
                if name in written:
                    raise unsupported(f"changing the global variable '{name}'", written[name])
                live[name] = lit
            live.update({k: v for k, v in loose.items() if k not in params and k not in written})
            if live:
                f.body = map_expr(f.body, lambda e, live=live: self.literal(e, live))
        if typed:
            self.m.body = map_expr(self.m.body, lambda e: self.literal(e, typed))
        read = {n.id for s in self.m.body for n in A.walk(s) if isinstance(n, A.Name)
                and not (isinstance(s, A.Assign) and s.target is n)}
        self.m.body = [s for s in self.m.body if not (isinstance(s, A.Assign) and isinstance(s.target, A.Name)
                                                       and s.target.id in loose and s.target.id not in read)]

    @staticmethod
    def writers(stmts):
        out = {}
        for s in A.walk_all(stmts):
            if isinstance(s, A.For):
                out.setdefault(s.var, s)
            if isinstance(s, (A.Assign, A.AugAssign)) and isinstance(s.target, A.Name):
                out.setdefault(s.target.id, s)
            if isinstance(s, (A.TupleAssign, A.Swap)):
                for t in (s.targets if isinstance(s, A.TupleAssign) else [s.a, s.b]):
                    if isinstance(t, A.Name):
                        out.setdefault(t.id, s)
        return out

    @staticmethod
    def literal(e, consts):
        if isinstance(e, A.Name) and e.id in consts:
            return type(consts[e.id])(consts[e.id].value, line=e.line, col=e.col)
        return e

    def top_level_constants(self):
        counts = {}
        for s in A.walk_all(self.m.body):
            if isinstance(s, A.For):
                counts[s.var] = counts.get(s.var, 0) + 1
            elif isinstance(s, A.Stmt) and not A.blocks(s):
                for name in self.writers([s]):
                    counts[name] = counts.get(name, 0) + 1
        used = {n.id for n in A.walk_all([f for f in self.m.functions]) if isinstance(n, A.Name)}
        changed = set()
        for f in self.m.functions:
            changed |= set(self.writers(f.body))
        out = {}
        for s in self.m.body:
            if isinstance(s, A.Assign) and isinstance(s.target, A.Name) and isinstance(s.value, LITERALS):
                name = s.target.id
                if name in used and counts.get(name) == 1 and not (self.m.lang == "js" and name in changed):
                    out[name] = s.value
        return out

    def calls(self):
        funcs = {f.name: f for f in self.m.functions}
        for f in self.m.functions:
            seen = set()
            for p in f.params:
                if p.default is None and seen:
                    raise unsupported(f"parameter '{p.name}' without a default after one with a default", p)
                if p.default is not None:
                    seen.add(p.name)
        for n in A.walk_all([*self.m.functions, *self.m.body]):
            if not isinstance(n, A.Call) or n.func == "print":
                continue
            f = funcs.get(n.func)
            if f is None:
                if n.kw:
                    raise unsupported(f"keyword arguments to {n.func}()", n)
                continue
            if len(n.args) > len(f.params):
                continue
            given = dict(n.kw)
            if len(given) != len(n.kw):
                raise unsupported("the same keyword argument twice", n)
            args = list(n.args)
            for p in f.params[len(n.args):]:
                if p.name in given:
                    args.append(given.pop(p.name))
                elif p.default is not None:
                    args.append(copy.deepcopy(p.default))
                    for x in A.walk(args[-1]):
                        x.line, x.col = n.line, n.col
                else:
                    if given:
                        raise unsupported(f"missing argument '{p.name}' in a call to {n.func}()", n)
                    break
            if given:
                name = next(iter(given))
                bad = "repeats a positional argument" if name in {p.name for p in f.params} else "is not a parameter"
                raise unsupported(f"keyword argument '{name}' {bad} of {n.func}()", n)
            n.args, n.kw = args, []
        for f in self.m.functions:
            for p in f.params:
                p.default = None

    def block(self, stmts):
        out = []
        for s in stmts:
            for b in A.blocks(s):
                b[:] = self.block(b)
            out += self.stmt(s)
        return out

    def stmt(self, s):
        p = first(s, PLACEHOLDERS + (A.Intrinsic,))
        while isinstance(p, A.Intrinsic) and p.name != "@prompt":
            p = self.next_placeholder(s, p)
        if p is not None:
            if isinstance(s, A.While):
                raise unsupported("a comprehension or literal in a loop condition", p)
            pre, s = self.hoist(s, p)
            return self.block(pre + [s])
        c = first(s, A.Cond)
        if c is None:
            return [s]
        if isinstance(s, (A.While, A.For, A.If)):
            raise unsupported("a conditional expression in a condition or loop header", c)
        then, other = subst(s, c, c.then), subst(s, c, c.other)
        return [A.If(c.test, self.stmt(then), self.stmt(other), **at(s, end=s.end))]

    @staticmethod
    def next_placeholder(s, after):
        found = False
        for e in own_exprs(s):
            for n in A.walk(e):
                if n is after:
                    found = True
                elif found and (isinstance(n, PLACEHOLDERS) or isinstance(n, A.Intrinsic) and n.name == "@prompt"):
                    return n
        return None

    def hoist(self, s, p):
        pos = at(s, end=s.end)
        if isinstance(p, A.Intrinsic):
            show = A.Print([p.args[0]], **pos)
            show.ending = ""
            return [show], subst(s, p, A.Intrinsic("read_line", [], line=p.line, col=p.col))
        whole = isinstance(s, A.Assign) and s.value is p and isinstance(s.target, A.Name) \
            and s.target.id not in A.names(p)
        name = s.target.id if whole else self.fresh({A.Comp: "result" if isinstance(s, A.Return) else "items",
                                                    A.DictLit: "table", A.SetLit: "members"}[type(p)])
        if isinstance(p, A.Comp):
            self.private(p)
        ref = A.Name(name, line=p.line, col=p.col)
        pre = [A.Assign(A.Name(name, line=p.line, col=p.col), self.empty(p), **pos)]
        if isinstance(p, A.DictLit):
            pre += [A.Assign(A.Index(copy.deepcopy(ref), k, line=k.line, col=k.col), v, **pos)
                    for k, v in zip(p.keys, p.values)]
        elif isinstance(p, A.SetLit):
            pre += [A.ExprStmt(A.Intrinsic("set_add", [copy.deepcopy(ref), x], line=x.line, col=x.col), **pos)
                    for x in p.items]
        else:
            if p.key is not None:
                add = A.Assign(A.Index(copy.deepcopy(ref), p.key, line=p.line, col=p.col), p.elt, **pos)
            else:
                add = A.ExprStmt(A.Intrinsic("push", [copy.deepcopy(ref), p.elt], line=p.line, col=p.col), **pos)
            body = [A.If(p.cond, [add], [], **pos)] if p.cond is not None else [add]
            loop = copy.copy(p.loop)
            loop.body = body
            loop.line, loop.col, loop.end = s.line, s.col, s.end
            pre.append(loop)
        if whole:
            return pre[:-1], pre[-1]
        return pre, subst(s, p, ref)

    def private(self, p):
        var = p.loop.var

        def count(nodes):
            return sum(1 for n in A.walk_all(nodes) if isinstance(n, A.Name) and n.id == var
                       or isinstance(n, A.For) and n.var == var)

        if count(self.scope) <= count([p]):
            return
        new = self.fresh(var)
        p.loop.var = new
        for x in (p.elt, p.cond, p.key):
            for n in A.walk(x) if x is not None else []:
                if isinstance(n, A.Name) and n.id == var:
                    n.id = new

    @staticmethod
    def empty(p):
        if isinstance(p, A.SetLit):
            return A.Intrinsic("set_new", [], line=p.line, col=p.col)
        if isinstance(p, A.DictLit) or isinstance(p, A.Comp) and p.key is not None:
            return A.Intrinsic("map_new", [], line=p.line, col=p.col)
        return A.ArrayLit([], line=p.line, col=p.col)
