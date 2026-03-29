$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$version = python -c "from app import __version__; print(__version__)"
if (-not $version) { Write-Error "Could not read app.__version__" }

New-Item -ItemType Directory -Force -Path "dist-packages" | Out-Null

$onefile = Join-Path $Root "dist\EncodeForge.exe"
if (Test-Path $onefile) {
    $out = Join-Path $Root "dist-packages\EncodeForge-$version-windows-x64.exe"
    if (Test-Path $out) { Remove-Item $out }
    Copy-Item -Path $onefile -Destination $out
    Write-Host "Wrote $out (one-file build)"
    exit 0
}

$dist = Get-ChildItem -Path "dist" -Directory -Filter "*.dist" | Select-Object -First 1
if (-not $dist) {
    Write-Error "No dist\EncodeForge.exe or dist\*.dist. Run: python build_nuitka.py"
}

$zip = Join-Path $Root "dist-packages\EncodeForge-$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }

Compress-Archive -Path (Join-Path $dist.FullName "*") -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Wrote $zip"
