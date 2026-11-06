param([switch]$IncludeAlphaRegression, [switch]$IncludeLoad, [switch]$ScriptedAcceptance)
$ErrorActionPreference = 'Stop'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE) { throw "Check failed: $Program $($Arguments[0])" }
}
function Get-PhaseRuntime([string]$Provider = '') {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        try {
            $value = Invoke-RestMethod 'http://127.0.0.1:18880/api/health' -TimeoutSec 3
            if (-not $Provider -or $value.model_provider -eq $Provider) { return $value }
        } catch { } # Caddy's active health check needs time to restore a recreated upstream.
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Phase 1 proxy/provider did not become ready'
}
Push-Location (Split-Path -Parent $PSScriptRoot)
$previousUrl = $env:PHASE1_URL
$previousProvider = $env:PHASE_MODEL_PROVIDER
$changedProvider = $false
try {
    $runtime = Get-PhaseRuntime
    if ($ScriptedAcceptance) {
        if ($runtime.model_provider -notin @('disabled','scripted')) { throw 'Scripted acceptance only runs on an offline dev/test deployment' }
        $changedProvider = $true
        $env:PHASE_MODEL_PROVIDER = 'scripted'
        Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','up','-d','--no-deps','--force-recreate','--wait','chat-1','chat-2')
        $runtime = Get-PhaseRuntime 'scripted'
    }
    $exists = & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db psql -U phase_owner -d phase1 -Atc "select 1 from pg_database where datname='phase1_test'"
    if ($LASTEXITCODE) { throw 'Start the Phase 1 environment first' }
    if ($exists -ne '1') { Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','exec','-T','db','createdb','-U','phase_owner','phase1_test') }
    Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','run','--rm','--no-deps','test')
    Invoke-Checked npm.cmd @('test')
    Invoke-Checked npm.cmd @('run','build')
    Invoke-Checked npm.cmd @('run','lint')
    $env:PHASE1_URL = 'http://127.0.0.1:18880'
    Invoke-Checked npm.cmd @('run','test:e2e')
    if ($runtime.model_provider -eq 'scripted') {
        Invoke-Checked backend/.venv/Scripts/python.exe @('-X','utf8','scripts/verify-phase1.py')
        Invoke-Checked backend/.venv/Scripts/python.exe @('-X','utf8','scripts/verify-phase1-tls.py')
    } else { Write-Output 'Scripted fault/TLS acceptance skipped; use -ScriptedAcceptance on the offline local deployment.' }
    if ($IncludeLoad) {
        if ($runtime.model_provider -ne 'scripted') { throw 'Offline load baseline needs -ScriptedAcceptance; real model load has a separate approval gate' }
        Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','run','--rm','--no-deps','seed','python','-m','app.phase_cli','seed-load','--output','/artifacts/phase1-load-tokens.json')
        foreach ($learners in @(30,40,50)) {
            Invoke-Checked backend/.venv/Scripts/python.exe @('-X','utf8','scripts/load-phase1.py','--tokens','.local/phase1-load-tokens.json','--learners',"$learners",'--seconds','60','--output',".local/phase1-load-$learners.json")
        }
    }
    if ($IncludeAlphaRegression) {
        Push-Location backend
        try {
            Invoke-Checked .venv/Scripts/python.exe @('-m','app.cli','export-openapi','--check')
            Invoke-Checked .venv/Scripts/python.exe @('-m','pytest','-q')
        } finally { Pop-Location }
    }
} finally {
    $env:PHASE1_URL = $previousUrl
    $env:PHASE_MODEL_PROVIDER = $previousProvider
    if ($changedProvider) {
        Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','up','-d','--no-deps','--force-recreate','--wait','chat-1','chat-2')
    }
    Pop-Location
}
exit 0
