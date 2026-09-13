@echo off
echo Installing dependencies...
cd /d %~dp0backend
pip install -r requirements.txt
echo.
echo Done! Press any key to exit...
pause >nul
