---
name: drawings-from-3d
description: Turn the 3D project (3ds Max scene via its Vantage .vrscene export) into detailed, high-quality AutoCAD drawings - interior elevations (all walls of a room and its sub-spaces), sections/coupes and later plans - with exact hidden lines computed in Blender, line weights, black cut poché, flat render-palette finish colours, measured levels, red BAAK dimension chains, numbered finish callouts, BAAK charter layers and the BAAK A1 cartouche, then verify every line against the hero renders through their own cameras. Use whenever the user asks for élévations, élévations intérieures, coupes, coupes aménagées, détails, plans or "drawings from the 3D", "turn the 3D into plans/elevations", "better quality drawings", "verify the lines with the render / hero", or names a room/space to draw from the 3D, even if they only say "draw the walls" or "elevations of the vestiaire".
---

# Drawings from the 3D

Built 14/11/2026 for PROJECT ("search skills to turn our 3D project into detailed plans elevations with better quality of drawing", "YES BUILD IT"). Test result: the four interior elevations of the women's changing room (vestiaire femmes) on one A1 sheet, `D:\DCE SITE\ARCHITECTURE\DWG\Salle de sport Site - ELEVATIONS INTERIEURES VESTIAIRE FEMMES - DU 14 11 2026.dwg`. Job file: `C:\Users\sbs\dwgwork\d3d\job_vf.json`. Copy that job for the next room.

## Why it is built this way

Earlier routes failed for reasons the user stated:
- Max's DWG export gives meshes, not drawings ("NOT LISIBLE").
- Extruded plan blocks don't look like the render ("NO ELEMENT IS SIMILAR TO WHAT WE SEE AT THE RENDER").
- Our own Python depth-buffer engine (dce_mezz/mz_items.py) took minutes per coupe and approximated the edges.

This skill keeps what the user validated on the D-D coupe (12/11), with one change: Blender's Line Art computes the visible edges exactly in seconds. The validated look is:
- elements exactly as rendered;
- a flat colour per material in the render palette;
- dark cut fills;
- levels and dimensions;
- esquisse first, then DWG at the same quality.

Respect these rulings. Each comes from the user:
- **Every sub-space of the room** ("some sub spaces are not showen"). Draw all walls of the room, including niches, déshabilloirs, doors and side cabins. The frame runs to the outer faces of the cut side walls. Don't stop at the main furniture run.
- **Verify on the hero images** ("not this the hero ones"). Use the final Codex heroes, not the raw Vantage frame. Report any line with no edge under it.
- Draw outlines, not mesh triangulation, and work element by element or room by room. See [[max-to-cad-outlines-by-element]].
- Use the BAAK charter layers, dimension styles and cartouche, and never invent a layer. See [[baak-charter-layers-legends]] and [[baak-autocad-polylines-blocks]].
- Walls go to the slab soffit; report any void above a wall head. See [[walls-to-slab-soffit-default]].
- Deliver under `D:\DCE SITE`, under a new name. Never write to G: and never overwrite.

## Pipeline (one job = one sheet, about 2 minutes)

```
python -I scripts/pipeline.py job.json            [--only views|sheet|verify]
```
Run it with `C:\Users\sbs\dwgwork\pyenv\Scripts\python.exe`, which has numpy, shapely, PIL and pdfplumber. Blender 5.2 runs headless; AutoCAD 2027 runs as the core console. Neither touches the user's open apps.

1. **extract_vrscene.py** reads the .vrscene without Max.
   - It cuts out the room box: visible nodes, world transforms, per-face materials (MtlMulti).
   - It converts to DWG metres with the project transform. z is measured from the level's finished floor.
   - It drops the profile's `ignore` objects and zero-area triangles.
2. **hlr_blender.py** builds the meshes in Blender for each view.
   - Orthographic camera, with the near clip plane on the cut plane.
   - Line Art: contours + creases / material borders / intersections, with each stroke's owner object.
   - A flat id image: one colour per (object, material) pair.
