"""2D drafting of one view: hidden lines from Blender -> weighted polylines on the charter layers, cut poché, flat finish colours,
levels, dimension chains, finish callouts, title and legend. Writes the primitives for build_dwg.lsp and a PNG preview.

usage: python -I draft.py view.json geom.npz hlr_dir out_dir
out_dir/prims.txt (model-space metres, drawing placed with its frame's bottom-left at 0,0):
  L|layer|lw(1/100 mm)|r,g,b|closed|x,y;x,y;...        LWPOLYLINE (lineweight 370, true colour 420)
  H|layer|r,g,b|x,y;...|x,y;...                          SOLID hatch, one or more loops
  T|layer|x|y|h|just|rot|text                            MTEXT (just: L C R, attachment top) in the profile font
  D|layer|dimstyle|x1,y1|x2,y2|xd,yd|rot                 rotated linear dimension (rot 0 horizontal, 90 vertical)
  E|xmin,ymin,xmax,ymax                                  extents of everything (viewport)
out_dir/preview.png, out_dir/draft.json (levels, chains, callouts, counts)"""
import sys, json, re, math
import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box, Point, GeometryCollection
from shapely.ops import linemerge, unary_union
from PIL import Image, ImageDraw

VIEWJ, GEOM, HLR, OUT = sys.argv[1:5]
view = json.load(open(VIEWJ, encoding="utf-8"))
prof = json.load(open(view["profile"], encoding="utf-8"))
S = float(view.get("scale", 20)); MM = S / 1000.0                   # model metres per paper millimetre
g = np.load(GEOM)
V, F, FN, FM = g["V"].astype(np.float64), g["F"], g["FN"], g["FM"]
names, nlay, mats = json.loads(str(g["names"])), json.loads(str(g["layers"])), json.loads(str(g["mats"]))
meta = json.load(open(HLR + "/meta.json"))
U, Vv, D = np.array(meta["U"]), np.array(meta["V"]), np.array(meta["D"]); PD = meta["plane_d"]
st = np.load(HLR + "/strokes.npz")
P, OFF, KIND, NODE, MAT = st["P"].astype(np.float64), st["OFF"], st["KIND"], st["NODE"], st["MAT"]
PLAN = view.get("kind") == "plan"

# ---------------------------------------------------------------- frame and placement
p0, p1 = np.array(view["p0"], float), np.array(view["p1"], float)
if PLAN:
    ua, ub = sorted([p0[0], p1[0]]); va, vb = sorted([p0[1], p1[1]])
else:
    ua, ub = sorted([p0 @ U[:2], p1 @ U[:2]]); va, vb = view["z"]
ua, ub, va, vb = view.get("frame", [ua, ub, va, vb])
OX, OY = -ua, (-va if PLAN else 0.0)                                # model = (u + OX, v + OY): frame starts at x 0, floor at y 0
FRAME = box(ua, va, ub, vb)

# ---------------------------------------------------------------- classification of nodes (profile rules)
WALLS, SLABS = re.compile(prof["walls"]), re.compile(prof["slabs"], re.I)
IGN = re.compile(prof.get("ignore", "^$"))
PALR = [(re.compile(p, re.I), tuple(c), l) for p, c, l in prof["palette"]]
LAYR = [(re.compile(p, re.I), l) for p, l in prof["layers"]]
CALR = [(re.compile(p, re.I), l) for p, l in prof.get("callouts", [])]
def is_wall(n): return bool(WALLS.match(names[n])) and not re.search("Cladding|Feutre|Tole", names[n])
def is_struct(n): return is_wall(n) or bool(SLABS.search(names[n]))
def layer_of(n, m):
    if n < 0: return prof["default_layer"]
    if is_struct(n): return prof["wall_layer"]
    key = names[n] + " " + nlay[n] + " " + (mats[m] if m >= 0 else "")
    return next((l for r, l in LAYR if r.search(key)), prof["default_layer"])
