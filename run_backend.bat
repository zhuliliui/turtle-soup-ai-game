@echo off
echo Starting Backend API Server...
cd /d %~dp0backend
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo [提示] 后端已经在运行中，无需重复启动。
    echo 直接在浏览器打开 http://localhost:8000 即可游玩。
    echo.
    pause
    exit /b 0
)
"D:\develop\anaconda\python.exe" main.py
pause
