---
name: vantage-codex-render
description: Put render cameras in a 3ds Max room (PROJECT or any BAAK project), render them in Chaos Vantage with the project's last render settings (environment, background, colour correction, resolution, samples), then pass each render to Codex to become a real photograph at the "Hyundai / Site" level. Use whenever the user says cameras + render + Codex, "rendu", "pass to Codex", "Hyundai level", "as latest render", or asks for photoreal images of a space from the 3D.
---

# Vantage → Codex render

The user's pipeline, as always: cameras in Max → Vantage with the LAST render settings of that project → Codex turns each render into a real photo ("HYUNDAI LEVEL OF QUALITY", "AS ALWAYS"). Keep usage low: no long explorations, reuse these scripts, short reports.

`PY` = `C:\Users\sbs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -I`. `S` = this skill's `scripts` folder.

## 0. Before anything (lesson of 07/11/2026)
- **Save the .max first** (new name, never overwrite). On 07/11 Vantage overloaded the 12 GB RTX 5070 at the first render seconds, the NVIDIA driver died, the PC blue-screened, and 5 h of unsaved Max work were lost. Ask "save v11?" once, before launching Vantage, and stop if refused.
- GPU memory: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`. Vantage needs ≥ 5 GB free for the PROJECT building. Ask the user to close Photos windows / AutoCAD / Telegram (never close them yourself). Closing Max is the big win: export, save, then the user closes Max.
- Export only what the cameras see (hide RDC / rooftop / far site while exporting, restore after) to cut VRAM.

## 1. Cameras
- Level cameras (target at camera height) for straight verticals, eye height 1.40–1.50 m above the floor, hfov 73–80°.
- Preview fast in the viewport, no render: set `camPrevViews = #(#("NAME", [pos], [target], hfov), ...)` then `fileIn S/cam_preview.ms` (isolates the region, 16:9 safe frame, grabs to `D:\PROJECT_work\cams_1er\preview\`), sheet with `PY S/psheet.py "A,B,C" sheet.jpg`. Reject views blocked by columns, outside walls, or inside furniture.
- Create the kept cameras in Max on a `CAMERAS_RENDU_<date>` layer and write `name|px|py|pz|tx|ty|hfov` lines (see `D:\PROJECT_work\cams_1er\cams_0711.ms`).

## 2. Vantage, as the latest render
- "As latest render" = the project's last `.vantage` file. PROJECT: `C:\Users\sbs\Desktop\GGG.vantage` (HDRI `D:\PROJECT_D5\maps\autumn_park_4k_nosun.exr` ×34.36 rot 0.117, background image, ACES OCIO display, filmic, auto exposure, 2089 × 1421, 500 samples, denoiser). Hyundai/Charguia and Dopamine have their own files — never mix projects ("NO PROJECT LATEST RENDER" means the PROJECT one).
- Export: `vrayExportVRScene "<D:\...\name.vrscene>"` from Max (~20 s, 1.7 GB for the full building).
- Project: `PY S/build_vantage_project.py cams.txt scene.vrscene out.vantage outdir` (copies everything from the base file, sets cameras + one render task per camera). Edit `BASE` for another project.
- Launch: `PY S/vantage_launch.py scene.vrscene out.vantage` (second screen, focus handed back, loads the project through the command API on port 20702). The API cannot start the render queue: the user clicks Start once.

## 3. Codex, Hyundai level

