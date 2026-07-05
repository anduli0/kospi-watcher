@echo off
title KOSPI-WATCHER worker (08:00 briefing + catch-up) - keep open
cd /d "%~dp0"
REM Self-healing worker loop: reclaims the single-instance lock port (18079) from
REM any stale holder, then (re)starts the APScheduler worker. If it dies for any
REM reason it restarts in 5s, so a crash no longer silently kills the daily brief.
REM Mirrors _kw-api.bat. The 18079 lock is KOSPI-ONLY, so reclaiming it never
REM touches the us-watcher worker (same apps\worker\main.py command line, but it
REM holds NO lock). Launched at logon by the autostart launcher; can also be
REM double-clicked. Close this window to stop the worker.
:loop
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18079 " ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
".venv\Scripts\python.exe" apps\worker\main.py
echo.
echo   [worker stopped] restarting in 5s...  (close this window to stop the worker)
timeout /t 5 /nobreak >nul
goto loop
