import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
CAP = 64 * 1024
COMPILE_S = float(os.environ.get("COMPILE_TIMEOUT", 5))
RUN_S = float(os.environ.get("RUN_TIMEOUT", 3))
WARM_S = 300
JOBS = threading.BoundedSemaphore(int(os.environ.get("MAX_JOBS", 4)))
EXE = ".exe" if os.name == "nt" else ""
TOOLS = {"python": [], "c": ["gcc"], "java": ["javac", "java"], "js": ["node"], "go": ["go"], "rust": ["rustc"]}
FILES = {"python": "main.py", "c": "main.c", "java": "Main.java", "js": "main.js", "go": "main.go", "rust": "main.rs"}


def search_path():
    if os.name != "nt":
        return os.environ.get("PATH", "")
    import winreg
    parts = [os.environ.get("PATH", "")]
    keys = [(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, "Environment")]
    for root, sub in keys:
        try:
            with winreg.OpenKey(root, sub) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    return os.pathsep.join(parts)


def locate(tool):
    found = shutil.which(tool, path=search_path())
    home = os.environ.get("JAVA_HOME")
    if not found and home and tool in ("javac", "java"):
        candidate = Path(home) / "bin" / (tool + EXE)
        found = str(candidate) if candidate.exists() else None
    return found


PATHS = {lang: [locate(t) for t in tools] for lang, tools in TOOLS.items()}
TOOLCHAINS = {lang: all(paths) for lang, paths in PATHS.items()}

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)


def environment(workdir):
    env = dict(os.environ, TEMP=str(workdir), TMP=str(workdir), TMPDIR=str(workdir), PYTHONIOENCODING="utf-8",
               PATH=search_path(), GOCACHE=str(CACHE / "go-build"), GOPATH=str(CACHE / "gopath"),
               GOTOOLCHAIN="local", APPDATA=str(CACHE / "appdata"), LOCALAPPDATA=str(CACHE / "appdata"))
    env.pop("JAVA_TOOL_OPTIONS", None)
    return env


def commands(lang, workdir, source):
    tool = PATHS[lang]
    exe = str(workdir / ("main" + EXE))
    if lang == "python":
        return None, [sys.executable, "-I", str(source)]
    if lang == "c":
        return [tool[0], "-std=c99", "-o", exe, str(source), "-lm"], [exe]
    if lang == "java":
        cls = source.stem
        return [tool[0], "-encoding", "UTF-8", "-d", str(workdir), str(source)], \
            [tool[1], "-Xshare:auto", "-XX:TieredStopAtLevel=1", "-Dfile.encoding=UTF-8", "-cp", str(workdir), cls]
    if lang == "js":
        return None, [tool[0], str(source)]
    if lang == "go":
        return [tool[0], "build", "-o", exe, str(source)], [exe]
    return [tool[0], *RUST_ARGS, "--edition", "2021", "-o", exe, str(source)], [exe]


def read(path):
    data = path.read_bytes() if path.exists() else b""
    text = data[:CAP].decode("utf-8", errors="replace").replace("\r\n", "\n")
    return text + ("\n… output truncated" if len(data) > CAP else "")


def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))


