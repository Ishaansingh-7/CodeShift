"""Build a sample's other five language files and its tests.json entry from the Python version.

usage: python scripts/make_sample.py <id> <folder> "<Name>" "<covers>" "<description>" <topic,topic> '<json inputs>' ['<stdin>']

For a program that reads stdin, the inputs are stdin texts and the last argument is the default stdin.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import runner
from app.difftest import difftest
from codeshift.pipeline import LANGS, translate

ROOT = Path(__file__).resolve().parents[2] / "samples"
EXT = {"python": "py", "c": "c", "java": "java", "js": "js", "go": "go", "rust": "rs"}


def files_for(folder):
    return {lang: "Main.java" if lang == "java" else f"{folder}.{EXT[lang]}" for lang in LANGS}


def line_groups(code):
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x

    none = {}
    for src in LANGS:
        for tgt in LANGS:
            if src == tgt:
                continue
            r = translate(src, tgt, code[src])
            assert not r["errors"], (src, tgt, r["errors"])
            first = {}
            for lang, rows in ((src, r["srcLines"]), (tgt, r["tgtLines"])):
                for n, row in enumerate(rows):
                    key = (lang, n)
                    if row["group"] is None:
                        none.setdefault(key, True)
                        continue
                    none[key] = False
                    g = row["group"]
                    if g in first:
                        parent[find(key)] = find(first[g])
                    else:
                        first[g] = key
    ids, out = {}, {}
    for lang in LANGS:
        rows = code[lang].rstrip("\n").split("\n")
        out[lang] = []
        for n in range(len(rows)):
            if none.get((lang, n), True):
                out[lang].append(None)
            else:
                out[lang].append(ids.setdefault(find((lang, n)), len(ids)))
    return out


def main():
    sid, folder, name, covers, desc, topics, inputs = sys.argv[1:8]
    stdin = sys.argv[8] if len(sys.argv) > 8 else None
    inputs = json.loads(inputs)
    runner.warm()
    files = files_for(folder)
    base = ROOT / folder
    code = {"python": (base / files["python"]).read_text(encoding="utf-8")}
    for lang in LANGS[1:]:
        r = translate("python", lang, code["python"])
        assert not r["errors"], (lang, r["errors"])
        code[lang] = r["output"]
        (base / files[lang]).write_text(code[lang], encoding="utf-8", newline="\n")
    stdout = {}
    for lang in LANGS:
        res = runner.run(lang, code[lang], stdin)
        assert res["status"] == "ok", (lang, res["stderr"])
        stdout[lang] = res["stdout"].rstrip("\n")
    rows = [{"input": v, "output": {}} for v in inputs]
    for lang in LANGS[1:]:
        res = difftest("python", lang, code["python"], inputs, stdin)
        assert not res["errors"], res["errors"]
        for row, got in zip(rows, res["rows"]):
            row["output"]["python"] = got["srcOut"]
            row["output"][lang] = got["tgtOut"]
    py = translate("python", "c", code["python"])
    tests = json.loads((ROOT / "tests.json").read_text(encoding="utf-8"))
    tests[sid] = {
        "folder": folder, "files": files, "groups": py["groups"], "lineGroups": line_groups(code),
        "programStdout": stdout, "differential": rows,
        "ir": [{"text": r["text"], "kind": r["kind"], "tag": r["tag"]} for r in py["ir"]],
    }
    if stdin is not None:
        tests[sid]["stdin"] = stdin
    (ROOT / "tests.json").write_text(json.dumps(tests, indent=2) + "\n", encoding="utf-8", newline="\n")
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    catalog[sid] = {"desc": desc, "topics": topics.split(",")}
    if stdin is not None:
        catalog[sid]["stdin"] = stdin
    text = "{\n" + ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in catalog.items()) + "\n}\n"
    (ROOT / "catalog.json").write_text(text, encoding="utf-8", newline="\n")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    row = f"| {folder} | {name} | {covers} |"
    if f"| {folder} |" not in readme:
        lines = readme.split("\n")
        last = max(k for k, line in enumerate(lines) if line.startswith("| ") and not line.startswith("| Folder"))
        lines.insert(last + 1, row)
        (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps(stdout, indent=1))


if __name__ == "__main__":
    main()
