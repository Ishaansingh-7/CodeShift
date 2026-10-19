import pytest

from codeshift.pipeline import translate

CASES = [
    ("def f(n)\n    return n\n", "parser", "Syntax error: expected ':', found end of line at line 1, col 9"),
    ("x = 7.5\nprint(x % 2)\n", "semantic", "Unsupported: '%' on floats at line 2, col 9"),
    ("x = 7.5\nx //= 2\n", "semantic", "Unsupported: '//=' between float and int at line 2, col 1"),
    ("print(y)\n", "semantic", "Undefined name 'y' at line 1, col 7"),
    ("def f(c):\n    if c > 0:\n        x = 1\n    return x\n\nprint(f(1))\n", "semantic",
     "Variable 'x' may be used before it is assigned at line 4, col 12"),
    ("def f(n):\n    x = 1\n  return x\n", "lexer",
     "Indentation error: unindent does not match any outer indentation level at line 3, col 3"),
    ('print("abc)\n', "lexer", "Syntax error: unterminated string at line 1, col 7"),
    ("def f(n):\n    if n > 0:\n        return 1\n\nprint(f(1))\n", "semantic",
     "Unsupported: function 'f' can reach its end without returning a value at line 1, col 1"),
    ("g = [[0.5] * 2 for _ in range(2)]\nprint(g[0][0])\n", "codegen",
     "Unsupported: a list of this type in C ('g') at line 1, col 1"),
    ("xs = [1, 2]\nprint(xs[-1])\n", "semantic", "Unsupported: negative index at line 2, col 10"),
    ("x = 1\nx = \"a\"\n", "semantic", "Unsupported: 'x' holds both int and str values at line 2, col 1"),
    ("for i in range(3):\n    i = 5\n", "semantic",
     "Unsupported: 'i' used both as a loop variable and as an ordinary variable at line 2, col 5"),
    ("print(f(1))\n\ndef f(n):\n    return n\n", "semantic", "Function 'f' is called before it is defined at line 1, col 7"),
    ("import os\n", "parser", "Unsupported: import os at line 1, col 1"),
    ("xs = [1, 2]\nxs.extend([3])\n", "parser", "Unsupported: method or attribute '.extend' at line 2, col 3"),
    ("print(round(2.5, 1))\n", "parser", "Unsupported: round() with a number of digits at line 1, col 7"),
    ("def f():\n    return [[1.5]]\n\nprint(f()[0][0])\n", "codegen",
     "Unsupported: returning a list of this type in C at line 2, col 5"),
]


@pytest.mark.parametrize("code, stage, message", CASES)
def test_errors_report_stage_line_and_column(code, stage, message):
    r = translate("python", "c", code)
    assert r["output"] == ""
    assert r["errors"] == [{"message": message, "line": r["errors"][0]["line"], "col": r["errors"][0]["col"],
                            "stage": stage, "side": "target" if stage == "codegen" else "source"}]
    assert message.endswith(f"at line {r['errors'][0]['line']}, col {r['errors'][0]['col']}")


def test_unavailable_pair_is_an_error_not_a_crash():
    r = translate("python", "python", "print(1)\n")
    assert r["errors"][0]["message"] == "Unsupported: translating Python to Python is not available yet"


def test_target_side_errors_list_the_targets_that_work():
    r = translate("python", "c", "g = [[0.5] * 2 for _ in range(2)]\nprint(g[0][0])\n")
    assert [e["side"] for e in r["errors"]] == ["target"]
    assert r["works"] == ["java", "js", "go", "rust"]
    bad = translate("python", "c", "def f(n)\n    return n\n")
    assert bad["errors"][0]["side"] == "source" and bad["works"] == []


def test_error_response_keeps_source_lines_ungrouped():
    r = translate("python", "c", "x = 1.5 % 2\n")
    assert [row["group"] for row in r["srcLines"]] == [None, None]
