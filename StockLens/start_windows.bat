@echo off
setlocal
cd /d "%~dp0"
echo StockLens - creating Python environment and installing requirements...
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv 2>nul
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 (echo Python 3.10+ is required & pause & exit /b 1)
)
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed. Check internet connectivity. & pause & exit /b 1)
echo.
echo Open http://127.0.0.1:8000 in your browser.
echo Ctrl+C will stop the server.
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
