@echo off
title KOSPI-WATCHER API (127.0.0.1:18080) - keep open
cd /d "%~dp0"
REM Self-healing API loop: reclaims port 18080 from any stale/orphan listener,
REM then (re)starts uvicorn. If uvicorn dies for any reason it restarts in 3s.
REM Mirrors us-watcher\_usw-api.bat (proven durable). Launched at logon by the
REM autostart launcher; can also be double-clicked. Close this window to stop.
:loop
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080 " ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
".venv\Scripts\python.exe" -m uvicorn main:app --app-dir apps/api --host 127.0.0.1 --port 18080 --log-level warning
echo.
echo   [API stopped] restarting in 3s...  (close this window to take the API offline)
timeout /t 3 /nobreak >nul
goto loop
