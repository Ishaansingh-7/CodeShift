import re

import pytest

from codeshift import ast as A
from codeshift.harness import Harness, same
from codeshift.ir import lower
from codeshift.optimize import optimize
from codeshift.pipeline import translate
from codeshift.semantic import analyze
from helpers import SAMPLES, TESTS, Machine, build_ir, source

FORMAT = {
    "label": re.compile(r"^(\w+\(.*\):|L\d+:)$"),
    "code": re.compile(r"^  (\w+ = .+|\w+\[.+\] = .+|call .+|print .*)$"),
    "jump": re.compile(r"^  (ifFalse \S+ goto L\d+|goto L\d+|return( .+)?)$"),
}


def with_input(sid, value, live):
    h = Harness("python", "c", source(sid, "python"), [value])
    module = A.Module(h.module.functions, h.cases[0]["body"], line=1, col=1)
    funcs = lower(module, analyze(module))
    if live:
        optimize(funcs)
    return Machine(funcs, live=live).main()


@pytest.mark.parametrize("sid", SAMPLES)
def test_ir_rows_use_the_documented_format(sid):
    rows = translate("python", "c", source(sid, "python"))["ir"]
    for row in rows:
        assert FORMAT[row["kind"]].match(row["text"]), row
        assert row["tag"] in ("", "fold", "dce", "copy-prop", "cse", "+")


@pytest.mark.parametrize("sid", SAMPLES)
def test_ir_before_and_after_optimizing_behaves_like_python(sid):
    module, plain, opt, _ = build_ir(source(sid, "python"))
    expected = TESTS[sid]["programStdout"]["python"]
    stdin = TESTS[sid].get("stdin")
    assert same(Machine(plain, stdin=stdin).main(), expected)
    assert same(Machine(opt, live=True, stdin=stdin).main(), expected)
    if stdin is not None:
        for row in TESTS[sid]["differential"]:
            assert same(Machine(opt, live=True, stdin=row["input"]).main(), row["output"]["python"])
        return
    for row in TESTS[sid]["differential"]:
        want = row["output"]["python"]
        assert same(with_input(sid, row["input"], False), want)
        assert same(with_input(sid, row["input"], True), want)


def rows_of(code):
    return [(r["text"].strip(), r["tag"]) for r in build_ir(code)[3]]


def test_cse_reuses_the_repeated_load_in_binary_search():
    rows = rows_of(source("bsearch", "python"))
    assert ("t5 = xs[mid]", "cse") in rows
    assert ("t6 = t3 < t", "+") in rows


def test_range_step_is_folded_and_the_snapshot_copy_propagated():
    rows = rows_of(source("fib", "python"))
    assert ("i = i + t1", "fold") in rows and ("i = i + 1", "+") in rows
    assert ("t1 = 1", "dce") in rows
    assert ("t2 = i < n", "+") in rows


def test_swap_is_reduced_to_two_stores():
    rows = rows_of(source("bubble", "python"))
    assert ("xs[j] = t10", "+") in rows and ("xs[t9] = t8", "+") in rows


def test_constants_fold_and_dead_branches_disappear():
    code = "def f(x):\n    k = 2 * 3 + 4\n    if k > 5:\n        return x + k\n    return 0\nprint(f(1))\n"
    module, plain, opt, rows = build_ir(code)
    rows = [(r["text"].strip(), r["tag"]) for r in rows]
    assert ("k = t0 + 4", "fold") in rows and ("t2 = x + 10", "+") in rows
    assert ("ifFalse t1 goto L1", "fold") in rows and ("return 0", "dce") in rows
    assert Machine(opt, live=True).main() == Machine(plain).main() == "11"
