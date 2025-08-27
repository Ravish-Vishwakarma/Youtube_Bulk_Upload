@echo off
call .venv\Scripts\activate

REM Run backend in background
start /b uvicorn app:app --host 127.0.0.1 --port 8000

REM Run frontend in background
start /b python -m http.server 3000 -d dist

REM Wait a bit to let servers start
timeout /t 3 >nul

REM Open browser
start http://127.0.0.1:3000

echo App is running! Press Ctrl+C to stop everything.
pause >nul
