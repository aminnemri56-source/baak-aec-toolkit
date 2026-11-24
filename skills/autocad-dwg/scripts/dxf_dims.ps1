<#
List what a DXF says about sizes, for checking dimensions on every side of a plan:
- every DIMENSION in a window with its measured points (codes 13/23 and 14/24), direction and value
- every closed LWPOLYLINE on a layer (e.g. the plot boundary) with its vertices and side lengths

  -Dxf    the .dxf file
  -Win    "x1,y1,x2,y2" window (dimension text or first point inside)
  -Layer  layer of the outlines to measure (default MUR)
  -MinLen ignore outlines whose box is smaller than this (drawing units, default 5)
#>
param(
  [Parameter(Mandatory = $true)][string]$Dxf,
  [string]$Win = "",
  [string]$Layer = "MUR",
  [double]$MinLen = 5
)
$ErrorActionPreference = "Stop"
$inv = [Globalization.CultureInfo]::InvariantCulture
function P([string]$v) { [double]::Parse($v.Trim(), $inv) }
function F([double]$v) { $v.ToString('0.00', $inv) }
$L = [IO.File]::ReadAllLines($Dxf)
$st = -1; for ($k = 0; $k -lt $L.Length - 1; $k++) { if ($L[$k].Trim() -eq '2' -and $L[$k + 1].Trim() -eq 'ENTITIES') { $st = $k + 2; break } }
$wx1 = $wy1 = [double]::MinValue; $wx2 = $wy2 = [double]::MaxValue
if ($Win) { $wx1, $wy1, $wx2, $wy2 = $Win -split ',' | ForEach-Object { P $_ } }
function In($x, $y) { $x -ge $wx1 -and $x -le $wx2 -and $y -ge $wy1 -and $y -le $wy2 }

$ents = New-Object System.Collections.Generic.List[object]; $cur = $null
for ($k = $st; $k -lt $L.Length - 1; $k += 2) {
  $c = $L[$k].Trim(); $v = $L[$k + 1]
  if ($c -eq '0') { if ($cur) { $ents.Add($cur) }; if ($v.Trim() -eq 'ENDSEC') { break }; $cur = @{ t = $v.Trim(); g = New-Object System.Collections.Generic.List[object] }; continue }
  if ($cur) { $cur.g.Add(@($c, $v)) }
}

"=== DIMENSIONS (value as displayed · from (13/23) to (14/24) · direction · layer)"
$rows = foreach ($e in $ents | Where-Object { $_.t -eq 'DIMENSION' }) {
  $h = @{}; $lay = ''
  foreach ($p in $e.g) { if ($p[0] -eq '8') { $lay = $p[1].Trim() } elseif ($p[0] -in '10', '20', '11', '21', '13', '23', '14', '24', '42', '50', '70') { if (-not $h.ContainsKey($p[0])) { $h[$p[0]] = P $p[1] } } }
  if (-not ($h.ContainsKey('13') -and $h.ContainsKey('14'))) { continue }
  $tx = if ($h.ContainsKey('11')) { $h['11'] } else { $h['10'] }; $ty = if ($h.ContainsKey('21')) { $h['21'] } else { $h['20'] }
  if ($Win -and -not (In $tx $ty)) { continue }
  $dx = [Math]::Abs($h['14'] - $h['13']); $dy = [Math]::Abs($h['24'] - $h['23'])
  $ang = if ($h.ContainsKey('50')) { $h['50'] } else { 0 }
  $dir = if ([Math]::Abs([Math]::Sin($ang * [Math]::PI / 180)) -gt 0.7) { 'vertical' } elseif ($ang -ne 0) { 'horizontal' } elseif ($dx -ge $dy) { 'horizontal' } else { 'vertical' }
  [pscustomobject]@{ val = $h['42']; x1 = $h['13']; y1 = $h['23']; x2 = $h['14']; y2 = $h['24']; dir = $dir; lay = $lay }
}
$rows | Sort-Object dir, @{ e = { -$_.val } } | ForEach-Object {
  "{0,9} · ({1}, {2}) → ({3}, {4}) · {5} · [{6}]" -f $_.val.ToString('0.##', $inv), (F $_.x1), (F $_.y1), (F $_.x2), (F $_.y2), $_.dir, $_.lay
}

"`n=== OUTLINES on layer [$Layer] (closed or 4+ vertex LWPOLYLINE, box ≥ $MinLen)"
foreach ($e in $ents | Where-Object { $_.t -eq 'LWPOLYLINE' }) {
  $lay = ($e.g | Where-Object { $_[0] -eq '8' } | Select-Object -First 1)[1].Trim(); if ($lay -ne $Layer) { continue }
  $vs = New-Object System.Collections.Generic.List[object]; $closed = $false
  foreach ($p in $e.g) { switch ($p[0]) { '70' { $closed = ([int]$p[1].Trim() -band 1) -eq 1 } '10' { $vs.Add(@((P $p[1]), 0.0)) } '20' { $vs[$vs.Count - 1][1] = P $p[1] } } }
  if ($vs.Count -lt 3) { continue }
  $xs = $vs | ForEach-Object { $_[0] }; $ys = $vs | ForEach-Object { $_[1] }
  $bw = ($xs | Measure-Object -Maximum).Maximum - ($xs | Measure-Object -Minimum).Minimum; $bh = ($ys | Measure-Object -Maximum).Maximum - ($ys | Measure-Object -Minimum).Minimum
  if ([Math]::Max($bw, $bh) -lt $MinLen) { continue }
  if ($Win -and -not (In $vs[0][0] $vs[0][1])) { continue }
  "outline: $($vs.Count) vertices, closed=$closed, box $(F $bw) x $(F $bh)"
  $n = $vs.Count; $segs = if ($closed) { $n } else { $n - 1 }
  for ($i = 0; $i -lt $segs; $i++) {
    $a = $vs[$i]; $b = $vs[($i + 1) % $n]; $len = [Math]::Sqrt([Math]::Pow($b[0] - $a[0], 2) + [Math]::Pow($b[1] - $a[1], 2))
    if ($len -lt 0.05) { continue }
    "   ({0}, {1}) → ({2}, {3})   {4} m" -f (F $a[0]), (F $a[1]), (F $b[0]), (F $b[1]), (F $len)
  }
}