def colour_of(n, m):
    """finish key: ('WALL'|palette index|'OTHER')"""
    key = (mats[m] if m >= 0 else "") + " " + names[n]
    k = next((i for i, (r, c, l) in enumerate(PALR) if r.search(key)), None)
    if k is not None: return k
    return "WALL" if is_wall(n) else "OTHER"
def rgb_of(k):
    return tuple(prof["wall_colour"]) if k == "WALL" else tuple(prof["other_colour"]) if k == "OTHER" else PALR[k][1]
def label_of(k):
    return prof["wall_label"] if k == "WALL" else "Autres éléments" if k == "OTHER" else PALR[k][2]

L = []                                                             # output primitives
def fmt(pts): return ";".join(f"{x + OX:.4f},{y + OY:.4f}" for x, y in pts)
def PL(lay, lw, rgb, pts, closed=0): L.append(f"L|{lay}|{lw}|{rgb[0]},{rgb[1]},{rgb[2]}|{closed}|{fmt(pts)}")
def HT(lay, rgb, loops): L.append(f"H|{lay}|{rgb[0]},{rgb[1]},{rgb[2]}|" + "|".join(fmt(lp) for lp in loops))
def TX(lay, x, y, h_mm, just, txt, rot=0): L.append(f"T|{lay}|{x + OX:.4f}|{y + OY:.4f}|{h_mm * MM:.4f}|{just}|{rot}|{txt}")
DIMSTYLE = view.get("dimstyle") or (prof.get("dimstyle_plan", "BAAK") if S >= 50 else prof["dimstyle"])   # Detail BAAK text is 7 cm: too small at 1/50
def DM(p1_, p2_, pd, rot): L.append(f"D|{prof['dim_layer']}|{DIMSTYLE}|{p1_[0] + OX:.4f},{p1_[1] + OY:.4f}|{p2_[0] + OX:.4f},{p2_[1] + OY:.4f}|{pd[0] + OX:.4f},{pd[1] + OY:.4f}|{rot}")

# ---------------------------------------------------------------- section (cut plane) -> poché polygons per node
T3 = V[F]; sd = T3 @ D - PD - 1e-6
cross = (sd.min(1) < 0) & (sd.max(1) > 0)
segs_by_node = {}
for i in np.nonzero(cross)[0]:
    n = int(FN[i])
    if IGN.search(names[n]): continue
    t, s_ = T3[i], sd[i]; pts = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        if (s_[a] < 0) != (s_[b] < 0):
            q = t[a] + (t[b] - t[a]) * (s_[a] / (s_[a] - s_[b]))
            pts.append((round(float(q @ U), 5), round(float(q @ Vv), 5)))
    if len(pts) == 2: segs_by_node.setdefault(n, []).append(pts)
CUT = {}                                                           # node -> polygon (frame-clipped)
for n, segs in segs_by_node.items():
    segs = [s_ for s_ in segs if s_[0] != s_[1]]
    if not segs: continue
    segs = list({tuple(sorted(s_)) for s_ in segs})               # a face seen twice (double-sided mesh) would flip the parity
    ml = shapely.node(MultiLineString(segs))
    faces = [p for p in shapely.get_parts(shapely.polygonize(shapely.get_parts(ml))) if p.area > 1e-6]
    S_ = np.array(segs, float)
    def solid(f):                                                  # even-odd rule: the hole inside a closed loop is not material
        x, y = f.representative_point().coords[0]
        y1, y2, x1, x2 = S_[:, 0, 1], S_[:, 1, 1], S_[:, 0, 0], S_[:, 1, 0]
        c = (y1 > y) != (y2 > y)
        xi = x1[c] + (y - y1[c]) * (x2[c] - x1[c]) / (y2[c] - y1[c])
        return int((xi > x).sum()) % 2 == 1
    polys = [f for f in faces if solid(f)]
    if not polys and is_struct(n):                                 # open box (missing faces): a slab or wall still reads as its hull
        hull = MultiLineString(segs).convex_hull
        if hull.geom_type == "Polygon" and hull.area > 1e-5 and min(hull.bounds[2] - hull.bounds[0], hull.bounds[3] - hull.bounds[1]) < 0.7:
            polys = [hull]
    if not polys: continue                                         # open surface (single plane): no poché, no cut line
    pg = unary_union(polys).buffer(0).intersection(FRAME)
    if not pg.is_empty and pg.area > 1e-6: CUT[n] = pg
