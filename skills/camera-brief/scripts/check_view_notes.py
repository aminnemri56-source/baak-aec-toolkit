"""Refuses a Codex batch when a view has no per-camera note. usage: check_view_notes.py out_dir [filter]
Each view in out_dir/jobs.json needs, in out_dir/fixes.json, notes containing 'THIS CAMERA SEES' and 'NOT IN THIS VIEW'."""
import json
import os
import sys

OUT = sys.argv[1]
FLT = sys.argv[2] if len(sys.argv) > 2 else ""
jobs = json.load(open(os.path.join(OUT, "jobs.json"), encoding="utf-8"))
fx_p = os.path.join(OUT, "fixes.json")
fx = json.load(open(fx_p, encoding="utf-8")) if os.path.exists(fx_p) else {}
missing = []
for j in jobs:
    n = j["name"]
    if FLT not in n:
        continue
    e = fx.get(n, {})
    notes = " ".join(e.get("notes", [])) if isinstance(e, dict) else ""
    if "THIS CAMERA SEES" not in notes or "NOT IN THIS VIEW" not in notes:
        missing.append(n)
print("views without a camera note:", missing if missing else "none")
sys.exit(1 if missing else 0)
