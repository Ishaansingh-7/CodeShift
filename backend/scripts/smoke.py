import json
import sys
import urllib.request

BASE = sys.argv[1].rstrip("/")
LANGS = ["python", "c", "java", "js", "go", "rust"]


def call(path, body=None, origin=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r), r.headers


info, _ = call("/health")
print("health", info)
sample = call("/samples")[0][0]
failed = []
for tgt in LANGS:
    src = "c" if tgt == "python" else "python"
    code = sample["code"][src]
    expected = call("/run", {"lang": src, "code": code})[0]["stdout"]
    out = call("/translate", {"src": src, "tgt": tgt, "code": code, "optimize": True})[0]
    res = call("/run", {"lang": tgt, "code": out["output"]})[0]
    ok = not out["errors"] and res["status"] == "ok" and res["stdout"] == expected
    print(f"{sample['id']} {src} -> {tgt}: {res['status']} {res['timeMs']}ms {'ok' if ok else 'FAIL ' + res['stderr'][:200]}")
    if not ok:
        failed.append(tgt)
_, headers = call("/health", origin="https://codeshift-demo.vercel.app")
cors = headers.get("access-control-allow-origin")
print("cors", cors)
sys.exit(1 if failed or not cors else 0)
