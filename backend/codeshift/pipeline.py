import copy

from . import ast as A
from .backends.c import CBackend
from .backends.go import GoBackend
from .backends.java import JavaBackend
from .backends.js import JSBackend
from .backends.python import PythonBackend
from .backends.rust import RustBackend
from .cfg import graph
from .errors import CompileError
from .frontends.c.lexer import lex as c_lex
from .frontends.c.parser import parse as c_parse
from .frontends.go.lexer import lex as go_lex
from .frontends.go.parser import parse as go_parse
from .frontends.java.lexer import lex as java_lex
from .frontends.java.parser import parse as java_parse
from .frontends.js.lexer import lex as js_lex
from .frontends.js.parser import parse as js_parse
from .frontends.python.lexer import lex as py_lex
from .frontends.python.parser import parse as py_parse
from .frontends.rust.lexer import lex as rust_lex
from .frontends.rust.parser import parse as rust_parse
from .ir import lower
from .linemap import assign_groups, finalize
from .optimize import count, optimize as run_passes
from .report import LABEL, approx, changed, library
from .semantic import analyze

LANGS = ["python", "c", "java", "js", "go", "rust"]
FRONTENDS = {"python": (py_lex, py_parse, "#"), "c": (c_lex, c_parse, "//"), "java": (java_lex, java_parse, "//"),
             "js": (js_lex, js_parse, "//"),
             "go": (go_lex, go_parse, "//"),
             "rust": (rust_lex, rust_parse, "//")}
BACKENDS = {"python": PythonBackend, "c": CBackend, "java": JavaBackend, "js": JSBackend, "go": GoBackend, "rust": RustBackend}


def available(src, tgt):
    return src in FRONTENDS and tgt in BACKENDS and src != tgt


def front(src, code):
    lex, parse, _ = FRONTENDS[src]
    tokens = lex(code.replace("\r\n", "\n").replace("\r", "\n"))
    module = parse(tokens)
    return tokens, module, analyze(module)


def emit(tgt, module, info):
    assign_groups(module)
    backend = BACKENDS[tgt](module, info)
    return backend, backend.generate()


def empty(code):
    return {
        "output": "", "srcLines": [{"text": t, "group": None} for t in code.split("\n")], "tgtLines": [],
        "tokens": [], "ast": None, "symbols": [], "ir": [], "cfg": {"blocks": [], "edges": []},
        "types": [], "changed": [], "approx": [], "groups": [], "library": [], "imports": [],
        "stats": {"tokens": 0, "irOps": 0, "removed": 0, "lines": 0}, "errors": [], "works": [],
    }


def translate(src, tgt, code, optimize=True, others=True):
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    res = empty(code)
    if not available(src, tgt):
        msg = f"Unsupported: translating {LABEL.get(src, src)} to {LABEL.get(tgt, tgt)} is not available yet"
        res["errors"] = [CompileError("pipeline", msg).to_dict()]
        return res
    lex, parse, comment = FRONTENDS[src]
    try:
        tokens = lex(code)
        res["tokens"] = [t.to_dict() for t in tokens if t.kind != "EOF"]
        res["stats"]["tokens"] = len(res["tokens"])
        module = parse(tokens)
        info = analyze(module)
        names = assign_groups(module)
        funcs = lower(module, info)
        plain = copy.deepcopy(funcs)
        res["ir"] = run_passes(funcs)
        res["cfg"] = graph(funcs if optimize else plain, optimize)
        before, after = count(funcs, False), count(funcs, True)
        res["stats"].update(irOps=after if optimize else before, removed=before - after if optimize else 0)
    except CompileError as e:
        res["errors"] = [{**e.to_dict(), "side": "source"}]
        return res
    try:
        backend = BACKENDS[tgt](module, info)
        lines = backend.generate()
        res["symbols"] = backend.symbols()
        res["types"] = backend.types()
    except CompileError as e:
        res["errors"] = [{**e.to_dict(), "side": "target"}]
        if others:
            res["works"] = [t for t in LANGS if t not in (src, tgt) and not translate(src, t, code, optimize, False)["errors"]]
        return res
    src_rows, tgt_rows, groups, fid = finalize(code, comment, module, names, lines, backend.merges)
    res.update({
        "output": "\n".join(t for t, _ in lines) + "\n",
        "srcLines": src_rows,
        "tgtLines": tgt_rows,
        "groups": groups,
        "ast": tree(module, fid),
        "changed": changed(src_rows, tgt_rows, groups, src, tgt),
        "approx": approx(module, src, tgt, backend.notes),
        "library": library(module, src, tgt),
        "imports": getattr(backend, "imports", []),
    })
    res["stats"]["lines"] = len(lines)
    return res


def describe(s):
    if isinstance(s, A.FunctionDef):
        return f"{s.name}({', '.join(p.name for p in s.params)})"
    if isinstance(s, A.Assign):
        return f"{A.show(s.target)} = {A.show(s.value)}"
    if isinstance(s, A.AugAssign):
        return f"{A.show(s.target)} {s.op}= {A.show(s.value)}"
    if isinstance(s, A.TupleAssign):
        return f"{', '.join(map(A.show, s.targets))} = {', '.join(map(A.show, s.values))}"
    if isinstance(s, A.Swap):
        return f"{A.show(s.a)}, {A.show(s.b)}"
    if isinstance(s, (A.If, A.While)):
        return A.show(s.test)
    if isinstance(s, A.For):
        if s.kind == "each":
            return f"{s.var} in {A.show(s.iter)}"
        step = "" if s.step.value == 1 else f" step {s.step.value}"
        return f"{s.var} in {A.show(s.start)}..{A.show(s.stop)}{step}"
    if isinstance(s, A.Return):
        return A.show(s.value) if s.value is not None else ""
    if isinstance(s, A.ExprStmt):
        return A.show(s.expr)
    if isinstance(s, A.Print):
        return ", ".join(map(A.show, s.args))
    return ""


def tree(module, fid):
    def node(s):
        kind = "Call" if isinstance(s, (A.ExprStmt, A.Print)) else type(s).__name__
        detail = f"print({describe(s)})" if isinstance(s, A.Print) else describe(s)
        kids = []
        for b in A.blocks(s):
            if isinstance(s, A.If) and b is s.orelse:
                if len(b) == 1 and not A.blocks(b[0]):
                    kids.append({"type": "Else", "detail": describe(b[0]), "line": b[0].line, "group": fid(b[0].group),
                                 "children": []})
                elif b:
                    kids.append({"type": "Else", "detail": "", "line": b[0].line, "group": fid(s.group),
                                 "children": [node(c) for c in b]})
            else:
                kids += [node(c) for c in b]
        return {"type": kind, "detail": detail, "line": s.line, "group": fid(s.group), "children": kids}

    items = sorted([*module.functions, *module.body], key=lambda n: n.line)
    return {"type": "Module", "detail": "", "line": 1, "group": None, "children": [node(s) for s in items]}
