' Apex-Launch.vbs
' Double-click this file to launch Apex.
' Works on any Windows without CMD or execution policy changes.
Dim parentPath, ps1Path, cmd
parentPath = Left(WScript.ScriptFullPath, InStrRev(WScript.ScriptFullPath, "\"))
ps1Path = parentPath & "Apex.ps1"
cmd = "powershell.exe -ExecutionPolicy Bypass -File """ & ps1Path & """"
Set shell = CreateObject("WScript.Shell")
shell.Run cmd, 1, False
