"""Wait until no Codex job is running on a view (its folder name in a codex.exe command line), max 40 min.
usage: wait_view_idle.py out_dir VIEW   -> prints 'idle' (or 'timeout')"""
import os
import subprocess
import sys
import time

OUT, VIEW = sys.argv[1], sys.argv[2]
key = os.path.basename(os.path.normpath(OUT)).replace("'", "") + ".*" + VIEW
# no double quotes in the command: Windows argument quoting broke the -Filter "Name='codex.exe'" form (false 'idle', 08/11)
ps = ("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'codex.exe' -and $_.CommandLine -match '%s' }).Count" % key.replace(" ", "."))
t0 = time.time()
while time.time() - t0 < 2400:
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    n = (r.stdout or "0").strip() or "0"
    if n in ("0", ""):
        print("idle", int(time.time() - t0), "s")
        sys.exit(0)
    time.sleep(20)
print("timeout")
