---
name: camera-brief
description: Before sending render views to Codex (or any image model), read every camera's render and write a per-view note of exactly what that camera sees and where (walls, screens, letters, stairs, glazing, machines), so room-level design features are never added to a view that does not show them, or in the wrong place. Use every time several views of the same room go to Codex, whenever a room brief describes features (a screen, a feature wall, an esquisse), when the camera changes, and whenever the user says a feature was added in the wrong place, removed, or "when you change the camera change your prompt".
---

# Camera brief

The user's rule (07/11/2026): **"WHEN YOU CHANGE THE CAMERA CHANGE YOUR PROMPT — YOU ADDED THE SCREEN IN WRONG PLACE"**.

A room brief describes what the room contains. It does not say what one camera sees. When the same room text went to all six RPM views, Codex did two wrong things:
- It placed the video screen and the orange perforated screen in views that don't show them.
- It turned the typographic wall into the perforated screen.

The cure is one written note per camera, made by looking at its render, before the job is built.

`PY` = `C:\Users\sbs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -I`, `S` = this skill's `scripts`.

## 1. Read every render
- `PY S/render_read_sheet.py <renders dir> <out.jpg> [filter]` writes a contact sheet of the renders. They are brightened ×1.6 so dark walls read, and each carries a 3×3 grid (left / centre / right × top / middle / bottom) and its view name.
- Look at each view and write down, from left to right:
  - each wall and what is on it (graphic, letters and their colours, cladding, LED lines);
  - every screen, sign or display, and where it sits;
  - glazing, and what lies behind it (outside, another room, a film);
  - stairs and columns;
  - machines: how many and which way they face;
  - the camera direction.
- Then list the room features this camera does NOT see. They are forbidden in this view.
- Name each feature by the same name in every view: TYPOGRAPHIC WALL, 5D SCREEN, STAIR CLADDING + VIDEO SCREEN. The same name must always mean the same physical object.

## 2. Write the notes into fixes.json
`<out>\fixes.json`, one entry per view:

```json
{"HYB_0711_RPM_7": {"notes": [
  "THIS CAMERA SEES: facing the camera, the TYPOGRAPHIC WALL (...); right of the column, ...",
  "NOT IN THIS VIEW (never add): the 5D SCREEN, the STAIR CLADDING, the video screen"],
  "remove": []}}
```

- Keep the room text in `codex_brief.ROOMS` conditional: "each feature ONLY where image 1 shows it".
- Restrict per-view references, such as an esquisse, to the views that show that feature: `codex_refs.DESIGN_VIEWS`.

## 3. Check before running
`PY S/check_view_notes.py <out dir>` lists every view in `jobs.json` that has no THIS CAMERA SEES / NOT IN THIS VIEW note, and exits with an error if any is missing. Do not run Codex until it passes.

## 4. When a result puts a feature in the wrong place
Send a correction round naming the camera's real content, using the same wording as the note. Then fix the note, so the views still to come don't repeat the error.

Related skills: `render-enhancer` (review loop), `vantage-codex-render` (brief, jobs).
