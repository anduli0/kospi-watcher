# KOSPI-WATCHER launcher — starts API (18080) + worker (08:00 cron) + web (3000).
# Idempotent: re-running (or a duplicate logon trigger) is a no-op if already up.
# Invoked at logon by the Startup-folder .vbs (see install_autostart.ps1).
$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot        # scripts\ -> repo root
$py   = Join-Path $root ".venv\Scripts\python.exe"
$web  = Join-Path $root "apps\web"
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Location $root

# --- Environment (children of Start-Process inherit this) ---
$dbPath = ($root -replace '\\', '/') + "/kospi_watcher.db"
$env:DATABASE_URL          = "sqlite+aiosqlite:///$dbPath"
$env:TRADING_MODE          = "PAPER"
$env:MARKET_DATA_PROVIDER  = "yahoo"
$env:NEWS_PROVIDER         = "google"
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:18080"

# Optional secrets / overrides from .env (e.g. TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
      $val = $matches[2].Trim().Trim('"')
      if ($val -ne "") { Set-Item -Path ("Env:" + $matches[1]) -Value $val }
    }
  }
}

function Test-Port([int]$p) {
  [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

# --- Ensure DB schema exists (create_all; idempotent) ---
& $py (Join-Path $root "scripts\ensure_db.py") 1>> (Join-Path $logs "ensure_db.log") 2>&1

# --- API (18080) ---
if (-not (Test-Port 18080)) {
  Start-Process -WindowStyle Hidden -FilePath $py -WorkingDirectory $root `
    -ArgumentList '-m','uvicorn','main:app','--app-dir','apps/api','--host','127.0.0.1','--port','18080','--log-level','warning' `
    -RedirectStandardOutput (Join-Path $logs "api.out.log") `
    -RedirectStandardError  (Join-Path $logs "api.err.log")
}

# --- Worker (scheduler: 08:00 KST morning briefing + hourly news) ---
# The worker holds a single-instance lock on 18079; check that, not the process
# list (a benign idle child shares the worker's command line).
if (-not (Test-Port 18079)) {
  Start-Process -WindowStyle Hidden -FilePath $py -WorkingDirectory $root `
    -ArgumentList 'apps/worker/main.py' `
    -RedirectStandardOutput (Join-Path $logs "worker.out.log") `
    -RedirectStandardError  (Join-Path $logs "worker.err.log")
}

# --- Web (3000, production build) ---
if (-not (Test-Port 3000)) {
  if (-not (Test-Path (Join-Path $web ".next"))) {
    Push-Location $web
    & npm run build 1>> (Join-Path $logs "web.build.log") 2>&1
    Pop-Location
  }
  Start-Process -WindowStyle Hidden -FilePath "npm.cmd" -WorkingDirectory $web `
    -ArgumentList 'run','start' `
    -RedirectStandardOutput (Join-Path $logs "web.out.log") `
    -RedirectStandardError  (Join-Path $logs "web.err.log")
}
