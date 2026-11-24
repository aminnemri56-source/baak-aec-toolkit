"""Builds the PROJECT 07/11 Vantage project: everything from the last PROJECT render file (C:/Users/sbs/Desktop/GGG.vantage, 27/10:
environment HDRI, background, colour correction, options, scene changes and Cosmos imports, render task 2089 x 1421, 500 samples,
auto exposure, denoiser), on the fresh vrscene, with the 07/11 cameras and one render task per camera.
usage: build_vantage_0711.py cams.txt scene.vrscene out.vantage outdir"""
import json
import math
import os
import sys

BASE = r"C:/Users/sbs/Desktop/GGG.vantage"  # read only
cams_txt, vrscene, out, outdir = sys.argv[1:5]
base = json.load(open(BASE, encoding="utf-8"))
cfg = dict(base)
task0 = dict(base["render_settings"]["render_tasks"][0])
tmpl = dict(base["cameras"][0])
tmpl.pop("thumbnail", None)
for p in (cfg["options"].get("env_image_path"), cfg["options"].get("bg_image_path")):
    print("exists" if p and os.path.exists(p) else "MISSING", p)


def cam(name, e, t, hf):
    d = [e[0] - t[0], e[1] - t[1], e[2] - t[2]]
    L = math.sqrt(sum(v * v for v in d))
    z = [v / L for v in d]
    x = [-z[1], z[0], 0.0]
    n = math.hypot(x[0], x[1])
    x = [x[0] / n, x[1] / n, 0.0]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    o = dict(tmpl)
    o.update(name=name, cam_type=0, use_fov=0, hfov_deg=hf, focal_length=18.0 / math.tan(math.radians(hf) / 2), film_gate=36.0, zoom_factor=1.0,
             transform=x + y + z + list(e), roll_angle=0.0, clip_enabled=0, focus_dist=L, vert_tilt_correction=0, vert_tilt=0.0, hor_tilt=0.0,
             vert_shift=0.0, hor_shift=0.0, cam_scene_state=-1, resolution_x=task0["output_width"], resolution_y=task0["output_height"], cam_group_idx=0)
    o["dof"] = dict(tmpl["dof"], enable=0)
    return o


entries = []
for line in open(cams_txt, encoding="utf-8"):
    p = line.strip().split("|")
    if len(p) < 7:
        continue
    entries.append(cam(p[0].replace("CAM_R0711_", ""), [float(p[1]), float(p[2]), float(p[3])], [float(p[4]), float(p[5]), float(p[3])], float(p[6])))
cur = dict(entries[0])
for k in ("name", "cam_scene_state", "resolution_x", "resolution_y", "cam_group_idx"):
    cur.pop(k, None)
tasks = []
for c in entries:
    t = dict(task0)
    t.update(cam_index=c["name"], task_name=c["name"], task_enabled=True, output_file="%s/HYB_0711_%s.png" % (outdir.replace("\\", "/"), c["name"]))
    tasks.append(t)
cfg.update(camera=cur, root_filename=vrscene.replace("\\", "/"), cameras=entries,
           camera_groups=[dict(camera_group_name="PROJECT 07 11 - RPM COURS PILATES", camera_group_visible=True, camera_group_ss_idx=-1, camera_group_index=0, camera_group_count=len(entries))],
           render_settings=dict(base["render_settings"], render_tasks=tasks))
os.makedirs(outdir, exist_ok=True)
json.dump(cfg, open(out, "w", encoding="utf-8"), indent=1)
print("written", out, len(entries), "cameras", len(tasks), "tasks", task0["output_width"], "x", task0["output_height"], task0["max_frame_samples"], "samples")
