@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check
python -m venv .venv
if errorlevel 1 goto error
:check
".venv\Scripts\python.exe" -c "import pygame" >nul 2>&1
if not errorlevel 1 goto play
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
:play
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Could not start PAC-MAN. Please install Python 3.11 or newer,
echo then run: python -m pip install -r requirements.txt
pause
exit /b 1
