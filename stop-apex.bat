@echo off
REM ============================================================
REM  Apex Resident - quick stop
REM  Double-click to kill all running Apex processes.
REM  Alternative: right-click the tray icon -^> Quit.
REM ============================================================

taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq Apex*" >nul 2>nul
taskkill /f /im python.exe  /fi "WINDOWTITLE eq Apex*" >nul 2>nul

REM Fallback: kill any Python process running main.py --resident
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%main.py --resident%%' and not commandline like '%%wmic%%'" get processid /value 2^>nul ^| find "="') do taskkill /f /pid %%p >nul 2>nul

echo Apex stopped.
timeout /t 2 >nul
