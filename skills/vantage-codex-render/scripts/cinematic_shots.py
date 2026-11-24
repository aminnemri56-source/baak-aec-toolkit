"""Cinematic shots from a finished Codex hero photo (Hyundai set), with the self-checking brief of codex_brief.py:
waits for <hero_dir>/photo.png, then runs one Codex job per shot in parallel, each in <hero_dir>/<SHOT>/photo.png.
Image 1 = the hero photo (sets room, people, light, colours); the level refs only set the photographic level.
usage: cinematic_shots.py hero_dir "what the room is" [ref images...]   (no refs given = codex_brief.REFS)"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codex_brief  # noqa: E402

HERO, WHERE = sys.argv[1], sys.argv[2]
VIEW = os.path.basename(os.path.normpath(HERO))
STYLE, LIGHT = codex_brief.room_style(VIEW)   # a room with its own approved style (salle de cours) uses it
REFS = sys.argv[3:] or STYLE or [r for r in codex_brief.REFS if os.path.exists(r)]
EXT = [] if codex_brief.room_for(VIEW).get("no_ext") else ([codex_brief.EXTERIOR_IMG] if os.path.exists(codex_brief.EXTERIOR_IMG) else [])


def shot_prompt(text):
    p = codex_brief.shot(WHERE, text, len(REFS), bool(EXT))
    if STYLE and not sys.argv[3:]:
        p = p.replace(codex_brief._refs_text(len(REFS)), codex_brief.style_text(len(REFS), LIGHT))
        p = p.replace("Soft, diffuse natural daylight that wraps the room with gentle soft shadows (no harsh dappled sun patches all over the floor)",
                      "The light of the style images: " + LIGHT)
    return p
CODEX = r"C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"

hero = os.path.join(HERO, "photo.png")
t0 = time.time()
while not os.path.exists(hero) and time.time() - t0 < 3600:
    time.sleep(15)
if not os.path.exists(hero):
    sys.exit("no hero photo")
time.sleep(5)
procs = {}
for name, text in codex_brief.SHOTS.items():
    d = os.path.join(HERO, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "PROMPT.txt"), "w", encoding="utf-8").write(shot_prompt(text))
    cmd = [CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-i", hero]
    for r in REFS + EXT:
        cmd += ["-i", r]
    cmd += ["-o", "result.md", "-"]
    procs[name] = subprocess.Popen(cmd, cwd=d, stdin=open(os.path.join(d, "PROMPT.txt"), "rb"),
                                   stdout=open(os.path.join(d, "codex.log"), "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    print(time.strftime("%H:%M:%S"), "started", name, flush=True)
for name, p in procs.items():
    p.wait()
    print(time.strftime("%H:%M:%S"), name, "photo" if os.path.exists(os.path.join(HERO, name, "photo.png")) else "NO PHOTO", flush=True)
