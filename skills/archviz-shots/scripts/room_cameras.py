"""room_cameras.py (skill archviz-shots): archviz cameras for each room, tested against the real geometry WITHOUT 3ds Max.
It reads the .vrscene that is exported for Vantage anyway, turns every surface into a cloud of points and looks through each candidate
camera, so no view starts in a wall, shows the back of a wall or looks mostly out of the room. The best ones are kept.

usage: room_cameras.py scene.vrscene rooms.json out_dir [tag]
rooms.json: {"mode": "general" | "types", "region": [[xmin, ymin, zmin], [xmax, ymax, zmax]] (optional, the part of the scene to read),
             "rooms": [{"name": "SDC", "seed": [-457, -1545], "floor": 550.8, "ceiling": 845, "views": 4}, ...]}
  a room is given by "seed" (any free point of its floor: the walls round it are found by themselves) or by "min" / "max" corners (cm);
  "views" = how many cameras for that room (general mode); "ceiling_feature": true and "points": {"NAME": [x, y, z]} serve the types mode.

mode "general" = views of the whole room, the user's rule of 11/11/2026: FRONTALE (one-point, on an axis) and OBLIQUE (45 degrees from a
  corner), 28 to 40 mm so nothing is stretched, the camera pulled back OUTSIDE the room and the near wall removed by camera clipping.
  The clipping distance is set so that the frame at the cut is exactly the room's height (floor and ceiling both in frame, nothing of the
  floors above or below), the camera is level at mid-height.
mode "types" = cameras inside the room, no clipping: LARGE corner view 24-28 mm | AXE one-point | BAS low hero 0.62 m | HAUT elevated |
  TELE 70 mm | CINE 2.39:1 | VERTICAL 4:5 | PLAFOND looking up at a feature ceiling | DETAIL_<point> 85 mm.

writes out_dir/cams_<tag>.txt   name|px|py|pz|tx|ty|tz|hfov|focal|type|score|width|height|clip   (clip 0 = none; feeds cams_to_vantage.py)
       out_dir/CAMS_<tag>_n.jpg  what each kept camera sees (shaded depth), to check every framing before any render."""
import base64
import json
import math
import os
import re
import sys
import time
import zlib

import numpy as np
from PIL import Image, ImageDraw

SRC, CFG, OUT = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8")), sys.argv[3]
TAG = sys.argv[4] if len(sys.argv) > 4 else "X"
ROOMS, MODE = CFG["rooms"], CFG.get("mode", "general")
os.makedirs(OUT, exist_ok=True)
t0 = time.time()
data = open(SRC, "rb").read()
blocks = {}
for m in re.finditer(rb"\n(\w+) ([^\r\n]*?) \{\r?\n", data):
    blocks[m.group(2)] = (m.group(1), m.end())


def body(name):
    b = blocks.get(name)
    return (None, None) if b is None else (b[0], data[b[1]:data.find(b"\n}", b[1])])


def unpack(txt, dtype):
    if txt[:4] in (b"ZIPC", b"ZIPB"):
        raw = txt[20:]
        comp = base64.b64decode(raw + b"=" * (-len(raw) % 4)) if txt[:4] == b"ZIPC" else bytes.fromhex(raw.decode())
        return np.frombuffer(zlib.decompress(comp), dtype=dtype)
    return np.frombuffer(bytes.fromhex(txt.decode()), dtype=dtype)


mesh_cache = {}


def mesh(name, depth=0):
    if name in mesh_cache:
        return mesh_cache[name]
    typ, b = body(name)
    res = None
    if b is not None:
        if typ == b"GeomStaticMesh":
            mv = re.search(rb'vertices=ListVectorHex\("([^"]*)"\)', b)
            mf = re.search(rb'faces=ListIntHex\("([^"]*)"\)', b)
            if mv and mf:
                res = (unpack(mv.group(1), "<f4").reshape(-1, 3), unpack(mf.group(1), "<i4").reshape(-1, 3))
        elif depth < 3:
            mm = re.search(rb"\n\s*mesh=([^;\s]+);", b)
            if mm:
                res = mesh(mm.group(1), depth + 1)
    mesh_cache[name] = res
    return res


