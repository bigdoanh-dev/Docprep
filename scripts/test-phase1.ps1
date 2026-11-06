param([switch]$IncludeAlphaRegression, [switch]$IncludeLoad)
$ErrorActionPreference = 'Stop'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE) { throw "Check failed: $Program $($Arguments[0])" }
}
Push-Location (Split-Path -Parent $PSScriptRoot)
$previousUrl = $env:PHASE1_URL
try {
    $exists = & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db psql -U phase_owner -d phase1 -Atc "select 1 from pg_database where datname='phase1_test'"
    if ($LASTEXITCODE) { throw 'Start the Phase 1 environment first' }
    if ($exists -ne '1') { Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','exec','-T','db','createdb','-U','phase_owner','phase1_test') }
    Invoke-Checked docker @('compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml','run','--rm','--no-deps','test')
    Invoke-Checked npm.cmd @('test')
    Invoke-Checked npm.cmd @('run','build')
    Invoke-Checked npm.cmd @('run','lint')
    $env:PHASE1_URL = 'http://127.0.0.1:18880'
    Invoke-Checked npm.cmd @('run','test:e2e')
    Invoke-Checked backend/.venv/Scripts/python.exe @('-X','utf8','scripts/verify-phase1.py')
    Invoke-Checked backend/.venv/Scripts/python.exe @('-X','utf8','scripts/verify-phase1-tls.py')
    if ($IncludeLoad) {
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
    Pop-Location
}
exit 0
