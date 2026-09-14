@echo off
chcp 936 >nul
title 海龟汤 Demo 保活安装
cd /d "C:\Users\zhu\Desktop\海龟汤"
echo ============================================
echo   海龟汤 Demo 保活安装（后端 + Funnel 守护）
echo ============================================
echo.
echo [1/3] 创建开机启动快捷方式...
wscript "make_shortcut.vbs"
echo.
echo [2/3] 注册计划任务（登录时自动启动）...
schtasks /create /tn "TurtleSoupBackend" /tr "\"D:\develop\anaconda\pythonw.exe\" \"C:\Users\zhu\Desktop\海龟汤\tsu_watchdog.py\"" /sc onlogon /f
echo.
echo [3/3] 立即启动后端与守护进程...
start "" "D:\develop\anaconda\pythonw.exe" "C:\Users\zhu\Desktop\海龟汤\tsu_watchdog.py"
echo.
echo 完成。稍等 10 秒后浏览器打开验证：
echo   https://laptop-a763c6tn.taild83cf2.ts.net:8443/
echo.
echo 守护进程每 2 分钟自检，后端掉线会自动拉起；开机自动运行，无需再手动操作。
pause
exit /b 0
