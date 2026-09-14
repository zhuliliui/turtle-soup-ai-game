# -*- coding: utf-8 -*-
"""海龟汤 Demo 保活守护进程（TSU Watchdog）

职责：
1. 每 2 分钟探测本机 8000 端口，后端掉线自动拉起（独立进程，脱离守护存活）
2. 定期重申 Tailscale Funnel 映射（8443 → 8000）
3. 写心跳日志到 backend/backend_watchdog.log

启动方式：由计划任务 TurtleSoupBackend 在登录时用 pythonw.exe 拉起（无窗口）
"""
import datetime
import os
import subprocess
import sys
import time
import urllib.request

ROOT = r"C:\Users\zhu\Desktop\海龟汤"
BACKEND_DIR = os.path.join(ROOT, "backend")
PY = r"D:\develop\anaconda\python.exe"
TS = r"C:\Program Files\Tailscale\tailscale.exe"
LOG = os.path.join(BACKEND_DIR, "backend_watchdog.log")
URL = "http://127.0.0.1:8000/"
FUNNEL_TARGET = "http://127.0.0.1:8000"

DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def backend_alive():
    try:
        r = _opener.open(URL, timeout=4)
        return 200 <= r.status < 500
    except Exception:
        return False


def start_backend():
    try:
        out = open(os.path.join(BACKEND_DIR, "backend_8000.log"), "a", encoding="utf-8")
        subprocess.Popen(
            [PY, "main.py"],
            cwd=BACKEND_DIR,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=DETACHED,
            close_fds=True,
        )
        log("backend 已拉起（detached）")
        return True
    except Exception as e:
        log("backend 拉起失败: %r" % (e,))
        return False


def ensure_funnel():
    try:
        subprocess.run(
            [TS, "funnel", "--bg", "--https=8443", FUNNEL_TARGET],
            capture_output=True,
            timeout=30,
        )
        log("Funnel 映射已重申（8443 → 8000）")
    except Exception as e:
        log("Funnel 重申失败: %r" % (e,))


def main():
    log("=== watchdog 启动 pid=%d ===" % os.getpid())
    tick = 0
    while True:
        try:
            if not backend_alive():
                log("检测到后端离线，尝试拉起")
                start_backend()
                time.sleep(12)
                log("拉起后状态: %s" % ("在线" if backend_alive() else "仍离线"))
            tick += 1
            if tick % 30 == 0:          # 约每 1 小时重申一次 Funnel
                ensure_funnel()
        except Exception as e:
            log("循环异常（已忽略继续）: %r" % (e,))
        time.sleep(120)


if __name__ == "__main__":
    main()
