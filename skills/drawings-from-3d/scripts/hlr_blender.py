"""Hidden-line pass in Blender (headless) for one view: exact visible edges of the 3D (Line Art) + a flat material-id image for the fills.

usage: blender -b --factory-startup --python hlr_blender.py -- geom.npz view.json out_dir
writes out_dir/strokes.npz  P float32 (n,3) stroke points in drawing metres (world), OFF int32 stroke start offsets (+ final n),
                            KIND int8 per stroke (0 = contour / borders / cut boundary, 1 = crease, material border, intersection)
       out_dir/ids.png      flat material ids (R*256+G = material index + 1, 0 = nothing), same frame as meta.json
       out_dir/meta.json    camera frame: U, V, D axes, u0/v0/px of the id image, timings
The camera is orthographic, its near clip plane IS the cut plane (Line Art draws the cut boundary with use_clip_plane_boundaries)."""
import bpy, sys, json, os, time, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
GEOM, VIEWJ, OUTD = argv[:3]
os.makedirs(OUTD, exist_ok=True)
t0 = time.time()
view = json.load(open(VIEWJ, encoding="utf-8"))
d = np.load(GEOM)
V, F, FN, FM = d["V"].astype(np.float64), d["F"], d["FN"], d["FM"]
names, mats = json.loads(str(d["names"])), json.loads(str(d["mats"]))
print("geometry", len(names), "nodes", len(F), "triangles", flush=True)

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
sc = bpy.context.scene

# ---------------------------------------------------------------- view frame (same as extract_vrscene.py)
p0, p1 = np.array(view["p0"], float), np.array(view["p1"], float)
if view.get("kind") == "plan":
    D = np.array([0, 0, -1.0]); U = np.array([1.0, 0, 0]); Vv = np.array([0, 1.0, 0])
    zc = float(view.get("cut_z", 1.0))
    u0, u1 = sorted([p0[0], p1[0]]); v0, v1 = sorted([p0[1], p1[1]])
    plane_pt = np.array([0, 0, zc]); depth = zc - float(view.get("z", [-0.6, 4.0])[0])
else:
    look = np.array(view["look"], float)
    D = np.array([look[0], look[1], 0.0]); D /= np.linalg.norm(D); Vv = np.array([0, 0, 1.0]); U = np.cross(D, Vv)
    u0, u1 = sorted([p0 @ U[:2], p1 @ U[:2]]); v0, v1 = view.get("z", [-0.6, 4.0])
    plane_pt = np.array([p0[0], p0[1], 0.0]); depth = float(view.get("depth", 6.0))
pad = float(view.get("pad", 0.3))
u0 -= pad; u1 += pad; v0 -= pad; v1 += pad
W_m, H_m = u1 - u0, v1 - v0
cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
BACK = 2.0                                                       # camera stands 2 m in front of the cut plane
d0 = plane_pt @ D
centre = U * cu + Vv * cv + D * d0 - D * BACK                    # u, v, depth -> world (axes orthonormal)
if view.get("kind") != "plan":
    # u, v are measured from the world origin along U and z; put the point back in world space
    centre = U * cu + np.array([0, 0, cv]) + D * (plane_pt @ D) - D * BACK

# ---------------------------------------------------------------- meshes, one object per node, materials with id colours
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

