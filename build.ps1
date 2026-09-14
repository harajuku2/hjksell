$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Create it with: py -3.13 -m venv .venv"
}

foreach ($artifact in @(
    (Join-Path $PSScriptRoot "build"),
    (Join-Path $PSScriptRoot "dist"),
    (Join-Path $PSScriptRoot "HJKsell.spec")
)) {
    if (Test-Path $artifact) {
        Remove-Item -LiteralPath $artifact -Recurse -Force
    }
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name HJKsell `
    --distpath (Join-Path $PSScriptRoot "dist") `
    --workpath (Join-Path $PSScriptRoot "build") `
    --icon (Join-Path $PSScriptRoot "assets\icons\hjksell.ico") `
    --add-data "alembic;alembic" `
    --add-data "assets\icons;assets\icons" `
    --add-data "assets\fonts\onest;assets\fonts\onest" `
    --add-data "assets\fonts\kulag-sha;assets\fonts\kulag-sha" `
    --add-data "assets\fonts\oswald;assets\fonts\oswald" `
    --collect-all PySide6 `
    (Join-Path $PSScriptRoot "run_hjksell.py")

Write-Host "Build complete: $PSScriptRoot\dist\HJKsell\HJKsell.exe"
