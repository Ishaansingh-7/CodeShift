import pytest

from app import runner
from codeshift.pipeline import translate
from test_programs import PROGRAMS as PY

PROGRAMS = {
    "vowels": ("fn is_vowel(c: char) -> bool {\n    c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u'\n}\n\n"
               "fn vowels(s: &str) -> i64 {\n    let mut n = 0;\n    for c in s.chars() {\n        if is_vowel(c) {\n"
               "            n += 1;\n        }\n    }\n    n\n}\n\nfn tri(n: i64) -> i64 {\n    let mut total: i64 = 0;\n"
               "    for i in 1..=n {\n        total += i;\n    }\n    total\n}\n\n"
               'fn main() {\n    let k = vowels("programming");\n    println!("{} {} {}", k, tri(10), -k);\n}\n',
               "3 55 -3", ["python", "c", "java", "js", "go"]),
    "slices": ("fn max_of(xs: &[i64]) -> i64 {\n    let mut best = xs[0];\n    for &x in xs.iter() {\n        if x > best {\n"
               "            best = x;\n        }\n    }\n    best\n}\n\nfn sort(xs: &mut Vec<i64>) {\n    for i in 0..xs.len() {\n"
               "        for j in (i + 1..xs.len()).rev() {\n            if xs[j - 1] > xs[j] {\n                xs.swap(j - 1, j);\n"
               "            }\n        }\n    }\n}\n\nfn label(n: i64) -> String {\n    if n % 2 == 0 {\n"
               '        String::from("even")\n    } else {\n        "odd".to_string()\n    }\n}\n\n'
               "fn main() {\n    let mut xs = vec![4, 9, 2, 7];\n    sort(&mut xs);\n"
               '    println!("max {} {} {}", max_of(&xs), xs[0], label(max_of(&xs)));\n}\n',
               "max 9 2 odd", ["python", "java", "js", "go"]),
    "loops": ("fn digits(mut n: i64) -> String {\n    let mut out = String::new();\n    loop {\n        let d = n % 10;\n"
              "        if d == 0 {\n            out.insert(0, '0');\n        } else if d % 2 == 0 {\n            out.insert(0, 'e');\n"
              '        } else {\n            out.push_str("o");\n        }\n        n /= 10;\n        if n == 0 {\n'
              "            return out;\n        }\n    }\n}\n\nfn fib(n: i64) -> i64 {\n    let (mut a, mut b) = (0, 1);\n"
              "    for _ in 0..n {\n        (a, b) = (b, a + b);\n    }\n    a\n}\n\n"
              'fn main() {\n    let n = 7;\n    let n = n * 3;\n    println!("{} {} {}", digits(1203), fib(n), n);\n}\n',
              "e0oo 10946 21", ["python", "java", "js", "go"]),
}


@pytest.mark.parametrize("name, tgt", [(n, t) for n, p in PROGRAMS.items() for t in p[2]])
def test_rust_programs_translate_and_run(name, tgt):
    if not runner.TOOLCHAINS[tgt]:
        pytest.skip("toolchain missing")
    code, want, _ = PROGRAMS[name]
    r = translate("rust", tgt, code)
    assert r["errors"] == [], r["errors"]
    res = runner.run(tgt, r["output"])
    assert res["status"] == "ok", res["stderr"]
    assert res["stdout"].strip() == want


@pytest.mark.parametrize("name", PY)
def test_python_round_trips_through_rust(name):
    rust = translate("python", "rust", PY[name])
    assert rust["errors"] == [], rust["errors"]
    back = translate("rust", "python", rust["output"])
    assert back["errors"] == [], back["errors"]
    assert runner.run("python", back["output"])["stdout"] == runner.run("python", PY[name])["stdout"]


@pytest.mark.parametrize("code, line", [
    ("def f(n):\n    if n < 0:\n        r = -1\n    else:\n        r = 1\n    return r\n\nprint(f(2))\n", "    let r: i64;"),
    ("def f(n):\n    while n > 0:\n        if n > 2:\n            q = 5\n        else:\n            q = 6\n        n -= q\n"
     "    return n\n\nprint(f(5))\n", "        let q: i64;"),
    ("def f(n):\n    s = 0\n    for i in range(n, 0, -2):\n        s += i\n    return s\n\nprint(f(10))\n",
     "    for i in (1..n + 1).rev().step_by(2) {"),
    ("def f(s, n):\n    k = 0\n    for i in range(len(s)):\n        if s[i] < \"m\" and i < n:\n            k += 1\n"
     "    return k\n\nprint(f(\"hello\", 3))\n", "        if (s.as_bytes()[i] as char) < 'm' && (i as i64) < n {"),
    ("x = 6\nprint(x * 1000000 * 1000000)\n", "    let x = 6i64;"),
    ("def f(s):\n    out = \"\"\n    for ch in s:\n        out = out + ch + ch\n    return out\n\nprint(f(\"ab\"))\n",
     '        out = format!("{}{}{}", out, ch, ch);'),
    ("def f(xs):\n    xs[0] = 5\n\ndef g(xs):\n    f(xs)\n\nys = [1, 2]\ng(ys)\nprint(ys)\n", "fn g(xs: &mut Vec<i64>) {"),
    ("def f(n):\n    return not n\n\nprint(f(0))\n", "    n == 0"),
])
def test_rust_backend_forms(code, line):
    out = translate("python", "rust", code)["output"]
    assert line in out.split("\n"), out


ERRORS = [
    ("fn main() {\n    let x = 1;\n    if x > 0 {\n        let x = 2;\n        println!(\"{}\", x);\n    }\n}\n",
     "Unsupported: redeclaring 'x' inside an inner block (shadowing) at line 4, col 13"),
    ("fn main() {\n    let v: f32 = 1.5;\n}\n", "Unsupported: f32 (use f64) at line 2, col 12"),
    ("use std::io;\n\nfn main() {\n}\n", "Unsupported: use std::io at line 1, col 1"),
    ("#[inline]\nfn main() {\n}\n", "Unsupported: attributes at line 1, col 1"),
    ("fn main() {\n    let x = 5;\n    println!(\"{:e}\", x);\n}\n", "Unsupported: format spec '{:e}' at line 3, col 14"),
    ("fn f(x: i64) -> bool {\n    !x == 0\n}\n\nfn main() {\n    println!(\"{}\", f(1));\n}\n",
     "Unsupported: '!' on an integer (bitwise not in Rust) at line 2, col 5"),
    ("fn main() {\n    let s = \"ab\";\n    for (i, c) in s.chars().enumerate() {\n    }\n}\n",
     "Unsupported: tuple patterns in for loops at line 3, col 5"),
    ("fn main() {\n    let x = 5;\n    match x {\n    }\n}\n", "Unsupported: 'match' statement at line 3, col 5"),
    ("fn main() {\n    let x = 5;\n    eprintln!(\"{}\", x);\n}\n", "Unsupported: macro eprintln! at line 3, col 5"),
]


@pytest.mark.parametrize("code, message", ERRORS)
def test_rust_errors_have_positions(code, message):
    r = translate("rust", "python", code)
    assert [e["message"] for e in r["errors"]] == [message]
