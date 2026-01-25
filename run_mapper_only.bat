@echo off
REM Simple launcher for Launchpad Mapper
REM Put this file next to launchpad_mapper.py, then double-click it.

setlocal EnableExtensions
cd /d "%~dp0"

echo Running from: %CD%
echo.

REM Prefer the same Python you use in terminal.
REM If you want to force a venv, set USE_VENV=1 before running this script.
if /I "%USE_VENV%"=="1" (
  if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
  ) else if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
  ) else (
    echo USE_VENV=1 but no venv found at .venv\Scripts\python.exe or venv\Scripts\python.exe
    echo Falling back to system Python.
    set "PY=python"
  )
) else (
  set "PY=python"
)

%PY% --version
if errorlevel 1 (
  echo.
  echo ERROR: Could not run "%PY%".
  echo If double-clicking opens the Microsoft Store, install Python from python.org and re-run.
  pause
  exit /b 1
)

echo.
echo Using launchpad_mapper at:
%PY% -c "import launchpad_mapper; print(launchpad_mapper.__file__)"
echo.

echo Checking syntax...
%PY% -m py_compile "launchpad_mapper.py"
if errorlevel 1 (
  echo.
  echo ERROR: launchpad_mapper.py has a syntax error.
  pause
  exit /b 1
)

echo Starting Launchpad Mapper...
echo (Tip: click your target app after the server starts so it receives the shortcuts)
echo.

%PY% "launchpad_mapper.py"

echo.
echo Process exited with code %ERRORLEVEL%
pause
