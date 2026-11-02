@echo off
REM Starts the backend API (settings in .env).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The virtual environment is missing. Run setup_backend.bat first.
  pause & exit /b 1
)

".venv\Scripts\python.exe" main.py
pause
