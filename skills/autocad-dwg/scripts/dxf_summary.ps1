<#
Summarise an ASCII DXF (from dwg_export.ps1) without Python or ezdxf.
Prints header units/extents, where the real content sits, entity counts per layer,
texts with positions, and dimension values.

  -Dxf        the .dxf file
  -Win        optional filter "x1,y1,x2,y2": only texts/dims/entities inside it
  -Layer      optional exact layer filter
  -TextLimit  max texts printed (default 400)
  -NoDims     skip the dimension listing
#>
param(
  [Parameter(Mandatory = $true)][string]$Dxf,
  [string]$Win = "",
  [string]$Layer = "",
  [int]$TextLimit = 400,
  [switch]$NoDims
)
$ErrorActionPreference = "Stop"
$inv = [Globalization.CultureInfo]::InvariantCulture
$L = [IO.File]::ReadAllLines($Dxf)

"=== HEADER"
foreach ($v in '$INSUNITS', '$LUNITS', '$MEASUREMENT', '$DIMLFAC', '$EXTMIN', '$EXTMAX') {
  $i = [Array]::IndexOf($L, $v)
  if ($i -ge 0) {
    $vals = @(); $k = $i + 1
    while ($k + 1 -lt $L.Length -and $L[$k].Trim() -ne '9' -and $L[$k].Trim() -ne '0') { $vals += $L[$k + 1].Trim(); $k += 2 }
    "{0,-13} {1}" -f $v, ($vals -join ', ')
  }
}
"(INSUNITS 4 = mm, 5 = cm, 6 = m; check it against a known dimension before trusting it)"

# Locate the ENTITIES section.
$s = -1
for ($k = 0; $k -lt $L.Length - 1; $k++) { if ($L[$k].Trim() -eq '2' -and $L[$k + 1].Trim() -eq 'ENTITIES') { $s = $k + 2; break } }
if ($s -lt 0) { throw "No ENTITIES section" }

$ents = New-Object System.Collections.Generic.List[object]
$cur = $null
for ($k = $s; $k -lt $L.Length - 1; $k += 2) {
  $c = $L[$k].Trim(); $val = $L[$k + 1]
  if ($c -eq '0') {
    if ($cur) { $ents.Add($cur) }
    if ($val.Trim() -eq 'ENDSEC') { $cur = $null; break }
    $cur = [pscustomobject]@{ t = $val.Trim(); l = ''; txt = ''; x = $null; y = $null; tx = $null; ty = $null; meas = $null
      minx = [double]::MaxValue; miny = [double]::MaxValue; maxx = [double]::MinValue; maxy = [double]::MinValue }
    continue
  }
  if (-not $cur) { continue }
  switch ($c) {
    '8'  { $cur.l = $val.Trim() }
    '1'  { $cur.txt += $val }
    '3'  { if ($cur.t -ne 'DIMENSION') { $cur.txt += $val } }  # on DIMENSION, 3 is the dim style name
    '42' { if ($cur.t -eq 'DIMENSION') { $cur.meas = [double]::Parse($val.Trim(), $inv) } }
    # 11/21 is a real point only on LINE and DIMENSION; on MTEXT it is a direction vector.
    { $_ -in '10', '11' } {
      $n = [double]::Parse($val.Trim(), $inv)
      if ($c -eq '10' -and $cur.x -eq $null) { $cur.x = $n }
      if ($c -eq '11' -and $cur.tx -eq $null) { $cur.tx = $n }
      if ($c -eq '10' -or $cur.t -in 'LINE', 'DIMENSION') { if ($n -lt $cur.minx) { $cur.minx = $n }; if ($n -gt $cur.maxx) { $cur.maxx = $n } }
    }
    { $_ -in '20', '21' } {
      $n = [double]::Parse($val.Trim(), $inv)
      if ($c -eq '20' -and $cur.y -eq $null) { $cur.y = $n }
      if ($c -eq '21' -and $cur.ty -eq $null) { $cur.ty = $n }
      if ($c -eq '20' -or $cur.t -in 'LINE', 'DIMENSION') { if ($n -lt $cur.miny) { $cur.miny = $n }; if ($n -gt $cur.maxy) { $cur.maxy = $n } }
    }
  }
}

