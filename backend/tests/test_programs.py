import pytest

from app import runner
from codeshift.pipeline import BACKENDS, LANGS, translate
from helpers import Machine, build_ir, needs_gcc, run_c, run_py

TARGETS = [l for l in LANGS if l in BACKENDS]

PROGRAMS = {
    "widen": "def tri(n):\n    s = 0\n    for i in range(n):\n        s += i * i\n    return s\n\nprint(tri(5))\n",
    "hoist": "def sign(n):\n    if n < 0:\n        r = -1\n    else:\n        r = 1\n    return r\n\nprint(sign(-5))\n",
    "chars": "def count(s):\n    c = 0\n    for ch in s:\n        if ch == 'a':\n            c += 1\n    return c\n\n"
             "print(count(\"banana\"))\n",
    "elif": "def grade(n):\n    if n >= 90:\n        return 3\n    elif n >= 50:\n        return 2\n    else:\n"
            "        return 1\n\nprint(grade(75))\n",
    "label": "def sq(x):\n    return x * x\n\nprint(\"square:\", sq(7))\n",
    "collatz": "def collatz(n):\n    steps = 0\n    while n != 1 and steps < 1000:\n        if n % 2 == 0:\n"
               "            n = n // 2\n        else:\n            n = 3 * n + 1\n        steps += 1\n    return steps\n\n"
               "print(collatz(27))\n",
    "append": "def copy(s):\n    out = \"\"\n    for ch in s:\n        out = out + ch\n    return out\n\n"
              "print(copy(\"hello\"))\n",
    "sum": "def total(xs):\n    s = 0\n    for x in xs:\n        s += x\n    return s\n\nprint(total([3, 4, 5]))\n",
    "step": "def down(n):\n    s = 0\n    for i in range(n, 0, -2):\n        s += i\n    return s\n\nprint(down(10))\n",
    "swap": "def order(a, b):\n    if a > b:\n        a, b = b, a\n    return a * 100 + b\n\nprint(order(9, 4))\n",
    "forward": "def f(n):\n    return g(n) + 1\n\ndef g(n):\n    return n * 2\n\nprint(f(5))\n",
    "after": "def last(n):\n    i = 0\n    while i < n:\n        i += 3\n    return i\n\nprint(last(10))\n",
    "toplevel": "x = 6\ny = 7\nprint(x * y)\nprint(\"done\")\n",
}


COMPILED = [l for l in TARGETS if l != "python"]


@needs_gcc
@pytest.mark.parametrize("name", PROGRAMS)
def test_c_prints_what_python_prints(name, tmp_path):
    code = PROGRAMS[name]
    r = translate("python", "c", code)
    assert r["errors"] == [], r["errors"]
    assert run_c(r["output"], tmp_path) == run_py(code)


@pytest.mark.parametrize("tgt", [l for l in COMPILED if l != "c"])
@pytest.mark.parametrize("name", PROGRAMS)
def test_every_target_prints_what_python_prints(name, tgt):
    if not runner.TOOLCHAINS[tgt]:
        pytest.skip(f"{tgt} toolchain missing")
    code = PROGRAMS[name]
    r = translate("python", tgt, code)
    assert r["errors"] == [], r["errors"]
    res = runner.run(tgt, r["output"])
    assert res["status"] == "ok", res["stderr"] + r["output"]
    out = run_py(code)
    if "True" in out or "False" in out:
        out = out.replace("True", "true").replace("False", "false")
    assert res["stdout"] == out


@pytest.mark.parametrize("name", PROGRAMS)
def test_ir_prints_what_python_prints(name):
    code = PROGRAMS[name]
    _, plain, opt, _ = build_ir(code)
    want = run_py(code).rstrip("\n")
    assert Machine(plain).main() == want
    assert Machine(opt, live=True).main() == want


def output(name):
    return translate("python", "c", PROGRAMS[name])["output"]


def test_index_arithmetic_is_widened_before_reaching_a_long():
    assert "s += (long long)i * i;" in output("widen")


def test_variable_assigned_in_both_branches_is_hoisted():
    assert "    long long r;\n    if (n < 0)" in output("hoist")


def test_loop_element_is_declared_so_c_reads_back_as_for_each():
    out = output("chars")
    assert "char ch = s[i];" in out and "if (ch == 'a')" in out
    assert "for ch in s:" in translate("c", "python", out)["output"]


def test_elif_becomes_else_if():
    assert "else if (n >= 50)" in output("elif")


def test_string_literals_join_the_format():
    assert 'printf("square: %lld\\n", sq(7));' in output("label")


def test_append_builder_writes_forward():
    assert "out[i] = s[i];" in output("append")


def test_negative_step_counts_down():
    assert "for (int i = n; i > 0; i -= 2)" in output("step")


def test_name_swap_uses_a_temp():
    assert "long long t = a;\n        a = b;\n        b = t;" in output("swap")


def test_forward_call_gets_a_prototype():
    assert output("forward").startswith("#include <stdio.h>\n\nlong long g(long long n);\n\nlong long f(long long n)")


def test_length_parameter_only_when_needed():
    out = translate("python", "c", "def f(xs):\n    xs[0] = 5\n\nys = [1, 2]\nf(ys)\nprint(ys)\n")["output"]
    assert "void f(long long xs[])" in out and "f(ys);" in out


def test_counter_used_after_loop_stays_a_while():
    out = output("after")
    assert "while (i < n)" in out and "for (" not in out
