# ==============================================================================
# FBR Invoice Cloud - PostgreSQL & Documents Automated Backup Script (Windows)
# ==============================================================================
param (
    [string]$DestDir = "./backups"
)

$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $DestDir "fbr_invoice_cloud_$Timestamp.sql"

if (!(Test-Path $DestDir)) {
    New-Item -ItemType Directory -Path $DestDir | Out-Null
}

Write-Host "[INFO] Starting database backup at $(Get-Date)..." -ForegroundColor Cyan

$dbUrl = $env:DATABASE_URL
if ($dbUrl -and $dbUrl.StartsWith("sqlite:///")) {
    $sqlitePath = $dbUrl.Replace("sqlite:///", "")
    $sqliteDest = Join-Path $DestDir "fbr_invoice_cloud_$Timestamp.db"
    Copy-Item -Path $sqlitePath -Destination $sqliteDest -Force
    $hash = (Get-FileHash -Path $sqliteDest -Algorithm SHA256).Hash
    Set-Content -Path "$sqliteDest.sha256" -Value $hash
    Write-Host "[SUCCESS] SQLite database backed up to $sqliteDest (SHA256: $hash)" -ForegroundColor Green
} else {
    $pghost = if ($env:PGHOST) { $env:PGHOST } else { "localhost" }
    $pgport = if ($env:PGPORT) { $env:PGPORT } else { "5432" }
    $pguser = if ($env:PGUSER) { $env:PGUSER } else { "postgres" }
    $pgdb   = if ($env:PGDATABASE) { $env:PGDATABASE } else { "fbr_invoice_cloud" }

    pg_dump -h $pghost -p $pgport -U $pguser -d $pgdb --no-owner --no-privileges -f $BackupFile
    $hash = (Get-FileHash -Path $BackupFile -Algorithm SHA256).Hash
    Set-Content -Path "$BackupFile.sha256" -Value $hash
    Write-Host "[SUCCESS] PostgreSQL backup completed: $BackupFile (SHA256: $hash)" -ForegroundColor Green
}
