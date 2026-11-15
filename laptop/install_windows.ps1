# Lock In: install the laptop guard on Windows. Run in PowerShell **as Administrator**:
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1 -PiUrl http://lockin.local:8000
# Blocks sites in every browser (hosts file) and quits blocked apps while the box is locked.
param([string]$PiUrl = "http://lockin.local:8000")
$ErrorActionPreference = "Stop"

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction Stop).Source }
$dir = Join-Path $env:ProgramData "LockIn"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "lockin_guard.py") $dir -Force
@{ pi_url = $PiUrl } | ConvertTo-Json | Set-Content (Join-Path $dir "config.json")

$action  = New-ScheduledTaskAction -Execute $py -Argument "`"$dir\lockin_guard.py`" system"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "LockInGuard" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName "LockInGuard"
Write-Host "Installed. The laptop now follows the box at $PiUrl"
Write-Host "Uninstall: Unregister-ScheduledTask LockInGuard; python `"$dir\lockin_guard.py`" clear"
