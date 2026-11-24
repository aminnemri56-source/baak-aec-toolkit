# Renders a local HTML or SVG page to PNG with headless Chrome.
# Chrome fails silently on very long paths, so it writes to a short temp folder and the result is copied afterwards.
param(
  [Parameter(Mandatory = $true)][string]$Html,
  [string]$Size = '1920,1080',
  [string]$Out,
  [string]$Hash = '',
  [int]$Budget = 12000
)
$ErrorActionPreference = 'Stop'
$page = (Resolve-Path -LiteralPath $Html).Path
if (-not $Out) { $Out = [IO.Path]::ChangeExtension($page, '.png') }
if ($Out.Length -ge 260) { throw "Output path is too long for Windows PowerShell (260 characters): $Out" }
$browser = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'Chrome or Edge not found.' }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ('vishot' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
$url = 'file:///' + (($page -replace '\\', '/') -replace ' ', '%20')
if ($page -match '\.svg$') {
  # An SVG opened directly keeps its own size, so wrap it to fill the requested window.
  $wrapper = Join-Path $tmp 'wrap.html'
  "<!doctype html><style>html,body{margin:0;background:#fff}img{display:block;width:100vw;height:100vh;object-fit:contain}</style><img src=`"$url`">" | Set-Content -LiteralPath $wrapper -Encoding UTF8
  $url = 'file:///' + (($wrapper -replace '\\', '/') -replace ' ', '%20')
}
if ($Hash) { $url += '#' + $Hash.TrimStart('#') }
$png = Join-Path $tmp 'shot.png'
$argLine = '--headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --no-sandbox --hide-scrollbars ' +
  '--user-data-dir="' + (Join-Path $tmp 'prof') + '" --screenshot="' + $png + '" ' +
  '--virtual-time-budget=' + $Budget + ' --window-size=' + ($Size -replace ' ', '') + ' "' + $url + '"'
Start-Process -FilePath $browser -ArgumentList $argLine -WindowStyle Hidden -Wait
if (-not (Test-Path $png)) {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  throw "No screenshot was produced for $page. If the path is over 260 characters, move the page somewhere shorter."
}
Copy-Item -LiteralPath $png -Destination $Out -Force
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Output $Out
