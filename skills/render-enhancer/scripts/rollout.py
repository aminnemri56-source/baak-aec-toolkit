"""Roll a correction out to many views at once: per view, the hero comment round first, then its shots in parallel
(each shot sees the corrected hero). All views run at the same time.
usage: rollout.py plan.json
plan.json: [{"view": "SDC_4", "hero": "<job dir>" or null, "hero_comments": "<txt>", "hero_extra": [imgs],
             "shots": ["<CU dir>", ...], "shot_comments": "<txt>", "shot_extra": [imgs, "{hero}" = the view's photo.png]}]
Prints one line per finished round; the photos are backed up by codex_comment.py (photo_rN.png)."""
import json
import os
import subprocess
import sys
import threading

PY = sys.executable
CC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codex_comment.py")
plan = json.load(open(sys.argv[1], encoding="utf-8"))
lock = threading.Lock()


def run(d, comments, extra):
    r = subprocess.run([PY, "-I", CC, d, comments] + extra, capture_output=True, text=True)
    with lock:
        print(os.path.basename(os.path.dirname(d)) + "/" + os.path.basename(d), "|", (r.stdout or r.stderr).strip().splitlines()[-1:], flush=True)


def view(v):
    hero_photo = None
    if v.get("hero"):
        run(v["hero"], v["hero_comments"], v.get("hero_extra", []))
    hero_photo = os.path.join(v.get("hero") or os.path.dirname(v["shots"][0]), "photo.png")
    ts = []
    for s in v.get("shots", []):
        extra = [hero_photo if e == "{hero}" else e for e in v.get("shot_extra", [])]
        t = threading.Thread(target=run, args=(s, v["shot_comments"], extra))
        t.start(); ts.append(t)
    for t in ts:
        t.join()


threads = [threading.Thread(target=view, args=(v,)) for v in plan]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("ROLLOUT DONE", flush=True)
