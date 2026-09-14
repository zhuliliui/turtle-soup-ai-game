# -*- coding: utf-8 -*-
"""生成海龟汤保活脚本（统一走 Python 守护 tsu_watchdog.py，GBK 编码防中文路径乱码）"""
import io
import os

ROOT = r"C:\Users\zhu\Desktop\海龟汤"
PY = r"D:\develop\anaconda\python.exe"
PYW = r"D:\develop\anaconda\pythonw.exe"
TS = r"C:\Program Files\Tailscale\tailscale.exe"

# 手动一键启动后端（备用，双击即可）
KEEP_BAT = r"""@echo off
chcp 936 >nul
cd /d "{root}\backend"
netstat -ano | findstr ":8000" | findstr LISTENING >nul
if not errorlevel 1 goto funnel
start "" "{py}" main.py
:funnel
"{ts}" funnel --bg --https=8443 http://127.0.0.1:8000 >nul 2>&1
echo 后端已启动，Demo: https://laptop-a763c6tn.taild83cf2.ts.net:8443/
exit /b 0
""".format(root=ROOT, py=PY, ts=TS)

# 开机启动快捷方式 → 指向 Python 守护
MAKE_LNK = r"""' 在开机启动目录创建守护快捷方式（Python 守护，无窗口）
Option Explicit
Dim sh, lnk, q
Set sh = CreateObject("WScript.Shell")
q = Chr(34)
Set lnk = sh.CreateShortcut(sh.SpecialFolders("Startup") & "\TurtleSoupBackend.lnk")
lnk.TargetPath = "{pyw}"
lnk.Arguments = q & "{root}\tsu_watchdog.py" & q
lnk.WorkingDirectory = "{root}"
lnk.WindowStyle = 7
lnk.Description = "海龟汤 Demo 保活（后端 + Tailscale Funnel 守护）"
lnk.Save
WScript.Echo "SHORTCUT_OK " & sh.SpecialFolders("Startup")
""".format(root=ROOT, pyw=PYW)

# 一键注册：开机自启 + 计划任务 + 立即启动
REGISTER_BAT = r"""@echo off
chcp 936 >nul
title 海龟汤 Demo 保活安装
cd /d "{root}"
echo ============================================
echo   海龟汤 Demo 保活安装（后端 + Funnel 守护）
echo ============================================
echo.
echo [1/3] 创建开机启动快捷方式...
wscript "make_shortcut.vbs"
echo.
echo [2/3] 注册计划任务（登录时自动启动）...
schtasks /create /tn "TurtleSoupBackend" /tr "\"{pyw}\" \"{root}\tsu_watchdog.py\"" /sc onlogon /f
echo.
echo [3/3] 立即启动后端与守护进程...
start "" "{pyw}" "{root}\tsu_watchdog.py"
echo.
echo 完成。稍等 10 秒后浏览器打开验证：
echo   https://laptop-a763c6tn.taild83cf2.ts.net:8443/
echo.
echo 守护进程每 2 分钟自检，后端掉线会自动拉起；开机自动运行，无需再手动操作。
pause
exit /b 0
""".format(root=ROOT, pyw=PYW)


def w(name, text):
    p = os.path.join(ROOT, name)
    io.open(p, "w", encoding="gbk", newline="\r\n").write(text)
    print("wrote", name)


w("keep_alive_backend.bat", KEEP_BAT)
w("make_shortcut.vbs", MAKE_LNK)
w("register_turtle_soup.bat", REGISTER_BAT)

# 清理已被替代的 VBS 守护脚本
stale = os.path.join(ROOT, "keep_alive_backend.vbs")
if os.path.exists(stale):
    os.remove(stale)
    print("removed keep_alive_backend.vbs (已被 tsu_watchdog.py 取代)")
