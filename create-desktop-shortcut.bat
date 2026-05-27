@echo off
REM ============================================================
REM  Apex Resident - Desktop shortcut creator
REM  Double-click to put an "Apex" icon on your desktop that
REM  launches Apex silently (no terminal window).
REM ============================================================

setlocal
cd /d "%~dp0"

set "TARGET=%~dp0start-apex.bat"
set "LINK=%USERPROFILE%\Desktop\Apex.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%LINK%');" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Launch Apex Resident in the background';" ^
  "$s.Save()"

if exist "%LINK%" (
    echo.
    echo Desktop shortcut created: %LINK%
    echo Double-click "Apex" on your desktop to launch.
) else (
    echo.
    echo Shortcut creation failed.
)

echo.
pause
