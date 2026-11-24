---
name: autocad-dwg
description: Read, inspect, measure and plot AutoCAD drawings (.dwg/.dxf) with the user's own AutoCAD 2027 — through the dce-autocad MCP when the file is in its project folders, otherwise through AutoCAD's headless console (accoreconsole). Use this for every DWG task, even a quick look - a relevé / survey, plan masse, plan RDC, DCE sheet, a DWG attached with @ or sitting in Downloads, "what's in this drawing", site or room dimensions, layers, texts, cartouche info, or turning a DWG into a PDF/image to read. Never guess a drawing's content, and never ask the user to export it themselves first.
---

# AutoCAD DWG

The user (BAAK STUDIO, architect in Tunis) works in AutoCAD 2027 and wants DWG files handled through AutoCAD itself, every time. Two routes exist. Pick by where the file is.

## 1. Route

| File location | Route |
|---|---|
| `D:\DCE SITE`, `G:\Mon Drive\@@BAAK CLOUD 2026`, `D:\PROJECT_models` | **dce-autocad MCP**: `acad_open_document` → `acad_document_info` → `acad_list_layers` → `acad_query_entities` |
| Anywhere else (Downloads, Desktop, client folders, email attachments) | **Headless console**: `scripts/dwg_export.ps1` → read the PDFs → `scripts/dxf_summary.ps1` |

The MCP only reads those three folders, and it refuses anything else with "Lecture autorisée seulement dans…". Don't copy an unrelated drawing into them to get around that. They are the Site PROJECT project folders, and a stray relevé there would pollute that project. Use the console route instead.

`acad_list_documents` can fail with `<unknown>.Count` when AutoCAD has no documents open, or in other odd states. That error is harmless: go straight to `acad_open_document`.

When you use the MCP, follow its own rules. Files on G: are read-only. Deliverables go under `D:\DCE SITE` with a new name or index. Draw with LWPOLYLINE, and use only the drawing's existing layers and blocks.

## 2. Headless console route

The console (`C:\Program Files\Autodesk\AutoCAD 20xx\accoreconsole.exe`) is a separate process. It never touches the drawing the user has open in AutoCAD, and the script works on a copy.

**Step A: export DXF (and optionally PDFs)**

```powershell
& "$env:USERPROFILE\.claude\skills\autocad-dwg\scripts\dwg_export.ps1" -Dwg "C:\Users\sbs\Downloads\RELEVE (1).dwg"
```

This writes `<name>.dxf` into `%USERPROFILE%\dwgwork\<name>\`. Pass `-WorkDir` to put the outputs in the session folder instead, when the user should see them. The path must stay short (see pitfalls).

**Step B: find where the content is, then summarise**

```powershell
& "$env:USERPROFILE\.claude\skills\autocad-dwg\scripts\dxf_summary.ps1" -Dxf "<workdir>\<name>.dxf"
```

The summary prints:
- the header: units, `$DIMLFAC` and extents
- the 2–98 % box of entity positions
- the span of the texts
- entity counts per layer
- the largest entities, which are usually the site boundary, sheet frames and outlines
- every text with its coordinates
- every dimension with its value

Narrow it with `-Win "x1,y1,x2,y2"` (insertion point inside the window) and `-Layer`. Pipe it through `Select-String` to pull one section.

**Step C: plot windows to PDF and look at them**

Use the text coordinates to choose windows, one per sheet or view. Re-run the export with `-NoDxf -Window`:

```powershell
& "...\dwg_export.ps1" -Dwg "<dwg>" -NoDxf -Window "rdc|21308,24170|21368,24226|L","masse|21360,24160|21400,24235|P"
```

Each window is `name|x1,y1|x2,y2|P-or-L`. Open each PDF with the Read tool. You get the rendered sheet plus its text layer. Plot tight windows: a whole A1 sheet fitted to one page is too small to read room names and dimensions.

## 3. Pitfalls (each one cost time before)

- **Long paths break the console.** It fails with "Improper drawing name", ErrorStatus 360. The session scratchpad path is far too long, so keep the work folder under ~150 characters. The script copies the DWG to a plain name, because names like `RELEVE (1).dwg` are risky.
- **Extents plots come out blank** when stray objects sit far away. `$EXTMIN`/`$EXTMAX` then spans kilometres while the real content occupies a small area. Plot windows taken from the text span, not `_E`.
- **Units lie.** `$INSUNITS` can say mm while the geometry is in metres and dimensions display in cm (`$DIMLFAC` = 100). This is common in Tunisian relevés. Check one known dimension against the coordinates, such as a 37.00 m façade spanning 37 drawing units, before quoting any size.
- **The console may idle after the script.** The export script ends with `_.QUIT` and has a timeout. If you write your own `.scr`, do the same, or run it in the background.
- **Command prompts.** Use English underscore commands (`_.DXFOUT`, `_.-PLOT`) and run with `/l en-US`, so the script works in a French install too. For the exact `-PLOT` prompt order in model space, see `PlotBlock` in `dwg_export.ps1`.
- **No Python on this PC.** Don't reach for ezdxf. Parse DXF with the PowerShell script.

**Step D (optional): clean vector drawings for decks and diagrams**

```powershell
& "...\dxf_to_svg.ps1" -Dxf "<dxf>" -Win "x1,y1,x2,y2" -Width 1600 -Layers "00-mur,MUR" -Style "00-mur=#16120F:1.6" [-Rotate180] -Out plan.svg
```

The script writes the LINE, LWPOLYLINE (bulges included), ARC and CIRCLE linework of a window to SVG. It skips blocks, hatches and texts, so put labels on the slide instead. It prints the transform from drawing units to pixels, so overlays (zones, labels, badges) can be placed exactly. `-Rotate180` puts the street side at the bottom.

**Richer drawings:** add `-Explode` to `dwg_export.ps1`. It unlocks and thaws every layer, then explodes blocks four times so nested blocks come apart, and writes `<name>_x.dxf`. Doors, furniture, seats and people then turn into linework that `dxf_to_svg.ps1` can draw, ellipses included. Without it, plans come out bare.

**Checking sizes on every side:**

```powershell
& "...\dxf_dims.ps1" -Dxf "<dxf>" -Win "x1,y1,x2,y2" -Layer MUR -MinLen 20
```

It lists every DIMENSION with its measured points, which tells you where each chain runs, and every outline on a layer with its side lengths (for example the plot boundary). Use it to quote the plot sides, the building chains and setbacks, and the level chain of a section.

**Levels trap:** an elevation's ground line is often the garden, not the floor. Take ±0.00 from the section's dimension chain (usually at the foot of the glazing), read the step heights on the elevation, and give every height relative to that ±0.00. When the section and the elevation disagree, say so instead of picking one.

## 4. Changing a drawing outside the MCP folders

Write a `.scr` or LISP that edits the copy in the work folder, then `_.SAVEAS` to a **new** file name next to the original, for example `RELEVE - BAAK v1.dwg`. Never overwrite the user's original, and say exactly which file you wrote.

## 5. Reporting back

Tell the user:
- what the drawing is: the title-block text (project, owner, architect, date, scales, sheet numbers)
- which views it contains
- the dimensions that matter for the task, in metres, with what you measured them from
- where the PDFs/DXF are, if they'll want them

Read room names and the plan layout from the plotted PDFs. Take sizes from the DXF numbers, not from eyeballing the image.