3. **draft.py** turns the strokes into 2D drawing primitives.
   - Line weights: cut 0.50/0.35; profiles 0.25 (0.18 far); details 0.13; small parts 0.09; grey beyond 2.5 m.
   - Duplicates are merged and weaker lines give way to stronger ones.
   - Cut fills come from the plane section. Slab bands come from the levels, because the slabs are open boxes.
   - Finish fills come from the id image, in the render palette.
   - Levels are measured: floor, HSP (lowest visible ceiling) and slab underside.
   - Dimension chains run along full-height and full-width divisions.
   - Numbered callouts, title and sub-title.
   - Layer per object comes from the profile rules (lockers → BAAK MENUISERIE VESTIAIRES, doors → BAAK - MENUISERIE, …).
4. **compose.py** places the views by rows, numbers the callouts across the sheet, and adds REPÈRES, LÉGENDE and À NOTER. It checks the A1 fit.
5. **make_sheet.py + build_sheet.lsp** run AutoCAD.
   - Base: `assets/base_baak.dwg`, the empty BAAK base with 141 charter layers and the BAAK / Detail BAAK dimension styles.
   - Entities are entmade with true colour and lineweight. Dimensions use Detail BAAK on BAAK - COTATION (cm, 7 cm text).
   - The cartouche layout CAH-08-01 is imported from `assets/cartouche_a1.dwg`; title, document n°, level and date are filled in.
   - One locked viewport; PDF plotted with acad.ctb on ISO full bleed A1.
6. **verify_render.py** loads the same 3D through each hero camera (`cams_G33.txt`: position, target, horizontal FOV, resolution, clip) and draws Line Art in cyan over the hero.
   - Look at every overlay.
   - A line with no edge under it means an object the render doesn't show: a stray or parked piece, or a different export.
   - An edge with no line means a Codex addition or an object missing from the export.

## Writing a job

Start from `C:\Users\sbs\dwgwork\d3d\job_vf.json`.
- **source.** Use the .vrscene the heroes were rendered from. For the mezzanine that is `VISUELS\VANTAGE\Gym_Vantage_PREREVIT_v39_MEZZ_1ER_1211.vrscene`. The FULL_COUPES export of 13/11 holds pieces the renders don't show.
- **room.box.** The room extent plus about 0.5 m, so the walls are included.
  - Room boxes are in `D:\PROJECT_work\cams_mezz\cams_1111\general_v33\rooms_G33.json`, in 3D cm. Convert: x = (x − 18549)/100, y = (y + 9239)/100.
  - Probe the walls by cutting the geometry: see `dwgwork\d3d\probe_room.py`.
- **views.**
  - One per wall, N/E/S/W. `p0`/`p1` give the cut line, which sets the frame ends; `look` is the direction looked at.
  - Put the cut plane 0.8–1.2 m in front of the wall, clear of loose furniture such as a central bench. Depth is about 2 m.
  - Run the frame to the outer face of the cut side walls. Include sub-spaces at the ends (déshabilloir, doors, sauna front).
  - Scale: 1/25 fits four walls of a 7 × 5 m room on A1 (drawing area 726 × 566 mm). Use 1/20 for one or two walls.
