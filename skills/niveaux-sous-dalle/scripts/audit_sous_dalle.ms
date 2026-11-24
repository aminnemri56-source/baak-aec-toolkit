-- Audit "niveaux sous dalle": visible pieces standing on the floor whose top stops short of the slab soffit.
-- Set before fileIn:  nsdZone = #(x0, x1, y0, y1)   nsdFloorZ = floor level   nsdSoffitZ = slab underside
-- Returns a text list (also in global nsdAudit). Bounding boxes only: fast on big scenes, no ray casts.
global nsdZone, nsdFloorZ, nsdSoffitZ, nsdAudit
(
  local rep = stringStream ""
  local x0 = nsdZone[1], x1 = nsdZone[2], y0 = nsdZone[3], y1 = nsdZone[4]
  local n = 0
  for o in geometry where not o.isNodeHidden and o.layer.on and classOf o != Targetobject and o.min.x > x0 and o.max.x < x1 and o.min.y > y0 and o.max.y < y1 and o.min.z < nsdFloorZ + 60.0 and o.max.z > nsdFloorZ + 190.0 and o.max.z < nsdSoffitZ - 0.5 do (
    n += 1
    format "% | % | top % (% cm under the slab) | x %..% y %..%\n" o.name o.layer.name (formattedPrint o.max.z format:".1f") (formattedPrint (nsdSoffitZ - o.max.z) format:".1f") (formattedPrint o.min.x format:".0f") (formattedPrint o.max.x format:".0f") (formattedPrint o.min.y format:".0f") (formattedPrint o.max.y format:".0f") to:rep
  )
  format "% piece(s) stop short of the slab soffit % in the zone\n" n nsdSoffitZ to:rep
  nsdAudit = rep as string
  nsdAudit
)