GLASS = re.compile(rb"glass|verre|vitr", re.I)
nodes = []
for name, (typ, s) in blocks.items():
    if typ != b"Node":
        continue
    b = data[s:data.find(b"\n}", s)]
    mg = re.search(rb"geometry=([^;\r\n]+);", b)
    mh = re.search(rb'transform=TransformHex\("([0-9A-Fa-f]+)"\)', b)
    if not mg or not mh or re.search(rb"\n\s*visible=0;", b):
        continue
    mm = re.search(rb"material=([^;\r\n]+);", b)
    raw = bytes.fromhex(mh.group(1).decode())  # 9 float32, 4 bytes of padding, 3 float64
    M = np.frombuffer(raw[:36], dtype="<f4").reshape(3, 3).T.astype(np.float32)
    nodes.append((M, np.frombuffer(raw[40:64], dtype="<f8").astype(np.float32), mg.group(1), bool(GLASS.search(name) or (mm and GLASS.search(mm.group(1))))))
print("scene read:", len(nodes), "objects,", round(time.time() - t0, 1), "s", flush=True)
STEP = 12.0  # one point per 12 x 12 cm of surface
rng = np.random.default_rng(7)
LIGHT = np.array([0.35, 0.25, 0.9], dtype=np.float32)
LIGHT /= np.linalg.norm(LIGHT)


def cloud(lo, hi):
    """points on every surface inside the box lo..hi, a shade for the preview, and whether the point is on glass"""
    P, S, G = [], [], []
    for M, T, g, glass in nodes:
        mv = mesh(g)
        if mv is None or len(mv[1]) == 0:
            continue
        W = mv[0] @ M.T + T
        if (W.max(0) < lo).any() or (W.min(0) > hi).any():
            continue
        tri = W[mv[1]]
        tri = tri[~((tri.max(1) < lo).any(1) | (tri.min(1) > hi).any(1))]
        if not len(tri):
            continue
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        area = np.linalg.norm(nrm, axis=1) / 2
        want = area / (STEP * STEP)
        n = np.minimum(np.floor(want).astype(np.int64) + (rng.random(len(tri)) < (want - np.floor(want))), 20000)
        idx = np.repeat(np.arange(len(tri)), n)
        if not len(idx):
            continue
        u, v = rng.random(len(idx), dtype=np.float32), rng.random(len(idx), dtype=np.float32)
        f = u + v > 1
        u[f], v[f] = 1 - u[f], 1 - v[f]
        p = tri[idx, 0] + (tri[idx, 1] - tri[idx, 0]) * u[:, None] + (tri[idx, 2] - tri[idx, 0]) * v[:, None]
        ok = ((p >= lo) & (p <= hi)).all(1)
        P.append(p[ok].astype(np.float32))
        S.append((np.abs(nrm[idx] @ LIGHT) / np.maximum(area[idx] * 2, 1e-6))[ok].astype(np.float32))
        G.append(np.full(int(ok.sum()), glass))
    return np.concatenate(P), np.concatenate(S), np.concatenate(G)


