$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root 'dist'
$build = Join-Path $env:TEMP ("Phillap-build-" + [guid]::NewGuid().ToString('N'))
$stage = Join-Path $build 'package'
$stageDocs = Join-Path $stage 'docs'
New-Item -ItemType Directory -Force $dist, $stageDocs | Out-Null
try {
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or newer is required to build Phillap.' }
    python -c "import PyInstaller, cryptography, pypdf"
    if ($LASTEXITCODE -ne 0) { throw 'Install build dependencies with: python -m pip install -r requirements-build.txt' }
    $arguments = @(
        '--noconfirm', '--clean', '--onefile', '--console', '--name', 'Phillap',
        '--distpath', $dist, '--workpath', (Join-Path $build 'work'), '--specpath', $build,
        '--add-data', ((Join-Path $root 'index.html') + ';.'),
        '--add-data', ((Join-Path $root 'forest-temple.svg') + ';.'),
        '--collect-all', 'cryptography', '--collect-all', 'pypdf',
        (Join-Path $root 'app.py')
    )
    python -m PyInstaller @arguments
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller could not build Phillap.exe.' }
    Copy-Item (Join-Path $dist 'Phillap.exe') $stage
    Copy-Item (Join-Path $root 'README.md') $stage
    Copy-Item (Join-Path $root 'CHANGELOG.md') $stage
    Copy-Item (Join-Path $root 'docs\user-guide.md') $stageDocs
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath (Join-Path $dist 'Phillap.zip') -Force
    Write-Host "Built standalone executable: $(Join-Path $dist 'Phillap.exe')"
    Write-Host "Built release bundle: $(Join-Path $dist 'Phillap.zip')"
}
finally {
    if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
}
