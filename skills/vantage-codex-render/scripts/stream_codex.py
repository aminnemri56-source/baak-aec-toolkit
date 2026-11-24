"""Starts Codex on each Vantage render as soon as it is saved (no waiting for the whole batch), 3 at a time, until `expected`
photos exist or the time limit. Uses make_codex_jobs.py for folders and prompts. usage: stream_codex.py renders_dir codex_dir expected [since_epoch]"""
import json
import os
import subprocess
import sys
import time

R, C, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
SINCE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0   # only renders written after this epoch time
STAGE = os.path.join(C, "_renders")
os.makedirs(STAGE, exist_ok=True)
import shutil
PY = sys.executable
S = os.path.dirname(os.path.abspath(__file__))
CODEX = r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"
running = {}
sizes = {}
t0 = time.time()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


while time.time() - t0 < 4 * 3600:
    # renders that stopped growing
    stable = []
    for f in sorted(os.listdir(R)) if os.path.isdir(R) else []:
        if not f.lower().endswith(".png"):
            continue
        p = os.path.join(R, f)
        if os.path.getmtime(p) < SINCE:
            continue
        s = os.path.getsize(p)
        if sizes.get(f) == s and s > 100000:
            stable.append(f)
        sizes[f] = s
    for f in stable:
        if not os.path.exists(os.path.join(STAGE, f)):
            shutil.copy2(os.path.join(R, f), os.path.join(STAGE, f))
    if stable:
        subprocess.run([PY, "-I", os.path.join(S, "make_codex_jobs.py"), STAGE, C], capture_output=True, text=True)
        jobs = json.load(open(os.path.join(C, "jobs.json"), encoding="utf-8"))
        for j in jobs:
            name = j["name"]
            if name + ".png" not in stable or name in running or os.path.exists(os.path.join(j["dir"], "photo.png")):
                continue
            if len(running) >= 3:
                break
            cmd = [CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write"]
            for im in j["images"]:
                cmd += ["-i", im]
            cmd += ["-o", "result.md", "-"]
            lg = open(os.path.join(j["dir"], "codex.log"), "w", encoding="utf-8")
            running[name] = (subprocess.Popen(cmd, cwd=j["dir"], stdin=open(os.path.join(j["dir"], "PROMPT.txt"), "rb"), stdout=lg, stderr=subprocess.STDOUT), time.time(), j["dir"])
            log("codex started", name)
    for name in list(running):
        p, ts, d = running[name]
        if p.poll() is not None:
            log("codex done", name, "photo" if os.path.exists(os.path.join(d, "photo.png")) else "NO PHOTO", int(time.time() - ts), "s")
            del running[name]
    done = sum(1 for d in os.listdir(C) if os.path.exists(os.path.join(C, d, "photo.png"))) if os.path.isdir(C) else 0
    if done >= N and not running:
        break
    time.sleep(20)
log("finished, photos:", done)
