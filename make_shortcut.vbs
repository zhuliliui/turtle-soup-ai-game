' 在开机启动目录创建守护快捷方式（Python 守护，无窗口）
Option Explicit
Dim sh, lnk, q
Set sh = CreateObject("WScript.Shell")
q = Chr(34)
Set lnk = sh.CreateShortcut(sh.SpecialFolders("Startup") & "\TurtleSoupBackend.lnk")
lnk.TargetPath = "D:\develop\anaconda\pythonw.exe"
lnk.Arguments = q & "C:\Users\zhu\Desktop\海龟汤\tsu_watchdog.py" & q
lnk.WorkingDirectory = "C:\Users\zhu\Desktop\海龟汤"
lnk.WindowStyle = 7
lnk.Description = "海龟汤 Demo 保活（后端 + Tailscale Funnel 守护）"
lnk.Save
WScript.Echo "SHORTCUT_OK " & sh.SpecialFolders("Startup")
