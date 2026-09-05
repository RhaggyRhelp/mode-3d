@echo off
setlocal
title MoDe 3D Studio - Setup and Launch
cd /d "%~dp0"

echo ======================================================================
echo   MoDe 3D Studio - Starting One-Click Launcher...
echo ======================================================================

REM 1. Find Python executable. NOTE: no parentheses in any echo below:
REM a stray ")" inside a block ends the block early and garbles the script.
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_BOOTSTRAP=python"
    goto :run
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_BOOTSTRAP=py"
    goto :run
)

echo.
echo [ERROR] Python was not detected on your system.
echo Please install Python 3.10 or newer from https://www.python.org/downloads/
echo IMPORTANT: tick the box Add Python to PATH during installation.
echo Then double-click this file again.
echo.
pause
exit /b 1

:run
REM 2. Run automated setup and launch. Extra args are forwarded, e.g. --check --no-launch
"%PY_BOOTSTRAP%" tools\one_click_setup.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] MoDe 3D Studio exited with a problem. See messages above.
    pause
)
