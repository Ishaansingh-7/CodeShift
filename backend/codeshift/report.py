from . import ast as A
from .library import form
from .semantic import ARR, BOOL, FLOAT, INT

LABEL = {"python": "Python", "c": "C", "java": "Java", "js": "JavaScript", "go": "Go", "rust": "Rust"}
INT_MODEL = {
    "python": "int · unbounded", "c": "long long · 64-bit, wraps", "java": "long · 64-bit, wraps",
    "js": "number · 64-bit float", "go": "int64 · wraps", "rust": "i64 · panics on overflow",
}
INT_NOTE = {
    "c": "C long long wraps around past 2^63 − 1, so very large results differ from Python's exact integers.",
    "java": "Java long wraps around past 2^63 − 1, so very large results differ.",
    "go": "Go int64 wraps around past 2^63 − 1, so very large results differ.",
    "js": "JavaScript numbers lose precision above 2^53, so very large results are rounded.",
    "rust": "Rust panics on overflow in a debug build instead of returning a result.",
    "python": "Python integers never overflow, so it returns the exact value where the source overflowed.",
}
TRUNC = "/ and % round toward 0"
DIV = {"python": "// and % round toward −∞", "js": "Math.floor(a / b) rounds toward −∞, % toward 0"}
BOOLS = {"python": "True / False", "c": "1 / 0"}
LISTS = {"python": "[1, 2, 3]", "c": "1 2 3 (no brackets)", "java": "[1, 2, 3]", "js": "[ 1, 2, 3 ]", "go": "[1 2 3]",
         "rust": "[1, 2, 3]"}
NOTES = {"buffer": ("str return value", "char * out-parameter"), "order": ("insertion order", "sorted key order")}
TIES = {"python": "half to even", "c": "half to even", "go": "half to even", "rust": "half to even", "java": "half up",
        "js": "half up"}
MISSING = {"python": "KeyError", "c": "0 or empty string", "java": "null (NullPointerException when used)",
           "js": "undefined", "go": "zero value", "rust": "panic"}
WHOLE = {"python": "2.0", "c": "2.0", "java": "2.0", "js": "2", "go": "2", "rust": "2"}


def library(module, src, tgt):
    names = []
    for n in A.walk_all([*module.functions, *module.body]):
        if isinstance(n, A.Intrinsic) and n.name not in names:
            names.append(n.name)
    return [{"call": f"@{n}", "from": form(n, src), "to": form(n, tgt)} for n in names]


def changed(src, tgt, groups, src_lang, tgt_lang):
    def clean(rows, g):
        return "\n".join(r["text"].strip() for r in rows if r["group"] == g and r["text"].strip() not in ("", "{", "}"))

    out = []
    for g, name in enumerate(groups):
        x, y = clean(src, g), clean(tgt, g)
        if x == y:
            continue
        if not x:
            out.append({"where": f"{name.upper()} · ADDED", "from": f"(not needed in {LABEL[src_lang]})", "to": y})
        elif not y:
            out.append({"where": f"{name.upper()} · REMOVED", "from": x, "to": f"(implicit in {LABEL[tgt_lang]})"})
        else:
            out.append({"where": name.upper(), "from": x, "to": y})
    return out


def literal(e):
    return isinstance(e, A.IntLit)


def grows(e):
    if isinstance(e, A.BinOp) and e.ty == INT:
        operands = (e.left, e.right)
        if e.op == "*" and not all(map(literal, operands)):
            return True
        if e.op in ("+", "-") and not any(literal(x) or (isinstance(x, A.BinOp) and x.op in "/%") for x in operands):
            return True
    if isinstance(e, A.AugAssign) and e.target.ty == INT and e.op in "+-*":
        v = e.value
        return not (literal(v) or (isinstance(v, A.BinOp) and v.op in "/%"))
    return False


def approx(module, src, tgt, notes):
    nodes = list(A.walk_all([*module.functions, *module.body]))
    out = []
    if INT_MODEL[src] != INT_MODEL[tgt] and any(map(grows, nodes)):
        out.append({"from": INT_MODEL[src], "to": INT_MODEL[tgt], "note": INT_NOTE[tgt]})
    divides = any(isinstance(n, (A.BinOp, A.AugAssign)) and n.op in ("/", "%") for n in nodes)
    if divides and DIV.get(src, TRUNC) != DIV.get(tgt, TRUNC):
        out.append({"from": DIV.get(src, TRUNC), "to": DIV.get(tgt, TRUNC),
                    "note": "Results differ only when an operand is negative."})
    printed = {a.ty for n in nodes if isinstance(n, A.Print) for a in n.args}
    if BOOL in printed and BOOLS.get(src, "true / false") != BOOLS.get(tgt, "true / false"):
        out.append({"from": BOOLS.get(src, "true / false"), "to": BOOLS.get(tgt, "true / false"),
                    "note": f"Booleans print differently in {LABEL[tgt]}."})
    if FLOAT in printed and WHOLE[src] != WHOLE[tgt]:
        out.append({"from": f"{WHOLE[src]} for a whole-number float", "to": WHOLE[tgt],
                    "note": f"Floats print in {LABEL[tgt]}'s own format; the values are the same."})
    if ARR in printed and LISTS[src] != LISTS[tgt]:
        out.append({"from": LISTS[src], "to": LISTS[tgt], "note": f"Lists print in {LABEL[tgt]}'s own format."})
    if any(isinstance(n, A.Intrinsic) and n.name == "fixed" for n in nodes) and TIES[src] != TIES[tgt]:
        out.append({"from": f"fixed decimals: exact halves round {TIES[src]}", "to": TIES[tgt],
                    "note": "Only a value exactly halfway between two outputs (like 0.125 to 2 places) can print differently."})
    if any(isinstance(n, A.Intrinsic) and n.name == "map_get" for n in nodes):
        out.append({"from": f"missing key: {MISSING[src]}", "to": MISSING[tgt],
                    "note": "Only matters when the key is missing; d.get(k, default) behaves the same everywhere."})
    for key, note in notes.items():
        a, b = NOTES[key]
        out.append({"from": a, "to": b, "note": note})
    return out
