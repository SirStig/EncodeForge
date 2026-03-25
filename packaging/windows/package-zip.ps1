$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$dist = Get-ChildItem -Path "dist" -Directory -Filter "*.dist" | Select-Object -First 1
if (-not $dist) {
    Write-Error "No dist\*.dist folder. Run: python build_nuitka.py"
}

$version = python -c "from app import __version__; print(__version__)"
if (-not $version) { Write-Error "Could not read app.__version__" }

New-Item -ItemType Directory -Force -Path "dist-packages" | Out-Null
$zip = Join-Path $Root "dist-packages\EncodeForge-$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }

Compress-Archive -Path (Join-Path $dist.FullName "*") -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Wrote $zip"
