@echo off
echo Starting backend API server...
cd /d %~dp0backend
"D:\develop\anaconda\python.exe" main.py
pause
