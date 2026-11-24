"""Codex photo jobs from Vantage renders with the "unlimited level" brief of codex_brief.py (locked inventory, allowed
changes only, per-view 3D errors to remove, self-check with up to 3 attempts). One folder per view with render.png and
PROMPT.txt, plus jobs.json for run_codex_jobs.py / stream_codex.py.
usage: make_codex_jobs.py renders_dir out_dir [fixes.json]   (renders named *_<VIEW>.png, e.g. HYB_0711_PIL_1.png)
fixes.json: {"HYB_0711_PIL_5": ["the thin horizontal bar ...", "the long diagonal pole ..."]}; also read from out_dir/fixes.json."""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import codex_brief  # noqa: E402

RENDERS, OUT = sys.argv[1], sys.argv[2]
fx_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "fixes.json")
FIXES = json.load(open(fx_path, encoding="utf-8")) if os.path.exists(fx_path) else {}

os.makedirs(OUT, exist_ok=True)
refdir = os.path.join(OUT, "_level_refs")
os.makedirs(refdir, exist_ok=True)
refs = []
for i, src in enumerate(codex_brief.REFS, 1):
    if os.path.exists(src):
        dst = os.path.join(refdir, "level_%d%s" % (i, os.path.splitext(src)[1]))
        shutil.copy2(src, dst)
        refs.append(dst)
ext = []
if os.path.exists(codex_brief.EXTERIOR_IMG):
    ext = [os.path.join(refdir, "exterior" + os.path.splitext(codex_brief.EXTERIOR_IMG)[1])]
    shutil.copy2(codex_brief.EXTERIOR_IMG, ext[0])
jobs, skipped = [], []
for f in sorted(os.listdir(RENDERS)):
    if not f.lower().endswith(".png"):
        continue
    name = os.path.splitext(f)[0]
    a = np.asarray(Image.open(os.path.join(RENDERS, f)).convert("RGB"))
    if (a.max(axis=2) < 6).mean() > 0.7:
        skipped.append(name + " black")
        continue
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    style, _light = codex_brief.room_style(name)   # a room with its own approved style uses it instead of the level refs
    lv = style or refs
    mach, design, pose = codex_brief.room_refs(name)   # real machine photos, validated esquisse, real class positions
    ext_v = [] if codex_brief.room_for(name).get("no_ext") else ext   # closed rooms (RPM) get no exterior photo
    imgs = [os.path.join(d, "render.png")] + lv + mach + design + pose + ext_v
    if os.path.exists(os.path.join(d, "photo.png")):   # already made: keep its render, prompt and log
        jobs.append(dict(name=name, dir=d, images=imgs))
        continue
    shutil.copy2(os.path.join(RENDERS, f), os.path.join(d, "render.png"))
    open(os.path.join(d, "PROMPT.txt"), "w", encoding="utf-8").write(codex_brief.hero(name, FIXES.get(name, ()), len(lv), bool(ext_v), len(mach), len(pose), len(design), bool(style)))
    jobs.append(dict(name=name, dir=d, images=imgs))
json.dump(jobs, open(os.path.join(OUT, "jobs.json"), "w", encoding="utf-8"), indent=0)
print("prepared", len(jobs), "skipped", skipped)
