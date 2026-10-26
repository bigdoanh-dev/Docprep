$ErrorActionPreference = 'Stop'
Push-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'backend')
try {
    & .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE) { throw 'Backend stopped with an error' }
} finally { Pop-Location }
