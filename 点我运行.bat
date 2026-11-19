@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv，请先双击运行 点我配置环境.bat
    pause
    exit /b 1
)
rem 让内置 token 抓取能找到 mitmdump.exe
set "PATH=%~dp0.venv\Scripts;%PATH%"
echo 正在启动 Easy_Cidaren，运行期间请勿关闭本窗口...
".venv\Scripts\python.exe" "main.py"
echo.
echo 程序已退出。
pause