CUT_STRUCT = unary_union([p for n, p in CUT.items() if is_struct(n)]) if CUT else Polygon()
CUT_OTHER = {n: p for n, p in CUT.items() if not is_struct(n)}
CUT_ALL = unary_union(list(CUT.values())) if CUT else Polygon()
print("cut nodes", len(CUT), "struct area", round(CUT_STRUCT.area, 3), flush=True)

# ---------------------------------------------------------------- flat finish fills from the id image
ids = np.array(Image.open(HLR + "/ids.png").convert("RGBA"))
idm = ids[:, :, 0].astype(np.int64) * 256 + ids[:, :, 1]; idm[ids[:, :, 3] < 128] = 0
pairs = meta["pairs"]; px = meta["px"]; u0, v1 = meta["u0"], meta["v1"]

# ---------------------------------------------------------------- measured levels (from the section)
info = {}
mid_u = (ua + ub) / 2
def cut_at_u(u, geom):
    ln = LineString([(u, va - 1), (u, vb + 1)]).intersection(geom)
    return [p for p in shapely.get_parts(ln) if not p.is_empty]
lv = view.get("level", {"name": "", "elev": 0.0}); E0 = float(lv.get("elev", 0.0))
if not PLAN:
    # floor: top of the struct cut at v<=0.05 under the room; ceiling: lowest non-struct cut above 1.9 m; soffit: lowest struct above 1.9 m
    ups, ceil_b, soff_b = [], [], []
    for uu in np.linspace(ua + 0.25 * (ub - ua), ub - 0.25 * (ub - ua), 9):
        for seg in cut_at_u(uu, CUT_STRUCT):
            lo, hi = seg.bounds[1], seg.bounds[3]
            if hi < 0.3: ups.append(hi)
            elif lo > 1.9: soff_b.append(lo)
        for n, pg in CUT_OTHER.items():
            for seg in cut_at_u(uu, pg):
                if seg.bounds[1] > 1.9: ceil_b.append(seg.bounds[1])
    info["floor"] = 0.0
    info["soffit"] = round(float(np.median(soff_b)), 3) if soff_b else None
    info["ceiling"] = round(float(np.median(ceil_b)), 3) if ceil_b else None
    # fallbacks from the geometry seen in the frame: slab underside, lowest false-ceiling element of real size
    tu_ = T3 @ U; tz_ = T3[:, :, 2]
    inside = (tu_.max(1) > ua) & (tu_.min(1) < ub) & ((T3 @ D).max(1) > PD)
    if info["soffit"] is None:
        zs = [tz_[(FN == n) & inside].min() for n in range(len(names)) if SLABS.search(names[n]) and ((FN == n) & inside & (tz_.min(1) > 1.9)).any()]
        zs = [z for z in zs if z > 1.9]
        info["soffit"] = round(float(min(zs)), 3) if zs else None
    if info["ceiling"] is None:
        cands = []
        vis_n = {}                                                  # nodes actually seen in the view (id image), with their pixel area
        for k_, c_ in zip(*np.unique(idm[idm > 0], return_counts=True)): vis_n[pairs[k_ - 1][0]] = vis_n.get(pairs[k_ - 1][0], 0) + c_ * px * px
        for n in range(len(names)):
            if layer_of(n, -1) != "BAAK - FAUX PLAFOND" or vis_n.get(n, 0) < 0.02: continue
            sel = (FN == n) & inside & (tz_.min(1) > 1.9)
            if not sel.any(): continue
            fp = tu_[sel]
            if min(fp.max(), ub) - max(fp.min(), ua) < 0.5 * (ub - ua): continue
            cands.append(float(tz_[sel].min()))
        info["ceiling"] = round(min(cands), 3) if cands else None
    if info["ceiling"] and info["soffit"] and info["ceiling"] > info["soffit"] - 0.005: info["ceiling"] = None
