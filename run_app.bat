@echo off
setlocal
title NetWatch
cd /d "%~dp0"
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
echo Starting NetWatch... open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C in this window to stop.
start "" /b cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
python app.py
pause
