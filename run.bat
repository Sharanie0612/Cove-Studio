@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow README.md to install the Python environment first.
  pause
  exit /b 1
)
if not exist "dist\index.html" (
  echo Please run npm install and npm run build first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m toolbench
