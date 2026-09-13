@echo off
echo ========================================
echo   Turtle Soup Game - Starting
echo ========================================
echo.

REM Check Python
echo [1/4] Checking Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)
echo.

REM Create .env if not exists
echo [2/4] Checking config...
if not exist "backend\.env" (
    echo [INFO] Creating .env file...
    copy backend\.env.example backend\.env >nul
    echo [OK] Created backend\.env
)
echo.

REM Install dependencies
echo [3/4] Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    cd backend
    pip install -r requirements.txt
    cd ..
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)
echo.

REM Start services
echo [4/4] Starting services...
echo.
echo Starting backend API...
start "Backend-API" cmd /k "cd /d %~dp0backend && python main.py"

echo Waiting for backend...
timeout /t 3 /nobreak >nul

echo Starting frontend...
start "Frontend-Web" cmd /k "cd /d %~dp0frontend && python -m http.server 8080"

echo.
echo ========================================
echo   Game Started!
echo ========================================
echo.
echo  Backend API:  http://localhost:8000
echo  Game URL:     http://localhost:8080
echo  API Docs:     http://localhost:8000/docs
echo.
echo ========================================
echo.
echo Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:8080

echo.
echo Press any key to exit...
pause >nul
