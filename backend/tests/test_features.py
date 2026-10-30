from pathlib import Path

import pytest

from app import runner
from codeshift.pipeline import LANGS, translate

HERE = Path(__file__).parent / "features"
PROGRAMS = {"features.py": "python", "c_features.c": "c", "c_extra.c": "c", "Main_features.java": "java",
            "js_features.js": "js", "go_features.go": "go", "rust_features.rs": "rust", "bits.py": "python",
            "c_bits.c": "c", "Main_bits.java": "java", "js_bits.js": "js", "go_bits.go": "go", "rust_bits.rs": "rust"}


@pytest.mark.parametrize("tgt", LANGS)
@pytest.mark.parametrize("name", PROGRAMS)
def test_new_features_print_the_same_everywhere(name, tgt):
    src = PROGRAMS[name]
    if tgt == src:
        pytest.skip("same language")
    if not (runner.TOOLCHAINS[src] and runner.TOOLCHAINS[tgt]):
        pytest.skip("toolchain missing")
    code = (HERE / name).read_text()
    expected = runner.run(src, code)
    assert expected["status"] == "ok", expected["stderr"]
    r = translate(src, tgt, code)
    assert r["errors"] == [], r["errors"]
    got = runner.run(tgt, r["output"])
    assert got["status"] == "ok", got["stderr"] + r["output"]
    assert got["stdout"].replace("True", "true").replace("False", "false") == \
        expected["stdout"].replace("True", "true").replace("False", "false")
