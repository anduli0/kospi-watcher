# KOSPI-WATCHER — self-healing public tunnel daemon.
#
# Keeps a Cloudflare Quick Tunnel alive in front of the prod web
# (3100 -> /api proxy -> 18080). Quick Tunnel URLs change whenever cloudflared
# (re)starts, so on EVERY (re)start this daemon:
#   1) captures the new https://*.trycloudflare.com URL from the log,
#   2) writes it to scripts\current-url.txt, and
#   3) pushes it to Telegram (creds read from the repo-root .env).
# As long as the PC + this daemon stay up, the URL is stable; if anything
# restarts the tunnel, you get the fresh URL on Telegram instantly.
#
# Single-instance (lock on 127.0.0.1:18078). Launched hidden at logon by
# start_kospi_watcher.ps1, and runnable manually for a one-off start.

$ErrorActionPreference = "SilentlyContinue"
$root      = Split-Path -Parent $PSScriptRoot       # scripts\ -> repo root
$web       = Join-Path $root "apps\web"
$exe       = Join-Path $PSScriptRoot "bin\cloudflared.exe"
$log       = Join-Path $PSScriptRoot "tunnel.log"
$urlFile   = Join-Path $PSScriptRoot "current-url.txt"
$apiTarget = "http://127.0.0.1:18080"

# --- single-instance lock (a free local port we just hold open) ---
try {
  $lock = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 18078)
  $lock.Start()
} catch {
  exit 0   # another daemon already owns the tunnel
}

function Test-Port([int]$p) {
  [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

# --- Telegram creds from repo-root .env (token never logged) ---
$tgToken = $null; $tgChat = $null
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*TELEGRAM_BOT_TOKEN\s*=\s*(.+?)\s*$') { $tgToken = $matches[1].Trim().Trim('"') }
    if ($line -match '^\s*TELEGRAM_CHAT_ID\s*=\s*(.+?)\s*$')   { $tgChat  = $matches[1].Trim().Trim('"') }
  }
}

function Send-Telegram([string]$text) {
  if (-not $tgToken -or -not $tgChat) { return }
  try {
    Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$tgToken/sendMessage" `
      -Body @{ chat_id = $tgChat; text = $text } -TimeoutSec 15 | Out-Null
  } catch {}
}

# --- ensure the prod web is up on 3100 (separate build dir from `next dev`) ---
if (-not (Test-Port 3100)) {
  $distExists = Test-Path (Join-Path $web ".next-public")
  $cmd = "cd /d `"$web`" && set NEXT_DIST_DIR=.next-public&& set API_PROXY_TARGET=$apiTarget&& "
  if (-not $distExists) { $cmd += "npx next build && " }
  $cmd += "npx next start -p 3100"
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Hidden
  for ($i = 0; $i -lt 90; $i++) { if (Test-Port 3100) { break }; Start-Sleep -Milliseconds 800 }
}

# --- Cloudflare Quick Tunnel RETIRED ---
# KOSPI is now served on a DEDICATED Tailscale Funnel port (8443 -> 3100). The
# Cloudflare Quick Tunnel kept rotating its URL (and was blocked on some networks),
# which repeatedly broke the public link. The stable bookmark
# https://krw-watcher.tail3e31a9.ts.net/kospi now 302-redirects to that fixed port via
# current-url.txt, and https://krw-watcher.tail3e31a9.ts.net:8443 works directly. No
# rotation. (The funnel mount itself persists in tailscaled across reboots.)
# NOTE: 2026-06-19 swapped 10000 -> 8443 — :10000 was reassigned to US-watcher, and
# fed moved to 443/fed, freeing 8443 for KOSPI as its permanent dedicated port.
$stableUrl = "https://krw-watcher.tail3e31a9.ts.net:8443"

# Stop any leftover cloudflared (no longer needed) and pin the stable URL for /kospi.
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match '3100' } |
  ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
if ((Get-Content $urlFile -ErrorAction SilentlyContinue) -ne $stableUrl) {
  Set-Content -Path $urlFile -Value $stableUrl -Encoding ASCII
  Send-Telegram "✅ KOSPI-WATCHER 공개 주소가 고정됐습니다 (Cloudflare 제거, 더는 안 바뀜):`n`n$stableUrl`n`n고정 북마크 https://krw-watcher.tail3e31a9.ts.net/kospi 도 이 주소로 연결됩니다."
}

# Keep the prod web (3100) alive forever — the funnel port + the /kospi redirect both
# depend on it. (This replaces the old cloudflared supervisor.)
while ($true) {
  if (-not (Test-Port 3100)) {
    $distExists = Test-Path (Join-Path $web ".next-public")
    $cmd = "cd /d `"$web`" && set NEXT_DIST_DIR=.next-public&& set API_PROXY_TARGET=$apiTarget&& "
    if (-not $distExists) { $cmd += "npx next build && " }
    $cmd += "npx next start -p 3100"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Hidden
    for ($i = 0; $i -lt 90; $i++) { if (Test-Port 3100) { break }; Start-Sleep -Milliseconds 800 }
  }
  Start-Sleep -Seconds 30
}
