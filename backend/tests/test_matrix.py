import pytest

from app import runner
from app.difftest import difftest
from codeshift.ir import lower
from codeshift.optimize import optimize
from codeshift.pipeline import BACKENDS, FRONTENDS, LANGS, emit, front, translate
from helpers import SAMPLES, TESTS, Machine, source

SOURCES = [l for l in LANGS if l in FRONTENDS]
TARGETS = [l for l in LANGS if l in BACKENDS]
PAIRS = [(s, t) for s in SOURCES for t in TARGETS if s != t]
BOTH = [l for l in SOURCES if l in TARGETS]
CASES = [(s, t, sid) for s, t in PAIRS for sid in SAMPLES]
ids = lambda c: "-".join(c)


@pytest.mark.parametrize("src, tgt, sid", CASES, ids=map(ids, CASES))
def test_translation_matches_sample(src, tgt, sid):
    r = translate(src, tgt, source(sid, src))
    assert r["errors"] == []
    assert r["output"] == source(sid, tgt)


@pytest.mark.parametrize("lang, sid", [(l, s) for l in BOTH for s in SAMPLES])
def test_backend_regenerates_its_own_sample(lang, sid):
    _, module, info = front(lang, source(sid, lang))
    _, lines = emit(lang, module, info)
    assert "\n".join(t for t, _ in lines) + "\n" == source(sid, lang)


@pytest.mark.parametrize("src, tgt, sid", CASES, ids=map(ids, CASES))
def test_line_groups_refine_expected(src, tgt, sid):
    r = translate(src, tgt, source(sid, src))
    mapping = {}
    for rows, lang in ((r["srcLines"], src), (r["tgtLines"], tgt)):
        expected = TESTS[sid]["lineGroups"][lang]
        assert len(rows) == len(expected)
        for n, (row, e) in enumerate(zip(rows, expected), 1):
            assert (row["group"] is None) == (e is None), (lang, n, row["text"])
            if e is not None:
                assert mapping.setdefault(row["group"], e) == e, (lang, n, row["text"])


@pytest.mark.parametrize("lang, sid", [(l, s) for l in SOURCES for s in SAMPLES])
def test_ir_from_every_frontend_behaves_like_python(lang, sid):
    _, module, info = front(lang, source(sid, lang))
    funcs = lower(module, info)
    optimize(funcs)
    out = Machine(funcs, live=True, stdin=TESTS[sid].get("stdin")).main()
    assert out.rstrip("\n") == TESTS[sid]["programStdout"]["python"]


@pytest.mark.parametrize("lang, sid", [(l, s) for l in TARGETS for s in SAMPLES])
def test_sample_file_runs_and_prints_expected(lang, sid):
    if not runner.TOOLCHAINS[lang]:
        pytest.skip(f"{lang} toolchain missing")
    res = runner.run(lang, source(sid, lang), TESTS[sid].get("stdin"))
    assert res["status"] == "ok", res["stderr"]
    assert res["stdout"].rstrip("\n") == TESTS[sid]["programStdout"][lang]


@pytest.mark.parametrize("src, tgt, sid", CASES, ids=map(ids, CASES))
def test_difftest_matches_expected_columns(src, tgt, sid):
    if not (runner.TOOLCHAINS[src] and runner.TOOLCHAINS[tgt]):
        pytest.skip("toolchain missing")
    res = difftest(src, tgt, source(sid, src), [r["input"] for r in TESTS[sid]["differential"]], TESTS[sid].get("stdin"))
    assert res["errors"] == []
    expected = TESTS[sid]["differential"]
    assert [r["srcOut"] for r in res["rows"]] == [e["output"][src] for e in expected]
    assert [r["tgtOut"] for r in res["rows"]] == [e["output"][tgt] for e in expected]
    assert res["program"]["match"]
