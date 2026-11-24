<#
Headless DWG export with AutoCAD's core console (accoreconsole.exe).
Copies the DWG to a short work folder, then writes an ASCII DXF and/or PDF plots.
The original file and the user's open AutoCAD session are never touched.

  -Dwg      source .dwg (any path, spaces/parentheses OK)
  -WorkDir  short output folder (default %USERPROFILE%\dwgwork\<name>); keep the full path well under 200 chars
  -Window   plot windows in model space, each "name|x1,y1|x2,y2|P" (P = portrait, L = landscape)
  -Extents  also plot model-space extents (often blank when stray objects sit far away)
  -NoDxf    skip the DXF export

Example:
  .\dwg_export.ps1 -Dwg "C:\Users\sbs\Downloads\RELEVE (1).dwg" -Window "rdc|21308,24170|21368,24226|L"
#>
param(
  [Parameter(Mandatory = $true)][string]$Dwg,
  [string]$WorkDir = "",
  [string[]]$Window = @(),
  [switch]$Extents,
  [switch]$NoDxf,
  [switch]$Explode,   # explode every block (doors, furniture, people) before DXFOUT, so converters see their linework
  [int]$TimeoutSec = 240,
  [string]$Paper = "ISO full bleed A1 (841.00 x 594.00 MM)"
)
$ErrorActionPreference = "Stop"

$acc = Get-ChildItem "C:\Program Files\Autodesk\AutoCAD 20*\accoreconsole.exe" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending | Select-Object -First 1
if (-not $acc) { throw "accoreconsole.exe not found under C:\Program Files\Autodesk\AutoCAD 20*" }

$base = ([IO.Path]::GetFileNameWithoutExtension($Dwg) -replace '[^\w\-]', '_' -replace '_+', '_').Trim('_')
if (-not $WorkDir) { $WorkDir = Join-Path $env:USERPROFILE "dwgwork\$base" }
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$WorkDir = (Resolve-Path $WorkDir).Path
if ($WorkDir.Length -gt 180) { throw "WorkDir path is $($WorkDir.Length) chars; accoreconsole rejects long paths ('Improper drawing name'). Use a shorter -WorkDir." }

# Work on a copy with a plain name: long paths and odd characters break accoreconsole.
$copy = Join-Path $WorkDir "$base.dwg"
Copy-Item -LiteralPath $Dwg -Destination $copy -Force

function PlotBlock([string]$area, [string]$orient, [string]$out) {
  @"
_.-PLOT
_Y

DWG To PDF.pc3
$Paper
_M
$orient
_N
$area
_F
_C
_Y
monochrome.ctb
_Y

"$out"
_N
_Y
"@
}

# TILEMODE 1: a drawing saved on a paper-space layout otherwise gets the layout's -PLOT prompts and the script derails.
$lines = @("FILEDIA", "0", "TILEMODE", "1")
$dxfName = $base
if ($Explode) {
  # Unlock/thaw everything, then explode block references four times to reach nested blocks.
  $lines += @("(setvar `"QAFLAGS`" 1)", "(command `"_.-LAYER`" `"_THAW`" `"*`" `"_ON`" `"*`" `"_UNLOCK`" `"*`" `"`")",
    "(repeat 4 (if (setq ss (ssget `"_X`" '((0 . `"INSERT`")))) (command `"_.EXPLODE`" ss `"`")))")
  $dxfName = "${base}_x"
}
if (-not $NoDxf) { $lines += @("_.DXFOUT", "`"$WorkDir\$dxfName.dxf`"", "16") }
if ($Extents) { $lines += (PlotBlock "_E" "_L" "$WorkDir\${base}_extents.pdf") }
foreach ($w in $Window) {
  $p = $w -split '\|'
  if ($p.Count -lt 3) { throw "Bad -Window '$w' (expected name|x1,y1|x2,y2|P or L)" }
  $o = if ($p.Count -ge 4 -and $p[3].Trim().ToUpper() -eq 'P') { "_P" } else { "_L" }
  $lines += (PlotBlock "_W`r`n$($p[1].Trim())`r`n$($p[2].Trim())" $o "$WorkDir\${base}_$($p[0].Trim()).pdf")
}
# QUIT so the console exits instead of idling after the script.
$lines += @("_.QUIT", "_Y")
$scr = Join-Path $WorkDir "export.scr"
Set-Content -Path $scr -Value ($lines -join "`r`n") -Encoding ASCII

$log = Join-Path $WorkDir "console.log"
$proc = Start-Process -FilePath $acc.FullName -ArgumentList "/i `"$copy`" /s `"$scr`" /l en-US" `
  -NoNewWindow -PassThru -RedirectStandardOutput $log
if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
  $proc.Kill()
  Write-Warning "accoreconsole did not exit within $TimeoutSec s and was stopped; check outputs below."
}

$txt = (Get-Content $log -Raw -ErrorAction SilentlyContinue) -replace "`0", ""
($txt -split "`n") | Where-Object { $_ -match 'Effective plotting area|Improper|Invalid|error|not found|Unknown command' } |
  ForEach-Object { "console: " + $_.Trim() }
"WorkDir: $WorkDir"
Get-ChildItem $WorkDir -Include *.dxf, *.pdf -Recurse | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String
