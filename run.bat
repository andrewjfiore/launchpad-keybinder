@echo off
REM Launchpad Mapper - Start Script for Windows

cd /d "%~dp0"

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is required but not installed.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check for virtual environment, create if missing
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Checking dependencies...
pip install -q -r requirements.txt

REM Run the server
echo.
echo Starting Launchpad Mapper...
echo Open http://localhost:5000 in your browser
echo.
python server.py

pause
