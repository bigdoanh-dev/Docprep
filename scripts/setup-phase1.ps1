param([switch]$SkipSeed)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path -LiteralPath 'backend/.env')) {
        Copy-Item -LiteralPath 'backend/.env.example' -Destination 'backend/.env'
    }
    & docker version --format '{{.Server.Version}}'
    if ($LASTEXITCODE) { throw 'Start Docker Desktop first' }
    if (-not (Test-Path -LiteralPath '.env.phase1')) {
        $content = Get-Content -LiteralPath '.env.phase1.example' -Raw
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            foreach ($name in @('OWNER_DB_PASSWORD','MIGRATOR_DB_PASSWORD','BUSINESS_DB_PASSWORD','CHAT_DB_PASSWORD','REDIS_PASSWORD','GRAFANA_PASSWORD')) {
                $buffer = New-Object byte[] 24
                $rng.GetBytes($buffer)
                $value = [BitConverter]::ToString($buffer).Replace('-','').ToLowerInvariant()
                $content = [regex]::Replace($content, "(?m)^$name=.*$", "$name=$value")
            }
        } finally { $rng.Dispose() }
        [IO.File]::WriteAllText((Join-Path (Get-Location) '.env.phase1'), $content, [Text.UTF8Encoding]::new($false))
    }
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml up -d --wait db redis
    if ($LASTEXITCODE) { throw 'Phase 1 database/Redis startup failed' }
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db sh /docker-entrypoint-initdb.d/10-roles.sh
    if ($LASTEXITCODE) { throw 'Database role bootstrap failed' }
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml build api-1 caddy
    if ($LASTEXITCODE) { throw 'Phase 1 image build failed' }
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml up -d --wait
    if ($LASTEXITCODE) { throw 'Phase 1 startup failed; inspect docker compose logs' }
    if (-not $SkipSeed) {
        & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm seed
        if ($LASTEXITCODE) { throw 'Local seed failed' }
    }
    Write-Output 'Phase 1 local: http://127.0.0.1:18880 (see .env.phase1 if port changed)'
} finally { Pop-Location }
exit 0
