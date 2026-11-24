"""Starts Chaos Vantage on the PROJECT 07/11 vrscene (second screen, focus handed back), waits for the load, then loads the
07/11 project (cameras, last PROJECT render settings, render queue) through the local command API. Refuses if Vantage already runs.
usage: vantage_launch.py scene.vrscene project.vantage"""
import ctypes
import ctypes.wintypes as w
import json
import subprocess
import sys
import time
import urllib.request

SCENE, PROJECT = sys.argv[1], sys.argv[2]
u = ctypes.windll.user32
u.SetProcessDPIAware()
WIN = (-1928, -71, 1936, 1048)


def call(o, t=20):
    r = urllib.request.Request("http://localhost:20702/command", data=json.dumps(o).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=t).read()


def gpu():
    return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()


def title(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def find():
    res = []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h) and title(h).startswith("Chaos Vantage"):
            res.append(h)
        return True

    u.EnumWindows(cb, 0)
    return res[0] if res else None


if subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process vantage -ErrorAction SilentlyContinue).Id"], capture_output=True, text=True).stdout.strip():
    sys.exit("a Vantage is already running, nothing started")
prev = u.GetForegroundWindow()
p = subprocess.Popen([r"C:\Program Files\Chaos\Vantage\vantage.exe", "-sceneFile=" + SCENE])
print("started pid", p.pid, "gpu", gpu(), flush=True)
h = None
t0 = time.time()
while time.time() - t0 < 180 and not h:
    time.sleep(1)
    h = find()
if h:
    u.SetWindowPos(h, 0, WIN[0], WIN[1], WIN[2], WIN[3], 0x0010 | 0x0004)
    u.SetForegroundWindow(prev)
    print("window after", int(time.time() - t0), "s", flush=True)
last = ""
seen_loading = False
while time.time() - t0 < 1500:
    time.sleep(5)
    if p.poll() is not None:
        sys.exit("Vantage exited with code %s, gpu %s" % (p.returncode, gpu()))
    try:
        s = json.loads(call({"command": "getStatus"}, 10))
        k = s.get("state", "?")
    except Exception as e:
        k = "no answer " + type(e).__name__
    if k != last:
        print(int(time.time() - t0), "s", k, "| gpu", gpu(), flush=True)
        last = k
    if "Loading" in k:
        seen_loading = True
    if "Interactive" in k and (seen_loading or time.time() - t0 > 60):
        break
print("scene ready after", int(time.time() - t0), "s | gpu", gpu(), flush=True)
time.sleep(5)
print("loadConfig", call({"command": "loadConfig", "path": PROJECT}, 120)[:300], flush=True)
time.sleep(20)
for i in range(60):
    try:
        s = json.loads(call({"command": "getStatus"}, 10))
        if "Interactive" in s.get("state", ""):
            break
    except Exception:
        pass
    time.sleep(5)
print("after config", json.dumps(s)[:600], "| gpu", gpu(), flush=True)
if h:
    u.SetWindowPos(h, 0, WIN[0], WIN[1], WIN[2], WIN[3], 0x0010 | 0x0004)
print("done", flush=True)
