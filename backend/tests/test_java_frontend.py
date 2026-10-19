import pytest

from app import runner
from codeshift.pipeline import translate

WRAP = "public class Main\n{\n%s\n    public static void main(String[] args)\n    {\n%s\n    }\n}\n"

PROGRAMS = {
    "concat": WRAP % ("    static long sq(long x)\n    {\n        return x * x;\n    }\n",
                      "        long a = 3;\n        System.out.println(\"square: \" + sq(a));\n"
                      "        System.out.println(a + \" \" + sq(a) + \" \" + (a + 1));"),
    "vowels": WRAP % ("    static boolean isVowel(char c)\n    {\n        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';\n"
                      "    }\n\n    static long vowels(String s)\n    {\n        long n = 0;\n        for (char c : s.toCharArray())\n"
                      "        {\n            if (isVowel(c))\n            {\n                n++;\n            }\n        }\n"
                      "        return n;\n    }\n",
                      "        System.out.println(vowels(\"programming\"));"),
    "doubling": WRAP % ("    static String twice(String s)\n    {\n        String out = \"\";\n        for (char c : s.toCharArray())\n"
                        "        {\n            out = out + c + c;\n        }\n        return out;\n    }\n",
                        "        System.out.println(twice(\"ab\"));"),
}


@pytest.mark.parametrize("name", PROGRAMS)
def test_java_to_python_prints_the_same(name):
    if not (runner.TOOLCHAINS["java"] and runner.TOOLCHAINS["python"]):
        pytest.skip("toolchain missing")
    r = translate("java", "python", PROGRAMS[name])
    assert r["errors"] == [], r["errors"]
    a, b = runner.run("java", PROGRAMS[name]), runner.run("python", r["output"])
    assert a["status"] == b["status"] == "ok", (a["stderr"], b["stderr"])
    assert a["stdout"] == b["stdout"]


def test_println_concatenation_becomes_print_arguments():
    out = translate("java", "python", PROGRAMS["concat"])["output"]
    assert 'print("square:", sq(a))' in out and "print(a, sq(a), a + 1)" in out


ERRORS = [
    (WRAP % ("    long f(long x)\n    {\n        return x;\n    }\n", ""),
     "Unsupported: instance members (only static methods are supported) at line 3, col 5"),
    ("import java.util.Random;\n" + WRAP % ("", ""), "Unsupported: import java.util.Random at line 1, col 1"),
    (WRAP % ("", "        float x = 1.5f;"), "Unsupported: 32-bit float (use double) at line 6, col 9"),
    (WRAP % ("    static long count = 0;\n", ""), "Unsupported: fields at line 3, col 17"),
    (WRAP % ("", "        double m = Math.random();"), "Unsupported: library call Math.random at line 6, col 24"),
    (WRAP % ("", "        long x = 1;\n        System.out.printf(\"%d%n\", x);"),
     "Unsupported: library call System.out.printf at line 7, col 19"),
]


@pytest.mark.parametrize("code, message", ERRORS)
def test_java_errors_have_positions(code, message):
    r = translate("java", "python", code)
    assert [e["message"] for e in r["errors"]] == [message]
