[CmdletBinding()]
param(
    [switch]$SkipSetup,
    [ValidateRange(1024, 65535)][int]$Port = 5190
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousBackend = $env:BACKEND_URL
Push-Location $projectRoot
try {
    if (-not $SkipSetup) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'setup-phase1.ps1')
        if ($LASTEXITCODE) { throw 'Phase 1 setup failed; frontend was not started.' }
    }

    $backendPort = '18880'
    if (Test-Path -LiteralPath '.env.phase1') {
        foreach ($line in Get-Content -LiteralPath '.env.phase1') {
            if ($line -match '^\s*PHASE_HTTP_PORT\s*=\s*(\d+)\s*$') { $backendPort = $Matches[1] }
        }
    }
    if ($env:PHASE_HTTP_PORT) { $backendPort = $env:PHASE_HTTP_PORT }
    if ($backendPort -notmatch '^\d+$' -or [int]$backendPort -lt 1024 -or [int]$backendPort -gt 65535) {
        throw 'PHASE_HTTP_PORT must be between 1024 and 65535.'
    }
    $env:BACKEND_URL = "http://127.0.0.1:$backendPort"
    try {
        $runtime = Invoke-RestMethod "$($env:BACKEND_URL)/api/health" -TimeoutSec 10
    } catch {
        throw 'Phase 1 API is unreachable. Open Docker Desktop and run npm.cmd run dev:full.'
    }
    if (-not $runtime.ok -or $runtime.mode -ne 'real' -or $runtime.service -ne 'chat') {
        throw 'Expected the real Phase 1 API. Check PHASE_HTTP_PORT and the running Docker stack.'
    }
    if (-not (Test-Path -LiteralPath 'node_modules/.bin/vite.cmd')) {
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }
    }
    Write-Output "Frontend: http://127.0.0.1:$Port/dang-nhap"
    Write-Output "API: $($env:BACKEND_URL) (AI provider: $($runtime.model_provider))"
    & npm.cmd run dev -- --port $Port --strictPort
    if ($LASTEXITCODE) { throw 'Frontend stopped with an error.' }
} finally {
    $env:BACKEND_URL = $previousBackend
    Pop-Location
}
