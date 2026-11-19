@echo off
chcp 936 >nul
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PG_SERVICE=postgresql-x64-16"

title 毕设论文审核系统 - 启动

echo ============================================
echo   毕设论文审核系统  一键启动
echo ============================================
echo.

echo [1/4] 检查数据库服务 %PG_SERVICE% ...
sc query "%PG_SERVICE%" 2>nul | findstr /C:"RUNNING" >nul
if not errorlevel 1 goto DB_READY

echo       服务未运行，正在启动（会弹出管理员授权，请点“是”）...
net start "%PG_SERVICE%" >nul 2>&1
if not errorlevel 1 goto DB_READY

powershell -NoProfile -Command "Start-Process -FilePath 'net' -ArgumentList 'start','%PG_SERVICE%' -Verb RunAs -Wait" >nul 2>&1
sc query "%PG_SERVICE%" 2>nul | findstr /C:"RUNNING" >nul
if errorlevel 1 (
    echo.
    echo [错误] 数据库启动失败，请右键本文件，选择“以管理员身份运行”后重试。
    pause
    exit /b 1
)

:DB_READY
echo       数据库已就绪。
echo.

echo [2/4] 检查后端 8000 端口 ...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo       后端已在运行，跳过启动。
) else (
    if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
        echo [错误] 找不到后端虚拟环境 %ROOT%backend\.venv
        echo        请先按说明安装依赖后再运行。
        pause
        exit /b 1
    )
    start "毕设系统-后端" /D "%ROOT%backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
    echo       后端窗口已打开。
)
echo.

echo [3/4] 检查前端 5173 端口 ...
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo       前端已在运行，跳过启动。
) else (
    if exist "%ROOT%frontend\node_modules" (
        start "毕设系统-前端" /D "%ROOT%frontend" cmd /k "npm run dev"
    ) else (
        start "毕设系统-前端" /D "%ROOT%frontend" cmd /k "npm install && npm run dev"
    )
    echo       前端窗口已打开。
)
echo.

echo [4/4] 等待服务启动，然后打开浏览器 ...
timeout /t 8 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo 完成。演示账号：admin / teacher / student，密码均为 123456
echo 关闭本窗口不会影响已启动的前后端窗口。
timeout /t 8 /nobreak >nul
endlocal
