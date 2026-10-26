[CmdletBinding()]
param([switch]$SkipCohort)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
    if (-not (Test-Path -LiteralPath 'backend/.venv/Scripts/python.exe')) {
        & py -3.13 -m venv backend/.venv
        if ($LASTEXITCODE) { throw 'Cannot create Python 3.13 environment' }
    }
    & backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
    if ($LASTEXITCODE) { throw 'Backend dependency installation failed' }
    & npm.cmd ci
    if ($LASTEXITCODE) { throw 'Frontend dependency installation failed' }
    & docker compose up -d --wait
    if ($LASTEXITCODE) { throw 'Start Docker Desktop, then retry setup' }
    Push-Location backend
    try {
        & .venv/Scripts/python.exe -m app.cli migrate
        if ($LASTEXITCODE) { throw 'Migration failed' }
        $seedArguments = @('-m', 'app.cli', 'seed-alpha')
        if ($SkipCohort) { $seedArguments += '--no-cohort' }
        & .venv/Scripts/python.exe @seedArguments
        if ($LASTEXITCODE) { throw 'Alpha seed failed' }
    } finally { Pop-Location }
    Write-Host 'Ready. Run scripts/start-backend.ps1 and npm.cmd run dev in separate terminals.'
} finally { Pop-Location }
