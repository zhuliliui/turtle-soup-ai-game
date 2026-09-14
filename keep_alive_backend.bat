@echo off
chcp 936 >nul
cd /d "C:\Users\zhu\Desktop\海龟汤\backend"
netstat -ano | findstr ":8000" | findstr LISTENING >nul
if not errorlevel 1 goto funnel
start "" "D:\develop\anaconda\python.exe" main.py
:funnel
"C:\Program Files\Tailscale\tailscale.exe" funnel --bg --https=8443 http://127.0.0.1:8000 >nul 2>&1
echo 后端已启动，Demo: https://laptop-a763c6tn.taild83cf2.ts.net:8443/
exit /b 0
