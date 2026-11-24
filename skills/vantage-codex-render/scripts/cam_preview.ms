-- Eye-level previews of candidate render cameras for the RPM, salle de cours and Pilates (viewport grabs, 16:9 safe frame).
-- Render size is set to 2560 x 1440 for the grab and put back afterwards. Nothing in the scene changes.
global camPrevViews
(
  local outDir = @"D:\PROJECT_work\cams_1er\preview\"
  makeDir outDir all:true
  local views = if camPrevViews != undefined then camPrevViews else #()
  local oldW = renderWidth, oldH = renderHeight, oldSF = displaySafeFrames
  renderWidth = 2560; renderHeight = 1440
  local sel = for o in objects where not o.isHidden and o.max.z > 480 and o.min.z < 900 and o.max.x > -980 and o.min.x < 1280 and o.max.y > -2200 and o.min.y < 80 collect o
  clearSelection(); select sel
  IsolateSelection.EnterIsolateSelectionMode()
  clearSelection()
  hideByCategory.lights = true; hideByCategory.helpers = true; hideByCategory.cameras = true; hideByCategory.shapes = true
  hideByCategory.particles = true; hideByCategory.spacewarps = true; hideByCategory.bones = true
  local tgt = Targetobject name:"CAMPREV_Tmp.Target" pos:[0, 0, 0]
  local cam = Targetcamera name:"CAMPREV_Tmp" fov:75 pos:[0, 0, 100] target:tgt
  viewport.setCamera cam
  displaySafeFrames = true
  viewport.SetRenderLevel #smoothhighlights
  local res = ""
  for v in views do (
    cam.pos = v[2]; tgt.pos = v[3]; cam.fov = v[4]
    completeRedraw()
    local bm = gw.getViewportDib()
    bm.filename = outDir + v[1] + ".png"
    save bm
    res = bm.width as string + "x" + bm.height as string
    close bm
  )
  displaySafeFrames = oldSF
  viewport.setType #view_persp_user
  delete cam
  if not isDeleted tgt do delete tgt
  IsolateSelection.ExitIsolateSelectionMode()
  hideByCategory.lights = false; hideByCategory.helpers = false; hideByCategory.cameras = false; hideByCategory.shapes = false
  hideByCategory.particles = false; hideByCategory.spacewarps = false; hideByCategory.bones = false
  renderWidth = oldW; renderHeight = oldH
  completeRedraw()
  (views.count as string) + " previews " + res
)
