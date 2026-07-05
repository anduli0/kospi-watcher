# Start (or attach to) the KOSPI-WATCHER public tunnel and print the current URL.
#
# The actual work is done by the self-healing daemon (public-tunnel-daemon.ps1),
# which keeps cloudflared alive, and on every (re)start writes the new
# https://*.trycloudflare.com URL to current-url.txt AND pushes it to Telegram.
# This wrapper just makes sure the daemon is running, then shows you the URL.
#
# A permanent (never-changing) URL still requires freeing one of the 3 Tailscale
# Funnel ports (443/8443/10000, currently fed/us/krw) and pointing it at :3100.

$ErrorActionPreference = "Stop"
$daemon  = Join-Path $PSScriptRoot "public-tunnel-daemon.ps1"
$urlFile = Join-Path $PSScriptRoot "current-url.txt"

# Launch the daemon hidden; its single-instance lock (18078) makes this a no-op
# if one is already running.
Start-Process -FilePath "powershell" -WindowStyle Hidden `
  -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $daemon

# Wait for the daemon to publish a URL.
$url = $null
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 800
  if (Test-Path $urlFile) {
    $u = (Get-Content $urlFile -Raw).Trim()
    if ($u -match 'https://[a-z0-9-]+\.trycloudflare\.com') { $url = $u; break }
  }
}

if ($url) {
  Write-Host "`n=============================================================="
  Write-Host "  PUBLIC URL:  $url"
  Write-Host "  (Cloudflare Quick Tunnel -> 127.0.0.1:3100 -> /api -> :18080)"
  Write-Host "  The daemon auto-restarts the tunnel and Telegrams a new URL if"
  Write-Host "  this one ever changes. Permanent URL = free a Tailscale port."
  Write-Host "==============================================================`n"
} else {
  Write-Warning "Daemon started but no URL yet. Check scripts\tunnel.log / current-url.txt"
}
