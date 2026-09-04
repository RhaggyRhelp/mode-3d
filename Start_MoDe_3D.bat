@echo off
title MoDe 3D Studio - Setup & Launch
cd /d "%~dp0"

echo ======================================================================
echo   MoDe 3D Studio - Starting One-Click Launcher...
echo ======================================================================

REM 1. Find Python executable
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Python was not detected on your system.
        echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/downloads/
        echo (IMPORTANT: Check the box "Add Python to PATH" during installation)
        echo.
        pause
        exit /b 1
    )
    set "PY_BOOTSTRAP=py"
) else (
    set "PY_BOOTSTRAP=python"
)

REM 2. Run automated setup and launch
"%PY_BOOTSTRAP%" tools\one_click_setup.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] MoDe 3D Studio exited with code %errorlevel%
    pause
)
