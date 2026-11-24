# Lists the images in a folder from darkest to lightest, with their average brightness from 0 to 1.
param([Parameter(Mandatory = $true)][string]$In)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$culture = [Globalization.CultureInfo]::InvariantCulture
$rows = Get-ChildItem -LiteralPath (Resolve-Path -LiteralPath $In).Path -File | Where-Object { $_.Extension -match '^\.(png|jpe?g)$' } | ForEach-Object {
  $img = [Drawing.Image]::FromFile($_.FullName)
  $bmp = New-Object Drawing.Bitmap 32, 32
  $g = [Drawing.Graphics]::FromImage($bmp)
  $g.Clear([Drawing.Color]::White)
  $g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBilinear
  $g.DrawImage($img, 0, 0, 32, 32)
  $sum = 0.0
  for ($y = 0; $y -lt 32; $y++) {
    for ($x = 0; $x -lt 32; $x++) {
      $p = $bmp.GetPixel($x, $y)
      $sum += 0.2126 * $p.R + 0.7152 * $p.G + 0.0722 * $p.B
    }
  }
  $g.Dispose(); $bmp.Dispose(); $img.Dispose()
  [pscustomobject]@{ Name = $_.Name; Luminance = $sum / (32 * 32 * 255) }
}
$rows | Sort-Object Luminance | ForEach-Object { '{0}  {1}' -f $_.Luminance.ToString('0.000', $culture), $_.Name }
