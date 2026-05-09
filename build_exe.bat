@echo off
cd /d "%~dp0"

echo ============================================
echo   Build Standalone EXE
echo ============================================
echo.

python --version
if errorlevel 1 (
    echo [Error] Python not found
    echo Install: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [1/3] Installing PyInstaller...
pip install pyinstaller -q
echo.

echo [2/3] Building EXE...
pyinstaller --onefile --windowed --name DouyinRecorder --add-data ffmpeg\bin\ffmpeg.exe;ffmpeg\bin --clean douyin_recorder_gui.py

echo.
if exist dist\DouyinRecorder.exe (
    echo [3/3] Build success!
    echo   EXE: dist\DouyinRecorder.exe
) else (
    echo [Failed]
)
pause
