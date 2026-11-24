"""Screenshots of every camera of a .vantage project from the running Vantage (Live Link or not) through the command API:
loadConfig(camera + post_process) then getImage. usage: vantage_grab_views.py project.vantage outdir [minSamples] [only,names]"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PROJECT, OUT = sys.argv[1], sys.argv[2]
MIN = int(sys.argv[3]) if len(sys.argv) > 3 else 128
ONLY = [x for x in (sys.argv[4].split(",") if len(sys.argv) > 4 else []) if x]
P = json.load(open(PROJECT, encoding="utf-8"))
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(OUT, "_cam_tmp.vantage")


def call(o, t=120):
    r = urllib.request.Request("http://localhost:20702/command", data=json.dumps(o).encode(), headers={"Content-Type": "application/json"})
    try:
        x = urllib.request.urlopen(r, timeout=t)
        return x.status, x.headers.get("Content-Type", ""), x.read()
    except urllib.error.HTTPError as e:
        return e.code, "", e.read()


for c in P["cameras"]:
    name = c.get("name", "")
    if ONLY and name not in ONLY:
        continue
    cam = dict(c)
    for k in ("name", "cam_scene_state", "resolution_x", "resolution_y", "cam_group_idx", "thumbnail"):
        cam.pop(k, None)
    json.dump(dict(camera=cam, post_process=P["post_process"], version=P.get("version", 14)), open(TMP, "w", encoding="utf-8"))
    call({"command": "loadConfig", "path": TMP.replace("\\", "/")})
    time.sleep(4)
    code, ct, body = call({"command": "getImage", "minimumSamples": MIN, "timeoutSeconds": 90}, 150)
    if code == 200 and len(body) > 1000:
        import base64
        import io

        from PIL import Image
        if body[:1] == b"{":  # JSON {"bitmap": base64 BMP}
            body = base64.b64decode(json.loads(body)["bitmap"])
        im = Image.open(io.BytesIO(body)).convert("RGB")
        p = os.path.join(OUT, "VIEW_%s.png" % name)
        im.save(p)
        print(name, "saved", im.size, flush=True)
    else:
        print(name, "getImage", code, ct, body[:200], flush=True)
os.remove(TMP)
print("done", flush=True)
