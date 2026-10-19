import pytest

from app import runner
from codeshift.backends.go import atom, x0
from codeshift.pipeline import translate

HEAD = 'package main\n\nimport "fmt"\n\n'
PROGRAMS = {
    "vowels": HEAD + "func isVowel(c rune) bool {\n    return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u'\n}\n\n"
              "func vowels(s string) int64 {\n    var n int64\n    for _, c := range s {\n        if isVowel(c) {\n"
              "            n++\n        }\n    }\n    return n\n}\n\nfunc tri(n int) int64 {\n    var total int64 = 0\n"
              "    for i := range n {\n        total += int64(i) * 2\n    }\n    return total\n}\n\n"
              'func main() {\n    k := vowels("programming")\n    fmt.Println(k, tri(10), -k, 7%3)\n}\n',
    "slices": HEAD + "func maxOf(xs []int64) int64 {\n    best := xs[0]\n    for _, x := range xs {\n        if x > best {\n"
              "            best = x\n        }\n    }\n    return best\n}\n\nfunc count(s string, c rune) int {\n    n := 0\n"
              "    for i := 0; i < len(s); i++ {\n        if rune(s[i]) == c {\n            n++\n        }\n    }\n"
              "    return n\n}\n\nfunc main() {\n    xs := []int64{4, 9, 2}\n    var label string\n    label = \"max\"\n"
              "    fmt.Println(label, maxOf(xs), count(\"banana\", 'a'))\n}\n",
}
PY = {
    "literals": "x = 1000000 * 1000000\ny = 5000000000\nz = 1 + 3 * 1000000000 - x\nprint(5, x, 2 * 3 + 1, -4, y, z)\n",
    "chars": 'def first_upper(s):\n    for ch in s:\n        if ch >= "A" and ch <= "Z":\n            return ch\n'
             '    return "?"\n\n\ndef steps(n):\n    k = 0\n    while n:\n        n //= 2\n        k += 1\n    return k\n\n\n'
             'def pick(s, i):\n    c = s[i]\n    t = "x"\n    t = c\n    return t\n\n\n'
             'unused = 3\nprint(first_upper("helloWorld"), steps(40), pick("abc", 1))\n',
}


@pytest.mark.parametrize("name", PROGRAMS)
@pytest.mark.parametrize("tgt", ["python", "c", "java", "js"])
def test_go_programs_print_the_same_in_every_target(name, tgt):
    if not (runner.TOOLCHAINS["go"] and runner.TOOLCHAINS[tgt]):
        pytest.skip("toolchain missing")
    r = translate("go", tgt, PROGRAMS[name])
    assert r["errors"] == [], r["errors"]
    a, b = runner.run("go", PROGRAMS[name]), runner.run(tgt, r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


@pytest.mark.parametrize("name", PY)
@pytest.mark.parametrize("tgt", ["go", "c", "java", "js"])
def test_python_programs_print_the_same(name, tgt):
    if not runner.TOOLCHAINS[tgt]:
        pytest.skip("toolchain missing")
    r = translate("python", tgt, PY[name])
    assert r["errors"] == [], r["errors"]
    a, b = runner.run("python", PY[name]), runner.run(tgt, r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


def b(op, l, r):
    return ("bin", op, atom(l) if isinstance(l, str) else l, atom(r) if isinstance(r, str) else r)


@pytest.mark.parametrize("node, depth, text", [
    (b("+", "a", b("*", "b", "c")), 1, "a + b*c"),
    (b("*", b("+", "a", "b"), "c"), 1, "(a + b) * c"),
    (b("+", b("*", "a", "b"), b("*", "c", "d")), 1, "a*b + c*d"),
    (b("-", "a", ("un", "-", atom("b"))), 1, "a - -b"),
    (b("<=", b("*", "i", "i"), "n"), 1, "i*i <= n"),
    (b("&&", b("==", "a", "b"), b("<", "c", "d")), 1, "a == b && c < d"),
    (b("-", b("-", ("call", "len", [atom("xs")]), "1"), "i"), 2, "len(xs)-1-i"),
    (("call", "f", [b("+", "a", "b"), atom("c")]), 1, "f(a+b, c)"),
    (("call", "f", [b("+", "a", "b")]), 1, "f(a + b)"),
    (("index", atom("xs"), b("+", "j", "1")), 1, "xs[j+1]"),
])
def test_gofmt_binary_spacing(node, depth, text):
    assert x0(node, depth) == text


def test_int_conditions_and_char_strings_compile_in_java():
    out = translate("python", "java", PY["chars"])["output"]
    assert "while (n != 0)" in out and "return String.valueOf(ch);" in out
    assert "String c = String.valueOf(s.charAt(i));" in out


def test_constant_arithmetic_is_widened_in_c_and_java():
    c = translate("python", "c", PY["literals"])["output"]
    assert "long long x = 1000000LL * 1000000;" in c and '5LL, x, 2LL * 3 + 1, -4LL' in c
    assert "long y = 5000000000L;" in translate("python", "java", PY["literals"])["output"]


def test_go_specific_forms():
    out = translate("python", "go", PY["chars"])["output"]
    assert "for n != 0 {" in out and "c := string(s[i])" in out and "var unused int64 = 3\n    _ = unused" in out
    back = translate("go", "python", PROGRAMS["vowels"])["output"]
    assert "n = 0" in back and "for i in range(n):" in back


ERRORS = [
    (HEAD + "func main() {\n    s := `raw`\n    fmt.Println(s)\n}\n", "Unsupported: raw string literals at line 6, col 10"),
    ('package main\n\nimport "time"\n\nfunc main() {\n}\n', 'Unsupported: import "time" at line 3, col 8'),
    (HEAD + "func main() {\n    var x float32 = 1.5\n    fmt.Println(x)\n}\n", "Unsupported: float32 (use float64) at line 6, col 11"),
    (HEAD + "func f(p *int64) int64 {\n    return 1\n}\n\nfunc main() {\n}\n", "Unsupported: pointers at line 5, col 10"),
    (HEAD + "func f() (int64, int64) {\n    return 1, 2\n}\n\nfunc main() {\n}\n",
     "Unsupported: multiple results at line 5, col 10"),
    (HEAD + "func main() {\n    defer fmt.Println(1)\n}\n", "Unsupported: 'defer' statement at line 6, col 5"),
    (HEAD + "func main() {\n    fmt.Printf(\"%d\", 1)\n}\n", "Unsupported: library call fmt.Printf at line 6, col 8"),
    (HEAD + "func main() {\n    xs := []int64{1}\n    for i, x := range xs {\n        fmt.Println(i, x)\n    }\n}\n",
     "Unsupported: range loop that uses the index at line 7, col 9"),
    (HEAD + "func main() {\n    if x := 1; x > 0 {\n        fmt.Println(x)\n    }\n}\n",
     "Unsupported: if with an init statement at line 6, col 5"),
]


@pytest.mark.parametrize("code, message", ERRORS)
def test_go_errors_have_positions(code, message):
    r = translate("go", "python", code)
    assert [e["message"] for e in r["errors"]] == [message]
