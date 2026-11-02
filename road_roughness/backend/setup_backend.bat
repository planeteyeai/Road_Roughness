@echo off
REM Creates the Python virtual environment (.venv) and installs the backend packages.
cd /d "%~dp0"

where python >nul 2>nul || (echo Python was not found. Install Python 3.10+ and tick "Add python.exe to PATH". & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  python -m venv .venv || (echo Could not create .venv & pause & exit /b 1)
)

echo Installing packages from requirements.txt ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Package install failed & pause & exit /b 1)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Setup finished.
echo  - Settings: backend\.env
echo  - First time on this PC only: .venv\Scripts\earthengine authenticate
echo  - Start the backend: run_backend.bat
pause