if not PLAN and view.get("slab_bands", True):
    zl = [tz_[(FN == n) & inside].min() for n in range(len(names)) if SLABS.search(names[n]) and ((FN == n) & inside & (tz_.max(1) <= 0.01)).any()]
    fb = max(-0.6, min([float(min(zl)) if zl else 0.0, -float(view.get("floor_slab", prof.get("floor_slab", 0.23)))]))
    zt = [tz_[(FN == n) & inside].max() for n in range(len(names)) if SLABS.search(names[n]) and info.get("soffit") and ((FN == n) & inside & (tz_.min(1) >= info["soffit"] - 0.01)).any()]
    bands = [box(ua, max(va, fb), ub, 0.0)]
    if info.get("soffit"): bands.append(box(ua, info["soffit"], ub, min(vb, max(zt) if zt else info["soffit"] + 0.18)))
    CUT_STRUCT = unary_union([CUT_STRUCT] + bands).intersection(FRAME)
    CUT_ALL = unary_union([CUT_ALL, CUT_STRUCT])
    info["slab_bands"] = [round(float(fb), 3), round(float(max(zt)), 3) if zt else None]
print("levels", info, flush=True)

pair_key = {0: None}
for k, (n, m) in enumerate(pairs, 1):
    pair_key[k] = None if IGN.search(names[n]) else colour_of(n, m)
keys = sorted({k for k in pair_key.values() if k is not None}, key=str)
FILLS = {}
for key in keys:
    ks = [k for k, v in pair_key.items() if v == key]
    mask = np.isin(idm, ks)
    if not mask.any(): continue
    boxes = []
    for y in np.nonzero(mask.any(1))[0]:
        dd = np.diff(np.concatenate([[0], mask[y].astype(np.int8), [0]]))
        for a_, b_ in zip(np.nonzero(dd == 1)[0], np.nonzero(dd == -1)[0]):
            boxes.append(box(u0 + a_ * px, v1 - (y + 1) * px, u0 + b_ * px, v1 - y * px))
    gg = shapely.union_all(boxes, grid_size=px / 20).simplify(px * 0.7).intersection(FRAME).difference(CUT_ALL)
    if not gg.is_empty and gg.area > (3 * px) ** 2: FILLS[key] = gg
print("fill classes", len(FILLS), flush=True)

# ---------------------------------------------------------------- lines
W_CUT_S, W_CUT_O, W_CONT, W_CONT_FAR, W_DET, W_FINE = 50, 35, 25, 18, 13, 9
INK, GREY = (30, 30, 32), (125, 125, 128)
groups = {}                                                        # (layer, lw, rgb) -> list of LineStrings
for i in range(len(KIND)):
    n, m = int(NODE[i]), int(MAT[i])
    if n >= 0 and IGN.search(names[n]): continue
    pts = P[OFF[i]:OFF[i + 1]]
    dep = pts @ D - PD
    uv = np.column_stack([pts @ U, pts @ Vv])
    keep = dep > 0.002                                             # points lying on the cut plane are the cut outline (drawn from the section)
    runs, cur = [], []
    for k_ in range(len(uv)):
        if keep[k_]: cur.append(tuple(uv[k_]))
        elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    for r in runs:
        if len(r) < 2: continue
        ls = LineString(r)
        if ls.length < 0.002: continue
        dmean = float(dep.mean())
        small = max(ls.bounds[2] - ls.bounds[0], ls.bounds[3] - ls.bounds[1]) < 0.06
        if KIND[i] == 0: lw = W_FINE if small else (W_CONT if dmean < 1.5 else W_CONT_FAR)
        else: lw = W_FINE if (small or dmean > 2.5) else W_DET
        rgb = GREY if dmean > 2.5 else INK
        groups.setdefault((layer_of(n, m), lw, rgb), []).append(ls)
