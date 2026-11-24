---
name: niveaux-sous-dalle
description: Levels rule for every BAAK 3D scene and drawing - by default every wall, partition, bulkhead, wall lining and full-height joinery rises to the underside of the slab (niveau sous dalle), never stopping at a false-ceiling plane or at an old slab level, so no void shows between wall heads and ceilings. Use whenever walls, partitions, cabins, bulkheads, ceilings, slabs or clear heights are built, moved, raised or lowered in 3ds Max (PROJECT or any project), whenever a ceiling becomes open (lattes, baffles, grid, lames), before every render export or save of a new scene version, and whenever the user says niveau, niveaux, sous dalle, HSP, void, vide, gap, "rectifie les niveaux", "touche la dalle", or circles the top of a wall, even if they only ask for a ceiling or a height change.
---

# Niveaux sous dalle

The user's rule, 12/11/2026, on a Vantage view where a wall stopped short and the next room showed over it: "RECTIFIE LES NIVEAU", "DONT KEEP THIS VOID EACH TIME", "PAR DEFAULT IL FAUT TOUCHE LE NIVEAU SOUS DALLE".

**Default: every vertical element that reads as a wall goes up to the slab soffit.** A false ceiling is fitted between walls; it is not what closes them. A void above a wall head is a fault each time it appears, and it has come back several times (door heads with nothing above, cabin tops, walls left at an old slab level).

## What counts
- Walls and partitions, their finish skins and claddings, door transoms (the wall above a door head).
- Bulkheads over cabins, saunas, changing cubicles; drops and upstands at a change of ceiling level.
- Wall linings and full-height joinery (locker top panels, joinery walls) when the room reads them as the wall.
- Not furniture below ceiling height, not door leaves, not glazed screens the design keeps low on purpose (say so if you leave one).

## When it matters most
- **Open ceilings** (lattes, baffles, grid, lames): the eye goes between the slats to the slab. A wall that stops at the ceiling underside leaves a visible void and shows the next room.
- **After any level change.** Raising or lowering a slab or ceiling moves the small local objects and leaves the big shared wall meshes behind. On PROJECT the room walls (`Line765`) stayed at z 600 when the vestiaire slab went to 656.7 and then 626.7.
- **Two slab levels meeting** (a raised zone beside the ordinary floor): close the step with a drop down to the lower soffit.

## Procedure
1. **Get the soffit level per zone** from the slab object itself (its `min.z`), not from a ceiling object. Write the clear height under the slab (HSD) and under the ceiling (HSP) in your notes.
2. **Audit before building and again before exporting.** In Max set `nsdZone = #(x0, x1, y0, y1)`, `nsdFloorZ`, `nsdSoffitZ` and `fileIn` `scripts/audit_sous_dalle.ms`: it lists every visible piece standing on the floor whose top stops between 1.9 m and the soffit. Without Max, cut the export: object bounding boxes give each wall's top (PROJECT: `dce_mezz/mz_plan_extract.py`, the `z` field of kind `C` objects). Sort real exceptions (furniture, glazing) from faults.
3. **Fix by wall line, not by vertex, on big meshes.** A long wall is often one quad across several rooms: moving some top vertices tilts it. Add an upstand box on the wall line from the old top to the soffit, in the wall's own material and thickness. Small local pieces (bulkheads, boxes): raise their top.
4. **Keep the wall finish continuous** up to at least the ceiling underside, so the upstand does not read as a band of another colour.
5. **Check with a view from inside each room looking up along each wall**, then export. Say in the report which pieces were left low on purpose.

## Drawings
The same default applies in 2D: sections and wall elevations show partitions to the slab soffit with the false ceiling fitted between them, and ceiling plans give both HSP and the slab level when they differ.

## PROJECT levels (12/11/2026)
- Mezzanine finished floor z 300.7 (+3.00).
- Vestiaire / shower / sauna zone: slab `MEZZ_GREEN_Slab_600`, soffit z 626.7; ceilings (lattes, grid, staff) at z 610.7 = HSP 3.10 m.
- Rest of the mezzanine: walls top z 532, plenum z 531, lattes and staff undersides z 520 to 522.
- Fix script for the vestiaire zone: `D:\PROJECT_work\cams_mezz\niveaux_sous_dalle.ms` (upstands `MZRH_Rehausse_*`, bulkhead tops).