# one Blender material per (node, material) pair: the id image then tells both what object and what finish each pixel shows
PAIR = FN.astype(np.int64) * 65536 + FM.astype(np.int64)
upair, FP = np.unique(PAIR, return_inverse=True)
bmats = []
for i, pk in enumerate(upair):
    m = bpy.data.materials.new("p%d" % i)
    k = i + 1
    m.diffuse_color = (srgb_to_lin((k // 256) / 255.0), srgb_to_lin((k % 256) / 255.0), 0.0, 1.0)
    bmats.append(m)
FM_render = FP.astype(np.int32)

order = np.argsort(FN, kind="stable")
FNs = FN[order]
starts = np.searchsorted(FNs, np.arange(len(names) + 1))
for n in range(len(names)):
    idx = order[starts[n]:starts[n + 1]]
    if len(idx) == 0: continue
    Fn = F[idx]
    used, inv = np.unique(Fn.ravel(), return_inverse=True)
    Vn = V[used]; Fl = inv.reshape(-1, 3)
    me = bpy.data.meshes.new(names[n][:60])
    me.vertices.add(len(Vn)); me.vertices.foreach_set("co", Vn.astype(np.float32).ravel())
    me.loops.add(len(Fl) * 3); me.loops.foreach_set("vertex_index", Fl.astype(np.int32).ravel())
    me.polygons.add(len(Fl)); me.polygons.foreach_set("loop_start", (np.arange(len(Fl)) * 3).astype(np.int32))
    mi = FM_render[idx]; um, mloc = np.unique(mi, return_inverse=True)
    for mm in um: me.materials.append(bmats[int(mm)])
    me.polygons.foreach_set("material_index", mloc.astype(np.int32))
    me.update(calc_edges=True); me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(names[n][:60], me); sc.collection.objects.link(ob)
print("objects built", round(time.time() - t0, 1), "s", flush=True)

# ---------------------------------------------------------------- orthographic camera, near clip = cut plane
cd = bpy.data.cameras.new("cam"); cd.type = "ORTHO"
cd.ortho_scale = max(W_m, H_m); cd.clip_start = BACK; cd.clip_end = BACK + depth
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
import mathutils
R = mathutils.Matrix(((U[0], Vv[0], -D[0]), (U[1], Vv[1], -D[1]), (U[2], Vv[2], -D[2])))
cam.matrix_world = mathutils.Matrix.Translation(mathutils.Vector(centre)) @ R.to_4x4()
sc.camera = cam
PX = float(view.get("px", 0.004))                                 # metres per pixel of the id image (4 mm)
rx, ry = int(math.ceil(W_m / PX)), int(math.ceil(H_m / PX))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
cd.sensor_fit = "HORIZONTAL" if W_m >= H_m else "VERTICAL"

# ---------------------------------------------------------------- Line Art: two passes into two layers
gpd = bpy.data.grease_pencils.new("LA"); gp = bpy.data.objects.new("LA", gpd); sc.collection.objects.link(gp)
gmat = bpy.data.materials.new("lineart"); bpy.data.materials.create_gpencil_data(gmat); gpd.materials.append(gmat)
crease = math.radians(float(view.get("crease_deg", 140.0)))
for lname, kinds in (("C", ("contour",)), ("D", ("crease", "material", "intersection", "edge_mark"))):   # no loose edges: a render cannot show them
    gpd.layers.new(lname)
    m = gp.modifiers.new("la_" + lname, "LINEART")
    m.source_type = "SCENE"; m.target_layer = lname; m.target_material = gmat
    m.use_contour = "contour" in kinds; m.use_loose = "loose" in kinds; m.use_crease = "crease" in kinds
    m.use_material = "material" in kinds; m.use_intersection = "intersection" in kinds; m.use_edge_mark = "edge_mark" in kinds
    m.use_clip_plane_boundaries = (lname == "C")
    m.crease_threshold = crease
    m.use_crease_on_smooth = True; m.use_crease_on_sharp = True
    m.use_image_boundary_trimming = False; m.overscan = 0.05
    m.chaining_image_threshold = 0.0; m.smooth_tolerance = 0.0; m.split_angle = 0.0
    m.use_back_face_culling = False; m.use_cache = False
    m.use_object_instances = False
    m.use_overlap_edge_type_support = False
    m.use_detail_preserve = True
dg = bpy.context.evaluated_depsgraph_get(); dg.update()
ge = gp.evaluated_get(dg).data
P, OFF, KIND = [], [0], []
for li, lay in enumerate(ge.layers):
    fr = lay.current_frame()
    if fr is None: continue
    dr = fr.drawing
    k = 0 if lay.name == "C" else 1
    try:
        n = len(dr.attributes["position"].data)
        pos = np.empty(n * 3, np.float32); dr.attributes["position"].data.foreach_get("vector", pos); pos = pos.reshape(-1, 3)
        offs = np.empty(len(dr.strokes) + 1, np.int32)
        dr.curve_offsets.foreach_get("value", offs)
        for a, b in zip(offs[:-1], offs[1:]):
            if b - a < 2: continue
            P.append(pos[a:b]); OFF.append(OFF[-1] + (b - a)); KIND.append(k)
    except Exception as e:
        print("slow stroke read:", e, flush=True)
        for s in dr.strokes:
            pts = np.array([tuple(p.position) for p in s.points], np.float32)
            if len(pts) < 2: continue
            P.append(pts); OFF.append(OFF[-1] + len(pts)); KIND.append(k)
P = np.concatenate(P) if P else np.zeros((0, 3), np.float32)
OFF = np.array(OFF, np.int32)
# owner of each stroke: nearest triangle of the source geometry at 3 points along the stroke (majority) -> node and material
from mathutils.bvhtree import BVHTree
tree = BVHTree.FromPolygons(V.tolist(), F.tolist(), all_triangles=True)
NODE = np.full(len(KIND), -1, np.int32); MAT = np.full(len(KIND), -1, np.int32)
for i in range(len(KIND)):
    a, b = OFF[i], OFF[i + 1]
    votes = {}
    for t in (0.2, 0.5, 0.8):
        q = P[a + min(b - a - 1, int(t * (b - a)))]
        loc, nrm, fi, dist = tree.find_nearest(mathutils.Vector((float(q[0]), float(q[1]), float(q[2]))), 0.05)
        if fi is not None:
            key = (int(FN[fi]), int(FM[fi])); votes[key] = votes.get(key, 0) + 1
    if votes:
        NODE[i], MAT[i] = max(votes.items(), key=lambda kv: kv[1])[0]
np.savez_compressed(os.path.join(OUTD, "strokes.npz"), P=P, OFF=OFF, KIND=np.array(KIND, np.int8), NODE=NODE, MAT=MAT)
t_la = time.time() - t0
print("line art", len(KIND), "strokes", len(P), "points", round(t_la, 1), "s", flush=True)

# ---------------------------------------------------------------- flat material-id render (Workbench, no AA, no dither)
gp.hide_render = True
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "FLAT"; sh.color_type = "MATERIAL"; sh.show_object_outline = False; sh.show_cavity = False; sh.show_shadows = False
sh.show_specular_highlight = False
try: sc.display.render_aa = "OFF"
except Exception: pass
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"; sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
sc.render.dither_intensity = 0.0
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.color_depth = "8"
sc.render.filepath = os.path.join(OUTD, "ids.png")
bpy.ops.render.render(write_still=True)
meta = dict(U=list(U), V=list(Vv), D=list(D), u0=cu - cd.ortho_scale / 2 if W_m >= H_m else cu - (cd.ortho_scale * rx / ry) / 2,
            v1=cv + (cd.ortho_scale * ry / rx) / 2 if W_m >= H_m else cv + cd.ortho_scale / 2,
            px=(cd.ortho_scale / rx) if W_m >= H_m else (cd.ortho_scale / ry), rx=rx, ry=ry,
            pairs=[[int(pk // 65536), int(pk % 65536)] for pk in upair],      # id k (1-based) -> [node, material]
            plane_d=float(plane_pt @ D), t_lineart=round(t_la, 1), t_total=round(time.time() - t0, 1))
json.dump(meta, open(os.path.join(OUTD, "meta.json"), "w"), indent=1)
print("done", round(time.time() - t0, 1), "s", flush=True)
