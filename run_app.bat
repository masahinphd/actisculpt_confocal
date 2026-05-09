@echo off
REM Cross-platform launcher for ActiSculpt Confocal Viewer
REM Creates/uses a local virtual environment and installs requirements automatically.

setlocal enabledelayedexpansion
cd /d "%~dp0"

where py >nul 2>nul
if !errorlevel! equ 0 (
    py -3 run_app.py
    if !errorlevel! neq 0 (
        echo.
        echo Error running the app.
        pause
        exit /b !errorlevel!
    )
    pause
    exit /b 0
)

where python >nul 2>nul
if !errorlevel! equ 0 (
    python run_app.py
    if !errorlevel! neq 0 (
        echo.
        echo Error running the app.
        pause
        exit /b !errorlevel!
    )
    pause
    exit /b 0
)

echo Python is not installed or not available on PATH.
pause
exit /b 1