**Start Codex automatically, without asking** ("always start codex without asking", 07/11, last word after a brief "wait for me" moment): `PY S/stream_codex.py <renders dir> <codex dir> <count> [since_epoch]` sends each render to Codex as soon as Vantage has written it, only renders newer than `since_epoch` (so an older batch is not reprocessed), into a fresh codex folder per batch. Stop it at once if the user says stop.
- `PY S/make_codex_jobs.py <renders dir> <codex out dir> [fixes.json]` writes one folder per view (`render.png` + `PROMPT.txt`) and `jobs.json`. Prompts come from `S/codex_brief.py`, the "unlimited level" brief the user asked for on 07/11 to reduce faults. It has these parts:
  - **Locked inventory** per room (PIL / RPM / SDC, edit `ROOMS` for another project).
  - **Machines are untouchable** ("no machines are untouchable", 07/11): every machine and machine part stays exactly as in the render, even a part that looks odd close to the lens. A machine part is never a 3D error to remove; describe it in `notes` instead (`{"VIEW": {"remove": [...], "notes": [...]}}`).
  - **Allowed changes** only.
  - **Per-view 3D errors to remove**, from `fixes.json` (`{"HYB_0711_PIL_5": ["…", "…"]}`, also read from `<out>/fixes.json`).
  - **Room-specific real exercises.**
  - **A mandatory self-check:** Codex writes `INVENTORY.txt`, generates, compares with image 1 against a 10-item checklist, retries up to 3 times, keeps the best and writes `CHECK.txt` (PASS/FAIL per item). Read `CHECK.txt` before showing a photo.
  - **Level refs** (`codex_brief.REFS`): the 3 Pinterest pins in `VISUELS\_REF_NIVEAU_PINTEREST\` + the Hyundai photo. `PY S/run_codex_jobs.py <codex out dir>` runs Codex 3 at a time (~2 min each), output `photo.png` in each folder.
- Prompt rules (approved): short, "Image 1 is my 3D render of … Make this exact image look like a real photograph… same camera, framing, design, materials, colours, lights. Do not add, remove, move or restyle anything." Images 2–4 = finished photos from earlier projects for **photographic level only** (PROJECT: `VISUELS\CHATGPT\COURS\02…`, `CARDIO\04…`; Hyundai: `D:\BAAK_CHARGUIA\RENDU_A_TRAITE_PROMPTS\_RESULTS_FINAL\HYPERREAL_1_ARCH_11_SOCIAL_HUB_LOUNGE.png`). Bright daylight, real people absorbed in the activity, machines matt black. Long style prompts and dark moods gave "AI slop".
- Quality target from Pinterest (07/11, "take them as quality level target"): high-end studio images with real daylight and real people, kept in `RENDUS CODEX - 07 11 2026 V2\_ESSAI_PINTEREST\_refs_pinterest\` (pin_03 people on reformers, pin_07 bright studio, pin_11 warm studio). Pass them as images 2–4 for level only; the prompt bans their arches, sage/beige palette and logos.
- 3D errors the user marks on a render can be fixed in the prompt instead of Max ("fix it in your prompt", 07/11): add a `REMOVE THESE 3D ERRORS (the only changes allowed)` paragraph describing each one by place and look (e.g. a thin horizontal bar across the glazing, a long diagonal pole), and say "Apart from the errors listed below, do not add, remove…". Example: `_ESSAI_PINTEREST\HYB_0711_PIL_5_v2\PROMPT.txt`.
- Hyundai set per view: hero + cinematic shots from the finished hero ("cinematic zoom… other cinematic shots… angles"): `PY S/cinematic_shots.py <hero dir> "<room>" [refs]` waits for `photo.png`, then runs an 85 mm zoom, a low-angle detail (never cutting through the head) and a telephoto side angle in parallel (subfolders `CU_*`, same self-check brief, refs default to `codex_brief.REFS`); then `S/finish_hyundai_ref.py` style pass (white balance if R/B > 1.5, lift if p99 < 212) into `_RESULTS_FINAL`.
- Files go under `D:\DCE SITE\ARCHITECTURE\VISUELS\` (never G:). CGI renders never go into decks; only the Codex photos.

## 4. Recovery if Max dies
`PY S/extract_calls.py <session.jsonl> <UTC since> outdir` lists every Max MCP call in order with OK/FAIL and saves inline scripts; replay only the final versions of validated work (not intermediate variants), e.g. `D:\PROJECT_work\recover_0711\replay.ms`. If the MCP is down, the user can run the replay script from Scripting → Run Script.
