import pytest

from codeshift.pipeline import translate
from helpers import SAMPLES, source


@pytest.mark.parametrize("sid", SAMPLES)
def test_response_shape(sid):
    r = translate("python", "c", source(sid, "python"))
    assert set(r) >= {"output", "srcLines", "tgtLines", "tokens", "ast", "symbols", "ir", "cfg", "types", "changed",
                      "approx", "stats", "errors"}
    assert r["stats"]["lines"] == len(r["tgtLines"]) == len(r["output"].splitlines())
    assert r["stats"]["tokens"] == len(r["tokens"])
    assert r["ast"]["type"] == "Module" and r["ast"]["children"]
    assert r["symbols"][0]["kind"] == "function"
    assert r["cfg"]["blocks"] and all(e["label"] in ("", "true", "false", "back") for e in r["cfg"]["edges"])
    last = r["ast"]["children"][-1]
    assert last["type"] == "Call" and last["detail"].startswith("print(")


def test_ast_tree_shows_else_as_a_leaf():
    tree = translate("python", "c", source("bsearch", "python"))["ast"]
    loop = tree["children"][0]["children"][1]
    branch = loop["children"][2]
    assert (branch["type"], branch["detail"]) == ("If", "xs[mid] < t")
    assert branch["children"][-1] == {"type": "Else", "detail": "hi = mid - 1", "line": 10, "group": branch["group"], "children": []}
