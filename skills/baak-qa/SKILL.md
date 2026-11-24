---
name: baak-qa
description: BAAK quality check before anything leaves the office - Revit models and sheets, AutoCAD DWGs, plotted PDFs and written pieces (CCTP, CCAP, notes), on both BAAK PCs (this PC and the Revit PC) and on everything passing through the transfer folders IN - OUT / OUT - IN. Runs the automatic checks (BAAK charter, cartouche, marks, missing links, text spelling), then a senior visual read, and reports faults by rule with a fix for each. Use before every delivery, index or send, whenever a file arrives in OUT - IN or goes to IN - OUT, whenever the user says vérifie, contrôle, check, QA, faute, erreur, fault, "1000 % correct", "no fault", "is it correct", "corrige la maquette", or pastes the path of an .rvt/.rte/.dwg/.pdf to look at, even if they only say "open it" or "look".
---

# BAAK QA - nothing leaves with a fault

The user wants the DCE "1000 % correct with no fault" (21/11/2026). Automatic checks catch the rule faults; the visual senior read catches the rest. Do both, every time, and say which was done.

## Where the work comes from: two PCs, two transfer folders

- **This PC** (`DESKTOP-O10RI8U`): 3ds Max, AutoCAD 2027, Vantage, Revit 2025.3, DCE deliverables on `D:\DCE SITE`, scripts in `D:\PROJECT_work` (Git history).
- **The Revit PC** ("Ahmad's PC"): Revit 2025.3 + pyRevit, work files in `D:\BAAK WORK\PROJECT SITE\01 RVT\`. Google Drive shows as `G:\My Drive` there and `G:\Mon Drive` here.
- **Exchange** `G:\...\_TRANSFERT PROJECT\`:
  - `OUT - IN` = from the Revit PC to this PC (Revit backups, PDFs, FBX);
  - `IN - OUT` = from this PC to the Revit PC. One dated subfolder per drop, "JJ MM AAAA - sujet".
- **G: is read-only for checking.** Copy what arrived to a local folder first (`D:\PROJECT_work\revit_local\`, or `%TEMP%`) and work on the copy: no lock file, no accidental save onto G:.
- Writing to G: (a drop into IN - OUT) needs the user's yes, typed in this session. Never overwrite a file there; use a new dated subfolder.
- On the Revit PC the same tools live in `%USERPROFILE%\Tools\BAAK_QA` once installed from the IN - OUT package (see INSTALL there).

## Tools (this PC)

| Tool | Path | Use |
|---|---|---|
| Python 3.12 + ezdxf, shapely, pymupdf, openpyxl | `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (not on PATH) | all checks |
| DWG checker | `%USERPROFILE%\Tools\BAAK_QA\baak_check.py check <dwg or folder>` | charter layers, dim/text styles, LINE vs LWPOLYLINE, layer 0, cartouche attributes, layouts without viewport → XLSX in `reports\` |
| Revit checker | `...\BAAK_QA\revit_check.py [--export]` | document on G: / .rte, duplicate marks, sheets, counts by category; `--export` sends sheets to DWG then runs the DWG checker |
| Revit link | `...\BAAK_QA\rvt.py <method> [json]` → BAAK add-in on 127.0.0.1:8099 | info, count, marks, levels, inspect, open_document, save ... |
| Charter | `charter.json` (Bénin APD 15/08: 212 layers, 11 dim styles, 70 text styles) + `charter_extra.json` | user rulings: `BAAK - REPERAGE MENUISERIE`, `BAAK - STRUCTURE` (one space), `BAAK - CARTOUCHE INVISIBL` |
| AutoCAD standards | `...\BAAK_QA\BAAK_CHARTE.dws` | the user's own CHECKSTANDARDS / Batch Standards Checker |
| French text | `%USERPROFILE%\Tools\Grammalecte-fr-v2.3.0\grammalecte-cli.py -ff file.txt` (UTF-8 in) | CCTP, CCAP, notes, sheet texts → `file.res.txt` |
| Script history | `%USERPROFILE%\Tools\snapshot_scripts.ps1 -Root <folder> -Message "..."` | snapshot generator scripts after each change / index |
| Also | dce-autocad `revit_differences`, Revit MCP (`mcp__revit__*`), `drawings-from-3d`, `niveaux-sous-dalle` skills | model vs DCE, hero check, levels |

If Revit sits on a dialog, the add-in answers "timed out waiting for Revit". List Revit's windows with UI Automation. "Références non résolues" means missing links: note them, then choose "Ignorer et poursuivre l'ouverture du projet".

## The BAAK rules to check (each fault is reported against one of these)

**Files and delivery**
1. Never read-write on G:; deliver to `D:\DCE SITE\...` with a new name or index; never overwrite. A console SAVEAS onto an existing file hangs. Name the phases before launching.
2. Status wording: everything is **EN COURS** until the user validates; open issues are OUVERT. Never write "fait" or "done".

**Cartouche (DWG, Revit title blocks, PDF)**
3. "Dessiné par" **empty** (no AM, never KD); "Approuvé par" **KA**; indice and date filled and matching the file name. Check the plotted PDF text too.

**Charter (DWG and Revit exports)**
4. Only charter layers; never invent one. Use the Bénin LEGENDE block; viewports on BAAK - CARTOUCHE INVISIBL.
5. Dim styles BAAK (plans) / Detail BAAK (details), DIMLFAC 100 in the metre DCE. Dimensions are **red**, in straight horizontal / vertical chains from first wall to last wall, one chain per room. Ceiling chains and lighting chains are separate. No number on a label, fitting or other number. Every end lands on something drawn.
6. LWPOLYLINE, never LINE; drawn elements in named blocks. Materials are real HATCH objects (ANSI31 walls, AR-SAND coatings, AR-CONC screed / béton / terrazzo, AR-RROOF wood). Model space: 10 m between views and rows.

**Content (what the drawing says)**
7. No light on a wall: point fixtures 40 cm clear of walls and 25 cm of collars; LED lines off walls, no fragment < 50 cm. Every room has a light and a height.
8. Walls, partitions and bulkheads go up to the slab soffit, with no void above a wall head (skill `niveaux-sous-dalle`). Doors sit in walls. Door heads stop at 2,20 and ceilings run over them.
9. Where joinery, lockers, columns and walls meet, the junction is designed, not left side by side. Every sub-space and every wall of a room is drawn.
10. Codes as in the bordereau Indice C (CAH-01..09, ARC, MUL, ETU, PE). Lockers: AG-05 vestiaires, AG-06 circulation and coaches (T2/T3/T4), AG-07 bandeau RDC, AG-07R rooftop; 40/30/30 split. Screens (E) are not signage (S).
11. Drawings made from the 3D: check the lines against the hero images through their own cameras. Details are drawn for execution (joints, fixings, erection), not traced.

**Revit model**
12. Work on a local `.rvt`, never on the `.rte` or on G:. No missing links. No duplicate **Mark**: a code such as S1 belongs in Type Mark, not Mark. Sheet numbers carry a bordereau code. No warnings left unexplained (Manage → Warnings, export HTML). Interference check for objects inside walls.

**Sheets and texts**
13. Render every PDF sheet with pymupdf at 100-220 dpi and read it like a senior architect: overlaps, clipped labels, wrong text, empty views, artefacts. Then do a cold foreman read: can a contractor build from it?
14. French text through Grammalecte. Ignore typographic-apostrophe hits in CAD text.

## Revit model vs the renders (same cameras)

Use this when the user asks to "analyse the renders" or to check or correct the Revit maquette against them. The model must end up realistic and buildable, not only look the same.

1. **Export.** Run `rvt.py export_fbx {"folder": ..., "name": ..., "fresh": true}`. It makes a new uncropped Fine 3D view. `{3D}` has a section box.
2. **Cameras** (3D cm, v42 frame; Ahmad's alignment rotate +26.1286°, + (159.777 ; 88.6058) m):
   - `cams_G33` = mezzanine, 48 cameras with fov, heroes in `VISUELS\RENDUS CODEX - 12 11 2026 - V39 - MEZZANINE\_FINAL`;
   - `mobrep\old_cameras.txt` = 24 V-Ray cameras CAM22_* (cardio, muscu, réception, lounge, cours, galerie, ext), fov 112.6;
   - `cams_1er\cams_0711*.txt` = position and target only. Fit the fov with `rvr_fov_fit.py`; the target z may be relative to the 1er floor.
3. **Render.** `blender -b --factory-startup --python rvr_blender.py -- <fbx> <cams> <regex> <outdir> 0.5` writes a clay render and Line Art per camera, about 30 s each.
4. **Match and score.**
   - Known hero: `rvr_compose.py`, then `rvr_score.py` (worst first), then `rvr_contact.py` (3×3 sheets).
   - Presentation renders with no camera: `rvr_match_zone.py <wide_dir> <render_dir> <cam_regex> <out>` finds the camera and Codex zoom for each render. Close-ups fail on purpose.
5. **Identify.** `rvr_probe.py <cams> <name> [near far]` lists the Revit elements in front of a camera.
6. **Decide by the latest rulings, not the render alone.**
   - The mezzanine has V2 finishes (20/11), DG and meeting room as 13/11.
   - In the DG: no perforated sheet, a walnut joinery wall, a black baffle ceiling.
   - The dossier mobilier beats older renders.
   - Classify each difference: REVIT À CORRIGER / RENDU DÉPASSÉ – GARDER REVIT / À VALIDER / CONFORME.
7. **Deliver.** Under `D:\DCE SITE\ARCHITECTURE\CONTROLE REVIT\...`: the constats XLSX (finding, decision, buildable fix, reference) and the comparison PDF. Status stays EN COURS.

## Procedure

1. **Name the phases** in one line. Copy anything from G: to a local folder.
2. **Automatic pass**:
   - DWG: `baak_check.py check <folder>`.
   - Revit: `revit_check.py`, then `--export` when sheets must be checked line by line.
   - Texts: Grammalecte.
   - Model vs DCE: dce-autocad `revit_differences`.
3. **Visual pass**: zoom-render the PDFs (rule 13) and read each sheet.
4. **Report**: one table with Fault | Where (file, sheet, id or handle, coordinates) | Rule n° | Proposed fix. Put the auto-fixable faults first, then the design questions (OUVERT). The XLSX / TXT reports go to `BAAK_QA\reports\`.
5. **Fix only what the user asks**, in new files or indexes. Re-run the checks on the new version and show before / after counts. Snapshot the scripts with Git.
6. When the result goes to the other PC, drop it in `IN - OUT\JJ MM AAAA - sujet` (after the user's yes) with a one-page note of what changed.

## First runs (21/11/2026)

- **CAH-06 ind. C DWG:** clean after the spelling ruling. Its cartouche is plain text, so rule 3 has to be checked on the PDF.
- **Revit "BACKUP avant relayout feuilles 21-11 - COORDINATION.rte":**
  - 261 sheets, 261 title blocks;
  - 4 missing DWG links (Desktop `RDC 18 11 2026.dwg`, and in `D:\PROJECT_work\02 DWG REF\` the ARC-06 chromatique, CLEAN 13 11 and RELEVE DE L'EXISTANT);
  - duplicate Marks: `1` x2 (ids 1471145, 1846263) and `S1` x17 (type code in Mark).
- **Add-in build:** the installed one lacks `views` / `export_dwg`. Rebuild `D:\PROJECT_work\baak_revit_mcp` and restart Revit to get sheet names and DWG export.
