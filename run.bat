@echo off
REM Launchpad Mapper - Start Script for Windows

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo [1/4] Checking Python environment...
REM Check for Python
set "PYTHON_EXE="
python --version >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    py -3 --version >nul 2>&1 && set "PYTHON_EXE=py -3"
)

if not defined PYTHON_EXE (
    echo ERROR: Python is required but not installed.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check for virtual environment
if not exist "venv" (
    echo [2/4] Creating virtual environment...
    %PYTHON_EXE% -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies
echo [3/4] Checking dependencies...
pip install -q -r requirements.txt

REM Launch AutoHotkey script
echo [4/4] Launching Modules...
set "AHK_EXE="
for /f "delims=" %%i in ('where AutoHotkey.exe 2^>nul') do set "AHK_EXE=%%i"
if not defined AHK_EXE if exist "%ProgramFiles%\AutoHotkey\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\AutoHotkey.exe"
if not defined AHK_EXE if exist "%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe"

if defined AHK_EXE (
    echo    - Starting AutoHotkey Helper...
    start "" /min "%AHK_EXE%" "%~dp0Modules\lightroom-slider-control.ahk"
) else (
    echo    - WARNING: AutoHotkey not found. Lightroom commands will NOT work.
    echo      Please install AutoHotkey v2.
)

REM Run the server
echo.
echo ===================================================
echo   LAUNCHPAD MAPPER STARTED
echo   1. Open http://localhost:5000
echo   2. Select MIDI Ports:
echo      - Input: "Launchpad Mini MK3 MIDI" (NOT DAW)
echo      - Output: "Launchpad Mini MK3 MIDI"
echo ===================================================
echo.

REM Open Browser
start "" "http://localhost:5000"

REM Run server (kept in this window to see errors)
python server.py
pause
