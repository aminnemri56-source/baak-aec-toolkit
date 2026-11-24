"""Run several hero jobs from <out>/jobs.json at the same time ("LAUNCH THEM IN PARALLEL PLEASE", 07/11).
usage: run_parallel.py out_dir VIEW [VIEW ...]   (views that already have photo.png are skipped)"""
import json
import os
import subprocess
import sys
import time

OUT, VIEWS = sys.argv[1], set(sys.argv[2:])
CODEX = r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"
procs = []
for j in json.load(open(os.path.join(OUT, "jobs.json"), encoding="utf-8")):
    if j["name"] not in VIEWS or os.path.exists(os.path.join(j["dir"], "photo.png")):
        continue
    cmd = [CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write"]
    for im in j["images"]:
        cmd += ["-i", im]
    cmd += ["-o", "result.md", "-"]
    p = subprocess.Popen(cmd, cwd=j["dir"], stdin=open(os.path.join(j["dir"], "PROMPT.txt"), "rb"),
                         stdout=open(os.path.join(j["dir"], "codex.log"), "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    procs.append((j, p, time.time()))
    print(time.strftime("%H:%M:%S"), "started", j["name"], flush=True)
for j, p, t0 in procs:
    p.wait()
    print(time.strftime("%H:%M:%S"), "done", j["name"], "photo" if os.path.exists(os.path.join(j["dir"], "photo.png")) else "NO PHOTO", int(time.time() - t0), "s", flush=True)