# merge duplicates, weaker lines give way to stronger ones, nothing inside the poché
order = sorted(groups, key=lambda k: -k[1])
taken = CUT_ALL.buffer(-0.0015) if not CUT_ALL.is_empty else Polygon()
heavier = []
LINES = {}
for key in order:
    gl = unary_union(groups[key])
    gl = gl.intersection(FRAME)
    if not taken.is_empty: gl = gl.difference(taken)
    if heavier: gl = gl.difference(unary_union(heavier).buffer(0.0012, cap_style="flat"))
    segs_ = [p for p in shapely.get_parts(gl) if p.geom_type == "LineString" and not p.is_empty]
    if len(segs_) > 1: segs_ = list(shapely.get_parts(linemerge(MultiLineString(segs_))))
    parts = [p.simplify(0.0008) for p in segs_ if p.length > 0.003]
    if parts:
        LINES[key] = parts; heavier.append(MultiLineString(parts))

# ---------------------------------------------------------------- emit drawing: fills, poché, lines (draw order)
def loops_of(pg):
    out = []
    for p in shapely.get_parts(pg):
        if p.geom_type != "Polygon" or p.area < 1e-6: continue
        out.append([list(p.exterior.coords)] + [list(r.coords) for r in p.interiors])
    return out
for key, gg in FILLS.items():
    for lp in loops_of(gg): HT(prof["fill_layer"], rgb_of(key), lp)
TA = 0.5 * np.linalg.norm(np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0]), axis=1)
def main_mat(n):
    sel = FN == n
    return int(np.bincount(FM[sel], weights=TA[sel]).argmax())
for n, pg in CUT_OTHER.items():
    k = colour_of(n, main_mat(n))
    c = tuple(int(x * 0.72) for x in rgb_of(k))
    for lp in loops_of(pg.difference(CUT_STRUCT)): HT(prof["fill_layer"], c, lp)
for lp in loops_of(CUT_STRUCT): HT(prof["fill_layer"], (40, 40, 42), lp)
for (lay, lw, rgb), parts in LINES.items():
    for p in parts: PL(lay, lw, rgb, list(p.coords))
for pg, lay, lw in [(CUT_STRUCT, prof["wall_layer"], W_CUT_S)] + [(p, layer_of(n, -1), W_CUT_O) for n, p in CUT_OTHER.items()]:
    for lp in loops_of(pg):
        for ring in lp: PL(lay, lw, INK, ring, 1)


