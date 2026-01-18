@echo off
REM Build a Windows EXE using PyInstaller.

cd /d "%~dp0"

REM Ensure PyInstaller is available.
python -m pip install --upgrade pip pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
)

REM Build the EXE using the provided spec.
python -m PyInstaller pyinstaller.spec
if errorlevel 1 (
    echo PyInstaller build failed. Check the output above for errors.
    exit /b 1
)

echo.
echo Build complete. Find the EXE under dist\launchpad-mapper\launchpad-mapper.exe
pause
