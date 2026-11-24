"""Build and run the Codex hero for ONE view (safe to run for several views at once: it never touches jobs.json).
usage: hero_one.py out_dir VIEW [render.png]
- render: <out>/<VIEW>/render.png, or <out>/_renders/<VIEW>.png, or the path given.
- notes: <out>/fixes.json entry + <out>/<VIEW>/camera_note.json ({"notes": [...], "remove": [...], "ext": true|false}).
- ext: camera_note/fixes "ext" wins; otherwise the room default (RPM closed = no exterior photo).
Writes PROMPT.txt, runs codex (foreground), output photo.png, log codex.log."""
import json
import os
import shutil
import subprocess
import sys

V = r"C:\Users\sbs\.claude\skills\vantage-codex-render\scripts"
sys.path.insert(0, V)
import codex_brief as cb  # noqa: E402

OUT, VIEW = sys.argv[1], sys.argv[2]
d = os.path.join(OUT, VIEW)
os.makedirs(d, exist_ok=True)
rp = os.path.join(d, "render.png")
src = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "_renders", VIEW + ".png")
if not os.path.exists(rp):
    shutil.copy2(src, rp)
fx_p = os.path.join(OUT, "fixes.json")
fx = json.load(open(fx_p, encoding="utf-8")).get(VIEW, {}) if os.path.exists(fx_p) else {}
if not isinstance(fx, dict):
    fx = {"remove": list(fx)}
cn_p = os.path.join(d, "camera_note.json")
if os.path.exists(cn_p):
    cn = json.load(open(cn_p, encoding="utf-8"))
    fx = dict(fx)
    fx["notes"] = cn.get("notes", []) + [n for n in fx.get("notes", []) if n not in cn.get("notes", [])]
    if cn.get("remove"):
        fx["remove"] = cn["remove"]
    if "ext" in cn:
        fx["ext"] = cn["ext"]
style, _light = cb.room_style(VIEW)
lv = style or [r for r in cb.REFS if os.path.exists(r)]
mach, design, pose = cb.room_refs(VIEW)
ext_on = fx.get("ext", not cb.room_for(VIEW).get("no_ext"))
ext = [cb.EXTERIOR_IMG] if (ext_on and os.path.exists(cb.EXTERIOR_IMG)) else []
fx_brief = {k: v for k, v in fx.items() if k in ("notes", "remove")}
open(os.path.join(d, "PROMPT.txt"), "w", encoding="utf-8").write(
    cb.hero(VIEW, fx_brief, len(lv), bool(ext), len(mach), len(pose), len(design), bool(style)))
cmd = [r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe", "exec", "--skip-git-repo-check", "-s", "workspace-write"]
for im in [rp] + lv + mach + design + pose + ext:
    cmd += ["-i", im]
cmd += ["-o", "result.md", "-"]
with open(os.path.join(d, "PROMPT.txt"), "rb") as fin, open(os.path.join(d, "codex.log"), "w", encoding="utf-8") as fout:
    subprocess.run(cmd, cwd=d, stdin=fin, stdout=fout, stderr=subprocess.STDOUT)
print(VIEW, "photo" if os.path.exists(os.path.join(d, "photo.png")) else "NO PHOTO", "| images:", 1 + len(lv) + len(mach) + len(design) + len(pose) + len(ext), "| ext:", bool(ext))