# ---------------------------------------------------------------- full-height / full-width divisions -> dimension chains
if not PLAN:
    top = info.get("ceiling") or info.get("soffit") or vb
    vseg, hseg = [], []
    for (lay, lw, rgb), parts in LINES.items():
        if rgb == GREY or lw < W_DET: continue
        for p in parts:
            cc = np.asarray(p.coords)
            for (xa, ya), (xb, yb) in zip(cc[:-1], cc[1:]):
                if abs(xb - xa) < 0.002 and abs(yb - ya) > 0.01: vseg.append((round((xa + xb) / 2, 2), min(ya, yb), max(ya, yb)))
                if abs(yb - ya) < 0.002 and abs(xb - xa) > 0.01: hseg.append((round((ya + yb) / 2, 2), min(xa, xb), max(xa, xb)))
    def covered(segs, lo_lim, hi_lim):
        by = {}
        for k_, a_, b_ in segs: by.setdefault(k_, []).append((max(a_, lo_lim), min(b_, hi_lim)))
        out = {}
        for k_, iv in by.items():
            iv = sorted(i for i in iv if i[1] > i[0]); tot, cur = 0.0, None
            for a_, b_ in iv:
                if cur is None or a_ > cur[1]: 
                    if cur: tot += cur[1] - cur[0]
                    cur = [a_, b_]
                else: cur[1] = max(cur[1], b_)
            if cur: tot += cur[1] - cur[0]
            out[k_] = tot
        return out
    vert = [x for x, c in covered(vseg, 0.0, top).items() if c > 0.6 * top]
    horz = [y for y, c in covered(hseg, ua, ub).items() if c > 0.45 * (ub - ua) and 0.02 < y < top - 0.02]
    # cut faces at both ends (struct or partitions) at mid-height
    ends = []
    for seg in shapely.get_parts(LineString([(ua - 1, 1.2), (ub + 1, 1.2)]).intersection(CUT_ALL)):
        if seg.is_empty: continue
        ends += [seg.bounds[0], seg.bounds[2]]
    inner_l = max([e for e in ends if e < mid_u], default=ua); inner_r = min([e for e in ends if e > mid_u], default=ub)
    def dedup(xs, tol):
        xs = sorted(xs); out = []
        for x in xs:
            if not out or x - out[-1] > tol: out.append(x)
        return out
    chain = dedup([inner_l] + [x for x in vert if inner_l + 0.03 < x < inner_r - 0.03] + [inner_r], 0.035)
    yb = va - 9 * MM
    for a_, b_ in zip(chain[:-1], chain[1:]): DM((a_, va), (b_, va), (a_, yb), 0)
    if len(chain) > 2: DM((inner_l, va), (inner_r, va), (inner_l, yb - 9 * MM), 0)
    info["chain_h"] = [round(x - inner_l, 3) for x in chain]
    if view.get("marks"):                                          # stairs / multi-level sections: chain on the levels, up to the top of the element
        top_el = max(p.bounds[3] for parts in LINES.values() for p in parts) if LINES else vb
        vch = dedup(sorted([float(z) for z, t in view["marks"] if va <= float(z) <= vb] + [min(top_el, vb)]), 0.03)
    else:
        vch = dedup([0.0] + [y for y in horz] + [x for x in (info.get("ceiling"), info.get("soffit")) if x], 0.03)
    xr = ub + 9 * MM
    for a_, b_ in zip(vch[:-1], vch[1:]): DM((ub, a_), (ub, b_), (xr, a_), 90)
    info["chain_v"] = [round(y, 3) for y in vch]

    # level marks on the left
    xl = ua - 4 * MM
    lvtxt = lambda z: f"{E0 + z:+.2f}".replace(".", ",").replace("+0,00", "±0,00")
    if view.get("marks"):                                          # explicit levels (stairs, sections through several floors)
        marks = [(float(z), t) for z, t in view["marks"]]
    else:
        marks = [(0.0, lvtxt(0.0) + " sol fini")]
        if info.get("ceiling"): marks.append((info["ceiling"], lvtxt(info["ceiling"]) + " s/f plafond"))
        if info.get("soffit"): marks.append((info["soffit"], lvtxt(info["soffit"]) + " s/f dalle"))
    for y, txt in marks:
        tri = [(xl, y), (xl - 1.4 * MM, y + 2.0 * MM), (xl + 1.4 * MM, y + 2.0 * MM), (xl, y)]
        PL(prof["level_layer"], W_DET, INK, tri, 1)
        PL(prof["level_layer"], W_FINE, INK, [(xl - 3 * MM, y), (xl + 3 * MM, y)])
        TX(prof["level_layer"], xl - 2.5 * MM, y + 3.4 * MM, 2.0, "R", txt)
    if info.get("ceiling"): info["HSP"] = info["ceiling"]
    if info.get("soffit"): info["HSD"] = info["soffit"]

