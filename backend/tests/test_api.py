import pytest
from fastapi.testclient import TestClient

from app import runner
from app.main import app
from helpers import SAMPLES, TESTS, needs_gcc, source

client = TestClient(app)
needs = lambda *langs: pytest.mark.skipif(not all(runner.TOOLCHAINS[l] for l in langs), reason="toolchain missing")


def test_samples_endpoint_serves_all_programs():
    rows = client.get("/samples").json()
    assert [r["id"] for r in rows] == SAMPLES
    fib = rows[0]
    assert fib["name"] == "Fibonacci" and "loops" in fib["tags"] and fib["file"] == "fib"
    assert set(fib["code"]) == {"python", "c", "java", "js", "go", "rust"}
    assert fib["code"]["python"] == source("fib", "python")
    assert all(len(r["inputs"]) == 5 for r in rows)
    assert fib["topics"] == ["loops", "math"] and fib["desc"].startswith("Iterative Fibonacci")


def test_translate_endpoint():
    r = client.post("/translate", json={"src": "python", "tgt": "c", "code": source("fib", "python")})
    assert r.status_code == 200 and r.json()["output"] == source("fib", "c")
    bad = client.post("/translate", json={"src": "python", "tgt": "c", "code": "def f(:\n"})
    assert bad.status_code == 200 and bad.json()["errors"][0]["stage"] == "lexer"


def test_malformed_requests_are_4xx():
    assert client.post("/translate", json={"src": "cobol", "tgt": "c", "code": ""}).status_code == 422
    assert client.post("/run", json={"lang": "python"}).status_code == 422
    assert client.post("/difftest", json={"src": "python", "tgt": "c", "code": "", "sample": "nope"}).status_code == 404


def test_run_python_ok_timeout_stdin_and_cap():
    ok = client.post("/run", json={"lang": "python", "code": "print(6 * 7)\n"}).json()
    assert (ok["status"], ok["stdout"], ok["exitCode"]) == ("ok", "42\n", 0)
    slow = client.post("/run", json={"lang": "python", "code": "while True:\n    pass\n"}).json()
    assert slow["status"] == "timeout" and slow["exitCode"] is None
    echo = client.post("/run", json={"lang": "python", "code": "print(input()[::-1])\n", "inputs": "abc\n"}).json()
    assert echo["stdout"] == "cba\n"
    big = client.post("/run", json={"lang": "python", "code": "print('x' * 200000)\n"}).json()
    assert big["stdout"].endswith("… output truncated") and len(big["stdout"]) < 70_000
    crash = client.post("/run", json={"lang": "python", "code": "print(1 // 0)\n"}).json()
    assert crash["status"] == "error" and "ZeroDivisionError" in crash["stderr"]


@needs_gcc
def test_run_c_compile_error_and_success():
    bad = client.post("/run", json={"lang": "c", "code": "int main(void) { return x; }\n"}).json()
    assert (bad["status"], bad["stage"]) == ("error", "compile") and "x" in bad["stderr"]
    good = client.post("/run", json={"lang": "c", "code": source("fib", "c")}).json()
    assert (good["status"], good["stdout"]) == ("ok", "55\n")


def test_missing_toolchain_is_reported_not_raised(monkeypatch):
    monkeypatch.setitem(runner.TOOLCHAINS, "js", False)
    res = client.post("/run", json={"lang": "js", "code": "console.log(1)"}).json()
    assert res["status"] == "missing-toolchain" and res["stderr"]


@needs("python", "c")
@pytest.mark.parametrize("sid", SAMPLES)
def test_difftest_python_to_c_matches_expected_outputs(sid):
    res = client.post("/difftest", json={"src": "python", "tgt": "c", "code": source(sid, "python"), "sample": sid}).json()
    assert res["errors"] == []
    expected = TESTS[sid]["differential"]
    assert [r["srcOut"] for r in res["rows"]] == [e["output"]["python"] for e in expected]
    assert [r["tgtOut"] for r in res["rows"]] == [e["output"]["c"] for e in expected]
    assert res["program"]["match"]
    reasons = [r["reason"] for r in res["rows"] if not r["match"]]
    want = {"fib": ["64-bit overflow"], "fact": ["64-bit overflow"], "power": ["64-bit overflow"] * 2,
            "gcd": ["% sign rule"]}.get(sid, [])
    assert reasons == want


@needs("python", "c")
def test_difftest_generates_inputs_for_user_code():
    code = "def sq(n):\n    return n * n\n\nprint(sq(3))\n"
    res = client.post("/difftest", json={"src": "python", "tgt": "c", "code": code}).json()
    assert res["label"] == "Input n"
    assert [(r["input"], r["srcOut"], r["match"]) for r in res["rows"]] == [
        ("0", "0", True), ("1", "1", True), ("7", "49", True), ("25", "625", True), ("100", "10000", True)]


@needs("python", "c")
def test_difftest_falls_back_to_auto_inputs_when_sample_was_edited():
    code = "def fib(a, b):\n    return a + b\n\nprint(fib(1, 2))\n"
    res = client.post("/difftest", json={"src": "python", "tgt": "c", "code": code, "sample": "fib"}).json()
    assert res["errors"] == [] and res["label"] == "Input a, b"
    assert res["rows"][2] == {"input": "7, 3", "srcOut": "10", "tgtOut": "10", "match": True, "reason": ""}


def test_difftest_reports_untestable_code():
    res = client.post("/difftest", json={"src": "python", "tgt": "c", "code": "print(1)\n"}).json()
    assert res["rows"] == [] and res["errors"][0]["message"].startswith("Unsupported: no function to test")
    if runner.TOOLCHAINS["c"]:
        assert res["program"]["match"] and res["program"]["tgtOut"] == "1\n"
