"""One job = one sheet: room geometry from the Vantage export -> Blender hidden lines per view -> drafting -> sheet composition
-> AutoCAD DWG + PDF in the BAAK cartouche -> overlay of the same 3D on the hero/render images (verification).

usage: python -I pipeline.py job.json            (add "--only views|sheet|verify" to redo one stage)
job.json keys (paths absolute):
  source      the .vrscene (Vantage export of the rendered state)
  work        work folder (short path, e.g. C:/Users/sbs/dwgwork/d3d/<job>)
  room        {"box": [x0,y0,x1,y1], "z": [z0,z1], "xf": {...}, "profile": "..."}   one extraction for every view
  views       {"N": {view keys of draft.py: title, sub, p0, p1, look, depth, z, scale, kind ...}, ...}
  sheet       {"name", "rows": [["N","E"],["S","W"]], "scale", "title", "doc", "niveau", "date", "notes": [...]}
  dwg, pdf    result files (must not exist)
  verify      {"cams": camera list file, "match": "^VEST_F_", "images": ["folder/{name}_hero.png", ...]}   optional"""
import sys, os, json, subprocess, shutil, glob, re

HERE = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(HERE)
PY = sys.executable
BL = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))[-1]
job = json.load(open(sys.argv[1], encoding="utf-8"))
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
W = job["work"]; os.makedirs(W, exist_ok=True)
room = dict(job["room"]); room.setdefault("kind", "elevation"); room.setdefault("p0", room["box"][:2]); room.setdefault("p1", room["box"][2:]); room.setdefault("look", [0, 1])
geom = os.path.join(W, "geom.npz")
def run(cmd, tag):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (r.stdout + r.stderr).splitlines():
        if re.search(r"^(nodes|line art|done|levels|prims|sheet needs|WARNING|entities|console|dwg|pdf|strokes|written)|Error|Traceback|File \"", line): print(tag, line.strip()[:220], flush=True)
    if r.returncode: sys.exit(f"{tag} failed ({r.returncode})")

if only in (None, "views"):
    json.dump(room, open(os.path.join(W, "room.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    run([PY, "-I", os.path.join(HERE, "extract_vrscene.py"), job["source"], os.path.join(W, "room.json"), geom], "extract")
    for k, v in job["views"].items():
        vj = dict(kind="elevation", pad=0.25, px=0.002, profile=room["profile"], xf=room["xf"], level=job.get("level", {}), z=room["z"])
        vj.update(v); vj["name"] = vj.get("name", job["sheet"]["name"] + "-" + k)
        p = os.path.join(W, f"view_{k}.json"); json.dump(vj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out = os.path.join(W, f"out_{k}"); os.makedirs(out, exist_ok=True)
        run([BL, "-b", "--factory-startup", "--python", os.path.join(HERE, "hlr_blender.py"), "--", geom, p, out], f"{k} blender")
        run([PY, "-I", os.path.join(HERE, "draft.py"), p, geom, out, out], f"{k} draft")

if only in (None, "sheet"):
    sh = dict(job["sheet"]); sh["profile"] = room["profile"]
    sh["rows"] = [[os.path.join(W, f"out_{k}") for k in row] for row in sh["rows"]]
    sj = os.path.join(W, "sheet.json"); json.dump(sh, open(sj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    so = os.path.join(W, "sheet_out")
    run([PY, "-I", os.path.join(HERE, "compose.py"), sj, so], "compose")
    run([PY, "-I", os.path.join(HERE, "make_sheet.py"), so, os.path.join(SK, "assets", "base_baak.dwg"), os.path.join(SK, "assets", "cartouche_a1.dwg"),
         job.get("template_layout", "CAH-08-01"), job["dwg"], job["pdf"]], "acad")

if only in (None, "verify") and job.get("verify"):
    vf = job["verify"]; vd = os.path.join(W, "verify"); os.makedirs(vd, exist_ok=True)
    cams = [l.strip() for l in open(vf["cams"], encoding="utf-8", errors="replace") if re.match(vf["match"], l)]
    anyview = os.path.join(W, f"view_{next(iter(job['views']))}.json")
    vgeom = geom
    if vf.get("box"):                          # verification needs what hides the element in the photo: extract a wider zone, no element filter
        vr = dict(room); vr.pop("include", None); vr["box"] = vf["box"]; vr["z"] = vf.get("z", room["z"])
        vr["p0"], vr["p1"] = vf["box"][:2], vf["box"][2:]
        json.dump(vr, open(os.path.join(W, "room_verify.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        vgeom = os.path.join(W, "geom_verify.npz")
        if not os.path.exists(vgeom): run([PY, "-I", os.path.join(HERE, "extract_vrscene.py"), job["source"], os.path.join(W, "room_verify.json"), vgeom], "extract-verify")
    for c in cams:
        nm = c.split("|")[0]
        img = next((p.format(name=nm) for p in vf["images"] if os.path.exists(p.format(name=nm))), None)
        if not img: print("verify: no image for", nm); continue
        run([BL, "-b", "--factory-startup", "--python", os.path.join(HERE, "verify_render.py"), "--", vgeom, anyview, c, img, os.path.join(vd, nm + ".png")], f"verify {nm}")
print("job done", flush=True)
