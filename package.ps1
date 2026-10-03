# Builds dist\Phillap.zip containing only what is needed to run Phillap.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root 'dist'
$stage = Join-Path $dist 'Phillap'
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
foreach ($f in 'app.py','backup.py','index.html','forest-temple.svg','requirements.txt','Start-Phillap.bat','README.md','CHANGELOG.md') {
    Copy-Item (Join-Path $root $f) $stage
}
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath (Join-Path $dist 'Phillap.zip')
Write-Host "Built $(Join-Path $dist 'Phillap.zip')"