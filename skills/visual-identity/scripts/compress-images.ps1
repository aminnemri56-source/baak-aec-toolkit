# Resizes every PNG or JPEG in a folder and saves it as JPEG in another folder. Originals are never changed.
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$MaxSide = 1600,
  [int]$Quality = 82
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$source = (Resolve-Path -LiteralPath $In).Path
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$target = (Resolve-Path -LiteralPath $Out).Path
if ($source -eq $target) { throw 'In and Out must be different folders.' }

$codec = [Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$params = New-Object Drawing.Imaging.EncoderParameters 1
$params.Param[0] = New-Object Drawing.Imaging.EncoderParameter ([Drawing.Imaging.Encoder]::Quality), ([long]$Quality)

$count = 0; $bytes = 0
Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Extension -match '^\.(png|jpe?g)$' } | ForEach-Object {
  $img = [Drawing.Image]::FromFile($_.FullName)
  $scale = [Math]::Min(1.0, $MaxSide / [Math]::Max($img.Width, $img.Height))
  $w = [int][Math]::Round($img.Width * $scale); $h = [int][Math]::Round($img.Height * $scale)
  $bmp = New-Object Drawing.Bitmap $w, $h
  $g = [Drawing.Graphics]::FromImage($bmp)
  $g.Clear([Drawing.Color]::White)
  $g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($img, 0, 0, $w, $h)
  $dest = Join-Path $target ($_.BaseName + '.jpg')
  $bmp.Save($dest, $codec, $params)
  $g.Dispose(); $bmp.Dispose(); $img.Dispose()
  $count++; $bytes += (Get-Item -LiteralPath $dest).Length
}
Write-Output ("{0} images, {1} MB, in {2}" -f $count, ($bytes / 1MB).ToString('0.0', [Globalization.CultureInfo]::InvariantCulture), $target)
