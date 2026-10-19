import pytest

from app import runner
from codeshift.pipeline import translate

PROGRAMS = {
    "vowels": 'function isVowel(c) {\n  return c === "a" || c === "e" || c === "i" || c === "o" || c === "u";\n}\n\n'
              'function vowels(s) {\n  let n = 0;\n  for (const c of s) {\n    if (isVowel(c)) {\n      n++;\n    }\n  }\n'
              '  return n;\n}\n\nconsole.log(vowels("programming"));\n',
    "mixed": "function sq(x) {\n  return x * x;\n}\n\nlet total = 0;\nfor (let i = 1; i <= 5; i++) {\n  total += sq(i);\n}\n"
             'const label = "sum";\nconsole.log(label, total, Math.floor(total / 7), total % 7);\n',
    "branches": "function half(n) {\n  let k = 0;\n  if (n > 3) {\n    k = Math.floor(n / 2);\n  } else if (n > 1) {\n"
                "    k = 1;\n  } else {\n    k = -1;\n  }\n  return k;\n}\n\nconsole.log(half(9), half(2), half(0));\n",
    "countdown": "function countdown(n) {\n  let s = 0;\n  for (let i = n; i > 0; i--) {\n    s = s + i * 2;\n  }\n"
                 "  return s;\n}\n\nconsole.log(countdown(10));\n",
}
PY = {
    "collatz": "def collatz(n):\n    steps = 0\n    while n != 1:\n        if n % 2 == 0:\n            n //= 2\n        else:\n"
               "            n = 3 * n + 1\n        steps += 1\n    return steps\n\n\nprint(collatz(27))\n",
    "count": "def count(s, c):\n    k = 0\n    for ch in s:\n        if ch == c:\n            k += 1\n    return k\n\n\n"
             'print(count("banana", "a"))\n',
}


@pytest.mark.parametrize("name", PROGRAMS)
@pytest.mark.parametrize("tgt", ["python", "c", "java"])
def test_js_programs_print_the_same_in_every_target(name, tgt):
    if not (runner.TOOLCHAINS["js"] and runner.TOOLCHAINS[tgt]):
        pytest.skip("toolchain missing")
    r = translate("js", tgt, PROGRAMS[name])
    assert r["errors"] == [], r["errors"]
    a, b = runner.run("js", PROGRAMS[name]), runner.run(tgt, r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


@pytest.mark.parametrize("name", PY)
@pytest.mark.parametrize("src", ["python", "c"])
def test_programs_translated_to_js_print_the_same(name, src):
    if not (runner.TOOLCHAINS["js"] and runner.TOOLCHAINS[src]):
        pytest.skip("toolchain missing")
    code = PY[name]
    if src != "python":
        code = translate("python", src, code)["output"]
    r = translate(src, "js", code)
    assert r["errors"] == [], r["errors"]
    a, b = runner.run(src, code), runner.run("js", r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


def test_floor_division_round_trips_through_math_floor():
    out = translate("python", "js", PY["collatz"])["output"]
    assert "n = Math.floor(n / 2);" in out
    assert "n //= 2" in translate("js", "python", out)["output"]


def test_char_argument_becomes_a_char_parameter():
    out = translate("python", "c", PY["count"])["output"]
    assert "long long count(const char *s, char c)" in out and "count(\"banana\", 'a')" in out


def test_const_only_for_bindings_written_once():
    out = translate("python", "js", "a = 1\nb = 2\na = a + b\nprint(a, b)\n")["output"]
    assert out == "let a = 1;\nconst b = 2;\na = a + b;\nconsole.log(a, b);\n"


ERRORS = [
    ("let x = 7.5 % 2;\nconsole.log(x);\n", "Unsupported: '%' on floats at line 1, col 13"),
    ("let x = 8;\ndo {\n  x--;\n} while (x > 0);\n", "Unsupported: 'do' statement at line 2, col 1"),
    ("console.log(`hi`);\n", "Unsupported: template literals at line 1, col 13"),
    ("console.log(Math.random());\n", "Unsupported: library call Math.random at line 1, col 17"),
    ("const xs = [1, 2];\nfor (const k in xs) {\n}\n", "Unsupported: for-in loops at line 2, col 12"),
    ("let o = null;\n", "Unsupported: null at line 1, col 9"),
    ("function f() {\n  function g() {\n  }\n}\n", "Unsupported: nested functions at line 2, col 3"),
    ("function f(a = 1) {\n  return a;\n}\n", "Unsupported: default parameter values at line 1, col 14"),
]


@pytest.mark.parametrize("code, message", ERRORS)
def test_js_errors_have_positions(code, message):
    r = translate("js", "python", code)
    assert [e["message"] for e in r["errors"]] == [message]
