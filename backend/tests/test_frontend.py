from codeshift import ast as A
from codeshift.frontends.python.lexer import lex
from codeshift.frontends.python.parser import parse
from codeshift.pipeline import translate
from codeshift.semantic import IDX, INT, analyze
from helpers import source


def kinds(code):
    return [(t.kind, t.text) for t in lex(code)]


def test_lexer_kinds_positions_and_layout():
    toks = lex("def f(n):\n    return len(n)  # c\n")
    assert [(t.kind, t.text) for t in toks] == [
        ("KEYWORD", "def"), ("NAME", "f"), ("PUNCT", "("), ("NAME", "n"), ("PUNCT", ")"), ("PUNCT", ":"),
        ("NEWLINE", "\n"), ("INDENT", "    "), ("KEYWORD", "return"), ("BUILTIN", "len"), ("PUNCT", "("),
        ("NAME", "n"), ("PUNCT", ")"), ("NEWLINE", "\n"), ("DEDENT", ""), ("EOF", ""),
    ]
    ret = toks[8]
    assert (ret.line, ret.col) == (2, 5)


def test_lexer_ignores_blank_lines_comments_and_brackets():
    code = "x = [1,\n     2]\n\n# note\ny = 3\r\n"
    assert [k for k, _ in kinds(code)].count("NEWLINE") == 2
    assert ("OP", "//=") in kinds("a //= 2\n")


def test_parser_builds_statement_nodes():
    m = parse(lex(source("bubble", "python")))
    fn = m.functions[0]
    outer = fn.body[0]
    assert isinstance(outer, A.For) and outer.kind == "range"
    swap = outer.body[0].body[0].body[0]
    assert isinstance(swap, A.Swap)
    assert [type(s).__name__ for s in m.body] == ["Assign", "ExprStmt", "Print"]


def test_floor_division_is_integer_division_in_the_ast():
    stmt = parse(lex("x = 7 // 2\n")).body[0]
    assert isinstance(stmt.value, A.BinOp) and stmt.value.op == "/"


def test_semantic_separates_index_ints_from_64_bit_values():
    info = analyze(parse(lex(source("bsearch", "python"))))
    f = info.funcs["search"]
    assert {v: f.vars[v] for v in ("lo", "hi", "mid", "t")} == {"lo": IDX, "hi": IDX, "mid": IDX, "t": INT}
    assert f.ret == IDX


def test_symbols_use_target_type_names():
    rows = translate("python", "c", source("fib", "python"))["symbols"]
    assert rows == [
        {"name": "fib", "kind": "function", "type": "(int) → long long", "scope": "global"},
        {"name": "n", "kind": "parameter", "type": "int", "scope": "fib"},
        {"name": "a", "kind": "local", "type": "long long", "scope": "fib"},
        {"name": "b", "kind": "local", "type": "long long", "scope": "fib"},
        {"name": "i", "kind": "loop var", "type": "int", "scope": "loop"},
    ]


def test_report_lists_types_changes_and_approximations():
    r = translate("python", "c", source("gcd", "python"))
    assert r["types"] == ["a, b: long long", "gcd → long long"]
    assert r["changed"][0] == {"where": "FUNCTION GCD", "from": "def gcd(a, b):", "to": "long long gcd(long long a, long long b)"}
    assert r["approx"] == [{"from": "// and % round toward −∞", "to": "/ and % round toward 0",
                            "note": "Results differ only when an operand is negative."}]
    assert any(c["where"] == "ENTRY POINT · ADDED" for c in r["changed"])
