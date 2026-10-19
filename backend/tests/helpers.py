import copy
import json
import operator
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from codeshift.frontends.python.lexer import lex
from codeshift.frontends.python.parser import parse
from codeshift.ir import Const, lower
from codeshift.library import IMPL
from codeshift.optimize import optimize
from codeshift.semantic import analyze

ROOT = Path(__file__).resolve().parents[2] / "samples"
TESTS = json.loads((ROOT / "tests.json").read_text())
SAMPLES = list(TESTS)
GCC = shutil.which("gcc")
needs_gcc = pytest.mark.skipif(not GCC, reason="gcc not installed")


def source(sid, lang):
    s = TESTS[sid]
    return (ROOT / s["folder"] / s["files"][lang]).read_text()


def run_c(code, tmp_path):
    src, exe = tmp_path / "main.c", tmp_path / "main.exe"
    src.write_text(code)
    for _ in range(2):
        build = subprocess.run([GCC, "-std=c99", "-pedantic", "-Wall", "-Wextra", "-Werror", "-o", str(exe), str(src)],
                               capture_output=True, text=True, timeout=60)
        if "Permission denied" not in build.stderr:
            break
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return run.stdout


def run_py(code):
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return run.stdout


def build_ir(code):
    module = parse(lex(code))
    funcs = lower(module, analyze(module))
    plain = copy.deepcopy(funcs)
    rows = optimize(funcs)
    return module, plain, funcs, rows


BIN = {
    "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.floordiv, "%": operator.mod,
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq, "!=": operator.ne,
}
UN = {"-": operator.neg, "!": operator.not_, "len": len}


class Machine:
    def __init__(self, funcs, live=False, stdin=""):
        self.funcs = {code[0].name: [i for i in code if not (live and i.dead)] for code in funcs}
        self.out = ""
        self.lines = iter((stdin or "").split("\n"))

    def value(self, a, env):
        if isinstance(a, Const):
            return [self.value(x, env) for x in a.value] if a.ty == "arr" else a.value
        return env[a]

    def call(self, name, args):
        code = self.funcs[name]
        env = dict(zip(code[0].args, args))
        labels = {i.name: k for k, i in enumerate(code) if i.op == "label"}
        pc = 1
        while pc < len(code):
            i = code[pc]
            pc += 1
            v = [self.value(a, env) for a in i.args] if i.op not in ("label", "goto") else []
            if i.op == "copy":
                env[i.dst] = v[0]
            elif i.op == "bin" and i.name == "/" and any(isinstance(x, float) for x in v):
                env[i.dst] = v[0] / v[1]
            elif i.op == "bin":
                env[i.dst] = BIN[i.name](*v)
            elif i.op == "un":
                env[i.dst] = UN[i.name](v[0])
            elif i.op == "load":
                env[i.dst] = v[0][v[1]]
            elif i.op == "store":
                v[0][v[1]] = v[2]
            elif i.op == "call":
                if i.name == "@read_line":
                    r = next(self.lines, "")
                else:
                    r = IMPL[i.name[1:]](*v) if i.name.startswith("@") else self.call(i.name, v)
                if i.dst:
                    env[i.dst] = r
            elif i.op == "iffalse" and not v[0] or i.op == "goto":
                pc = labels[i.name]
            elif i.op == "ret":
                return v[0] if v else None
            elif i.op == "print":
                self.out += " ".join(map(str, v)) + ("\n" if i.name is None else i.name)
        return None

    def main(self):
        try:
            self.call("main", [])
        except SystemExit:
            pass
        return self.out[:-1] if self.out.endswith("\n") else self.out
