-- Light vrscene for Vantage: temporarily hides every object entirely below zoneZ0 or above zoneZ1 (sun, cameras and helpers kept),
-- exports, then restores the exact hidden state. The .max is not changed. Set the globals before fileIn:
--   zoneZ0 = 480.0; zoneZ1 = 1000.0; zoneOut = @"D:\...\scene_zone.vrscene"
global zoneZ0, zoneZ1, zoneOut
(
  local hid = #()
  for o in objects where not o.isHidden and (superClassOf o == GeometryClass or superClassOf o == light) and classOf o != VRaySun do (
    if o.max.z < zoneZ0 or o.min.z > zoneZ1 do (append hid o; o.isHidden = true)
  )
  local t0 = timeStamp()
  vrayExportVRScene zoneOut
  for o in hid where not isDeleted o do o.isHidden = false
  "hidden for export " + hid.count as string + " | " + ((getFileSize zoneOut) / 1048576) as string + " MB in " + ((timeStamp() - t0) / 1000) as string + " s | restored"
)
