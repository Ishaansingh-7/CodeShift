import pytest

from app import runner
from codeshift.pipeline import translate

PROGRAMS = {
    "inclusive": "#include <stdio.h>\n\nlong long tri(long long n)\n{\n    long long s = 0;\n    for (long long i = 1; i <= n; i++)\n"
                 "    {\n        s += i;\n    }\n    return s;\n}\n\nint main(void)\n{\n    printf(\"%lld\\n\", tri(10));\n    return 0;\n}\n",
    "collatz": "#include <stdio.h>\n#include <stdbool.h>\n\nbool even(long long n)\n{\n    return n % 2 == 0;\n}\n\nint main(void)\n{\n"
               "    long long n = 7;\n    long long steps = 0;\n    while (n != 1)\n    {\n        if (even(n))\n        {\n"
               "            n = n / 2;\n        }\n        else\n        {\n            n = 3 * n + 1;\n        }\n        steps++;\n"
               "    }\n    printf(\"%lld\\n\", steps);\n    return 0;\n}\n",
    "chars": "#include <stdio.h>\n#include <string.h>\n\nlong long count(const char *s, char c)\n{\n    long long k = 0;\n"
             "    int n = strlen(s);\n    for (int i = 0; i < n; i++)\n    {\n        if (s[i] == c)\n        {\n            k++;\n"
             "        }\n    }\n    return k;\n}\n\nint main(void)\n{\n    printf(\"%lld\\n\", count(\"banana\", 'a'));\n    return 0;\n}\n",
    "comments": "/* block\n   comment */\n#include <stdio.h>\n\n// helper\nlong long twice(long long x) { return x * 2; }\n\n"
                "int main(void)\n{\n    long long a = 4, b = twice(a);\n    printf(\"%lld %lld\\n\", a, b);\n    return 0;\n}\n",
}


@pytest.mark.parametrize("name", PROGRAMS)
def test_c_to_python_prints_the_same(name):
    if not (runner.TOOLCHAINS["c"] and runner.TOOLCHAINS["python"]):
        pytest.skip("toolchain missing")
    r = translate("c", "python", PROGRAMS[name])
    assert r["errors"] == [], r["errors"]
    a, b = runner.run("c", PROGRAMS[name]), runner.run("python", r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


def test_inclusive_loop_becomes_range_plus_one():
    assert "for i in range(1, n + 1):" in translate("c", "python", PROGRAMS["inclusive"])["output"]


ERRORS = [
    ("int main(void)\n{\n    long long x = 1\n    return 0;\n}\n", "Syntax error: expected ';', found 'return' at line 4, col 5"),
    ("#include <time.h>\nint main(void) { return 0; }\n", "Unsupported: #include <time.h> at line 1, col 1"),
    ("int main(void)\n{\n    int *p;\n    return 0;\n}\n", "Unsupported: pointers at line 3, col 5"),
    ("int main(void)\n{\n    float x = 1.5f;\n    return 0;\n}\n", "Unsupported: float and long double (use double) at line 3, col 5"),
    ("long long g = 1;\nint main(void) { return 0; }\n", "Unsupported: global variables at line 1, col 11"),
    ("#include <stdio.h>\nint main(void)\n{\n    printf(\"%e\", 1.5);\n    return 0;\n}\n",
     "Unsupported: printf format '%e' at line 4, col 5"),
    ("int main(void)\n{\n    do { } while (1);\n    return 0;\n}\n", "Unsupported: 'do' statement at line 3, col 5"),
    ("int main(void)\n{\n    return 1;\n}\n", "Unsupported: main returning something other than 0 at line 3, col 5"),
]


@pytest.mark.parametrize("code, message", ERRORS)
def test_c_errors_have_positions(code, message):
    r = translate("c", "python", code)
    assert [e["message"] for e in r["errors"]] == [message]
