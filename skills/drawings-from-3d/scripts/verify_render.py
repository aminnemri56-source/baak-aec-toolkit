"""Check the drawing's source geometry against a render / hero photo: the same 3D, seen through the render's own camera, drawn with
Line Art and laid over the image. Every line must sit on an edge of the picture; a line with nothing under it, or a picture edge
with no line, is a difference between the 3D export used for the drawing and the rendered scene (or a Codex invention on a hero).

usage: blender -b --factory-startup --python verify_render.py -- geom.npz view.json "cam_line" image.png out.png
cam_line = one line of the camera list: name|px|py|pz|tx|ty|tz|hfov_deg|lens|type|k|width|height|clip  (3D centimetres)"""
import bpy, sys, json, os, math
import numpy as np
import mathutils
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
GEOM, VIEWJ, CAM, IMG, OUTP = argv[:5]
view = json.load(open(VIEWJ, encoding="utf-8")); xf = view["xf"]
d = np.load(GEOM)
V, F, FN = d["V"].astype(np.float64), d["F"], d["FN"]
names = json.loads(str(d["names"]))
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
sc = bpy.context.scene
order = np.argsort(FN, kind="stable"); starts = np.searchsorted(FN[order], np.arange(len(names) + 1))
for n in range(len(names)):
    idx = order[starts[n]:starts[n + 1]]
    if len(idx) == 0: continue
    used, inv = np.unique(F[idx].ravel(), return_inverse=True); Fl = inv.reshape(-1, 3)
    me = bpy.data.meshes.new(names[n][:60])
    me.vertices.add(len(used)); me.vertices.foreach_set("co", V[used].astype(np.float32).ravel())
    me.loops.add(len(Fl) * 3); me.loops.foreach_set("vertex_index", Fl.astype(np.int32).ravel())
    me.polygons.add(len(Fl)); me.polygons.foreach_set("loop_start", (np.arange(len(Fl)) * 3).astype(np.int32))
    me.update(calc_edges=True)
    ob = bpy.data.objects.new(names[n][:60], me); sc.collection.objects.link(ob)

c = CAM.split("|")
s, ox, oy, z0 = float(xf.get("unit", 0.01)), float(xf["ox"]), float(xf["oy"]), float(xf["z0"])
tod = lambda x, y, z: mathutils.Vector(((x - ox) * s, (y - oy) * s, (z - z0) * s))
pos, tgt = tod(*map(float, c[1:4])), tod(*map(float, c[4:7]))
W, H = int(c[11]), int(c[12]); clip = float(c[13]) * s if len(c) > 13 and c[13] else 0.1
cd = bpy.data.cameras.new("cam"); cd.type = "PERSP"; cd.sensor_fit = "HORIZONTAL"; cd.angle = math.radians(float(c[7]))
cd.clip_start = max(0.05, clip); cd.clip_end = 100
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
cam.location = pos
cam.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100

gpd = bpy.data.grease_pencils.new("LA"); gp = bpy.data.objects.new("LA", gpd); sc.collection.objects.link(gp)
gm = bpy.data.materials.new("la"); bpy.data.materials.create_gpencil_data(gm); gpd.materials.append(gm)
gpd.layers.new("L")
m = gp.modifiers.new("la", "LINEART")
m.source_type = "SCENE"; m.target_layer = "L"; m.target_material = gm
m.use_contour = m.use_crease = m.use_material = m.use_intersection = True; m.use_loose = False
m.crease_threshold = math.radians(float(view.get("crease_deg", 140.0))); m.use_clip_plane_boundaries = False   # the render does not draw its clip plane
m.use_image_boundary_trimming = True; m.use_cache = False
dg = bpy.context.evaluated_depsgraph_get(); dg.update()
ge = gp.evaluated_get(dg).data
strokes = []
for lay in ge.layers:
    fr = lay.current_frame()
    if fr is None: continue
    for st in fr.drawing.strokes:
        pts = []
        for p in st.points:
            q = world_to_camera_view(sc, cam, mathutils.Vector(p.position))
            pts.append((q.x * W, (1 - q.y) * H))
        if len(pts) > 1: strokes.append(pts)
print("strokes", len(strokes), flush=True)

# overlay on the image (resized to the camera resolution's aspect), using Blender's image API (no PIL inside Blender)
img = bpy.data.images.load(IMG)
iw, ih = img.size
arr = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)[::-1]          # top row first
base = arr[:, :, :3] * 0.55 + 0.45 * 0.0                                          # darken the photo so the lines read
out = np.concatenate([base, np.ones((ih, iw, 1), np.float32)], axis=2)
kx, ky = iw / W, ih / H
col = np.array([0.1, 1.0, 1.0], np.float32)
def plot(x, y):
    xi, yi = int(x), int(y)
    if 0 <= xi < iw and 0 <= yi < ih: out[yi, xi, :3] = col
for pts in strokes:
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        x1, y1, x2, y2 = x1 * kx, y1 * ky, x2 * kx, y2 * ky
        n_ = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
        for t in np.linspace(0, 1, n_ + 1): plot(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
res = bpy.data.images.new("ov", iw, ih, alpha=True)
res.pixels.foreach_set(out[::-1].ravel())
res.filepath_raw = OUTP; res.file_format = "PNG"; res.save()
json.dump({"strokes": [[list(map(float, p)) for p in s_] for s_ in strokes], "W": W, "H": H, "iw": iw, "ih": ih},
          open(os.path.splitext(OUTP)[0] + ".json", "w"))
print("written", OUTP, flush=True)
