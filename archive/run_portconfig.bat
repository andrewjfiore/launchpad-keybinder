@echo off
REM Simple launcher for Launchpad Mapper
REM Put this file next to launchpad_mapper.py, then double-click it.
REM Optional: pass port and host as args:
REM   launchpad_diag.bat 55555 127.0.0.1

setlocal EnableExtensions
cd /d "%~dp0"

REM ----------------------------
REM Lightroom socket settings
REM ----------------------------
REM Single target (used as defaults)
set "LR_SOCKET_HOST=127.0.0.1"
set "LR_SOCKET_PORT=55555"

REM Allow overrides from command-line args
if not "%~1"=="" set "LR_SOCKET_PORT=%~1"
if not "%~2"=="" set "LR_SOCKET_HOST=%~2"

REM Optional multi-target probing (comma-separated, no spaces)
REM If you know your plugin port, set it here or pass as %1 above.
if not defined LR_SOCKET_HOSTS set "LR_SOCKET_HOSTS=%LR_SOCKET_HOST%,localhost,127.0.0.1"
if not defined LR_SOCKET_PORTS set "LR_SOCKET_PORTS=%LR_SOCKET_PORT%,55555,5555"

echo Running from: %CD%
echo.
echo Lightroom socket candidates:
echo   Hosts: %LR_SOCKET_HOSTS%
echo   Ports: %LR_SOCKET_PORTS%
echo.

REM Quick preflight check: find the first listening host:port
set "LR_FOUND="
for %%H in (%LR_SOCKET_HOSTS%) do (
  for %%P in (%LR_SOCKET_PORTS%) do (
    powershell -NoProfile -Command ^
      "try { $r=Test-NetConnection -ComputerName '%%H' -Port %%P -WarningAction SilentlyContinue; if($r.TcpTestSucceeded){ exit 0 } else { exit 1 } } catch { exit 1 }"
    if not errorlevel 1 (
      set "LR_SOCKET_HOST=%%H"
      set "LR_SOCKET_PORT=%%P"
      set "LR_FOUND=1"
      goto :lr_done
    )
  )
)
:lr_done

echo Lightroom socket target: %LR_SOCKET_HOST%:%LR_SOCKET_PORT%
if not defined LR_FOUND (
  echo WARNING: Nothing is listening on %LR_SOCKET_HOST%:%LR_SOCKET_PORT%.
  echo Lightroom integration will not work until the Lightroom companion/plugin is running on that port.
  echo This does NOT affect the Launchpad Mapper web UI at http://localhost:5000
)
echo.

REM Export multi-target lists too (Python can try them)
set "LR_SOCKET_HOSTS=%LR_SOCKET_HOSTS%"
set "LR_SOCKET_PORTS=%LR_SOCKET_PORTS%"

REM ----------------------------
REM Python selection
REM ----------------------------
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
echo Web UI: http://localhost:5000
echo (Tip: click your target app after the server starts so it receives the shortcuts)
echo.

%PY% "launchpad_mapper.py"

echo.
echo Process exited with code %ERRORLEVEL%
pause
