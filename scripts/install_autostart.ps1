# Registers KOSPI-WATCHER to start automatically at Windows logon (no admin
# required). Primary mechanism: a hidden .vbs in the user's Startup folder.
# Bonus: a logon-triggered Scheduled Task (ignored if it needs elevation).
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
$ErrorActionPreference = "SilentlyContinue"

$root     = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root "scripts\start_kospi_watcher.ps1"
$startup  = [Environment]::GetFolderPath("Startup")
$vbsPath  = Join-Path $startup "kospi-watcher.vbs"

# Hidden launcher: wscript runs PowerShell with no window (style 0).
$vbs = 'CreateObject("WScript.Shell").Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""' + $launcher + '""", 0, False'
Set-Content -Path $vbsPath -Value $vbs -Encoding ASCII
Write-Host "[ok] Startup entry installed: $vbsPath"

# Bonus: logon Scheduled Task (best-effort; Startup folder already covers it).
$null = schtasks /Create /TN "KOSPI-WATCHER" /TR ('wscript.exe "' + $vbsPath + '"') /SC ONLOGON /F 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host "[ok] Scheduled task 'KOSPI-WATCHER' (at logon) created" }
else { Write-Host "[info] Scheduled task skipped (Startup-folder autostart is active)" }

Write-Host ""
Write-Host "Done. On the next logon (turn PC off/on, sign in), KOSPI-WATCHER starts"
Write-Host "automatically: API :18080, worker (08:00 KST briefing), web http://localhost:3000."
Write-Host "Telegram delivery activates once TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are in .env."
