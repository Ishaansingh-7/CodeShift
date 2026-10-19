import json

import pytest

from codeshift.pipeline import translate
from helpers import SAMPLES, TESTS, needs_gcc, run_c, source

CALL = {
    "bubble": "xs = {v}\nbubble(xs)\nprint(xs)\n",
    "bsearch": "print(search([1, 3, 5, 7, 9, 11], {v}))\n",
    "reverse": "print(reverse({v}))\n",
}


def harness(sid, value):
    code = source(sid, "python")
    defs = code[:code.rindex("\n\n") + 2]
    fn = defs.split("def ", 1)[1].split("(", 1)[0]
    if sid in CALL:
        return defs + CALL[sid].format(v=json.dumps(value))
    args = ", ".join(map(str, value if isinstance(value, list) else [value]))
    return defs + f"print({fn}({args}))\n"


ORIGINAL = ["fib", "gcd", "fact", "prime", "power", "digits", "bubble", "bsearch", "reverse"]


@needs_gcc
@pytest.mark.parametrize("sid", ORIGINAL)
def test_c_differentials_are_64_bit(sid, tmp_path):
    for row in TESTS[sid]["differential"]:
        r = translate("python", "c", harness(sid, row["input"]))
        assert r["errors"] == [], r["errors"]
        assert run_c(r["output"], tmp_path).strip() == row["output"]["c"], row
