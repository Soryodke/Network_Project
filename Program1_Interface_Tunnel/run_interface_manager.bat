@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "APP_PY=.venv\Scripts\python.exe"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python not found. Ask IT to install an approved Python 3.12 runtime.
    pause
    exit /b 1
  )
  set "APP_PY=python"
)
"%APP_PY%" -c "import nicegui, paramiko, serial, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo Dependencies missing. Follow the IT-approved installation in docs.
  pause
  exit /b 1
)
"%APP_PY%" app.py
if errorlevel 1 pause
