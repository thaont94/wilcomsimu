@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.12 64-bit with Python Launcher, then run this file again.
  pause
  exit /b 1
)
py -3.12 -m venv .build-venv
if errorlevel 1 goto :failed
".build-venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller==6.16.0"
if errorlevel 1 goto :failed
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name ThreadStudio --add-data "index.html;." --collect-submodules uvicorn desktop.py
if errorlevel 1 goto :failed
echo.
echo Created: %CD%\dist\ThreadStudio.exe
echo Double-click ThreadStudio.exe to start. Keep its console window open.
pause
exit /b 0
:failed
echo.
echo Build failed. Review the error above; no successful build is confirmed.
pause
exit /b 1
