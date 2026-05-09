@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Build Standalone EXE
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    echo Using venv Python
) else (
    set "PY=python"
    echo Using system Python
)

!PY! --version
if errorlevel 1 (
    echo [Error] Python not found
    echo Install: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [1/3] Installing streamlink + PyInstaller...
!PY! -m pip install streamlink pyinstaller -q
echo.

echo [2/3] Building EXE (1-3 minutes)...
!PY! -m PyInstaller --onefile --windowed --name DouyinRecorder --hidden-import streamlink --collect-all streamlink --add-data "ffmpeg\bin\ffmpeg.exe;ffmpeg\bin" --clean douyin_recorder_gui.py

echo.
if exist "dist\DouyinRecorder.exe" (
    echo [3/3] Build success!
    echo   EXE: dist\DouyinRecorder.exe
) else (
    echo [Failed] Check errors above
)
pause
