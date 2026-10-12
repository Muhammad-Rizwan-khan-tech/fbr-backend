# ==============================================================================
# FBR Invoice Cloud - Windows Task Scheduler Automated Backup Registration
# Schedule: Daily at 02:00 UTC (runs backup_postgres.ps1)
# ==============================================================================
param (
    [string]$TaskName = "FBR_Invoice_Cloud_Daily_Backup",
    [string]$BackupDir = "D:\WORKING\FB DI\main\backups",
    [string]$ScriptPath = "D:\WORKING\FB DI\main\scripts\backup_postgres.ps1"
)

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -DestDir `"$BackupDir`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily PostgreSQL and Document Backup for FBR Invoice Cloud" -Force

Write-Host "[SUCCESS] Registered Windows Scheduled Task: $TaskName (Daily at 02:00)"
