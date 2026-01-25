@echo off
REM Launchpad Mapper - start the app and initialize MIDI ports
REM Double-click this file to run.

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not defined OPEN_BROWSER set "OPEN_BROWSER=1"

echo [1/5] Python...
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo ERROR: Python 3 not found. Install from https://python.org
    pause
    exit /b 1
)

if exist "venv\Scripts\python.exe" (
    call "venv\Scripts\activate.bat"
    set "PY=python"
)

set "PYTHONUTF8=1"
set "PYTHONPATH=%cd%;%PYTHONPATH%"

echo [2/5] Dependencies...
python -m pip install -q -r "requirements.txt" 2>nul
if errorlevel 1 (
    echo ERROR: pip install failed. Run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [3/5] Check modules...
python -c "import launchpad_mapper, server" 2>nul
if errorlevel 1 (
    echo ERROR: Could not import app. Run from the folder that contains server.py.
    pause
    exit /b 1
)

echo [4/5] AutoHotkey (optional)...
set "AHK_EXE="
for /f "delims=" %%i in ('where AutoHotkey.exe 2^>nul') do (set "AHK_EXE=%%i" & goto :ahk_done)
if exist "%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\v2\AutoHotkey.exe"
if not defined AHK_EXE if exist "%ProgramFiles%\AutoHotkey\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\AutoHotkey.exe"
:ahk_done
if defined AHK_EXE if exist "Modules\lightroom-slider-control.ahk" (
    start "" /min "%AHK_EXE%" "%~dp0Modules\lightroom-slider-control.ahk"
)

echo [5/5] Starting server...
echo.
echo   LAUNCHPAD MAPPER
echo   Open http://localhost:5000
echo   MIDI + smiley auto-initialized on startup.
echo.
if /I "%OPEN_BROWSER%"=="1" start "" "http://localhost:5000"
python "server.py"
echo.
pause
