@echo off
setlocal
title NetWatch Installer
echo ==============================================
echo   NetWatch - Installer
echo ==============================================
set PYCMD=
py -3 --version >nul 2>&1
if not errorlevel 1 set PYCMD=py -3
if not defined PYCMD (
    python --version >nul 2>&1
    if not errorlevel 1 set PYCMD=python
)
if not defined PYCMD (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3 from https://www.python.org/downloads/ and tick "Add Python to PATH".
    pause
    exit /b 1
)
echo [1/3] Python found:
%PYCMD% --version
echo [2/3] Creating virtual environment in the "venv" folder...
%PYCMD% -m venv venv
if errorlevel 1 (
    echo [ERROR] Could not create the virtual environment.
    pause
    exit /b 1
)
echo [3/3] Installing requirements (Flask, psutil)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)
echo.
echo ==============================================
echo   Installation finished.
echo   Next step: run  run_app.bat
echo   Then open  http://127.0.0.1:5000  in your browser.
echo ==============================================
pause
