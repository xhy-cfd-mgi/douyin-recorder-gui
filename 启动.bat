@echo off
cd /d "%~dp0"

echo =======================================
echo   抖音直播录屏
echo =======================================
echo.

python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo 请安装: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [首次运行] 正在配置环境...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install streamlink -q
    echo [完成] 环境配置完毕
    echo.
)

echo 正在启动...
echo.
.venv\Scripts\python.exe douyin_recorder_gui.py
pause
