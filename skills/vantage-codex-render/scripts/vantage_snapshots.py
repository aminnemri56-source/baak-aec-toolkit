"""Renders every camera of a .vantage project through the running Vantage's command API (no click needed):
for each camera, loadConfig(camera + post_process), then startSnapshot to a PNG and wait for the offline render to finish.
usage: vantage_snapshots.py project.vantage outdir [samples] [only,names]"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PROJECT, OUT = sys.argv[1], sys.argv[2]
SAMPLES = int(sys.argv[3]) if len(sys.argv) > 3 else 500
ONLY = [x for x in (sys.argv[4].split(",") if len(sys.argv) > 4 else []) if x]
P = json.load(open(PROJECT, encoding="utf-8"))
TMP = os.path.join(OUT, "_cam_tmp.vantage")
os.makedirs(OUT, exist_ok=True)


def call(o, t=60):
    r = urllib.request.Request("http://localhost:20702/command", data=json.dumps(o).encode(), headers={"Content-Type": "application/json"})
    try:
        x = urllib.request.urlopen(r, timeout=t)
        return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def status():
    try:
        return json.loads(call({"command": "getStatus"}, 10)[1])
    except Exception:
        return {}


def wait_interactive(limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = status()
        if "Interactive" in s.get("state", "") and s.get("offlineTaskState", "None") in ("None", "Finished", "Done", ""):
            return s
        time.sleep(3)
    return status()


for c in P["cameras"]:
    name = c.get("name", "")
    if ONLY and name not in ONLY:
        continue
    out = os.path.join(OUT, "HYB_0711_%s.png" % name).replace("\\", "/")
    if os.path.exists(out):
        print(name, "exists", flush=True)
        continue
    cam = dict(c)
    for k in ("name", "cam_scene_state", "resolution_x", "resolution_y", "cam_group_idx", "thumbnail"):
        cam.pop(k, None)
    json.dump(dict(camera=cam, post_process=P["post_process"], version=P.get("version", 14)), open(TMP, "w", encoding="utf-8"))
    print(name, "loadConfig", call({"command": "loadConfig", "path": TMP.replace("\\", "/")})[0], flush=True)
    time.sleep(3)
    wait_interactive(60)
    t0 = time.time()
    code, txt = call({"command": "startSnapshot", "path": out, "samples": SAMPLES, "denoiser": True, "autoExposure": True, "lightCache": True, "temporal": True, "pngAlpha": False, "useUiParams": False})
    print(name, "startSnapshot", code, txt.strip()[:160], flush=True)
    if code != 200:
        continue
    time.sleep(5)
    s = wait_interactive(1800)
    for _ in range(20):
        if os.path.exists(out):
            break
        time.sleep(3)
    print(name, "done" if os.path.exists(out) else "NO FILE", int(time.time() - t0), "s", s.get("state"), flush=True)
print("all done", flush=True)
