"""fill_lights.py (skill archviz-shots): hidden fill lights in every room, so no space of a render stays dark.
The user's specification (11/11/2026): "put lights in every place to get the space more lighted without adding actual light, for example a
sphere with only diffuse, invisible, and remove reflection refraction".
So: a grid of small SPHERE lights hanging in mid-air in each room, invisible to the camera, lighting the diffuse only (no specular highlight,
not seen in reflections or through glass). A sphere lights the ceiling as well as the floor, which a downward panel does not: with panels
under the ceiling, a white ceiling was lit only by light bounced off terracotta walls and turned orange.
The lights are written as a MaxScript (run it in the .max, so every export carries them) and, optionally, straight into a copy of a
.vrscene when Max is closed.

usage: fill_lights.py rooms.json lights.ms [in.vrscene out.vrscene] [--intensity 25] [--spacing 160] [--drop 80]
  rooms.json = written by room_cameras.py (rooms_<tag>.json: name, min, max, floor, ceiling); a room may carry "fill": 0.5 or 0."""
import json
import shutil
import sys

A = sys.argv[1:]


def opt(name, default):
    return float(A[A.index(name) + 1]) if name in A else default


pos = [a for i, a in enumerate(A) if not a.startswith("--") and (i == 0 or not A[i - 1].startswith("--"))]
rooms = json.load(open(pos[0], encoding="utf-8"))
MS = pos[1]
SRC, DST = (pos[2], pos[3]) if len(pos) > 3 else (None, None)
INT, STEP, DROP = opt("--intensity", 25.0), opt("--spacing", 160.0), opt("--drop", 80.0)
RAD = 8.0
COL = (1.0, 0.98, 0.95)
blocks, n = [], 0
ms = ['-- hidden fill lights (archviz-shots, fill_lights.py): invisible sphere lights, diffuse only, no specular, not in reflections. Re-runnable.',
      '(\n  local lay = LayerManager.getLayerFromName "HYB_Lumieres_Appoint_Invisibles"\n  if lay == undefined do lay = LayerManager.newLayerFromName "HYB_Lumieres_Appoint_Invisibles"',
      '  for o in (for x in lights where matchPattern x.name pattern:"HYB_FILL_*" collect x) do (if isValidNode o do delete o)',
      '  fn mk nm p m lay = (local l = VRayLight name:nm type:2 pos:p size0:%g multiplier:m color:(color %d %d %d) invisible:true; try (l.affect_specular = false) catch (); try (l.affect_reflections = false) catch (); try (l.affect_diffuse = true) catch (); lay.addNode l)'
      % (RAD, round(COL[0] * 255), round(COL[1] * 255), round(COL[2] * 255))]
for r in rooms:
    k = float(r.get("fill", 1.0))
    if k <= 0:
        continue
    x0, y0, x1, y1 = r["min"][0], r["min"][1], r["max"][0], r["max"][1]
    nx, ny = max(1, round((x1 - x0) / STEP)), max(1, round((y1 - y0) / STEP))
    z = max(r["floor"] + 120.0, r["ceiling"] - DROP)
    for i in range(nx):
        for j in range(ny):
            n += 1
            x, y = x0 + (i + 0.5) * (x1 - x0) / nx, y0 + (j + 0.5) * (y1 - y0) / ny
            nm = "HYB_FILL_%s_%02d" % (r["name"], i * ny + j + 1)
            ms.append('  mk "%s" [%.1f, %.1f, %.1f] %g lay' % (nm, x, y, z, INT * k))
            blocks.append("""
LightSphere %s@light_fill_%d {
  enabled=1;
  transform=Transform(Matrix(Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)), Vector(%.2f, %.2f, %.2f));
  color=AColor(%g, %g, %g, 1);
  affectDiffuse=1;
  affectSpecular=0;
  affectAtmospherics=0;
  scene_name=ListString(
    "%s",
    "scene/%s",
    "layer/HYB_Lumieres_Appoint_Invisibles"
  );
  shadows=1;
  shadowBias=0.02;
  units=0;
  intensity=%g;
  invisible=1;
  affectReflections=0;
  noDecay=0;
  radius=%g;
  sphere_segments=20;
}
""" % (nm, n, x, y, z, COL[0], COL[1], COL[2], nm, nm, INT * k, RAD))
    print("%-9s %d x %d lights at z %.0f, intensity %g" % (r["name"], nx, ny, z, INT * k))
ms.append('  setSaveRequired true\n  "%d hidden fill lights on layer HYB_Lumieres_Appoint_Invisibles"\n)' % n)
open(MS, "w", encoding="utf-8").write("\n".join(ms) + "\n")
if DST:
    shutil.copyfile(SRC, DST)
    with open(DST, "ab") as f:
        f.write(("\n// ---- hidden fill lights (archviz-shots fill_lights.py) ----\n" + "".join(blocks)).encode("utf-8"))
print(n, "hidden sphere lights ->", MS, ("and " + DST) if DST else "")
