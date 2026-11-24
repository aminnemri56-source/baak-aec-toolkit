"""Cut the geometry of one view out of a V-Ray scene export (.vrscene, the Vantage export of the 3ds Max scene), without opening Max.

usage: python -I extract_vrscene.py scene.vrscene view.json out.npz

view.json (see SKILL.md): cut line p0 -> p1 in drawing metres, look direction, depth, z range, project transform.
Writes out.npz:
  V float32 (n,3)   vertices in drawing metres: x, y = plan coordinates of the DWG sheet, z = metres above the level's finished floor
  F int32  (m,3)    triangles (indices into V)
  FN int32 (m,)     node index of each triangle
  FM int32 (m,)     material index of each triangle (per-face MtlMulti ids resolved)
  names, layers, mats (json strings)   node names, node layers, material names
Triangles are kept when they touch the view volume (slab from 0.15 m in front of the cut plane to `depth` behind it,
cut-line extent + margin, z range + margin); triangles straddling the cut plane are kept whole (the hidden-line pass clips them)."""
import base64, json, re, sys, time, zlib
import numpy as np

SRC, VIEWJ, OUT = sys.argv[1:4]
t0 = time.time()
view = json.load(open(VIEWJ, encoding="utf-8"))
xf = view["xf"]                                   # {"ox": cm, "oy": cm, "unit": 0.01, "z0": cm of the level floor}
p0, p1 = np.array(view["p0"], float), np.array(view["p1"], float)
look = np.array(view["look"], float)
DEPTH = float(view.get("depth", 6.0)); Z0, Z1 = view.get("z", [-0.6, 4.0])
MARGIN = float(view.get("margin", 0.6))
EXCL_LAY = re.compile(view.get("exclude_layers", r"\(cache\)|^Ceiling_Vent|^REF50_"), re.I)
INCL = re.compile(view["include"], re.I) if view.get("include") else None   # element filter: regex on "layer name" (one element at a time)
EXCL_NM = re.compile(view.get("exclude_names", r"^(Camera|VRayLight|Light|Target|Sky|Sun|Dummy|Point)"), re.I)
if view.get("profile"):                                   # junk / helper objects listed in the project profile
    _ig = json.load(open(view["profile"], encoding="utf-8")).get("ignore")
    if _ig: EXCL_NM = re.compile("(" + EXCL_NM.pattern + ")|(" + _ig + ")", re.I)
BOX = view.get("box")                                     # [x0, y0, x1, y1]: keep everything in this plan box (one extraction for all the walls of a room)

# ---- view frame: D looked direction (horizontal for elevations/sections, down for plans), U viewer's right, cut plane through p0
if view.get("kind") == "plan":
    D = np.array([0, 0, -1.0]); U = np.array([1.0, 0, 0]); Vv = np.array([0, 1.0, 0])
else:
    D = np.array([look[0], look[1], 0.0]); D /= np.linalg.norm(D)
    Vv = np.array([0, 0, 1.0]); U = np.cross(D, Vv)