# ---------------------------------------------------------------- finish callouts (one per family seen, leader to a column on the right)
fams = {}
for k in range(1, len(pairs) + 1):
    n, m = pairs[k - 1]
    if IGN.search(names[n]): continue
    key = names[n] + " " + nlay[n] + " " + mats[m]
    lab = next((l for r, l in CALR if r.search(key)), None)
    if lab: fams.setdefault(lab, []).append(k)
col_x = ub + 30 * MM
anchors = []
for lab, ks in fams.items():
    mask = np.isin(idm, ks)
    if mask.sum() * px * px < 0.03: continue
    ys, xs = np.nonzero(mask)
    # anchor = pixel nearest to the centroid of the largest blob row band
    cy, cx = np.median(ys), np.median(xs)
    j = np.argmin((ys - cy) ** 2 + (xs - cx) ** 2)
    au, av = u0 + (xs[j] + 0.5) * px, v1 - (ys[j] + 0.5) * px
    if not FRAME.contains(Point(au, av)): continue
    anchors.append((av, au, lab))
# numbered tags in a row above the view; the number is a placeholder @@label@@ that compose.py numbers across the sheet
anchors.sort(key=lambda a: a[1])
if anchors:
    tag_y = vb + 9 * MM; gap = 8 * MM
    xs_ = []
    for av, au, lab in anchors:
        x_ = max(au, xs_[-1] + gap) if xs_ else au
        xs_.append(x_)
    over = xs_[-1] - (ub - 2 * MM)
    if over > 0: xs_ = [x - over for x in xs_]
    for (av, au, lab), tx_ in zip(anchors, xs_):
        PL(prof["text_layer"], W_FINE, INK, [(au, av), (au, vb + 3 * MM), (tx_, tag_y - 2.4 * MM)])
        L.append(f"C|{prof['text_layer']}|{au + OX:.4f}|{av + OY:.4f}|{0.5 * MM:.4f}")
        L.append(f"G|{prof['text_layer']}|{tx_ + OX:.4f}|{tag_y + OY:.4f}|{2.4 * MM:.4f}|{2.2 * MM:.4f}|@@{lab}@@")
info["callouts"] = [a[2] for a in anchors]