def stop(proc):
    if os.name == "nt":
        proc.kill()
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def execute(cmd, workdir, timeout, stdin=None):
    out, err = workdir / "stdout.txt", workdir / "stderr.txt"
    start = time.perf_counter()
    with open(out, "wb") as fo, open(err, "wb") as fe:
        proc = subprocess.Popen(cmd, cwd=workdir, stdout=fo, stderr=fe, env=environment(workdir),
                                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                **({} if os.name == "nt" else {"start_new_session": True, "preexec_fn": limits}))
        try:
            proc.communicate(stdin.encode() if stdin is not None else None, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            stop(proc)
            proc.wait()
            code = None
    ms = round((time.perf_counter() - start) * 1000)
    return {"stdout": read(out), "stderr": read(err), "exitCode": code, "timeMs": ms}


def filename(lang, code):
    if lang == "java":
        m = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", code)
        return f"{m.group(1) if m else 'Main'}.java"
    return FILES[lang]


CACHE_SIZE = 512
memo = OrderedDict()
memo_lock = threading.Lock()


def run(lang, code, stdin=None):
    key = (lang, code, stdin)
    if not TOOLCHAINS[lang]:
        return execute_program(lang, code, stdin)
    with memo_lock:
        if key in memo:
            memo.move_to_end(key)
            return dict(memo[key])
    res = execute_program(lang, code, stdin)
    if res["status"] in ("ok", "error"):
        with memo_lock:
            memo[key] = dict(res)
            if len(memo) > CACHE_SIZE:
                memo.popitem(last=False)
    return res


LOCKED = ("Permission denied", "Access is denied", "being used by another process")


def execute_program(lang, code, stdin=None):
    if not TOOLCHAINS[lang]:
        missing = ", ".join(t for t, p in zip(TOOLS[lang], PATHS[lang]) if not p)
        why = REASONS.get(lang) or f"{missing} not found on this machine"
        return {"stdout": "", "stderr": why, "exitCode": None, "timeMs": 0, "status": "missing-toolchain",
                "stage": "compile"}
    with JOBS:
        return execute_locked(lang, code, stdin)


def execute_locked(lang, code, stdin=None):
    (CACHE / "runs").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CACHE / "runs", ignore_cleanup_errors=True) as tmp:
        workdir = Path(tmp)
        source = workdir / filename(lang, code)
        source.write_text(code, encoding="utf-8", newline="\n")
        build, launch = commands(lang, workdir, source)
        if build:
            for _ in range(2):
                res = execute(build, workdir, WARM_S if not warmed.is_set() else COMPILE_S)
                if res["exitCode"] is not None and not any(s in res["stderr"] for s in LOCKED):
                    break
            if res["exitCode"] != 0:
                status = "timeout" if res["exitCode"] is None else "error"
                return {**res, "stdout": "", "stderr": res["stderr"] or res["stdout"], "status": status, "stage": "compile"}
        res = execute(launch, workdir, RUN_S, stdin)
    status = "timeout" if res["exitCode"] is None else "ok" if res["exitCode"] == 0 else "error"
    return {**res, "status": status, "stage": "run"}


warmed = threading.Event()
lock = threading.Lock()
REASONS = {}
RUST_ARGS = []
RUST_GNU = "stable-x86_64-pc-windows-gnu"
RUST_HINT = ("rustc is installed but cannot link programs here: install Visual Studio C++ Build Tools, or run "
             f"`rustup toolchain install {RUST_GNU}` (the gnu target alone also needs a 64-bit MinGW gcc)")


def rust_fallbacks():
    home = Path(os.environ.get("RUSTUP_HOME") or Path.home() / ".rustup")
    out = [[f"+{RUST_GNU}"]] if (home / "toolchains" / RUST_GNU).is_dir() else []
    return out + [["--target", "x86_64-pc-windows-gnu"]]
PROBES = {
    "c": '#include <stdio.h>\n\nint main(void)\n{\n    printf("%lld\\n", 1LL);\n    return 0;\n}\n',
    "java": "public class Main\n{\n    public static void main(String[] args)\n    {\n        System.out.println(1);\n    }\n}\n",
    "go": 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println(1)\n}\n',
    "rust": 'fn main() {\n    println!("{}", 1);\n}\n',
}


def warm():
    with lock:
        if warmed.is_set():
            return
        for lang, code in PROBES.items():
            if not TOOLCHAINS[lang]:
                continue
            res = execute_program(lang, code)
            if lang == "rust":
                for args in rust_fallbacks():
                    if res["status"] == "ok":
                        break
                    RUST_ARGS[:] = args
                    res = execute_program(lang, code)
                if res["status"] != "ok":
                    RUST_ARGS.clear()
            if res["status"] != "ok":
                TOOLCHAINS[lang] = False
                first = next((l.strip() for l in res["stderr"].splitlines() if l.strip()), res["status"])
                REASONS[lang] = RUST_HINT if lang == "rust" else f"{lang} toolchain cannot build programs here: {first}"
        warmed.set()