data = open(SRC, "rb").read()
print("read", len(data) // 1048576, "MB", round(time.time() - t0, 1), "s", flush=True)
blocks = {}
for m in re.finditer(rb"\n(\w+) ([^\r\n]*?) \{\r?\n", data):
    blocks[m.group(2)] = (m.group(1), m.end())
print("plugins", len(blocks), round(time.time() - t0, 1), "s", flush=True)


def body(name):
    b = blocks.get(name)
    if b is None: return None, None
    return b[0], data[b[1]:data.find(b"\n}", b[1])]


def unpack(txt, dtype):
    if txt[:4] in (b"ZIPC", b"ZIPB"):
        raw = txt[20:]
        comp = base64.b64decode(raw + b"=" * (-len(raw) % 4)) if txt[:4] == b"ZIPC" else bytes.fromhex(raw.decode())
        return np.frombuffer(zlib.decompress(comp), dtype=dtype)
    return np.frombuffer(bytes.fromhex(txt.decode()), dtype=dtype)


def mesh(name, depth=0):
    typ, b = body(name)
    if b is None: return None
    if typ == b"GeomStaticMesh":
        mv = re.search(rb'vertices=ListVectorHex\("([^"]*)"\)', b); mf = re.search(rb'faces=ListIntHex\("([^"]*)"\)', b)
        mi = re.search(rb'face_mtlIDs=ListIntHex\("([^"]*)"\)', b)
        if mv and mf:
            V = unpack(mv.group(1), "<f4").reshape(-1, 3).astype(np.float64); F = unpack(mf.group(1), "<i4").reshape(-1, 3)
            I = unpack(mi.group(1), "<i4") if mi else None
            return V, F, (I if I is not None and len(I) == len(F) else None)
        mv = re.search(rb"vertices=ListVector\((.*?)\);", b, re.S); mf = re.search(rb"faces=ListInt\((.*?)\);", b, re.S)
        if mv and mf:
            V = np.array([float(x) for x in re.findall(rb"-?\d+\.?\d*(?:e-?\d+)?", mv.group(1))]).reshape(-1, 3)
            F = np.array([int(x) for x in re.findall(rb"-?\d+", mf.group(1))]).reshape(-1, 3)
            return V, F, None
        return None
    if depth < 4:
        mm = re.search(rb"\n\s*mesh=([^;\s]+);", b)
        if mm: return mesh(mm.group(1), depth + 1)
    return None


MTL = {}
def multi(mname):
    """MtlMulti plugin -> {id: sub-material name}, else None."""
    if mname in MTL: return MTL[mname]
    res = None
    typ, b = body(mname.encode("latin1"))
    if typ == b"MtlMulti" and b is not None:
        subs = [x.decode("latin1").split("@")[0] for x in re.findall(rb"\n\s*([\w#\-\.]+@[\w]+),?", b.split(b"ids_list")[0])]
        mi = re.search(rb'ids_list=ListIntHex\("([^"]*)"\)', b)
        ids = list(unpack(mi.group(1), "<i4")) if mi else list(range(1, len(subs) + 1))
        res = dict(zip([int(i) for i in ids], subs))
    MTL[mname] = res
    return res


NUM = rb"(-?\d+\.?\d*(?:e[-+]?\d+)?)"
TRM = re.compile(rb"transform=Transform\(Matrix\(Vector\(" + rb",\s*".join([NUM] * 3) + rb"\),\s*Vector\(" + rb",\s*".join([NUM] * 3)
                 + rb"\),\s*Vector\(" + rb",\s*".join([NUM] * 3) + rb"\)\),\s*Vector\(" + rb",\s*".join([NUM] * 3) + rb"\)\)")

s, ox, oy, z0 = float(xf.get("unit", 0.01)), float(xf["ox"]), float(xf["oy"]), float(xf["z0"])
cmin = np.minimum(p0, p1); cmax = np.maximum(p0, p1)
if BOX: cmin, cmax = np.array(BOX[:2], float), np.array(BOX[2:], float)
PLANCROP = BOX is not None or view.get("kind") == "plan"
names, layers, mats, mat_id = [], [], [], {}
Vs, Fs, FNs, FMs = [], [], [], []
nv = 0; nnode = 0
for name, (typ, st) in blocks.items():
    if typ != b"Node": continue
    b = data[st:data.find(b"\n}", st)]
    if b"visible=1" not in b or b"primary_visibility=0" in b: continue
    mg = re.search(rb"geometry=([^;\r\n]+);", b)
    if not mg: continue
    mh = re.search(rb'transform=TransformHex\("([0-9A-Fa-f]+)"\)', b)
    if mh:
        raw = bytes.fromhex(mh.group(1).decode())
        v = list(np.frombuffer(raw[:36], dtype="<f4").astype(np.float64)) + list(np.frombuffer(raw[40:64], dtype="<f8"))
    else:
        mt_ = TRM.search(b)
        if not mt_: continue
        v = [float(x) for x in mt_.groups()]
    M = np.array([v[0:3], v[3:6], v[6:9]]).T; T = np.array(v[9:12])
    ml = re.search(rb'"layer/([^"]*)"', b); mm_ = re.search(rb"\n\s*material=([^;\r\n]+);", b)
    nm = name.decode("latin1").rsplit("@node_", 1)[0]
    lay = ml.group(1).decode("utf-8", "replace") if ml else "-"
    if EXCL_LAY.search(lay) or EXCL_NM.search(nm): continue
    if INCL and not INCL.search(lay + " " + nm): continue
    me = mesh(mg.group(1))
    if me is None or len(me[1]) == 0: continue
    Vl, F, I = me
    W = Vl @ M.T + T
    W = np.column_stack([(W[:, 0] - ox) * s, (W[:, 1] - oy) * s, (W[:, 2] - z0) * s])
    # quick reject on the node bounding box
    lo, hi = W.min(0), W.max(0)
    if PLANCROP:
        if hi[0] < cmin[0] - MARGIN or lo[0] > cmax[0] + MARGIN or hi[1] < cmin[1] - MARGIN or lo[1] > cmax[1] + MARGIN: continue
        if hi[2] < Z0 or lo[2] > Z1: continue
    else:
        dd = (np.array([[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], lo[1]], [hi[0], hi[1]]]) - p0) @ D[:2]
        uu = np.array([[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], lo[1]], [hi[0], hi[1]]]) @ U[:2]
        u0, u1 = sorted([p0 @ U[:2], p1 @ U[:2]])
        if dd.max() < -0.15 or dd.min() > DEPTH or uu.max() < u0 - MARGIN or uu.min() > u1 + MARGIN: continue
        if hi[2] < Z0 - MARGIN or lo[2] > Z1 + MARGIN: continue
    # per-triangle crop to the view volume
    T3 = W[F]
    if PLANCROP:
        keep = ~((T3[:, :, 0].max(1) < cmin[0] - MARGIN) | (T3[:, :, 0].min(1) > cmax[0] + MARGIN) |
                 (T3[:, :, 1].max(1) < cmin[1] - MARGIN) | (T3[:, :, 1].min(1) > cmax[1] + MARGIN) |
                 (T3[:, :, 2].max(1) < Z0) | (T3[:, :, 2].min(1) > Z1))
    else:
        td = (T3[:, :, :2] - p0) @ D[:2]; tu = T3[:, :, :2] @ U[:2]
        u0, u1 = sorted([p0 @ U[:2], p1 @ U[:2]])
        keep = ~((td.max(1) < -0.15) | (td.min(1) > DEPTH) | (tu.max(1) < u0 - MARGIN) | (tu.min(1) > u1 + MARGIN) |
                 (T3[:, :, 2].max(1) < Z0 - MARGIN) | (T3[:, :, 2].min(1) > Z1 + MARGIN))
    # zero-area triangles (stray splines converted to poly, e.g. Line766) never render: drop them
    ar = np.linalg.norm(np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0]), axis=1)
    keep &= ar > 1e-9
    if not keep.any(): continue
    F = F[keep]
    used, inv = np.unique(F.ravel(), return_inverse=True)
    Fk = inv.reshape(-1, 3).astype(np.int32) + nv
    mname = mm_.group(1).decode("latin1") if mm_ else ""
    sub = multi(mname) if mname else None
    if sub and I is not None:
        ids = I[keep]
        mlist = [sub.get(int(i), mname.split("@")[0]) or mname.split("@")[0] for i in ids]
    else:
        mlist = [mname.split("@")[0]] * len(F)
    fm = np.array([mat_id.setdefault(m_, len(mat_id)) for m_ in mlist], dtype=np.int32)
    Vs.append(W[used].astype(np.float32)); Fs.append(Fk); FNs.append(np.full(len(F), nnode, np.int32)); FMs.append(fm)
    names.append(nm); layers.append(lay); nv += len(used); nnode += 1

mats = [None] * len(mat_id)
for k, i in mat_id.items(): mats[i] = k
V = np.concatenate(Vs) if Vs else np.zeros((0, 3), np.float32)
F = np.concatenate(Fs) if Fs else np.zeros((0, 3), np.int32)
np.savez_compressed(OUT, V=V, F=F, FN=np.concatenate(FNs) if FNs else np.zeros(0, np.int32), FM=np.concatenate(FMs) if FMs else np.zeros(0, np.int32),
                    names=json.dumps(names), layers=json.dumps(layers), mats=json.dumps(mats))
print("nodes", nnode, "triangles", len(F), "vertices", len(V), "materials", len(mats), round(time.time() - t0, 1), "s", flush=True)
