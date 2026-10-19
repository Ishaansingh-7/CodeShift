import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codeshift import __version__
from codeshift.pipeline import translate

from .difftest import difftest
from .runner import TOOLCHAINS, run

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
Lang = Literal["python", "c", "java", "js", "go", "rust"]
Code = Field(max_length=200_000)

router = APIRouter()


class TranslateReq(BaseModel):
    src: Lang
    tgt: Lang
    code: str = Code
    optimize: bool = True


class RunReq(BaseModel):
    lang: Lang
    code: str = Code
    inputs: str | None = Field(default=None, max_length=100_000)


class DiffReq(BaseModel):
    src: Lang
    tgt: Lang
    code: str = Code
    sample: str | None = None
    stdin: str | None = Field(default=None, max_length=100_000)


@lru_cache
def samples():
    tests = json.loads((SAMPLES / "tests.json").read_text(encoding="utf-8"))
    catalog = json.loads((SAMPLES / "catalog.json").read_text(encoding="utf-8"))
    meta = {}
    for line in (SAMPLES / "README.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and (SAMPLES / cells[0]).is_dir():
            meta[cells[0]] = cells[1], [t.strip().replace("`", "") for t in cells[2].split(",")]
    out = []
    for sid, s in tests.items():
        name, tags = meta.get(s["folder"], (sid, []))
        code = {lang: (SAMPLES / s["folder"] / f).read_text(encoding="utf-8") for lang, f in s["files"].items()}
        out.append({"id": sid, "name": name, "file": Path(s["files"]["python"]).stem, "folder": s["folder"],
                    "files": s["files"], "tags": tags, "code": code, **catalog.get(sid, {"desc": "", "topics": []}),
                    "inputs": [r["input"] for r in s["differential"]]})
    return out


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__, "toolchains": TOOLCHAINS}


@router.get("/samples")
def list_samples():
    return samples()


@router.post("/translate")
def translate_route(req: TranslateReq):
    return translate(req.src, req.tgt, req.code, req.optimize)


@router.post("/run")
def run_route(req: RunReq):
    return run(req.lang, req.code, req.inputs)


@router.post("/difftest")
def difftest_route(req: DiffReq):
    sample = None
    if req.sample is not None:
        sample = next((s for s in samples() if s["id"] == req.sample), None)
        if sample is None:
            raise HTTPException(404, f"Unknown sample '{req.sample}'")
    stdin = req.stdin if req.stdin is not None or not sample else sample.get("stdin")
    res = difftest(req.src, req.tgt, req.code, sample["inputs"] if sample else None, stdin)
    if res["errors"] and sample:
        auto = difftest(req.src, req.tgt, req.code, None, stdin)
        if not auto["errors"]:
            return auto
    return res
