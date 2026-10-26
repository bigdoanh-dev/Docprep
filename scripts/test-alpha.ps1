$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    Push-Location backend
    try {
        & .venv/Scripts/python.exe -m app.cli export-openapi --check
        if ($LASTEXITCODE) { throw 'OpenAPI drift detected' }
        & .venv/Scripts/python.exe -m pytest -q --junitxml=../.local/backend-tests.xml
        if ($LASTEXITCODE) { throw 'Backend tests failed' }
    } finally { Pop-Location }
    & npm.cmd test
    if ($LASTEXITCODE) { throw 'Frontend unit tests failed' }
    & npm.cmd run build
    if ($LASTEXITCODE) { throw 'Frontend build failed' }
    & npm.cmd run test:e2e
    if ($LASTEXITCODE) { throw 'Browser tests failed. Is the real backend running on :8000?' }
} finally { Pop-Location }
