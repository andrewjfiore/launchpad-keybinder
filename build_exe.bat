@echo off
REM Build a Windows EXE using PyInstaller.

cd /d "%~dp0"

REM Ensure PyInstaller is available.
python -m pip install --upgrade pyinstaller

REM Build the EXE using the provided spec.
pyinstaller pyinstaller.spec

echo.
echo Build complete. Find the EXE under dist\launchpad-mapper\launchpad-mapper.exe
pause
