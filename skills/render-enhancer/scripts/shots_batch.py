"""Cinematic shots for several final heroes, one view after the other (each view runs its 3 shots in parallel).
The room text comes from codex_brief.ROOMS (where + requested addition). usage: shots_batch.py out_dir VIEW [VIEW ...]"""
import os
import subprocess
import sys

V = r"C:\Users\sbs\.claude\skills\vantage-codex-render\scripts"
sys.path.insert(0, V)
import codex_brief  # noqa: E402

OUT, VIEWS = sys.argv[1], sys.argv[2:]
for v in VIEWS:
    d = os.path.join(OUT, v)
    if all(os.path.exists(os.path.join(d, s, "photo.png")) for s in codex_brief.SHOTS):
        print(v, "shots already done", flush=True)
        continue
    r = codex_brief.room_for(v)
    where = r["where"] + ("; " + r["add"] if r.get("add") else "")
    subprocess.run([sys.executable, "-I", os.path.join(V, "cinematic_shots.py"), d, where])
    print(v, "shots finished", flush=True)
