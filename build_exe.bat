@echo off
cd /d "%~dp0"

echo ============================================
echo   打包为独立 EXE (无需 Python 即可运行)
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 打包需要 Python，请先安装:
    echo   https://www.python.org/downloads/
    echo   安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/3] 安装 PyInstaller...
pip install pyinstaller -q
echo.

echo [2/3] 构建 EXE (约需 1-3 分钟)...
pyinstaller --onefile --windowed ^
    --name "抖音直播录屏" ^
    --add-data "ffmpeg\bin\ffmpeg.exe;ffmpeg\bin" ^
    --hidden-import tkinter ^
    --hidden-import threading ^
    --clean ^
    douyin_recorder_gui.py

echo.
if exist "dist\抖音直播录屏.exe" (
    echo [3/3] 打包成功!
    echo.
    echo   EXE 位置: dist\抖音直播录屏.exe
    echo   将该文件复制到任意目录，双击运行即可。
    echo   无需安装 Python!
) else (
    echo [失败] 打包出错，请查看上方输出
)
pause
