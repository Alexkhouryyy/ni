' ============================================================
'  JARVIS — silent launcher
'  Double-click this file to wake JARVIS.
'  No console window, no terminal, no commands. Just the orb.
' ============================================================

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' This script's own folder = the JARVIS project folder
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = projectDir

' Find the windowless Python (pythonw.exe). Prefer the known install,
' fall back to whatever is on PATH.
pythonw = "pythonw"
candidates = Array( _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe" _
)
For Each c In candidates
    If fso.FileExists(c) Then
        pythonw = c
        Exit For
    End If
Next

' Window style 0 = hidden. False = don't wait for it to finish.
shell.Run """" & pythonw & """ """ & projectDir & "\desktop_shell.py""", 0, False
