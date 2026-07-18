@echo off
setlocal

if not exist ".venv\Scripts\streamlit.exe" (
    echo [ERROR] Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

set PYTHONPATH=%~dp0src
call ".venv\Scripts\streamlit.exe" run app.py
pause
