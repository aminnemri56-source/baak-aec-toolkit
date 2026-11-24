---
name: render-enhancer
description: Turn a 3D render (Vantage, V-Ray, Corona, D5) into a final real-photo image with Codex and correct it in rounds of review comments in the same Codex session until it is clean, then make cinematic shots (85 mm zoom, low-angle detail, telephoto side angle) and deliver the final set. Use whenever the user wants a render enhanced, made photoreal, "Hyundai level", "pass to Codex", "make corrections with Codex using comments", "give me the final result", marks errors on a Codex photo, or asks for cinematic zooms or other angles of a render.
---

# Render enhancer

The user's rule (07/11/2026): "make correction with him using comments and give me the final result". Codex makes the photo; Claude is the art director: reviews each result, writes numbered correction comments, sends them to Codex **in the same session** (it keeps its context), and repeats until the photo is clean. Only the final result is shown, with what was corrected. Start Codex without asking; stop at once on "stop". Keep usage low and reports short.

`PY` = `C:\Users\sbs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -I`. `S` = this skill's `scripts`. `V` = `C:\Users\sbs\.claude\skills\vantage-codex-render\scripts` (renders, briefs, shots).

## The workflow ("BUILD A WORK FLOW", 07/11)
The saved workflow **render-to-photo** (`C:\Users\sbs\.claude\workflows\render-to-photo.js`) runs the whole pipeline with one finisher agent per view:
1. Wait until no other job is running on the view (`S/wait_view_idle.py`).
2. Camera note.
3. Hero (`S/hero_one.py`, safe in parallel).
4. Strict full-detail review against the room rules, with comment rounds until the score is at least 8.5 and there is no hard fault.
5. Shots, shot review and correction.
6. Filing into `_FINAL`.

A delivery agent then builds `_SHEET_<ROOM>.jpg`.

Run it with `Workflow({name: "render-to-photo", args: {out: "<codex out dir>", views: ["HYB_..."], extra: "<any new rule>"}})`. Add every new user ruling to its RULES block and to this skill.

## 0. Camera notes first (skill `camera-brief`)
Before building jobs for several views of a room, read every render and write a THIS CAMERA SEES / NOT IN THIS VIEW note per view in `fixes.json`. Run `camera-brief/scripts/check_view_notes.py` and never start Codex while it fails. The 07/11 RPM batch broke this rule: the screen was added in the wrong place and the typographic wall became the 5D screen ("WHEN YOU CHANGE THE CAMERA CHANGE YOUR PROMPT").
Never call a hero final from thumbnails: review each one at full detail with `review_sheet.py` ("BRO NO YOU MADE TOO MUCH FAULTS").

## 1. Hero photo with the full brief
- `PY V/make_codex_jobs.py <renders dir> <out dir> [fixes.json]` → one folder per view with `render.png` + `PROMPT.txt` built by `V/codex_brief.py`.
  - The brief locks the inventory, the camera and the colours.
  - **Machines are untouchable.**
  - Only the listed changes are allowed: realism, a real outdoor view, people, and removal of the 3D errors listed in `fixes.json`.
  - People do real exercises for the room.
  - Codex must self-check against the checklist (up to 3 attempts) and write `INVENTORY.txt` + `CHECK.txt`. The checklist covers framing, inventory, errors, colours, light and exterior, people, HUMAN, GRAVITY, machines, text, FINESSE and format.
