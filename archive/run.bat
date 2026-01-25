@echo off
REM Launchpad Mapper - Start Script for Windows

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo [1/6] Checking Python environment...
set "PYTHON_CMD="

REM Prefer launcher if available (best on Windows), fall back to python in PATH
py -3 --version >nul 2>&1 && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python --version >nul 2>&1 && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERROR: Python 3 is required but not found.
    echo Install Python from https://python.org and ensure it is on PATH.
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%

REM Ensure venv exists
if not exist "venv\Scripts\python.exe" (
    echo [2/6] Creating virtual environment...
    %PYTHON_CMD% -m venv "venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate venv
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Force UTF-8 and ensure this folder is on PYTHONPATH (important when launched by double-click)
set "PYTHONUTF8=1"
set "PYTHONPATH=%cd%;%PYTHONPATH%"

REM Upgrade pip tooling to reduce install issues
echo [3/6] Checking dependencies...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found in %cd%
    pause
    exit /b 1
)

python -m pip install -r "requirements.txt"
if errorlevel 1 (
    echo ERROR: Dependency install failed.
    echo Try running: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM Sanity check: ensure we are importing the local module and no syntax errors exist
echo [4/6] Sanity check (module resolution + syntax)...
python -c "import sys, os; print('Python:', sys.executable); print('CWD:', os.getcwd()); import launchpad_mapper as lm; print('launchpad_mapper:', lm.__file__)"
if errorlevel 1 (
    echo ERROR: Failed to import launchpad_mapper from this folder.
    echo If you unzipped a folder-inside-a-folder, run this BAT from the inner folder that contains server.py.
    pause
    exit /b 1
)

python -m py_compile "server.py" "launchpad_mapper.py"
if errorlevel 1 (
    echo ERROR: Syntax check failed.
    pause
    exit /b 1
)

REM Launch AutoHotkey script (optional)
echo [5/6] Launching modules...
set "AHK_EXE="

for /f "delims=" %%i in ('where AutoHotkey.exe 2^>nul') do (
    set "AHK_EXE=%%i"
    goto :ahk_found
)

if exist "%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe"
if not defined AHK_EXE if exist "%ProgramFiles%\AutoHotkey\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\AutoHotkey.exe"

:ahk_found
if defined AHK_EXE (
    if exist "%~dp0Modules\lightroom-slider-control.ahk" (
        echo    - Starting AutoHotkey Helper...
        start "" /min "%AHK_EXE%" "%~dp0Modules\lightroom-slider-control.ahk"
    ) else (
        echo    - WARNING: AHK script not found: %~dp0Modules\lightroom-slider-control.ahk
    )
) else (
    echo    - WARNING: AutoHotkey not found. Lightroom commands will NOT work.
    echo      Install AutoHotkey v2.
)

REM Run the server
REM If the config page is focused, shortcuts will go to the browser.
REM Set OPEN_BROWSER=1 if you want this script to open the UI automatically.
set "OPEN_BROWSER=0"

echo.
echo ===================================================
echo   LAUNCHPAD MAPPER STARTED
echo   1. Open http://localhost:5000
echo   2. Select MIDI Ports:
echo      - Input: "Launchpad Mini MK3 MIDI" (NOT DAW)
echo      - Output: "Launchpad Mini MK3 MIDI"
echo ===================================================
echo.

echo [6/6] Starting server...
if exist "server.py" (
    if "%OPEN_BROWSER%"=="1" (
        start "" /min "http://localhost:5000"
    )
    python "server.py"
) else (
    echo ERROR: server.py not found in %cd%
)

echo.
pause
