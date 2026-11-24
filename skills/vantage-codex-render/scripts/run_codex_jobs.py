"""Sends the prepared views to Codex, three at a time, about two minutes each, and skips those already done. usage: run_codex_jobs.py out_dir (the folder with jobs.json)"""
import json
import os
import subprocess
import time

import sys
OUT = sys.argv[1].rstrip("/\\") + "/"
CODEX = r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"
jobs = [j for j in json.load(open(OUT + "jobs.json", encoding="utf-8")) if not os.path.exists(j["dir"] + "/photo.png")]
running = []
print("to do", len(jobs), flush=True)
while jobs or running:
    while jobs and len(running) < 3:
        j = jobs.pop(0)
        cmd = [CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write"]
        for im in j["images"]:
            cmd += ["-i", im]
        cmd += ["-o", "result.md", "-"]
        log = open(j["dir"] + "/codex.log", "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=j["dir"], stdin=open(j["dir"] + "/PROMPT.txt", "rb"), stdout=log, stderr=subprocess.STDOUT)
        running.append((j, p, time.time()))
        print("started", j["name"], flush=True)
    time.sleep(5)
    still = []
    for j, p, t0 in running:
        if p.poll() is None:
            still.append((j, p, t0))
        else:
            print("done", j["name"], "exit", p.returncode, "photo", os.path.exists(j["dir"] + "/photo.png"), round(time.time() - t0), "s", flush=True)
    running = still
print("all done", flush=True)

