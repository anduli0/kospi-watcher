# KOSPI-WATCHER — auto-start & operations (Windows)

These scripts run the whole stack locally and start it **automatically every time
you turn the PC on and sign in** — no manual command needed.

## What runs

| Service | Port | What it does |
|---|---|---|
| API | `:18080` | FastAPI (PAPER mode, live Yahoo quotes, Google News) |
| Web | `:3000` | Next.js dashboard → **http://localhost:3000** |
| Worker | (lock `:18079`) | APScheduler: **08:00 KST daily morning briefing** + hourly news scrape |

The worker holds a single-instance lock on `:18079`, so it can never run twice
(exactly one 08:00 briefing).

## One-time setup (already done)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
```

This drops a hidden launcher into your **Startup folder**
(`shell:startup` → `kospi-watcher.vbs`). On every logon Windows runs it, which
starts the API, worker, and web in the background (no windows pop up). No admin
rights required. To remove auto-start, delete that `kospi-watcher.vbs`.

## Telegram (daily 08:00 push)

The morning briefing always refreshes the data; to also receive it on Telegram,
put your credentials in `kospi-watcher\.env` (git-ignored), then the next worker
start (or reboot) picks them up:

```
TELEGRAM_BOT_TOKEN=123456:ABC...      # from @BotFather
TELEGRAM_CHAT_ID=12345678             # your chat id (see below)
```

Get the chat id: message your new bot once, then open
`https://api.telegram.org/bot<token>/getUpdates` and read `chat.id`.

Test it immediately (no need to wait for 08:00):
`curl -X POST http://localhost:18080/api/v1/notify/morning`

## Manual control

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_kospi_watcher.ps1   # start (idempotent)
powershell -ExecutionPolicy Bypass -File scripts\stop_kospi_watcher.ps1    # stop all
```

Logs are written to `kospi-watcher\logs\`.