- **level.** `{"name": "MEZZANINE", "elev": 3.00}`. Project transforms and levels are in `profiles/project.json`.
- **verify.** The camera list, a regex for the room's cameras, and the hero path pattern.
- **dwg, pdf.** New names under `D:\DCE SITE\ARCHITECTURE\DWG` and `...\PDF\<SET NAME>\`.

## Before delivering

- Open each `out_<view>/preview.png` and the plotted PDF.
  - The preview uses PIL fonts, so accents show as boxes there; AutoCAD is fine.
  - Check the levels (HSP and HSD as in the project notes), the cut fills, the frame ends and the callouts.
- Look at every verify overlay and say what differs.
- Report voids above wall heads (niveaux sous dalle) and stray objects as points to check. The 3D phase is over, so don't propose a 3D fix unless asked; see [[project-3d-finished-dce-phase]].
- Send the user the PDF and the overlay sheet.

## Traps met on the test

- **Slabs are open boxes** (MEZZ_GREEN_Floor_North, MEZZ_GREEN_Slab_600 miss faces), so their cut never closes. draft.py draws slab bands from the measured levels: floor at least `floor_slab` 0.23, slab from the soffit to its top. Struct nodes fall back to the hull of their cut.
- **Stray degenerate objects** (Line766: a zero-area line at 1.895 m) drew a line across the lockers. Zero-area triangles are dropped and Line Art's loose edges are off.
- **Don't add the 1er slab pieces to `ignore`** (Object3052 at 525 cm, Line333). They close the ceiling beyond the raised green zone; without them the view sees through to glass.
- **The HSP must come from a visible ceiling element** (id image), not from geometry behind walls such as the orange sheet ceilings of the circulation.
- **Cut objects take their colour from their main material by area.** By triangle count, the locker handles won.
- **Walls take their material colour first** (WALL_Terracotta_ClayPlaster is the terracotta end wall). Plain wall colour is only used when the material says nothing.
- **"Noir mat" fill is (70, 72, 76)** so the 0.13 door joints read. The cut fill stays (40, 40, 42).
- **The preview paints hatch holes white**; the DWG doesn't. Accents in the data are converted to MTEXT `\U+XXXX`. draft.json is UTF-8.
- **Known void (north-east of the vestiaire femmes):** above the déshabilloir soffit (z 2.27) up to the slab, between the edge beam (x −185.93) and the east wall.

## Single elements (stairs, joinery): second test, 14/11

ES-01, the helical stair, was drawn on one A1 sheet at 1/50: south and west elevations, section A-A through the core, plans at RDC +1,00 / mezzanine +4,00 / 1er.
- DWG: `D:\DCE SITE\ARCHITECTURE\DWG\Salle de sport Site - ES-01 ESCALIER HELICOIDAL - DESSINS 3D - DU 14 11 2026.dwg`
- Job: `C:\Users\sbs\dwgwork\d3d\job_es1.json`

What the stair needed:
- **`room.include`** isolates the element: a regex on "layer name", here `STAIRS_BlackOrange|TOUCH_Stair_Guard`. TOUCH_ is no longer excluded by default.
- **Views:** `"slab_bands": false`, because slab bands would cover the slab opening (trémie). `"marks": [[z, "text"], …]` gives the level marks, and the vertical dimension chain follows them.
- **Plan views work:** `"kind": "plan"`, `"cut_z"`, frame from p0/p1. Parts below the cut turn grey beyond 2.5 m.
- **At 1/50 the BAAK dimension style is used** (`dimstyle_plan`); Detail BAAK text would be 1.4 mm.
- **Cut fills use the even-odd rule.** Closed loops such as the curled ends of the perforated skin stay rings instead of black discs.
- **Regex trap:** "F**light**" matched the LED rule, so the flights turned LED-yellow on BAAK - ECLAIRAGE. The LED and Light rules now use `(?<![Ff])Light`.
- **Check figures:** the 3D gives 18 risers to the mezzanine and 15 to the 1er, at 16.7 cm (same as CAH-05).
- **No hero shows ES-01.** The DG, circulation and vestiaire heroes facing it have walls in front, and their overlays match. The 13/11 RPM heroes used a camera list we don't have (the cams_V39_1ER overlay is offset), so don't use it. When no hero sees an element, say so, and check against the 3D facts instead.
- **`verify.box` / `verify.z`** extract a wider zone without the element filter, so walls hide things as in the photo. Clip-plane lines are off in the check.

## New project

Copy `profiles/project.json` and change:
- the transforms and levels;
- the palette (regex on material + object name → colour + legend label);
- `walls` / `slabs` regex;
- the layer rules and callout families.

Plan views (`"kind": "plan"`, `cut_z`) are wired into extract and hlr but not tested yet. Test one before promising plans.