def box_from_seed(P, seed, zf):
    """the free rectangle round a point of the floor: on each side, the median first surface met by seven parallel lines (glass counts as a wall)"""
    Q = P[(P[:, 2] > zf + 150) & (P[:, 2] < zf + 200)][:, :2]
    ext = {"x0": 120.0, "x1": 120.0, "y0": 120.0, "y1": 120.0}
    for _ in range(3):
        new = {}
        for key, ax, sg in (("x1", 0, 1), ("x0", 0, -1), ("y1", 1, 1), ("y0", 1, -1)):
            lo, hi = (-ext["y0"], ext["y1"]) if ax == 0 else (-ext["x0"], ext["x1"])
            a, b = (Q[:, ax] - seed[ax]) * sg, Q[:, 1 - ax] - seed[1 - ax]
            hits = []
            for o in np.linspace(lo * 0.7, hi * 0.7, 7):
                sel = (np.abs(b - o) < 7) & (a > 15)
                hits.append(float(a[sel].min()) if sel.any() else 3000.0)
            new[key] = float(np.median(hits))
        ext = new
    return [seed[0] - ext["x0"], seed[1] - ext["y0"]], [seed[0] + ext["x1"], seed[1] + ext["y1"]]


def look(P, S, eye, tgt, hfov, asp, gw=48, clip=0.0):
    """depth and shade seen by a camera on a small grid; near points are painted larger so that a thin near object still blocks"""
    gh = max(4, int(round(gw / asp / 4)) * 4)
    fw = (tgt - eye) / np.linalg.norm(tgt - eye)
    rt = np.cross(fw, [0, 0, 1.0])
    rt /= np.linalg.norm(rt)
    up = np.cross(rt, fw)
    q = P - eye.astype(np.float32)
    z = q @ fw.astype(np.float32)
    tx = math.tan(math.radians(hfov) / 2)
    ty = tx / asp
    front = z > max(4.0, clip)
    q, z, s = q[front], z[front], S[front]
    u, v = (q @ rt.astype(np.float32)) / (z * tx), (q @ up.astype(np.float32)) / (z * ty)
    inside = (np.abs(u) < 1) & (np.abs(v) < 1)
    u, v, z, s, q = u[inside], v[inside], z[inside], s[inside], q[inside]
    dist = np.linalg.norm(q, axis=1)
    lvl = np.clip(np.floor(np.log2(np.maximum((STEP / z) / (2 * tx / gw), 1e-6))), 0, 4).astype(np.int64)
    D = np.full((gh, gw), np.inf, dtype=np.float32)
    C = np.zeros((gh, gw), dtype=np.float32)
    for L in range(5):
        m = lvl == L
        if not m.any():
            continue
        w, h = max(gw >> L, 1), max(gh >> L, 1)
        px = np.minimum(((u[m] + 1) / 2 * w).astype(np.int64), w - 1)
        py = np.minimum(((1 - v[m]) / 2 * h).astype(np.int64), h - 1)
        o = np.argsort(-dist[m])
        d = np.full((h, w), np.inf, dtype=np.float32)
        c = np.zeros((h, w), dtype=np.float32)
        d[py[o], px[o]] = dist[m][o]
        c[py[o], px[o]] = s[m][o]
        d = np.kron(d, np.ones((-(-gh // h), gw // w), dtype=np.float32))[:gh, :gw]
        c = np.kron(c, np.ones((-(-gh // h), gw // w), dtype=np.float32))[:gh, :gw]
        nearer = d < D
        D[nearer], C[nearer] = d[nearer], c[nearer]
    return D, C, (fw, rt, up, tx, ty)


def frame_stats(D, basis, eye, room):
    fw, rt, up, tx, ty = basis
    gh, gw = D.shape
    jj, ii = np.mgrid[0:gh, 0:gw]
    d = fw + rt[None, None] * (((ii + 0.5) / gw * 2 - 1) * tx)[..., None] + up[None, None] * ((1 - (jj + 0.5) / gh * 2) * ty)[..., None]
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    hit = eye + d * np.where(np.isfinite(D), D, 0)[..., None]
    x0, y0, x1, y1 = room["min"][0], room["min"][1], room["max"][0], room["max"][1]
    ins = np.isfinite(D) & (hit[..., 0] > x0 - 30) & (hit[..., 0] < x1 + 30) & (hit[..., 1] > y0 - 30) & (hit[..., 1] < y1 + 30) & (hit[..., 2] > room["floor"] - 30) & (hit[..., 2] < room["ceiling"] + 60)
    Df = np.where(np.isfinite(D), D, 4000.0)
    diag = math.hypot(x1 - x0, y1 - y0)
    return dict(share=float(ins.mean()), empty=float((~np.isfinite(D)).mean()), near=float((Df < 130).mean()), nearest=float(Df.min()),
                centre=float(np.median(Df[gh // 2 - 1:gh // 2 + 1, gw // 2 - 1:gw // 2 + 1])), median=float(np.median(Df)),
                layers=float(min(np.std(np.log(np.clip(Df, 50, max(diag, 60)))), 1.0)), diag=diag)


def hf(f):
    return math.degrees(2 * math.atan(18.0 / f))


def cut_count(Q, eye, d, c, th, tv):
    """how much is SLICED by the clipping plane inside the frame: points lying on the plane (within 5 cm) and seen by the camera. 0 = an invisible cut."""
    q = Q - eye.astype(np.float32)
    z = q @ d.astype(np.float32)
    m = np.abs(z - c) < 5.0
    if not m.any():
        return 0
    rt = np.cross(d, [0, 0, 1.0])
    rt /= np.linalg.norm(rt)
    up = np.cross(rt, d)
    u, v = (q[m] @ rt.astype(np.float32)) / (c * th), (q[m] @ up.astype(np.float32)) / (c * tv)
    return int(((np.abs(u) < 1.0) & (np.abs(v) < 1.0)).sum())


def clean_window(Q, p0, d):
    """the largest rectangle of the vertical plane through p0 (normal d) that NO surface crosses, round the axis: (lateral min, max, vertical min, max)
    in cm from p0, or None when something stands on the axis there. Floor, ceiling, walls, lockers, benches, lamps all stop it by themselves, so a frame
    set on this rectangle shows no section of anything: what the clipping removes is only what stands wholly in front of the plane."""
    q = Q - p0.astype(np.float32)
    m = np.abs(q @ d.astype(np.float32)) < 5.0
    side = np.array([-d[1], d[0], 0.0], dtype=np.float32)
    a, b = q[m] @ side, q[m][:, 2]
    CELL, NX, NY = 8.0, 220, 64
    ix, iy = np.floor(a / CELL).astype(np.int64) + NX // 2, np.floor(b / CELL).astype(np.int64) + NY // 2
    ok = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
    occ = np.zeros((NY, NX), dtype=bool)
    occ[iy[ok], ix[ok]] = True
    cxi, cyi = NX // 2, NY // 2
    if occ[cyi - 2:cyi + 2, cxi - 2:cxi + 2].any():
        return None
    band = occ[:, cxi - 3:cxi + 3].any(1)
    lo, hi = cyi - 1, cyi
    while lo > 0 and not band[lo - 1]:
        lo -= 1
    while hi < NY - 1 and not band[hi + 1]:
        hi += 1
    if lo == 0 or hi == NY - 1:
        return None  # no floor or no ceiling met: this plane is not inside a room
    best = None
    for cb in (0.0, 0.1, 0.2, 0.3):  # a window that starts a little above the floor or below the ceiling may be much wider
        for ct in (0.0, 0.1, 0.2):
            r0, r1 = lo + int(round((hi - lo) * cb)), hi - int(round((hi - lo) * ct))
            cols = occ[r0:r1 + 1].any(0)
            le, ri = cxi - 1, cxi
            while le > 0 and not cols[le - 1]:
                le -= 1
            while ri < NX - 1 and not cols[ri + 1]:
                ri += 1
            if le == 0 or ri == NX - 1:
                continue  # open to the side: no wall met
            w, h = (ri - le + 1) * CELL - 8.0, (r1 - r0 + 1) * CELL - 8.0
            if best is None or w * h > best[0]:
                best = (w * h, (le - NX // 2) * CELL + 4.0, (ri + 1 - NX // 2) * CELL - 4.0, (r0 - NY // 2) * CELL + 4.0, (r1 + 1 - NY // 2) * CELL - 4.0)
    return None if best is None else best[1:]


def size_for(asp):
    w = min(2880, int(round(math.sqrt(3.84e6 * asp) / 16)) * 16)
    return w, int(round(w / asp / 16)) * 16


def general(R, P, S, Q):
    """FRONTALE and OBLIQUE views of the whole room (the user's rules of 11/11/2026): camera outside the room, the near wall removed by camera
    clipping, 25 to 45 mm so nothing is stretched, and A CLEAR FRAME: the frame is set exactly on a rectangle of the cutting plane that nothing
    crosses, so no wall, floor, ceiling, locker or piece of furniture shows a section. Ratio and resolution follow that rectangle."""
    x0, y0, x1, y1, zf, zc = R["min"][0], R["min"][1], R["max"][0], R["max"][1], R["floor"], R["ceiling"]
    cx, cy, dx, dy = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    zm = zf + min((zc - zf) / 2, 165.0)

    def make(typ, p_axis, d, depth_left, val):
        win = clean_window(Q, p_axis, d)
        if win is None:
            return None
        a0, a1, b0, b1 = win
        w, h = a1 - a0, b1 - b0
        if w < 90 or h < 130:
            return None
        if w / h > 2.4:
            a0, a1 = (a0 + a1) / 2 - 1.2 * h, (a0 + a1) / 2 + 1.2 * h
        if w / h < 0.62:
            b0, b1 = (b0 + b1) / 2 - w / 1.24, (b0 + b1) / 2 + w / 1.24
        w, h = a1 - a0, b1 - b0
        side = np.array([-d[1], d[0], 0.0])
        centre = p_axis + side * ((a0 + a1) / 2) + np.array([0, 0, (b0 + b1) / 2])
        th = float(np.clip((w / 2) / max(0.667 * depth_left, 1.0), 18 / 45, 18 / 25))  # far wall about 40 % of the frame; lens kept between 25 and 45 mm
        c = (w / 2) / th
        eye = centre - d * c
        return [typ, eye, eye + d * (c + max(depth_left, 100.0)), 18 / th, w / h, c, val(w, h)]

    cands = []
    for ax, sg in ((0, 1), (0, -1), (1, 1), (1, -1)):  # one-point views along x or y, both ways
        length, width = (dx, dy) if ax == 0 else (dy, dx)
        if width > 4 * length:
            continue  # across a corridor there is only a wall to see
        d = np.array([sg if ax == 0 else 0, sg if ax == 1 else 0, 0.0])
        wall = np.array([x0 if sg > 0 else x1, cy, zm]) if ax == 0 else np.array([cx, y0 if sg > 0 else y1, zm])
        best = None
        for s in (6, 15, 30, 50, 75, 100, 130, 170, 210):  # the cut moves into the room until the clear rectangle is large
            if s > max(0.35 * length, 20):
                break
            k = make("FRONTALE", wall + d * s, d, length - s, lambda w, h, s=s: w * h / (width * (zc - zf)) - 0.3 * s / length)
            if k and (best is None or k[6] > best[6]):
                best = k
        if best:
            cands.append(best)
    for sx in (-1, 1):  # 45 degree views from each corner
        for sy in (-1, 1):
            d = np.array([-sx, -sy, 0.0]) / math.sqrt(2)
            corner = np.array([cx + sx * dx / 2, cy + sy * dy / 2, zm])
            best = None
            for s in range(110, int(0.75 * min(dx, dy)) + 1, 25):
                k = make("OBLIQUE", corner + d * s, d, 1.25 * min(dx, dy) - s, lambda w, h, s=s: min(w / h, 1.8) - 0.5 * s / min(dx, dy) if w / h >= 1.25 else -9)
                if k and k[6] > -9 and (best is None or k[6] > best[6]):
                    best = k
            if best:
                cands.append(best)
    J = []
    for typ, eye, tgt, f, asp, c, val in cands:
        D, _, basis = look(P, S, eye, tgt, hf(f), asp, clip=c)
        st = frame_stats(D, basis, eye, R)
        d = (tgt - eye) / np.linalg.norm(tgt - eye)
        st["cut"] = cut_count(Q, eye, d, c, 18 / f, 18 / f / asp)
        st["score"] = st["share"] - 0.5 * st["empty"] + 0.15 * st["layers"] + 0.2 * min(val, 1.0)
        J.append((typ, st, eye, tgt, f, asp, c))
    n = int(R.get("views", 2))
    nob = min(n // 2, sum(1 for j in J if j[0] == "OBLIQUE"))
    want = {"FRONTALE": n - nob, "OBLIQUE": nob}
    J.sort(key=lambda j: -j[1]["score"])
    keep = []
    for spread in (0.5, 2.0):  # first different directions, then whatever is left
        for j in J:
            if any(j is k for k in keep) or sum(1 for k in keep if k[0] == j[0]) >= want[j[0]]:
                continue
            dj = (j[3] - j[2]) / np.linalg.norm(j[3] - j[2])
            if all(k[0] != j[0] or float(dj @ ((k[3] - k[2]) / np.linalg.norm(k[3] - k[2]))) < spread for k in keep):
                keep.append(j)
    return keep, {}


def types(R, P, S, Q=None):
    """cameras inside the room, by type of angle, no clipping"""
    x0, y0, x1, y1, zf, zc = R["min"][0], R["min"][1], R["max"][0], R["max"][1], R["floor"], R["ceiling"]
    cx, cy, dx, dy = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    ze, ins, C = zf + 140.0, 75.0, []
    for sx in (-1, 1):
        for sy in (-1, 1):
            e, t = (cx + sx * (dx / 2 - ins), cy + sy * (dy / 2 - ins)), (cx - sx * dx * 0.2, cy - sy * dy * 0.2)
            C.append(("LARGE", (*e, ze), (*t, ze), 24 if min(dx, dy) < 520 else 28, 1.5, 250, 1e9))
            C.append(("BAS", (*e, zf + 62), (*t, zf + 62), 24, 1.5, 250, 1e9))
            C.append(("HAUT", (*e, min(zc - 30, zf + 215)), (cx, cy, zf + 90), 24, 1.5, 250, 1e9))
            C.append(("CINE", (*e, zf + 120), (*t, zf + 120), 35, 2.39, 250, 1e9))
            if R.get("ceiling_feature"):
                C.append(("PLAFOND", (*e, zf + 110), (cx - sx * dx * 0.05, cy - sy * dy * 0.05, zc), 35, 1.5, 150, 1e9))
    for s in (-1, 1):
        ax = ((cx - s * (dx / 2 - ins), cy), (cx + s * dx / 2, cy), 28 if dx >= dy else 24)
        ay = ((cx, cy - s * (dy / 2 - ins)), (cx, cy + s * dy / 2), 28 if dy > dx else 24)
        for a in (ax, ay):
            C.append(("AXE", (*a[0], ze), (*a[1], ze), a[2], 1.5, 300, 1e9))
            C.append(("VERTICAL", (*a[0], ze), (*a[1], ze), 28, 0.8, 300, 1e9))
            C.append(("BAS", (*a[0], zf + 62), (*a[1], zf + 62), 24, 1.5, 300, 1e9))
        for q in (-1, 1):
            if dx >= dy:
                C.append(("TELE", (cx - s * (dx / 2 - ins), cy + q * dy / 4, ze), (cx + s * dx / 2, cy - q * dy / 8, ze), 70, 1.5, 400, 1e9))
            else:
                C.append(("TELE", (cx + q * dx / 4, cy - s * (dy / 2 - ins), ze), (cx - q * dx / 8, cy + s * dy / 2, ze), 70, 1.5, 400, 1e9))
    for pn, pp in R.get("points", {}).items():
        for a in range(0, 360, 45):
            C.append(("DETAIL_" + pn, (pp[0] + 190 * math.cos(math.radians(a)), pp[1] + 190 * math.sin(math.radians(a)), pp[2]), tuple(pp), 85, 1.5, 120, 260))
    J, refused = [], {}
    for typ, e, t, f, asp, need, far in C:
        e, t = np.array(e, dtype=np.float64), np.array(t, dtype=np.float64)
        fw = np.array([t[0] - e[0], t[1] - e[1], 0.0])
        fw /= np.linalg.norm(fw)
        rt = np.array([fw[1], -fw[0], 0.0])
        shifts = [(0, 0), (0, 45), (0, 90), (0, 150)] if typ in ("AXE", "VERTICAL") else [(0, 0), (45, 0), (-45, 0), (0, 45), (90, 0), (-90, 0), (0, 90), (60, 60), (-60, 60)]
        best = None
        for a, b in shifts:
            pe = e + rt * a + fw * b
            if not (x0 + 35 < pe[0] < x1 - 35 and y0 + 35 < pe[1] < y1 - 35):
                continue
            if np.min(np.linalg.norm(P - pe.astype(np.float32), axis=1)) < 40.0:
                why = "no room for the camera"
            else:
                D, _, basis = look(P, S, pe, t, hf(f), asp)
                st = frame_stats(D, basis, pe, R)
                why = ("object against the lens" if st["nearest"] < 55 else "foreground too close" if st["near"] > 0.11 else "looks out of the room" if st["share"] < 0.55
                       else "centre blocked" if st["centre"] < need else "point hidden" if st["centre"] > far else "")
            if why:
                refused[why] = refused.get(why, 0) + 1
                continue
            st["score"] = min(st["median"], st["diag"]) / st["diag"] + 0.6 * st["share"] + 0.15 * st["layers"] - 1.4 * st["near"]
            if best is None or st["score"] > best[1]["score"]:
                best = (pe, st)
        if best:
            J.append((typ, best[1], best[0], t, f, asp, 0.0))
    J.sort(key=lambda j: -j[1]["score"])
    keep = []
    for j in J:
        cnt, dup = 0, False
        dj = (j[3] - j[2]) / np.linalg.norm(j[3] - j[2])
        for k in keep:
            same = float(dj @ ((k[3] - k[2]) / np.linalg.norm(k[3] - k[2]))) > 0.75
            gap = float(np.linalg.norm(k[2] - j[2]))
            cnt += k[0] == j[0]
            dup = dup or (gap < (220 if k[0] == j[0] else 60) and same)
        if cnt < {"LARGE": 2, "AXE": 2}.get(j[0], 1) and not dup:
            keep.append(j)
    return keep, refused


lo = np.array(CFG["region"][0] if "region" in CFG else [min(r.get("seed", r.get("min"))[0] for r in ROOMS) - 1500, min(r.get("seed", r.get("min"))[1] for r in ROOMS) - 1500, min(r["floor"] for r in ROOMS) - 15], dtype=np.float32)
hi = np.array(CFG["region"][1] if "region" in CFG else [max(r.get("seed", r.get("max"))[0] for r in ROOMS) + 1500, max(r.get("seed", r.get("max"))[1] for r in ROOMS) + 1500, max(r["ceiling"] for r in ROOMS) + 60], dtype=np.float32)
PA, SA, GA = cloud(lo, hi)
print("cloud:", len(PA), "points,", round(time.time() - t0, 1), "s", flush=True)
lines, tiles = [], []
for R in ROOMS:
    if "min" not in R:
        R["min"], R["max"] = box_from_seed(PA, R["seed"], R["floor"])
    x0, y0, x1, y1 = R["min"][0], R["min"][1], R["max"][0], R["max"][1]
    m = (PA[:, 0] > x0 - 700) & (PA[:, 0] < x1 + 700) & (PA[:, 1] > y0 - 700) & (PA[:, 1] < y1 + 700) & (PA[:, 2] > R["floor"] - 15) & (PA[:, 2] < R["ceiling"] + 60) & ~GA
    P, S = PA[m], SA[m]
    Q = PA[(PA[:, 0] > x0 - 700) & (PA[:, 0] < x1 + 700) & (PA[:, 1] > y0 - 700) & (PA[:, 1] < y1 + 700) & (PA[:, 2] > R["floor"] - 40) & (PA[:, 2] < R["ceiling"] + 120)]  # glass included: a cut must not slice a glazed partition either
    keep, refused = (general if MODE == "general" else types)(R, P, S, Q)
    print("%s: room %d..%d x %d..%d (%.1f x %.1f m), %d points, %d kept %s" % (R["name"], x0, x1, y0, y1, (x1 - x0) / 100, (y1 - y0) / 100, len(P), len(keep), refused or ""), flush=True)
    seen = {}
    for typ, st, e, t, f, asp, c in keep:
        seen[typ] = seen.get(typ, 0) + 1
        nm = "%s_%s_%d" % (R["name"], typ, seen[typ])
        w, h = size_for(asp) if c else (2400, 1004) if asp > 2 else (1600, 2000) if asp < 1 else (2400, 1600)
        lines.append("%s|%.1f|%.1f|%.1f|%.1f|%.1f|%.1f|%.3f|%.1f|%s|%.3f|%d|%d|%.1f" % (nm, *e, *t, hf(f), f, typ, st["score"], w, h, c))
        print("  %-24s %2d mm %4d x %4d | %3d %% of the frame in the room, %2d %% empty, clip %d cm, %s, score %.2f" % (
            nm, f, w, h, st["share"] * 100, st["empty"] * 100, c, "" if not c else "cut invisible" if st.get("cut", 0) <= 2 else "CUT SHOWS (%d points sliced in view)" % st["cut"], st["score"]), flush=True)
        D, Cc, _ = look(P, S, e, t, hf(f), asp, gw=192, clip=c)
        fog = np.clip(1.25 - np.where(np.isfinite(D), D, 1e9) / (1.3 * max(st["diag"], 300)), 0.12, 1.0)
        img = Image.fromarray((np.where(np.isfinite(D), (0.25 + 0.75 * Cc) * fog, 0.02) * 255).astype(np.uint8)).resize((480, int(480 * D.shape[0] / D.shape[1])), Image.BILINEAR).convert("RGB")
        ImageDraw.Draw(img).text((6, 4), "%s  %d mm" % (nm, f), fill=(238, 90, 30))
        tiles.append(img)
for n0 in range(0, len(tiles), 12):
    part = tiles[n0:n0 + 12]
    rows = [part[i:i + 3] for i in range(0, len(part), 3)]
    sheet = Image.new("RGB", (3 * 486, sum(max(t.height for t in r) + 6 for r in rows)), "white")
    y = 0
    for r in rows:
        for i, t in enumerate(r):
            sheet.paste(t, (i * 486, y))
        y += max(t.height for t in r) + 6
    sheet.save(os.path.join(OUT, "CAMS_%s_%d.jpg" % (TAG, n0 // 12 + 1)), quality=88)
open(os.path.join(OUT, "cams_%s.txt" % TAG), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(len(lines), "cameras ->", os.path.join(OUT, "cams_%s.txt" % TAG), "| total", round(time.time() - t0, 1), "s")
# the rooms as found (seed rooms get their walls here), for other tools such as fill_lights.py
json.dump([dict(name=r["name"], min=[float(v) for v in r["min"]], max=[float(v) for v in r["max"]], floor=r["floor"], ceiling=r["ceiling"]) for r in ROOMS],
          open(os.path.join(OUT, "rooms_%s.json" % TAG), "w", encoding="utf-8"), indent=1)