# ---------------------------------------------------------------- title, legend
ty = va - 27 * MM
TX(prof["text_layer"], ua, ty, 5.0, "L", view.get("title", view["name"]))
PL(prof["text_layer"], W_CUT_O, INK, [(ua, ty - 7.2 * MM), (ua + max(50, 3.4 * len(view.get("title", ""))) * MM, ty - 7.2 * MM)])
TX(prof["text_layer"], ua, ty - 9 * MM, 2.6, "L", f"{view.get('sub', '')}  ·  échelle 1/{int(S)}")
info["legend"] = [[list(rgb_of(k)), label_of(k)] for k in FILLS] + ([[[40, 40, 42], "Murs, cloisons et dalles coupés"]] if not CUT_STRUCT.is_empty else [])
ly = ty - 24 * MM; lx = ua
legend = [k for k in FILLS] + (["CUT"] if not CUT_STRUCT.is_empty else []) if view.get("legend", False) else []
if legend: TX(prof["text_layer"], lx, ly, 3.2, "L", "LÉGENDE")
for i, k in enumerate(legend):
    cx_ = lx + (i % 3) * 95 * MM; cy_ = ly - 7 * MM - (i // 3) * 6 * MM
    c = (40, 40, 42) if k == "CUT" else rgb_of(k)
    sq = [(cx_, cy_ - 3.2 * MM), (cx_ + 7 * MM, cy_ - 3.2 * MM), (cx_ + 7 * MM, cy_), (cx_, cy_)]
    HT(prof["fill_layer"], c, [sq + [sq[0]]]); PL(prof["text_layer"], W_FINE, INK, sq, 1)
    TX(prof["text_layer"], cx_ + 9 * MM, cy_, 2.2, "L", "Murs, cloisons et dalles coupés" if k == "CUT" else label_of(k))

# extents
allx, ally = [], []
for ln in L:
    f_ = ln.split("|")
    for fld in f_[1:]:
        if re.match(r"^-?\d+\.\d+,-?\d+\.\d+(;|$)", fld):
            for pt in fld.split(";"):
                x, y = pt.split(","); allx.append(float(x)); ally.append(float(y))
    if f_[0] in ("T", "G", "C"): allx.append(float(f_[2])); ally.append(float(f_[3]))
    if f_[0] == "T" and f_[5] == "R": allx.append(float(f_[2]) - 0.55 * float(f_[4]) * len(f_[7]))
ext = (min(allx) - 4 * MM, min(ally) - 4 * MM, max(allx) + 8 * MM, max(ally) + 6 * MM)
L.append("E|%.4f,%.4f,%.4f,%.4f" % ext)
open(OUT + "/prims.txt", "w", encoding="utf-8").write("\n".join(L) + "\n")
info.update(lines=sum(len(v) for v in LINES.values()), fills=len(FILLS), cut=len(CUT), extents=ext, scale=S)
json.dump(info, open(OUT + "/draft.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- preview (raster, for a quick look before AutoCAD)
R = 4.0 / MM / 1000 * 1000                                           # 4 px per paper mm
W_ = int((ext[2] - ext[0]) * R / 1); H_ = int((ext[3] - ext[1]) * R / 1)
sc_ = min(1.0, 7000 / max(W_, H_)); R *= sc_; W_ = int(W_ * sc_); H_ = int(H_ * sc_)
im = Image.new("RGB", (W_, H_), "white"); dr = ImageDraw.Draw(im)
T_ = lambda x, y: ((x - ext[0]) * R, (ext[3] - y) * R)
for ln in L:
    f_ = ln.split("|")
    if f_[0] == "H":
        c = tuple(int(v) for v in f_[2].split(","))
        mk = Image.new("L", (W_, H_), 0); md = ImageDraw.Draw(mk)
        for k_, lp in enumerate(f_[3:]):
            pts = [T_(*map(float, p.split(","))) for p in lp.split(";")]
            if len(pts) > 2: md.polygon(pts, fill=255 if k_ == 0 else 0)
        im.paste(c, mask=mk)
for ln in L:
    f_ = ln.split("|")
    if f_[0] == "L":
        c = tuple(int(v) for v in f_[3].split(",")); w = max(1, int(round(int(f_[2]) / 100 * 4 * sc_)))
        pts = [T_(*map(float, p.split(","))) for p in f_[5].split(";")]
        if f_[4] == "1": pts.append(pts[0])
        dr.line(pts, fill=c, width=w)
    elif f_[0] == "D":
        a_, b_, d_ = [tuple(map(float, p.split(","))) for p in f_[3:6]]
        if f_[6] == "0": dr.line([T_(a_[0], d_[1]), T_(b_[0], d_[1])], fill=(220, 60, 30), width=1); dr.text(T_((a_[0] + b_[0]) / 2, d_[1] + 3 * MM), f"{abs(b_[0] - a_[0]) * 100:.0f}", fill=(220, 60, 30))
        else: dr.line([T_(d_[0], a_[1]), T_(d_[0], b_[1])], fill=(220, 60, 30), width=1); dr.text(T_(d_[0] + 1 * MM, (a_[1] + b_[1]) / 2), f"{abs(b_[1] - a_[1]) * 100:.0f}", fill=(220, 60, 30))
    elif f_[0] == "T":
        dr.text(T_(float(f_[2]), float(f_[3])), f_[7], fill=(0, 0, 0))
    elif f_[0] in ("G", "C"):
        cx_, cy_ = T_(float(f_[2]), float(f_[3])); r_ = float(f_[4]) * R
        dr.ellipse([cx_ - r_, cy_ - r_, cx_ + r_, cy_ + r_], outline=(0, 0, 0), fill=(0, 0, 0) if f_[0] == "C" else None)
im.save(OUT + "/preview.png")
print("prims", len(L), "preview", im.size, flush=True)
