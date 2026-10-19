import concurrent.futures as cf
from pathlib import Path

import pytest

from app import runner
from codeshift.harness import same
from codeshift.ir import lower
from codeshift.optimize import optimize
from codeshift.pipeline import LANGS, front, translate
from helpers import Machine

GOLDEN = Path(__file__).parent / "golden"
EXT = {"python": "py", "c": "c", "java": "java", "js": "js", "go": "go", "rust": "rs"}
PROGRAMS = sorted(p.stem for p in GOLDEN.glob("*.py"))
POOL = cf.ThreadPoolExecutor(12)


def python(name):
    return (GOLDEN / f"{name}.py").read_text(encoding="utf-8")


def source(name, lang):
    hand = GOLDEN / f"{name}.{EXT[lang]}"
    if hand.exists():
        return hand.read_text(encoding="utf-8")
    r = translate("python", lang, python(name))
    assert r["errors"] == [], r["errors"]
    return r["output"]


def stdin(name):
    path = GOLDEN / f"{name}.in"
    return path.read_text(encoding="utf-8") if path.exists() else None


def expected(name):
    res = runner.run("python", python(name), stdin(name))
    assert res["status"] == "ok", res["stderr"]
    return res["stdout"]


@pytest.mark.parametrize("src", LANGS)
@pytest.mark.parametrize("name", PROGRAMS)
def test_golden_program_in_every_direction(name, src):
    if not runner.TOOLCHAINS[src]:
        pytest.skip(f"{src} toolchain missing")
    want = expected(name)
    code = source(name, src)
    jobs = [(src, code)]
    for tgt in LANGS:
        if tgt != src and runner.TOOLCHAINS[tgt]:
            r = translate(src, tgt, code)
            assert r["errors"] == [], (src, tgt, r["errors"])
            jobs.append((tgt, r["output"]))
    for (lang, text), res in zip(jobs, POOL.map(lambda j: runner.run(*j, stdin(name)), jobs)):
        assert res["status"] == "ok", (src, lang, res["stderr"], text)
        assert same(res["stdout"], want), (src, lang, res["stdout"], want, text)


@pytest.mark.parametrize("name", PROGRAMS)
def test_golden_ir_runs_like_python(name):
    _, module, info = front("python", python(name))
    funcs = lower(module, info)
    optimize(funcs)
    assert same(Machine(funcs, live=True, stdin=stdin(name)).main(), expected(name))
