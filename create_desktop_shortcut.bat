@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

echo Creating desktop shortcut for run.bat ...

for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "([Environment]::GetFolderPath('Desktop'))"`) do set "DESKTOP_DIR=%%D"

if not defined DESKTOP_DIR (
    echo [ERROR] Could not determine Desktop folder location.
    pause
    exit /b 1
)

set "SHORTCUT_PATH=%DESKTOP_DIR%\Amedas Rainfall App.lnk"
set "ICON_PATH=%SCRIPT_DIR%assets\app_icon.ico"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%SCRIPT_DIR%run.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = '%ICON_PATH%'; $s.Description = 'Amedas Long-term Rainfall / Railway Disaster Prevention Analysis App'; $s.Save()"

if errorlevel 1 (
    echo [ERROR] Failed to create the desktop shortcut.
    pause
    exit /b 1
)

echo Desktop shortcut created:
echo   %SHORTCUT_PATH%
pause
