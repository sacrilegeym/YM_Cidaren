@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv
    pause
    exit /b 1
)
echo 正在安装依赖（阿里云镜像加速）...
".venv\Scripts\python.exe" -m pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)
echo.
echo 环境配置完成，现在可以双击 点我运行.bat 启动程序。
pause