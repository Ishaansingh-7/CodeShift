from concurrent.futures import ThreadPoolExecutor

from codeshift import ast as A
from codeshift.errors import CompileError
from codeshift.harness import MARK, Harness, same
from codeshift.pipeline import front, translate
from codeshift.semantic import BOOL, IDX, INT

from .runner import run

INT64 = range(-2 ** 63, 2 ** 63)
FLOAT_LANGS = {"js"}


def shown(res):
    if res["status"] == "missing-toolchain":
        return "missing toolchain"
    if res["status"] == "timeout":
        return "timeout"
    if res["stage"] == "compile":
        return "compile error"
    if res["exitCode"]:
        err = res["stderr"]
        if "overflow" in err:
            return "panic: overflow"
        return "error: " + (err.strip().splitlines() or [f"exit code {res['exitCode']}"])[-1][:120]
    return None


def segments(res, n):
    if res["stage"] == "compile":
        return []
    parts = res["stdout"].split(MARK)
    return [p.strip("\n").rstrip() for p in parts[:-1]][:n]


def reason(h, src, tgt, a, b, value):
    for label in ("missing toolchain", "compile error"):
        if label in (a, b):
            return label
    if a.startswith(("panic", "error", "timeout")) or b.startswith(("panic", "error", "timeout")):
        return "overflow panic" if "panic: overflow" in (a, b) else "timeout" if "timeout" in (a, b) else "runtime error"
    if h.printed in (INT, IDX):
        try:
            x, y = int(a), int(b)
        except ValueError:
            return "different output"
        values = value if isinstance(value, list) else [value]
        if h.divides and any(isinstance(v, int) and v < 0 for v in values) and x in INT64:
            return "% sign rule"
        if x not in INT64 or y not in INT64:
            return "float precision" if FLOAT_LANGS & {src, tgt} else "64-bit overflow"
        if FLOAT_LANGS & {src, tgt} and max(abs(x), abs(y)) > 2 ** 53:
            return "float precision"
    return "different output"


def program(src, tgt, code, printed=None, stdin=None):
    full = translate(src, tgt, code)
    if full["errors"]:
        return None
    with ThreadPoolExecutor(2) as pool:
        pa, pb = pool.map(lambda j: run(*j, stdin), [(src, code), (tgt, full["output"])])
    alike = same(pa["stdout"], pb["stdout"], printed)
    return {"srcOut": pa["stdout"], "tgtOut": pb["stdout"], "srcStatus": pa["status"], "tgtStatus": pb["status"],
            "srcErr": pa["stderr"], "tgtErr": pb["stderr"], "match": alike and pa["status"] == pb["status"] == "ok"}


def reads_stdin(src, code):
    try:
        _, module, _ = front(src, code)
    except CompileError:
        return False
    return any(isinstance(n, A.Intrinsic) and n.name == "read_line" for n in A.walk_all([*module.functions, *module.body]))


def label_of(text):
    lines = text.rstrip("\n").split("\n")
    return " ⏎ ".join(lines) if text.strip() else "(empty)"


def stdin_rows(src, tgt, code, inputs, stdin):
    full = translate(src, tgt, code)
    if full["errors"]:
        return {"rows": [], "label": "", "program": None, "errors": full["errors"]}
    cases = list(inputs) if inputs else [stdin or ""]
    jobs = [(lang, text, case) for case in cases for lang, text in ((src, code), (tgt, full["output"]))]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda j: run(*j), jobs))
    rows = []
    for k, case in enumerate(cases):
        ra, rb = results[2 * k], results[2 * k + 1]
        sa = shown(ra) or ra["stdout"].strip("\n").rstrip()
        sb = shown(rb) or rb["stdout"].strip("\n").rstrip()
        ok = ra["status"] == rb["status"] == "ok" and same(sa, sb)
        why = "" if ok else next((x for x in ("missing toolchain", "compile error") if x in (sa, sb)), None) \
            or ("runtime error" if "error" in (ra["status"], rb["status"]) else "different output")
        rows.append({"input": label_of(case), "srcOut": sa, "tgtOut": sb, "match": ok, "reason": why})
    return {"rows": rows, "label": "Input stdin", "program": program(src, tgt, code, None, stdin), "errors": []}


def difftest(src, tgt, code, inputs=None, stdin=None):
    if reads_stdin(src, code):
        return stdin_rows(src, tgt, code, inputs, stdin)
    try:
        h = Harness(src, tgt, code, inputs)
        a, b = h.programs(range(len(h.cases)))
    except CompileError as e:
        return {"rows": [], "label": "", "program": program(src, tgt, code, None, stdin), "errors": [e.to_dict()]}
    with ThreadPoolExecutor(3) as pool:
        whole = pool.submit(program, src, tgt, code, h.printed, stdin)
        ra, rb = pool.map(lambda j: run(*j), [(src, a), (tgt, b)])
        full = whole.result()
    outs = [segments(ra, len(h.cases)), segments(rb, len(h.cases))]
    rows = []
    for k, case in enumerate(h.cases):
        pair = []
        for side, lang, res in ((0, src, ra), (1, tgt, rb)):
            if k < len(outs[side]):
                pair.append(outs[side][k])
                continue
            if shown(res) in ("compile error", "missing toolchain"):
                pair.append(shown(res))
                continue
            one = h.programs([k], marks=False)[side]
            single = run(lang, one)
            pair.append(shown(single) or single["stdout"].strip("\n").rstrip())
        sa, sb = pair
        ok = same(sa, sb, h.printed) and not sa.startswith(("panic", "error", "timeout",
                                                                                     "compile", "missing"))
        rows.append({"input": case["label"], "srcOut": sa, "tgtOut": sb, "match": ok,
                     "reason": "" if ok else reason(h, src, tgt, sa, sb, case["value"])})
    return {"rows": rows, "label": h.label, "program": full, "errors": []}
