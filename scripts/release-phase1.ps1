param([Parameter(Mandatory=$true)][ValidateSet('api-1','api-2','chat-1','chat-2')][string]$Service)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T $Service python -m app.phase_cli drain
    if ($LASTEXITCODE) { throw 'Drain failed' }
    $deadline = [DateTime]::UtcNow.AddSeconds(150)
    do {
        # Conservative: wait for all running turns, not just the target. Calls in quarantine need operator review.
        $count = & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db psql -U phase_owner -d phase1 -Atc "select count(*) from ai_turn where status='running'"
        if ($LASTEXITCODE) { throw 'Cannot verify running turns' }
        if ([int]$count -eq 0) { break }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Drain timed out; instance remains drained, not forcibly replaced' }
        Start-Sleep -Seconds 2
    } while ($true)
    Start-Sleep -Seconds 8 # 5s health interval + 2s timeout + scheduling margin
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml up -d --no-deps --force-recreate --wait $Service
    if ($LASTEXITCODE) { throw 'Replacement failed; inspect readiness before continuing' }
} finally { Pop-Location }
exit 0
