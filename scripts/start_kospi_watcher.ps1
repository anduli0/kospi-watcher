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

# --- API (18080) — self-healing loop (_kw-api.bat restarts uvicorn if it dies) ---
if (-not (Test-Port 18080)) {
  Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
    -ArgumentList '/c', (Join-Path $root "_kw-api.bat") -WorkingDirectory $root
}

# --- Worker (scheduler: 08:00 KST briefing + catch-up + hourly news) — self-healing loop ---
# The worker holds a single-instance lock on 18079; check that, not the process
# list (a benign idle child — and the us-watcher worker — share the command line).
# _kw-worker.bat restarts the worker if it dies, so a crash never kills the daily brief.
if (-not (Test-Port 18079)) {
  Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
    -ArgumentList '/c', (Join-Path $root "_kw-worker.bat") -WorkingDirectory $root
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

# --- Public tunnel (prod web 3100 + cloudflared Quick Tunnel) — self-healing daemon ---
# Keeps the public HTTPS URL alive and current-url.txt fresh; the redirect server
# below points the stable bookmark at it. Its lock (18078) makes this a no-op if up.
Start-Process -WindowStyle Hidden -FilePath "powershell" `
  -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', `
                (Join-Path $root "scripts\public-tunnel-daemon.ps1")

# --- Stable-URL redirector (18077) ---
# Tailscale Funnel mounts https://krw-watcher.tail3e31a9.ts.net/kospi -> 127.0.0.1:18077,
# and this server 302-redirects to the live Quick Tunnel URL (current-url.txt). The
# bookmark never changes even though the underlying tunnel URL does. The Tailscale
# funnel mount itself persists in tailscaled across reboots (no script needed).
if (-not (Test-Port 18077)) {
  Start-Process -WindowStyle Hidden -FilePath $py -WorkingDirectory $root `
    -ArgumentList (Join-Path $root "scripts\redirect_server.py") `
    -RedirectStandardOutput (Join-Path $logs "redirect.out.log") `
    -RedirectStandardError  (Join-Path $logs "redirect.err.log")
}
