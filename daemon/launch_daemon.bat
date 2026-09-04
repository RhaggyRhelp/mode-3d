@echo off
setlocal
REM MoGe Splat Daemon launcher (Windows)

set DAEMON_DIR=%~dp0
set REPO_ROOT=%DAEMON_DIR%..

REM 1. Check custom MOGE_PY
if defined MOGE_PY (
    if exist "%MOGE_PY%" (
        set PYTHON_BIN=%MOGE_PY%
        goto :RUN
    )
)

REM 2. Check local repo .venv
if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    set PYTHON_BIN=%REPO_ROOT%\.venv\Scripts\python.exe
    goto :RUN
)

REM 3. Check sibling MoGe .venv
if exist "%REPO_ROOT%\..\MoGe\.venv\Scripts\python.exe" (
    set PYTHON_BIN=%REPO_ROOT%\..\MoGe\.venv\Scripts\python.exe
    goto :RUN
)

REM 4. Check userprofile MoGe .venv
if exist "%USERPROFILE%\MoGe\.venv\Scripts\python.exe" (
    set PYTHON_BIN=%USERPROFILE%\MoGe\.venv\Scripts\python.exe
    goto :RUN
)

REM 5. Fallback to system python
set PYTHON_BIN=python

:RUN
echo [MoGe Launcher] Using Python: %PYTHON_BIN%
"%PYTHON_BIN%" "%DAEMON_DIR%moge_daemon.py" --host 127.0.0.1 --port 8766 --preload v3 %*
if errorlevel 1 (
    echo [ERROR] Daemon exited with code %errorlevel%
    pause
)
endlocal
