@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Amedas Rainfall App.lnk"

echo Creating desktop shortcut for run.bat ...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%SCRIPT_DIR%run.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'shell32.dll,220'; $s.Description = 'Amedas Long-term Rainfall / Railway Disaster Prevention Analysis App'; $s.Save()"

if errorlevel 1 (
    echo [ERROR] Failed to create the desktop shortcut.
    pause
    exit /b 1
)

echo Desktop shortcut created:
echo   %SHORTCUT_PATH%
pause