- Errors the user marks on a render go in `fixes.json`: `{"VIEW": {"remove": ["where + what it looks like"], "notes": ["view-specific instruction"]}}`. A machine or machine part is never a `remove`: describe it in `notes` ("part of a reformer, keep it, nobody holds it").
- Run (cwd = the view folder): `codex exec --skip-git-repo-check -s workspace-write -i render.png -i <level refs…> -i <exterior photo> -o result.md - < PROMPT.txt > codex.log`.
  - **Level refs** = `codex_brief.REFS`: 3 images from the Behance ROOF GYM project the user gave, in `D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_NIVEAU_BEHANCE_ROOFGYM\`. The user wants "THIS LEVEL OF FINESSE, CLEARNESS".
  - The Pinterest pins were dropped: they are AI-looking and gave a cartoonish result.
  - For another project, ask the user for their level reference (a Behance or Pinterest link) and download 2–3 images.

## The look and the people (the user's rulings, 07/11)
- **Finesse and clarity, never cartoonish** ("STYLE TOO CARTOONISH", then the ROOF GYM link).
  - The look: crystal-clear, crisp, refined, soft diffuse daylight (no harsh dappled sun all over the floor), a calm and slightly desaturated natural palette, matt deep orange, believable materials, and a bright, soft, hazy exterior exposed for the interior.
  - Banned: oversaturation, neon orange, glow, bloom, HDR, plastic skin, oversharpening, heavy grain.
  - Codified in `codex_brief.PHOTO` and the FINESSE checklist item.
- **Think as a human** ("BE MORE HUMAN THINK AS HUMAN"): one candid moment in a real club.
  - Every person is a different individual: no clone of the same woman, mixed ages, body types, skin tones, hair and outfit colours.
  - Not everyone holds a peak pose: someone rests, someone adjusts a strap, the coach corrects a posture.
  - A water bottle or towel by a machine is allowed.
  - Codified in `codex_brief.HUMAN` and the HUMAN checklist item.
- **It is a class, with exact positions** ("PEOPLE ARE NOT IN GOOD POSITIONS"):
  - Everyone follows the coach and does the same exercise in sync, one per reformer, bike or mat, aligned with it and facing the coach.
  - Nobody sits on a frame edge, lies across a machine, sits on the floor or faces the wrong way.
  - Reformer anatomy and the correct body placement are spelled out in `codex_brief.POSITIONS`.
  - The "candid" idea of people doing different things made it worse: variety comes from the individuals, not from what they do.
- **Codex sees the equipment and the positions** ("SHOW MACHINES TO CODEX [SO IT] UNDERSTANDS", "CHECK PINTEREST FOR POSITION AND PUT THEM IN THE INPUT CODEX"). `codex_refs.ROOM_REFS` attaches, per room:
  - Official photos of the real machine, a Technogym Reform or Group Cycle, in `VISUELS\_REF_MACHINES\`.
  - Real-class position photos, in `VISUELS\_REF_POSITIONS\`.

  Attach order: render, level refs, machine refs, pose refs, exterior. `make_codex_jobs.py` does it.
- **Show the machines**: the machines are the subject.
  - The machine nearest the camera stays empty and fully visible, and about half the machines stay free.
  - No person hides a machine.
  - Fewer people, well placed.
- **Hidden light** ("HIDDEN LIGHT", "CEILING PILATES"): every concealed LED line in the render stays on, warm and visible. The Pilates ceiling coffers between the black beams glow, brighter at their edges. This is `codex_brief.HIDDEN` and the PIL design text.
- **Walls and screens stay** ("FOR THE RENDERS THERE IS A SCREEN YOU REMOVED IT", "BRO THERE IS WALL"):
  - The exterior photo appears only through real glazing.
  - Codex had turned the RPM video screen and wall into a window onto the boulevard.
  - Every screen stays on with its picture, and no wall, panel or blind becomes a window. This is `codex_brief.SCREENS` and its check.
- **Validated esquisses go in as design references:** `codex_refs.ROOM_REFS[room]["design"]`. The RPM wall is esquisse 5D: the orange perforated screen with RIDE. SWEAT. REPEAT. cut through it, plus the vertical LED video screen. Codex builds the design, never the drawing style.
- **A room can keep its own approved style** ("BRO WE HAD BETTER RENDERS FOR SALLE DE COURS", "MATCH THEM STYLE"):
  - Set `codex_refs.ROOM_REFS[room]["style"]` (earlier photos the user liked) and `["light"]`. Those images then replace the level refs and the diffuse light.
  - Salle de cours: warm golden sun streaming across the oak in long patches, glowing terracotta coffers, honey oak, rich warm contrast. Refs are in `VISUELS\_REF_STYLE_SDC\`.
  - Before regenerating a room, compare with its earlier versions; if an older one was liked, keep its look.
- **Bright, well-lit spaces** ("IT SHOULD BE MORE LIGHTED SPACE", "ITS TOO DARK"): generous exposure, the room fully lit, open shadows, no dark corners. The warm sun patches stay, but the room around them must not go gloomy. This rule opens `codex_brief.PHOTO` and the SDC light. Check brightness in every review.
- **Visible light sources, clear glass, clean model** ("LIGHT SOURCE NOT SEEN", "FIX THE DARK GLASS", "TOO MUCH BAD MODELING ISSUES"):
  - No sun patches unless a window that can cast them is in view or just off-frame on that side.
  - Glass partitions are clear, never smoked.
  - Columns are straight cylinders with regular perforations, and mats are separate and flat.
  - No ceiling joint lines; nothing warped or merged.
  - This is `codex_brief.SOURCES` and its check. When the user prefers an earlier round ("keep this version's colour and light"), copy that `photo_rN.png` back to `photo.png` before the next `codex_comment.py` round and say "start from the attached image".
- **One-way films** ("THIS VISUAL IS ONE WAY SO IT SHOULD APPEAR ONLY FROM OUT"): a visual printed on a one-way vision film (the yoga / PROJECT visual on the salle de cours glazing) is never seen from inside. Inside, the glass reads slightly darkened with a fine dot screen, and the exterior shows softly through it. The render shows the print; correct that in every interior view.
- **RPM finishes:** the ceiling lattice is dark brushed bronze, contrasted, with a little reflection, never orange wood. The walls are black and orange only, never brown, beige or yellow.
- **Nothing floats** ("CHECK IMAGES THERE IS NOTHING COULD BE FLOATING"): every foot, knee, back and hand rests on the floor, a carriage, a mat or a bar, and every ball, roller, block and ring rests on a shelf, each with a real contact shadow. This is the GRAVITY item, in heroes and shots. Check it in every review, zooming in on contacts.

## 2. Review (Claude), then comments (Codex)
- `PY S/review_sheet.py <view dir>` → `_REVIEW_photo.jpg`: render | photo on top, the photo's four quarters below at full detail. Read it and `CHECK.txt`. Do not trust Codex's own PASS marks; look.
- Review list. These faults were each rejected by the user before:
  - A machine changed, moved, simplified, added or removed.
  - An accessory recoloured (beige turned orange).
  - Orange turned yellow.
  - A 3D error left in (a bar across the glass, a stray pole).
  - Someone holding a machine part as a rod.
  - A fake exercise, or a body not touching the machine.
  - Bad hands or limbs.
  - A head cut by the frame.
  - People at the wrong scale or place: seen through shelving or glass so they seem to stand inside a cabinet or on a shelf (PIL_6, 07/11).
  - An invented object, sign or text.
  - A wrong exterior. PROJECT's real site is Guéliz-Hivernage in Site: the building's own terrace, then a palm-lined avenue and modern terracotta-pink ochre buildings under a deep blue sky ("FIX THE EXTERIOR ENVIRONMENT", 07/11). Faults to catch:
    - generic white or grey European blocks;
    - a postcard Site with a minaret, medina walls or water.

    The project's exterior lives in `codex_brief.EXTERIOR` (words) and `codex_brief.EXTERIOR_IMG`, the photo the user picked: `VISUELS\_REF_EXTERIEUR\exterieur_boulevard_site.png`, a pink Site boulevard from upper-floor height. Every job attaches that photo LAST. To fix an existing photo, pass the photo as the extra image: `codex_comment.py <dir> ext.txt <EXTERIOR_IMG>`. For a new project, ask the user for their exterior photo.
  - A dark or AI look, a colour cast, or a cyan sky.
  - A cartoonish look: oversaturated colour, glowing orange, a postcard-sharp saturated exterior, hard sun patches everywhere, plastic skin.
  - Clone people (the same face or hair twice), everyone in identical black outfits, everyone frozen at the same peak pose.
  - RPM rejects ("REDUCE PEOPLE… DON'T CHANGE MACHINE PLACES", "KEEP LIKE 9 PEOPLE", "ONE DIRECTION… IF NOT YOU ARE WRONG"):
    - not exactly 9 riders;
    - a bike moved, added or turned compared with the render;
    - riders or bikes facing different directions.

    Every bike and rider faces the one direction the bikes have in the render. Count and check direction before filing.
  - In a shot, a person doing something other than their exercise in the hero. Twice on 07/11 the low-angle shot had a yoga student grabbing the hammock handles; the person must keep the hero's pose or the class's next pose, in sync.
  - Anything floating: a foot above the carriage, a body not resting on its machine, a ball in the air, a missing contact shadow.
- **Critique like an art director before showing anything** ("CRITIQUE YOUR RESULT", 07/11): give a score out of 10, what works, then the numbered faults, and send those faults to Codex as the next round. Faults found on SDC_4:
  - A staged row of mannequins at the back while the front mats are empty.
  - The teacher smiling at the camera.
  - Garbled letters on a screen or visual.
  - Light panels as dead white rectangles instead of glowing diffusers.
  - No contact shadows, so people look pasted in.
  - Props that look like plastic toys.
  - Flat, even CG light with no falloff.
  - The brief contradicting the render ("orange mats" when the render's mats are grey): the render wins, fix the brief.
- Write `comments_rN.txt`, one line per fault: **where** (left/right, front/back, which object or person) + **what is wrong** + **what it must be**. Short, concrete, no restyling, nothing about what is already right.
- `PY S/codex_comment.py <view dir> comments_rN.txt` runs the round:
  - It takes the session id from `codex.log` and backs up `photo.png` → `photo_rN.png`.
  - It resumes the same session with the current photo attached and logs `codex_rN.log`.
  - Codex edits, re-checks, overwrites `photo.png` and appends to `CHECK.txt`.
  - Run it in the background (~2–4 min).
- Review again. **Up to 3 rounds.** If a point survives 2 rounds, either accept it (say so in the report) or regenerate from the render with that point added to `fixes.json`. If a round makes the photo worse, keep the previous `photo_rN.png`.

## 3. Cinematic shots from the final hero
- `PY V/cinematic_shots.py <view dir> "<room>"` → `CU_85mm_zoom`, `CU_low_detail`, `CU_side_tele` subfolders, run in parallel with the same self-check. It waits for `photo.png`, so start it only once the hero is final.
- Review each shot like the hero (`review_sheet.py <CU dir>`; there is no render there, so it shows the photo and its quarters) and correct it with `codex_comment.py <CU dir> …`. Each shot has its own session.

## Many views (the general case: "generalise this solution", 07/11)
- Stage every render as `<out>\_renders\<VIEW>.png`, put per-view errors in `<out>\fixes.json`, then `PY V/make_codex_jobs.py <out>\_renders <out>` and run `PY V/run_codex_jobs.py <out>` in the background (3 at a time; views that already have `photo.png` are skipped, so a finished hero can be copied in first).
- Rules that apply to a whole room go in `codex_brief.ROOMS[room]`, not per view:
  - `add` = a design addition the user asked for. Example: the PROJECT Pilates storage unit gets clear glass doors wherever it is in view.
  - `remove` = a 3D error that recurs, written as "if visible: …". Example: the bar across the Pilates glazing.
  - For another project, add its rooms there (the key is a substring of the view name), with its own `REFS`.
- Bulk review: `PY S/pairs_sheet.py <out>` makes `_PAIRS_n.jpg` sheets of render | photo, 4 views per sheet. Spot the faulty views there, then deep-review only those with `review_sheet.py` and correct them with `codex_comment.py`. Up to 3 views can be in correction rounds at once.
- Then run the shots for every final hero, one view after the other (each runs its 3 shots in parallel). Bulk-review them with `pairs_sheet.py <out> CU_85mm_zoom/photo.png` (and the other two shot names), and correct the faulty ones.

## 4. Deliver
- Copy the finals to `<out dir>\_FINAL\` (`<VIEW>_hero.png`, `<VIEW>_<shot>.png`) and make one sheet: render, final hero, the shots. Send it with SendUserFile.
- Report in a few lines what Codex corrected in each round, and anything accepted as is.
- Never put CGI renders in decks; only the final photos.

## Esquisse overlay check and final grade (08/11/2026)

The architect said "you didn't follow the esquisse", then "over exposed, bad contrast, colours bad". Two tools answer that.

**Follow the esquisse, measurably.** When a room has a camera esquisse (same framing as the render, for example `_REF_STYLE_SDC\ESQ_CAM\ESQ_SDC_n.png` drawn by `D:\PROJECT_work\esq_sdc_cam\esq_sdc_cam.py`), check every photo against it:

```bash
PY S/esq_overlay.py <view>/photo.png <ESQ.png> <view>/_OVERLAY.png --side <view>/_OVERLAY_SIDE.jpg
```

- The green lines are the esquisse. Every niche frame, ball column, flat ceiling panel and column must sit on its line.
- Attach `_OVERLAY.png` to the comment round ("image 2 is your photo with the esquisse outlines in green: move each element onto its outline") and name each fault by position (count niches from the frame edge).
- The esquisse must itself be right before it goes to Codex: it hides what the wall face hides, and niche insides read lit, as in the approved photos. "IT WILL MAKE THE CODEX MAKE FAULTS".

**Exposure and colour: one measured grade, last.** Codex drifts tone in every round, so it is never asked to push brightness or saturation. After the last round, every image of a set gets the same grade, measured on the approved level photos (the cardio renders in `_REF_NIVEAU_CARDIO`):

```bash
PY S/photo_grade.py <out_dir> --ref <level refs...> --in <photos...> --lum 0.45 --col 0 --sat 0.9
```

- It matches the luminance percentiles (exposure and contrast) with a soft highlight roll-off.
- With `--col 0` it scales light in linear RGB, which keeps every hue: the orange ceiling stays orange. Darkening in Lab turned it red.
- Option D (`--lum 0.45 --sat 0.9`) was chosen on SDC_7 and SDC_9.
- Then "THIS BUT MORE LIGHTED": add `--gain 1.7`. It raises the exposure under a soft shoulder, so whites never blow. The set grade is `--lum 0.45 --col 0 --sat 0.9 --gain 1.7`.

## Speed: shots in parallel, never one by one (08/11/2026)

The user expects a batch of shots in about 15 minutes ("THEY SHOULD BE READY AT 15 MINS"). A workflow whose agents correct shots one after the other took 78 minutes and a network cut killed 5 of its 7 views. `scripts/rollout.py` with `"hero": null` ran 14 shots at once in 10.5 minutes (188 to 658 s each), one round each, with the hero, the elevation and one level reference attached. Then grade and file with one script. Use agents for review of heroes; use rollout for shots. A fault fixed on a hero (for example a panel turned into glass) must be named in the shot comments too: the generic comment left it on two SDC_7 shots.
