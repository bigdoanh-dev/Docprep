param([string]$RestoreDatabase)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $dump = "/backups/manual-$stamp.dump"
    & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db pg_dump -U phase_owner -d phase1 -Fc --no-owner -f $dump
    if ($LASTEXITCODE) { throw 'Backup failed' }
    Write-Output "Created container backup: $dump"
    if ($RestoreDatabase) {
        if ($RestoreDatabase -notmatch '^phase1_restore_[a-z0-9_]+$') { throw 'Restore requires a new phase1_restore_* database' }
        & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db createdb -U phase_owner $RestoreDatabase
        if ($LASTEXITCODE) { throw 'Restore destination already exists or cannot be created; no overwrite performed' }
        & docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db pg_restore -U phase_owner -d $RestoreDatabase --no-owner --exit-on-error $dump
        if ($LASTEXITCODE) { throw 'Restore failed' }
        Write-Output "Restored into $RestoreDatabase; verify data before changing application URLs"
    }
} finally { Pop-Location }
exit 0
