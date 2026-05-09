@echo off
cd /d "%~dp0"

echo ============================================
echo   抖音直播录屏 - 环境安装
echo ============================================
echo.

python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo 请安装: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

echo [1/3] 创建虚拟环境...
python -m venv .venv
echo 完成
echo.

echo [2/3] 安装 streamlink...
.venv\Scripts\python.exe -m pip install streamlink --upgrade
echo.

echo [3/3] 检查 ffmpeg...
ffmpeg -version >/dev/null 2>&1
if errorlevel 1 (
    echo [警告] 未找到 ffmpeg
    echo 下载: https://ffmpeg.org/download.html
    echo 或命令: winget install ffmpeg
) else (
    ffmpeg -version 2>&1 | find "version"
)

echo.
echo ============================================
echo   安装完成! 双击 "启动.bat" 开始使用
echo ============================================
pause
