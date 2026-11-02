@echo off
REM Serves the frontend on http://127.0.0.1:5500 (needs only Python, no packages).
REM The backend address is set in js\config.js.
cd /d "%~dp0"

where python >nul 2>nul || (echo Python was not found. & pause & exit /b 1)
echo Frontend: http://127.0.0.1:5500/
start "" "http://127.0.0.1:5500/"
python -m http.server 5500 --bind 127.0.0.1
pause
