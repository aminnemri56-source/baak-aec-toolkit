---
name: archviz-shots
description: Create good archviz cameras for a 3ds Max / Vantage scene without opening Max, colour-correct every rendered view on its own, and prepare the best possible input image for Codex. Use whenever the user asks for cameras, camera angles, general views, frontale or oblique views, clipping, "show the full space", "not stretched", colour correction of renders, "best Codex input", or wants renders prepared before Codex, even if they only say render. Works with vantage-codex-render (export, launch, Codex jobs) and camera-brief (per-view notes).
---

# Archviz shots: cameras, per-view colour, Codex input

Three scripts, in pipeline order. `PY` = `C:\Users\sbs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -I` (numpy + PIL). `S` = this skill's `scripts` folder. Everything runs without 3ds Max: it reads the `.vrscene` that is exported for Vantage anyway, so cameras can be made while Max is closed to free the GPU.

## 1. Cameras: `room_cameras.py`

```bash
PY S/room_cameras.py scene.vrscene rooms.json out_dir TAG
```

It turns every surface of the scene into a point cloud and looks through each candidate camera, so a view never starts in a wall, shows the back of a wall or looks out of the room. It writes `cams_TAG.txt` and `CAMS_TAG_n.jpg` (what each kept camera sees, as shaded depth). Read those sheets before any render: they are crude but they show a blocked or empty frame at once.

`rooms.json`: `{"mode": "general", "region": [[xmin,ymin,zmin],[xmax,ymax,zmax]], "rooms": [{"name": "HALL", "seed": [945,-760], "floor": 300.7, "ceiling": 520, "views": 4}]}`. A room is a `seed` (any free point of its floor: the walls are found by themselves) or explicit `min`/`max` corners. Give explicit corners when hanging things (hammocks, curtains) could be taken for a wall. Working example: `D:\PROJECT_work\cams_mezz\cams_1111\rooms_general_50.json` (19 rooms, 50 views, 20 s).

**Mode `general`: views of the whole room. This is the user's default** (11/11/2026: "50 general cameras, frontale / oblique, try to show the full space, use clipping, not stretched, clear frame no cut things, 25 mm to 45 mm, you can change resolution and ratio"):
- FRONTALE (one-point, on an axis) and OBLIQUE (45 degrees from a corner).
- The camera stands outside the room and the near wall is removed by camera clipping, so a normal lens (25 to 45 mm) shows the whole room without wide-angle stretch.
- A clear frame: the frame is set exactly on a rectangle of the cutting plane that no surface crosses, so no wall, floor, ceiling, locker or piece of furniture shows a section. The user rejected the first version because cuts appeared; the report line must say `cut invisible` for every view.
- Ratio and resolution follow that rectangle (a corridor becomes a vertical frame, a wide low room a 2.4:1 frame), about 3.8 megapixels.
- Camera level at the middle of the clear rectangle.

**Mode `types`: cameras inside the room, no clipping**, one or two per type: LARGE corner view 24-28 mm, AXE one-point, BAS low hero at 0.62 m, HAUT elevated three-quarter, TELE 70 mm, CINE 2.39:1, VERTICAL 4:5, PLAFOND looking up at a feature ceiling (`"ceiling_feature": true`), DETAIL at 85 mm on each `"points": {"NAME": [x,y,z]}`. Refused positions are counted by reason (no room for the camera, foreground too close, centre blocked, looks out of the room).

Do not use `RayMeshGridIntersect` in MaxScript for this: on the big PROJECT scene it returned no hit for most rays once several hundred objects were in the grid, and `intersectRayScene` costs about 0.8 s per ray.

## 2. Into Vantage: `cams_to_vantage.py`

```bash
PY S/cams_to_vantage.py cams_TAG.txt base.vantage scene.vrscene out.vantage render_dir --prefix HYB_1111_ --group "NAME" [--samples 1000] [--wb 4800]
```

Replaces all cameras of the project by the list, in one group, one render task per camera, with `clip_enabled` / `clip_near` and each view's own resolution. `base.vantage` is the project's last good project (its colour pipeline and material edits are kept). Load it into a running Vantage with the command API (`loadConfig`, port 20702); the API cannot start the queue, the user clicks Start. Export, GPU rules and launch are in `vantage-codex-render` (save the .max first, Max closed while Vantage renders on the 12 GB card).

## Hidden fill lights: `fill_lights.py`

```bash
PY S/fill_lights.py out_dir/rooms_TAG.json scene.vrscene scene_L.vrscene lights.ms [intensity 10] [spacing 220]
```

When the user asks for light everywhere with nothing visible ("put some lights everywhere to keep the space lighted, lights should be hidden", 11/11/2026): a grid of 50 x 50 cm rectangle lights 16 cm under each room's ceiling, pointing down, `invisible=1` and off for reflections, warm white. It writes them into a copy of the `.vrscene` (no need to reopen Max) and writes the same lights as a MaxScript to run in the `.max` later, so the next export keeps them. `rooms_TAG.json` is written by `room_cameras.py`; add `"fill": 0.5` to a room that already has daylight, `0` to skip one. Vantage has no command to open another scene: close the Vantage you started and launch it again on the new file. Only do this on the user's order: lights are otherwise not ours to change.

## 3. Colour-correct each view: `grade_views.py`

```bash
PY S/grade_views.py <renders dir> <codex input dir> [--watch N] [--since EPOCH] [--overrides file.json] [--only A,B]
```

Each render is corrected on its own, because rooms differ (warm lamps on the mezzanine, daylight in the salle de cours) and one global setting leaves half the views with a cast:
1. white balance from the view's own least-saturated bright surfaces, at 65 %, limited to -20 / +25 %, skipped when the view has no neutral surface (an all-terracotta room keeps its colour);
2. exposure: bright surfaces to 78 %, never burning a pale floor or a window to lift the rest, dark views lifted in the middle instead;
3. highlights rolled off on luminance and out-of-range colours brought back along their own hue, so a lit orange never turns yellow (brand orange #EE5A1E, hue 17); the balance is halved by itself if it moves the oranges by more than 5 degrees;
4. a small toe so black machines and lockers keep their shape; light sharpening.

It writes `<name>.png` (what Codex receives), `grade_report.json` and `_SHEETS/GRADE_SHEET_n.jpg` (before | after with the values). Read the sheets and the verdicts: RE-RENDER BRIGHTER, BURNT AREAS, TOO BLACK, ORANGE READS YELLOW / RED, STRONG CAST, SOFT, NOISY. A view with a verdict goes back to Vantage rather than to Codex. `--watch N` grades each render as soon as Vantage has written it, so Codex can be fed from the output folder. Per-view corrections: `{"VIEW": {"ev": 0.3, "warm": -6, "wb": false, "skip": true}}`.

## 4. What makes a good Codex input

Codex keeps what it can read and invents what it cannot, so the input must be easy to read:
- bright and neutral, never a dark mood; blacks with detail; no burnt window (the exterior must stay readable or Codex invents one);
- straight verticals, normal lens, nothing cut by the frame or by a clipping plane;
- no bloom, vignette, chromatic aberration, depth of field on wide views or noise: Codex adds its own photographic character and amplifies baked effects;
- PNG, about 2400 px on the long side, any ratio;
- only new renders: the user refused old images as input ("too bad") even for tests, so test the scripts on the current batch;
- then one camera note per view (`camera-brief`) and the Codex jobs (`vantage-codex-render`, section 3), fed from the graded folder, not from the raw renders.

## Report

Say how many cameras per room and of which kind, name any view whose cut shows or whose verdict is not OK, and send the camera sheet or the grade sheet rather than describing it.