$wx1 = $wy1 = [double]::MinValue; $wx2 = $wy2 = [double]::MaxValue
if ($Win) { $p = $Win -split ',' | ForEach-Object { [double]::Parse($_.Trim(), $inv) }; $wx1, $wy1, $wx2, $wy2 = $p }
function Inside($x, $y) { $x -ne $null -and $y -ne $null -and $x -ge $wx1 -and $x -le $wx2 -and $y -ge $wy1 -and $y -le $wy2 }
$sel = $ents | Where-Object { (-not $Layer -or $_.l -eq $Layer) -and (-not $Win -or (Inside $_.x $_.y)) }

"`n=== CONTENT LOCATION ($($sel.Count) of $($ents.Count) entities)"
$xs = $sel | Where-Object { $_.x -ne $null } | ForEach-Object { $_.x } | Sort-Object
$ys = $sel | Where-Object { $_.y -ne $null } | ForEach-Object { $_.y } | Sort-Object
if ($xs.Count) {
  $q = { param($a, $f) $a[[Math]::Min($a.Count - 1, [int]([Math]::Floor($a.Count * $f)))] }
  "2%-98% of entity insertion points: x {0:N2} .. {1:N2}   y {2:N2} .. {3:N2}" -f (& $q $xs 0.02), (& $q $xs 0.98), (& $q $ys 0.02), (& $q $ys 0.98)
}
$tp = $sel | Where-Object { $_.t -in 'TEXT', 'MTEXT' -and $_.x -ne $null }
if ($tp) { "texts span:                          x {0:N2} .. {1:N2}   y {2:N2} .. {3:N2}" -f ($tp.x | Measure-Object -Minimum).Minimum, ($tp.x | Measure-Object -Maximum).Maximum, ($tp.y | Measure-Object -Minimum).Minimum, ($tp.y | Measure-Object -Maximum).Maximum }
"(if EXTMIN/EXTMAX is far larger than this, stray objects exist: plot windows, not extents)"

"`n=== LAYERS (entity count, types)"
$sel | Group-Object l | Sort-Object Count -Descending | Select-Object -First 40 | ForEach-Object {
  "{0,6}  {1,-28} {2}" -f $_.Count, $_.Name, (($_.Group | Group-Object t | ForEach-Object { "$($_.Name):$($_.Count)" }) -join ', ')
}

"`n=== LARGEST ENTITIES (site boundaries, frames, outlines)"
$sel | Where-Object { $_.maxx -gt $_.minx } |
  Sort-Object { ($_.maxx - $_.minx) * [Math]::Max(1e-9, $_.maxy - $_.miny) } -Descending | Select-Object -First 15 | ForEach-Object {
  "{0,-11} [{1}]  x {2} .. {3}  y {4} .. {5}  ({6} x {7})" -f $_.t, $_.l, $_.minx.ToString('F2', $inv), $_.maxx.ToString('F2', $inv),
    $_.miny.ToString('F2', $inv), $_.maxy.ToString('F2', $inv), ($_.maxx - $_.minx).ToString('F2', $inv), ($_.maxy - $_.miny).ToString('F2', $inv)
}

function Clean([string]$t) {
  $t -creplace '\\P', ' / ' -creplace '\\[ACFHQTWfp][^;]*;', '' -creplace '\\[LlOoKk]', '' -replace '%%[uUoO]', '' -replace '[{}]', '' -replace '\s+', ' '
}
"`n=== TEXTS (x, y, layer, text)"
$tp | Where-Object { $_.txt.Trim() } | Select-Object -First $TextLimit | ForEach-Object {
  "{0,11} {1,11}  [{2}]  {3}" -f $_.x.ToString('F2', $inv), $_.y.ToString('F2', $inv), $_.l, (Clean $_.txt).Trim()
}

if (-not $NoDims) {
  "`n=== DIMENSIONS (text x, text y, layer, value, override text)"
  "(value is DXF code 42; DIMLFAC may already be applied - compare one value with the geometry above)"
  $sel | Where-Object { $_.t -eq 'DIMENSION' -and $_.meas -ne $null } | Select-Object -First $TextLimit | ForEach-Object {
    $px = if ($_.tx -ne $null) { $_.tx } else { $_.x }; $py = if ($_.ty -ne $null) { $_.ty } else { $_.y }
    "{0,11} {1,11}  [{2}]  {3}  {4}" -f $px.ToString('F2', $inv), $py.ToString('F2', $inv), $_.l, $_.meas.ToString('0.###', $inv), (Clean $_.txt).Trim()
  }
}
