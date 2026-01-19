@echo off
REM Launchpad Mapper - Start Script for Windows (one-click)

setlocal enabledelayedexpansion
cd /d "%~dp0"

if "%~1" neq "run" (
    REM Restart minimized for a cleaner one-click experience
    start "" /min "%~f0" run
    exit /b 0
)

REM Check for Python (prefer python, fall back to py -3)
set "PYTHON_EXE="
python --version >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    py -3 --version >nul 2>&1 && set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
    echo Python is required but not installed.
    echo Please install Python from https://python.org
    timeout /t 5 >nul
    exit /b 1
)

REM Check for virtual environment, create if missing
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Checking dependencies...
pip install -q -r requirements.txt

REM Launch AutoHotkey script if available
set "AHK_EXE="
for /f "delims=" %%i in ('where AutoHotkey.exe 2^>nul') do set "AHK_EXE=%%i"
if not defined AHK_EXE for /f "delims=" %%i in ('where AutoHotkey64.exe 2^>nul') do set "AHK_EXE=%%i"
if not defined AHK_EXE for /f "delims=" %%i in ('where AutoHotkeyU64.exe 2^>nul') do set "AHK_EXE=%%i"
if not defined AHK_EXE if exist "%ProgramFiles%\\AutoHotkey\\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\\AutoHotkey\\AutoHotkey.exe"
if not defined AHK_EXE if exist "%ProgramFiles%\\AutoHotkey\\AutoHotkey64.exe" set "AHK_EXE=%ProgramFiles%\\AutoHotkey\\AutoHotkey64.exe"
if not defined AHK_EXE if exist "%ProgramFiles(x86)%\\AutoHotkey\\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles(x86)%\\AutoHotkey\\AutoHotkey.exe"
if defined AHK_EXE (
    echo Starting AutoHotkey...
    start "" /min "%AHK_EXE%" "%~dp0Modules\lightroom-slider-control.ahk"
) else (
    echo AutoHotkey not found on PATH. Skipping AHK launch.
)

REM Run the server
echo.
echo Starting Launchpad Mapper...
echo Opening http://localhost:5000 in your browser
echo.
start "" "http://localhost:5000"
python server.py
