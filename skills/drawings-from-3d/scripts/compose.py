"""Compose several drafted views on one sheet and write the AutoCAD data file for build_sheet.lsp.

usage: python -I compose.py sheet.json out_dir
sheet.json: {"name": "EL-VF", "rows": [["dir_of_view", ...], ...], "scale": 25, "title": "...", "doc": "...", "niveau": "...",
             "date": "14/11/2026", "profile": ".../project.json", "notes": ["...", ...],
             "paper": [x0, y0, x1, y1]  (drawing area of the A1 template in mm, default 14,14,740,580)}
Each view dir holds prims.txt + draft.json from draft.py. Callout tags (@@label@@) are numbered across the sheet and listed in REPÈRES;
the finishes seen are listed in LÉGENDE. Writes out_dir/sheet_data.lsp, out_dir/sheet.json (viewport), out_dir/sheet_preview.png."""
import sys, json, re, os
from PIL import Image, ImageDraw

SJ, OUT = sys.argv[1:3]
sh = json.load(open(SJ, encoding="utf-8"))
prof = json.load(open(sh["profile"], encoding="utf-8"))
S = float(sh.get("scale", 25)); MM = S / 1000.0
GAP = 18 * MM

def load(d):
    L = open(os.path.join(d, "prims.txt"), encoding="utf-8").read().splitlines()
    info = json.load(open(os.path.join(d, "draft.json"), encoding="utf-8"))
    ext = [float(v) for v in next(l for l in L if l.startswith("E|")).split("|")[1].split(",")]
    return [l for l in L if not l.startswith("E|")], info, ext

def shift_line(l, dx, dy):
    f = l.split("|")
    t = f[0]
    def sp(s): return ";".join(f"{float(p.split(',')[0]) + dx:.4f},{float(p.split(',')[1]) + dy:.4f}" for p in s.split(";"))
    if t == "L": f[5] = sp(f[5])
    elif t == "H": f[3:] = [sp(x) for x in f[3:]]
    elif t in ("T", "G", "C"): f[2] = f"{float(f[2]) + dx:.4f}"; f[3] = f"{float(f[3]) + dy:.4f}"
    elif t == "D": f[3:6] = [sp(x) for x in f[3:6]]
    return "|".join(f)

# ---- place views row by row (top row first)
placed, legend, y_cursor = [], [], 0.0
for row in sh["rows"]:
    views = [load(d) for d in row]
    rh = max(e[3] - e[1] for _, _, e in views)
    x_cursor = 0.0
    for (L, info, e) in views:
        dx, dy = x_cursor - e[0], y_cursor - rh + (rh - (e[3] - e[1])) - e[1] + (e[3] - e[1]) - (e[3] - e[1])
        dy = y_cursor - e[3]                                        # align the tops of a row
        placed += [shift_line(l, dx, dy) for l in L]
        for c, lab in info.get("legend", []):
            if lab not in [x[1] for x in legend]: legend.append((tuple(c), lab))
        x_cursor += (e[2] - e[0]) + GAP
    y_cursor -= rh + GAP

# ---- number the callout tags across the sheet (top row first, left to right)
tags = [l for l in placed if l.startswith("G|")]
order = sorted(tags, key=lambda l: (-round(float(l.split("|")[3]), 1), float(l.split("|")[2])))
num = {}
for l in order:
    lab = l.split("|")[6].strip("@")
    if lab not in num: num[lab] = len(num) + 1
placed = [("|".join(l.split("|")[:6] + [str(num[l.split("|")[6].strip("@")])]) if l.startswith("G|") else l) for l in placed]

# ---- extents of the views, then REPÈRES and LÉGENDE under them
xs, ys = [], []
for l in placed:
    for fld in l.split("|")[1:]:
        if re.match(r"^-?\d+\.\d+,-?\d+\.\d+(;|$)", fld):
            for p in fld.split(";"): x, y = p.split(","); xs.append(float(x)); ys.append(float(y))
