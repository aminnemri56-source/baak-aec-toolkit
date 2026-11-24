<#
Convert the linework of an ASCII DXF window to a clean SVG (LINE, LWPOLYLINE with bulges, ARC, CIRCLE).
Blocks (INSERT), hatches and texts are skipped: add labels on top of the SVG instead.

  -Dxf     the .dxf file
  -Win     "x1,y1,x2,y2" in drawing units; entities whose box touches it are kept
  -Width   output width in px (height follows the window's proportions)
  -Layers  comma list of layers to keep (empty = all)
  -Style   "layer=#color:width;layer2=#color:width" (others use -Stroke/-StrokeWidth)
  -Out     .svg path. Prints the transform so labels can be placed: px = (x - x1) * s, py = (y2 - y) * s

Example:
  .\dxf_to_svg.ps1 -Dxf plan.dxf -Win "21308,24172,21364,24221" -Width 1600 -Layers "00-mur,MUR" -Out plan.svg
#>
param(
  [Parameter(Mandatory = $true)][string]$Dxf,
  [Parameter(Mandatory = $true)][string]$Win,
  [double]$Width = 1600,
  [string]$Layers = "",
  [string]$Style = "",
  [string]$Stroke = "#2b2f36",
  [double]$StrokeWidth = 1.2,
  [switch]$Rotate180,
  [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Stop"
$inv = [Globalization.CultureInfo]::InvariantCulture
function P([string]$v) { [double]::Parse($v.Trim(), $inv) }
$w = $Win -split ',' | ForEach-Object { P $_ }; $x1, $y1, $x2, $y2 = $w
$s = $Width / ($x2 - $x1); $H = [Math]::Round(($y2 - $y1) * $s, 1)
# -Rotate180 turns the drawing upside down (e.g. street side to the bottom); arc flags are unchanged by a rotation.
function X([double]$x) { $(if ($Rotate180) { ($x2 - $x) * $s } else { ($x - $x1) * $s }).ToString('0.#', $inv) }
function Y([double]$y) { $(if ($Rotate180) { ($y - $y1) * $s } else { ($y2 - $y) * $s }).ToString('0.#', $inv) }
$keep = @{}; if ($Layers) { $Layers -split ',' | ForEach-Object { $keep[$_.Trim()] = $true } }
$sty = @{}; if ($Style) { $Style -split ';' | Where-Object { $_ } | ForEach-Object { $k, $v = $_ -split '=', 2; $c, $sw = $v -split ':'; $sty[$k.Trim()] = @($c.Trim(), $(if ($sw) { P $sw } else { $StrokeWidth })) } }

$L = [IO.File]::ReadAllLines($Dxf)
$st = -1; for ($k = 0; $k -lt $L.Length - 1; $k++) { if ($L[$k].Trim() -eq '2' -and $L[$k + 1].Trim() -eq 'ENTITIES') { $st = $k + 2; break } }
if ($st -lt 0) { throw "No ENTITIES section" }

# Collect raw group pairs per entity.
$ents = New-Object System.Collections.Generic.List[object]; $cur = $null
for ($k = $st; $k -lt $L.Length - 1; $k += 2) {
  $c = $L[$k].Trim(); $v = $L[$k + 1]
  if ($c -eq '0') { if ($cur) { $ents.Add($cur) }; if ($v.Trim() -eq 'ENDSEC') { $cur = $null; break }; $cur = @{ t = $v.Trim(); g = New-Object System.Collections.Generic.List[object] }; continue }
  if ($cur) { $cur.g.Add(@($c, $v)) }
}

# Only coordinate/size codes are numbers worth parsing (handles and names are not).
$num = @('10', '20', '11', '21', '40', '50', '51')
$paths = @{}
function Inside([double]$a, [double]$b, [double]$c, [double]$d) { -not ($c -lt $x1 -or $a -gt $x2 -or $d -lt $y1 -or $b -gt $y2) }
function ArcSeg([double]$cx, [double]$cy, [double]$r, [double]$a0, [double]$a1) {
  $sweepDeg = (($a1 - $a0) % 360 + 360) % 360; if ($sweepDeg -eq 0) { $sweepDeg = 360 }
  $r0 = $a0 * [Math]::PI / 180; $r1 = $a1 * [Math]::PI / 180
  $sx = $cx + $r * [Math]::Cos($r0); $sy = $cy + $r * [Math]::Sin($r0); $ex = $cx + $r * [Math]::Cos($r1); $ey = $cy + $r * [Math]::Sin($r1)
  $la = if ($sweepDeg -gt 180) { 1 } else { 0 }; $R = ($r * $s).ToString('0.##', $inv)
  # DXF arcs run counter-clockwise; with Y flipped that is SVG sweep-flag 0.
  "M$(X $sx) $(Y $sy)A$R $R 0 $la 0 $(X $ex) $(Y $ey)"
}
foreach ($e in $ents) {
  $lay = ($e.g | Where-Object { $_[0] -eq '8' } | Select-Object -First 1)[1].Trim()
  if ($Layers -and -not $keep.ContainsKey($lay)) { continue }
  $d = ""
  switch ($e.t) {
    'LINE' {
      $gx = @{}; foreach ($p in $e.g) { if ($p[0] -in $num) { $gx[$p[0]] = P $p[1] } }
      if (Inside ([Math]::Min($gx['10'], $gx['11'])) ([Math]::Min($gx['20'], $gx['21'])) ([Math]::Max($gx['10'], $gx['11'])) ([Math]::Max($gx['20'], $gx['21']))) {
        $d = "M$(X $gx['10']) $(Y $gx['20'])L$(X $gx['11']) $(Y $gx['21'])" }
    }
    'LWPOLYLINE' {
      $vs = New-Object System.Collections.Generic.List[object]; $closed = $false
      foreach ($p in $e.g) {
        switch ($p[0]) { '70' { $closed = ([int]$p[1].Trim() -band 1) -eq 1 } '10' { $vs.Add(@((P $p[1]), 0.0, 0.0)) } '20' { $vs[$vs.Count - 1][1] = P $p[1] } '42' { $vs[$vs.Count - 1][2] = P $p[1] } }
      }
      if ($vs.Count -lt 2) { break }
      $xs = $vs | ForEach-Object { $_[0] }; $ys = $vs | ForEach-Object { $_[1] }
      if (-not (Inside ($xs | Measure-Object -Minimum).Minimum ($ys | Measure-Object -Minimum).Minimum ($xs | Measure-Object -Maximum).Maximum ($ys | Measure-Object -Maximum).Maximum)) { break }
      $n = $vs.Count; $segs = if ($closed) { $n } else { $n - 1 }
      $d = "M$(X $vs[0][0]) $(Y $vs[0][1])"
      for ($i = 0; $i -lt $segs; $i++) {
        $a = $vs[$i]; $b = $vs[($i + 1) % $n]; $bu = $a[2]
        if ([Math]::Abs($bu) -lt 1e-9) { $d += "L$(X $b[0]) $(Y $b[1])"; continue }
        $chord = [Math]::Sqrt([Math]::Pow($b[0] - $a[0], 2) + [Math]::Pow($b[1] - $a[1], 2)); $th = 4 * [Math]::Atan([Math]::Abs($bu))
        $r = $chord / (2 * [Math]::Sin($th / 2)); $R = ($r * $s).ToString('0.##', $inv)
        $la = if ($th -gt [Math]::PI) { 1 } else { 0 }; $sw = if ($bu -gt 0) { 0 } else { 1 }
        $d += "A$R $R 0 $la $sw $(X $b[0]) $(Y $b[1])"
      }
      if ($closed) { $d += "Z" }
    }
    'ARC' {
      $gx = @{}; foreach ($p in $e.g) { if ($p[0] -in $num) { $gx[$p[0]] = P $p[1] } }
      if (Inside ($gx['10'] - $gx['40']) ($gx['20'] - $gx['40']) ($gx['10'] + $gx['40']) ($gx['20'] + $gx['40'])) { $d = ArcSeg $gx['10'] $gx['20'] $gx['40'] $gx['50'] $gx['51'] }
    }
    'ELLIPSE' {
      $gx = @{}; foreach ($p in $e.g) { if ($p[0] -in '10', '20', '11', '21', '40', '41', '42') { if (-not $gx.ContainsKey($p[0])) { $gx[$p[0]] = P $p[1] } } }
      $cx = $gx['10']; $cy = $gx['20']; $mx = $gx['11']; $my = $gx['21']; $ra = $gx['40']
      $t0 = if ($gx.ContainsKey('41')) { $gx['41'] } else { 0 }; $t1 = if ($gx.ContainsKey('42')) { $gx['42'] } else { 2 * [Math]::PI }
      $a = [Math]::Sqrt($mx * $mx + $my * $my); $b = $a * $ra
      if (-not (Inside ($cx - $a) ($cy - $a) ($cx + $a) ($cy + $a))) { break }
      # Point at parameter t: centre + cos(t)*major + sin(t)*minor, minor = ratio * major turned 90 degrees CCW.
      $pt = { param($t) @(($cx + [Math]::Cos($t) * $mx - [Math]::Sin($t) * $ra * $my), ($cy + [Math]::Cos($t) * $my + [Math]::Sin($t) * $ra * $mx)) }
      $vx = if ($Rotate180) { -$mx } else { $mx }; $vy = if ($Rotate180) { $my } else { -$my }
      $rot = ([Math]::Atan2($vy, $vx) * 180 / [Math]::PI).ToString('0.#', $inv)
      $RX = ($a * $s).ToString('0.##', $inv); $RY = ($b * $s).ToString('0.##', $inv)
      $span = $t1 - $t0; while ($span -le 0) { $span += 2 * [Math]::PI }
      if ([Math]::Abs($span - 2 * [Math]::PI) -lt 1e-6) {
        $p0 = & $pt 0; $p1 = & $pt ([Math]::PI)
        $d = "M$(X $p0[0]) $(Y $p0[1])A$RX $RY $rot 0 0 $(X $p1[0]) $(Y $p1[1])A$RX $RY $rot 0 0 $(X $p0[0]) $(Y $p0[1])"
      } else {
        $p0 = & $pt $t0; $p1 = & $pt $t1; $la = if ($span -gt [Math]::PI) { 1 } else { 0 }
        $d = "M$(X $p0[0]) $(Y $p0[1])A$RX $RY $rot $la 0 $(X $p1[0]) $(Y $p1[1])"
      }
    }
    'CIRCLE' {
      $gx = @{}; foreach ($p in $e.g) { if ($p[0] -in $num) { $gx[$p[0]] = P $p[1] } }
      if (Inside ($gx['10'] - $gx['40']) ($gx['20'] - $gx['40']) ($gx['10'] + $gx['40']) ($gx['20'] + $gx['40'])) { $d = (ArcSeg $gx['10'] $gx['20'] $gx['40'] 0 180) + (ArcSeg $gx['10'] $gx['20'] $gx['40'] 180 360) }
    }
  }
  if ($d) { if (-not $paths.ContainsKey($lay)) { $paths[$lay] = New-Object System.Text.StringBuilder }; [void]$paths[$lay].Append($d) }
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.Append("<svg xmlns=`"http://www.w3.org/2000/svg`" width=`"$([Math]::Round($Width))`" height=`"$([Math]::Round($H))`" viewBox=`"0 0 $([Math]::Round($Width)) $([Math]::Round($H))`" fill=`"none`" stroke-linecap=`"round`" stroke-linejoin=`"round`">")
foreach ($lay in $paths.Keys) {
  $c = $Stroke; $sw = $StrokeWidth; if ($sty.ContainsKey($lay)) { $c = $sty[$lay][0]; $sw = $sty[$lay][1] }
  [void]$sb.Append("<path stroke=`"$c`" stroke-width=`"$($sw.ToString($inv))`" d=`"$($paths[$lay].ToString())`"/>")
}
[void]$sb.Append("</svg>")
[IO.File]::WriteAllText($Out, $sb.ToString())
"wrote $Out  $([Math]::Round($Width))x$([Math]::Round($H)) px, $([Math]::Round((Get-Item $Out).Length / 1KB, 1)) KB, layers: $(($paths.Keys | Sort-Object) -join ', ')"
if ($Rotate180) { "transform: px = ($x2 - x) * $($s.ToString('0.#####', $inv)) ; py = (y - $y1) * $($s.ToString('0.#####', $inv))" }
else { "transform: px = (x - $x1) * $($s.ToString('0.#####', $inv)) ; py = ($y2 - y) * $($s.ToString('0.#####', $inv))" }
