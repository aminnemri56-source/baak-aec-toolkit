"""Send numbered review comments to the Codex session that made <job_dir>/photo.png, in the same session (it keeps its
context), with the current photo attached. Backs up photo.png as photo_rN.png first; Codex overwrites photo.png.
usage: codex_comment.py job_dir comments.txt [extra images...]
comments.txt: one comment per line (where + what is wrong + what it must be). Blank lines ignored."""
import os
import re
import shutil
import subprocess
import sys
import time

D, CF = sys.argv[1], sys.argv[2]
EXTRA = sys.argv[3:]
CODEX = r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"

log = open(os.path.join(D, "codex.log"), encoding="utf-8", errors="ignore").read()
m = re.search(r"session id:\s*([0-9a-f-]{36})", log)
if not m:
    sys.exit("no session id in codex.log")
sid = m.group(1)
n = 1
while os.path.exists(os.path.join(D, "photo_r%d.png" % n)):
    n += 1
cur = os.path.join(D, "photo_r%d.png" % n)
shutil.copy2(os.path.join(D, "photo.png"), cur)
comments = [c.strip() for c in open(CF, encoding="utf-8").read().splitlines() if c.strip()]
body = "".join("%d. %s\n" % (i, c) for i, c in enumerate(comments, 1))
prompt = (
    f"REVIEW ROUND {n}. The attached image is your current photograph (photo_r{n}.png). The 3D render you started from "
    "is still the reference for the design, and every rule of the brief still applies (machines untouchable, colours, people, checklist).\n\n"
    f"Correct ONLY these points:\n{body}\n"
    "Keep everything else exactly as it is in your current photograph: same people, same framing, same light, same colours. "
    "Use the imagegen skill and edit your current photograph. Check each comment on the result, zooming in; if one is not fixed, "
    "edit again once (at most 1 more try; the art director reviews the result). Save the corrected image in this folder as photo.png (overwrite it). "
    f"Append to CHECK.txt: 'ROUND {n}' and each comment number with FIXED or NOT FIXED and a few words. Do not run Python.\n"
)
open(os.path.join(D, "COMMENTS_r%d.txt" % n), "w", encoding="utf-8").write(prompt)
cmd = [CODEX, "exec", "resume", sid, "--skip-git-repo-check", "-c", 'sandbox_mode="workspace-write"', "-i", cur]
for e in EXTRA:
    cmd += ["-i", e]
cmd += ["-o", "result_r%d.md" % n, "-"]
t0 = time.time()
before = os.path.getmtime(os.path.join(D, "photo.png"))
with open(os.path.join(D, "COMMENTS_r%d.txt" % n), "rb") as fin, open(os.path.join(D, "codex_r%d.log" % n), "w", encoding="utf-8") as fout:
    subprocess.run(cmd, cwd=D, stdin=fin, stdout=fout, stderr=subprocess.STDOUT)
after = os.path.getmtime(os.path.join(D, "photo.png"))
print("round", n, "session", sid, "new photo" if after > before else "PHOTO NOT UPDATED", int(time.time() - t0), "s")
