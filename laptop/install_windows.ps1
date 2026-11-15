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

# The same UI as the box, in your desktop session. A SYSTEM task can't open a window, so this
# one runs as you at logon: while the box is locked it shows http://<pi>:8000/ full-screen.
$screenAction  = New-ScheduledTaskAction -Execute $py -Argument "`"$dir\lockin_guard.py`" screen"
$screenTrigger = New-ScheduledTaskTrigger -AtLogOn
$screenSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "LockInScreen" -Action $screenAction -Trigger $screenTrigger -Settings $screenSettings -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited -Force | Out-Null
Start-ScheduledTask -TaskName "LockInScreen"

Write-Host "Installed. The laptop now follows the box at $PiUrl"
Write-Host "While locked, Chrome/Edge shows the box's own screen full-screen."
Write-Host "Uninstall: Unregister-ScheduledTask LockInGuard, LockInScreen; python `"$dir\lockin_guard.py`" clear"
