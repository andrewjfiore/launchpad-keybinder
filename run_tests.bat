@echo off
REM Run pytest for Launchpad Mapper

setlocal EnableExtensions
cd /d "%~dp0"

set "PY=python"
if exist "venv\Scripts\python.exe" (
    call "venv\Scripts\activate.bat"
    set "PY=python"
) else (
    where py -3 >nul 2>&1 && set "PY=py -3"
    where python >nul 2>&1 || set "PY=python"
)

echo Installing test dependencies...
%PY% -m pip install -q -r requirements.txt -r requirements-test.txt 2>nul || (
    echo Could not install deps. Run: pip install -r requirements.txt -r requirements-test.txt
    pause
    exit /b 1
)

set "PYTHONPATH=%cd%;%PYTHONPATH%"
echo Running pytest...
%PY% -m pytest tests\ -v --tb=short
set "EXIT=%ERRORLEVEL%"
echo.
if %EXIT% neq 0 pause
exit /b %EXIT%
