param()
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & docker version --format '{{.Server.Version}}'
    if ($LASTEXITCODE) { throw 'Start Docker Desktop first.' }
    if (-not (Test-Path -LiteralPath '.env.content')) {
        $content = Get-Content -LiteralPath '.env.content.example' -Raw
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            foreach ($name in @('CONTENT_OWNER_PASSWORD','CONTENT_APP_PASSWORD')) {
                $bytes = New-Object byte[] 24
                $rng.GetBytes($bytes)
                $value = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
                $content = [regex]::Replace($content,"(?m)^$name=.*$","$name=$value")
            }
        } finally { $rng.Dispose() }
        [IO.File]::WriteAllText((Join-Path (Get-Location) '.env.content'),$content,[Text.UTF8Encoding]::new($false))
    }
    New-Item -ItemType Directory -Path '.local/content' -Force | Out-Null
    & docker compose --env-file .env.content -f deploy/compose.content.yml build
    if ($LASTEXITCODE) { throw 'Content image build failed.' }
    & docker compose --env-file .env.content -f deploy/compose.content.yml up -d --wait
    if ($LASTEXITCODE) { throw 'Content startup failed; inspect compose logs.' }
    Write-Output 'Content workspace: http://127.0.0.1:18882 (or CONTENT_HTTP_PORT in .env.content)'
    Write-Output 'No default reviewer account is created. Provision it with the content-operator CLI.'
} finally { Pop-Location }
