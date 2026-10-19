import pytest

from codeshift.pipeline import translate

REJECTED = [
    ("js", "let x = 1;\nif (x > 0) {\n  let x = 2;\n  console.log(x);\n}\nconsole.log(x);\n", 3, 7),
    ("c", '#include <stdio.h>\n\nint main(void)\n{\n    long long x = 1;\n    for (int i = 0; i < 3; i++)\n    {\n'
          '        long long x = i;\n        printf("%lld\\n", x);\n    }\n    return 0;\n}\n', 8, 19),
    ("go", 'package main\n\nimport "fmt"\n\nfunc main() {\n    x := 1\n    if x > 0 {\n        x := 2\n'
           '        fmt.Println(x)\n    }\n    fmt.Println(x)\n}\n', 8, 9),
    ("rust", 'fn main() {\n    let x = 1;\n    if x > 0 {\n        let x = 2;\n        println!("{}", x);\n    }\n}\n', 4, 13),
]
ALLOWED = [
    ("js", "var x = 1;\nif (x > 0) {\n  var x = 2;\n}\nconsole.log(x);\n", "x = 1\nif x > 0:\n    x = 2\nprint(x)\n"),
    ("js", "function f(n) {\n  let t = 0;\n  for (let i = 0; i < n; i++) {\n    t += i;\n  }\n"
           "  for (let i = 0; i < n; i++) {\n    t += i;\n  }\n  return t;\n}\n\nlet t = 5;\nconsole.log(f(3), t);\n",
     "def f(n):\n    t = 0\n    for i in range(n):\n        t += i\n    for i in range(n):\n        t += i\n    return t\n\n"
     "t = 5\nprint(f(3), t)\n"),
    ("go", 'package main\n\nimport "fmt"\n\nfunc main() {\n    x := 1\n    x, y := 2, 3\n    fmt.Println(x, y)\n}\n',
     "x = 1\nx, y = 2, 3\nprint(x, y)\n"),
    ("rust", 'fn f(n: i64) -> i64 {\n    let n = n + 1;\n    n\n}\n\nfn main() {\n    println!("{}", f(1));\n}\n',
     "def f(n):\n    n = n + 1\n    return n\n\nprint(f(1))\n"),
]


@pytest.mark.parametrize("src, code, line, col", REJECTED)
def test_inner_block_shadowing_is_rejected(src, code, line, col):
    r = translate(src, "python", code)
    name = "x"
    assert [e["message"] for e in r["errors"]] == [
        f"Unsupported: redeclaring '{name}' inside an inner block (shadowing) at line {line}, col {col}"]


@pytest.mark.parametrize("src, code, python", ALLOWED)
def test_same_scope_redeclaration_is_kept(src, code, python):
    r = translate(src, "python", code)
    assert r["errors"] == [] and r["output"] == python
