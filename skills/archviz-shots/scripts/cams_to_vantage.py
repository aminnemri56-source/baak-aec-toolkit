"""cams_to_vantage.py (skill archviz-shots): put a camera list into a Chaos Vantage project: ALL earlier cameras are replaced by the list,
in one group, with one render task per camera, and camera clipping where the list asks for it.

usage: cams_to_vantage.py cams.txt base.vantage scene.vrscene out.vantage render_dir [--prefix HYB_1111_] [--group "NAME"]
                          [--samples 1000] [--wb 4800]
  cams.txt lines (room_cameras.py writes them): name|px|py|pz|tx|ty|tz|hfov|focal|type|score|width|height|clip
  (8 fields are enough: then 2400 x 1600 and no clipping). clip = distance of the near clipping plane from the camera, 0 = none.
  base.vantage = the project's last good project: its render options, colour pipeline, environment and material edits are kept as they are.
Vantage's command API (port 20702) can load the result (loadConfig) but cannot start the queue: the user clicks Start."""
import copy
import json
import math
import os
import sys

cams_txt, base, vrscene, out, outdir = sys.argv[1:6]
A = sys.argv[6:]


def opt(name, default):
    return A[A.index(name) + 1] if name in A else default


PREFIX, GROUP = opt("--prefix", ""), opt("--group", "CAMERAS")
d = json.load(open(base, encoding="utf-8"))
old, new = d["root_filename"], vrscene.replace("\\", "/")
d = json.loads(json.dumps(d).replace(json.dumps(old)[1:-1], json.dumps(new)[1:-1]))
d["root_filename"] = new
tmpl = copy.deepcopy(d["cameras"][0])
tmpl.pop("thumbnail", None)
task0 = copy.deepcopy(d["render_settings"]["render_tasks"][0])
if "--samples" in A:
    task0["max_frame_samples"] = int(opt("--samples", 1000))
entries, tasks = [], []
for line in open(cams_txt, encoding="utf-8"):
    p = line.strip().split("|")
    if len(p) < 8:
        continue
    e, t, hfov = [float(v) for v in p[1:4]], [float(v) for v in p[4:7]], float(p[7])
    w, h = (int(p[11]), int(p[12])) if len(p) > 12 else (2400, 1600)
    clip = float(p[13]) if len(p) > 13 else 0.0
    dd = [e[i] - t[i] for i in range(3)]
    L = math.sqrt(sum(v * v for v in dd))
    z = [v / L for v in dd]
    n = math.hypot(z[1], z[0])
    x = [-z[1] / n, z[0] / n, 0.0]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    c = copy.deepcopy(tmpl)
    c.update(name=p[0], cam_type=0, use_fov=0, hfov_deg=hfov, focal_length=18.0 / math.tan(math.radians(hfov) / 2), film_gate=36.0, zoom_factor=1.0,
             transform=x + y + z + e, roll_angle=0.0, clip_enabled=1 if clip > 0 else 0, clip_near=clip, focus_dist=max(L, clip + 100.0),
             vert_tilt_correction=0, vert_tilt=0.0, hor_tilt=0.0, vert_shift=0.0, hor_shift=0.0, vignetting=0.0, optical_vignetting=0.0,
             cam_scene_state=-1, resolution_x=w, resolution_y=h, cam_group_idx=0)
    c["dof"] = dict(tmpl["dof"], enable=0)
    entries.append(c)
    k = copy.deepcopy(task0)
    k.update(cam_index=p[0], task_name=p[0], task_enabled=True, task_scene_state="CURRENT", output_width=w, output_height=h,
             output_file="%s/%s%s.png" % (outdir.replace("\\", "/"), PREFIX, p[0]))
    tasks.append(k)
cur = copy.deepcopy(entries[0])
for k in ("name", "cam_scene_state", "resolution_x", "resolution_y", "cam_group_idx"):
    cur.pop(k, None)
d.update(camera=cur, cameras=entries,
         camera_groups=[dict(camera_group_name=GROUP, camera_group_visible=True, camera_group_ss_idx=-1, camera_group_index=0, camera_group_count=len(entries))],
         render_settings=dict(d["render_settings"], render_tasks=tasks))
if "--wb" in A:
    post = {"white_balance_on": 1, "white_balance_temperature": float(opt("--wb", 4800))}
    d["post_process"].update(post)
    for s in d["scene_states"]["post_sub_states"]:
        if s["common"]["name"] == "SAVED SCENE":
            s["properties"].update(post)
os.makedirs(outdir, exist_ok=True)
json.dump(d, open(out, "w", encoding="utf-8"), indent=1)
print("written", out, "|", len(entries), "cameras,", sum(1 for c in entries if c["clip_enabled"]), "with clipping |", task0["max_frame_samples"], "samples | renders ->", outdir)