for l in placed:                                                    # texts: estimated width from height x length
    f = l.split("|")
    if f[0] == "T":
        x, y, h, n_ = float(f[2]), float(f[3]), float(f[4]), len(f[7])
        w = 0.62 * h * n_
        xs += [x - w, x] if f[5] == "R" else [x - w / 2, x + w / 2] if f[5] == "C" else [x, x + w]; ys += [y]
    elif f[0] == "G": xs.append(float(f[2])); ys.append(float(f[3]) + float(f[4]))
x0, x1, y1 = min(xs), max(xs), max(ys)
yb = min(ys) - 6 * MM
TL = prof["text_layer"]; FL = prof["fill_layer"]
def T(x, y, h, j, s): placed.append(f"T|{TL}|{x:.4f}|{y:.4f}|{h * MM:.4f}|{j}|0|{s}")
colw = (x1 - x0) / 3
T(x0, yb, 3.4, "L", "REPÈRES")
for i, (lab, n) in enumerate(sorted(num.items(), key=lambda kv: kv[1])):
    cx, cy = x0 + (i % 3) * colw, yb - 8 * MM - (i // 3) * 5.5 * MM
    placed.append(f"G|{TL}|{cx + 2.2 * MM:.4f}|{cy - 1.0 * MM:.4f}|{2.2 * MM:.4f}|{2.0 * MM:.4f}|{n}")
    T(cx + 6 * MM, cy, 2.2, "L", lab)
yl = yb - 8 * MM - ((len(num) + 2) // 3) * 5.5 * MM - 6 * MM
T(x0, yl, 3.4, "L", "LÉGENDE")
for i, (c, lab) in enumerate(legend):
    cx, cy = x0 + (i % 3) * colw, yl - 8 * MM - (i // 3) * 5.5 * MM
    sq = [(cx, cy - 3.0 * MM), (cx + 7 * MM, cy - 3.0 * MM), (cx + 7 * MM, cy), (cx, cy), (cx, cy - 3.0 * MM)]
    placed.append(f"H|{FL}|{c[0]},{c[1]},{c[2]}|" + ";".join(f"{a:.4f},{b:.4f}" for a, b in sq))
    placed.append(f"L|{TL}|9|30,30,32|1|" + ";".join(f"{a:.4f},{b:.4f}" for a, b in sq[:4]))
    T(cx + 9 * MM, cy, 2.2, "L", lab)
yn = yl - 8 * MM - ((len(legend) + 2) // 3) * 5.5 * MM - 6 * MM
notes = sh.get("notes", [])
if notes:
    T(x0, yn, 3.4, "L", "À NOTER")
    for i, s in enumerate(notes): T(x0, yn - 7 * MM - i * 4.6 * MM, 2.2, "L", s)
    yn -= 7 * MM + len(notes) * 4.6 * MM
ext = (x0 - 6 * MM, yn - 4 * MM, x1 + 6 * MM, y1 + 4 * MM)

# ---- fit check on the paper area
px0, py0, px1, py1 = sh.get("paper", [14, 14, 740, 580])
need_w, need_h = (ext[2] - ext[0]) / MM, (ext[3] - ext[1]) / MM
print(f"sheet needs {need_w:.0f} x {need_h:.0f} mm at 1/{int(S)}, area {px1 - px0} x {py1 - py0} mm", flush=True)
if need_w > px1 - px0 or need_h > py1 - py0: print("WARNING: does not fit, use a smaller scale or fewer views per sheet", flush=True)

# ---- AutoCAD data (LISP calls)
def q(s): return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
out = []
for l in placed:
    f = l.split("|"); t = f[0]
    if t == "L":
        pts = " ".join(f"({p.split(',')[0]} {p.split(',')[1]})" for p in f[5].split(";"))
        r, g, b = f[3].split(",")
        out.append(f"(e-pl {q(f[1])} {f[2]} {r} {g} {b} {f[4]} '({pts}))")
    elif t == "H":
        r, g, b = f[2].split(",")
        loops = " ".join("(" + " ".join(f"({p.split(',')[0]} {p.split(',')[1]})" for p in lp.split(";")) + ")" for lp in f[3:])
        out.append(f"(e-hatch {q(f[1])} {r} {g} {b} '({loops}))")
    elif t == "T":
        out.append(f"(e-txt {q(f[1])} {f[2]} {f[3]} {f[4]} {q(f[5])} {f[6]} {q(f[7])})")
    elif t == "D":
        a, b_, c = [p.split(",") for p in f[3:6]]
        out.append(f"(e-dim {q(f[1])} {q(f[2])} {a[0]} {a[1]} {b_[0]} {b_[1]} {c[0]} {c[1]} {f[6]})")
    elif t == "G":
        out.append(f"(e-tag {q(f[1])} {f[2]} {f[3]} {f[4]} {f[5]} {q(f[6])})")
    elif t == "C":
        out.append(f"(e-dot {q(f[1])} {f[2]} {f[3]} {f[4]})")
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "sheet_data.lsp"), "w", encoding="utf-8").write("\n".join(out) + "\n")
cx, cy = (ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2
vw, vh = min(px1 - px0, need_w + 4), min(py1 - py0, need_h + 4)
vp = dict(name=sh["name"], title=sh["title"], doc=sh["doc"], niveau=sh["niveau"], date=sh["date"], scale=S,
          vp=[px0 + (px1 - px0 - vw) / 2, py0 + (py1 - py0 - vh) / 2, px0 + (px1 - px0 + vw) / 2, py0 + (py1 - py0 + vh) / 2],
          centre=[cx, cy], height=vh * MM, numbers=num, entities=len(out))
json.dump(vp, open(os.path.join(OUT, "sheet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("entities", len(out), "tags", len(num), "legend", len(legend), flush=True)

# ---- preview
R = 3.0 / MM
W_, H_ = int((ext[2] - ext[0]) * R), int((ext[3] - ext[1]) * R)
im = Image.new("RGB", (W_, H_), "white"); dr = ImageDraw.Draw(im)
Tm = lambda x, y: ((x - ext[0]) * R, (ext[3] - y) * R)
for l in placed:
    f = l.split("|")
    if f[0] == "H":
        c = tuple(int(v) for v in f[2].split(","))
        mk = Image.new("L", (W_, H_), 0); md = ImageDraw.Draw(mk)
        for k, lp in enumerate(f[3:]):
            pts = [Tm(*map(float, p.split(","))) for p in lp.split(";")]
            if len(pts) > 2: md.polygon(pts, fill=255 if k == 0 else 0)
        im.paste(c, mask=mk)
for l in placed:
    f = l.split("|")
    if f[0] == "L":
        pts = [Tm(*map(float, p.split(","))) for p in f[5].split(";")]
        if f[4] == "1": pts.append(pts[0])
        dr.line(pts, fill=tuple(int(v) for v in f[3].split(",")), width=max(1, int(int(f[2]) / 100 * 3)))
    elif f[0] == "G":
        x, y = Tm(float(f[2]), float(f[3])); r = float(f[4]) * R
        dr.ellipse([x - r, y - r, x + r, y + r], outline=(0, 0, 0)); dr.text((x - 3, y - 5), f[6], fill=(0, 0, 0))
    elif f[0] == "T":
        x, y = Tm(float(f[2]), float(f[3])); dr.text((x, y), f[7], fill=(0, 0, 0))
    elif f[0] == "D":
        a, b_, c = [tuple(map(float, p.split(","))) for p in f[3:6]]
        if f[6] == "0": dr.line([Tm(a[0], c[1]), Tm(b_[0], c[1])], fill=(220, 60, 30))
        else: dr.line([Tm(c[0], a[1]), Tm(c[0], b_[1])], fill=(220, 60, 30))
im.save(os.path.join(OUT, "sheet_preview.png"))
