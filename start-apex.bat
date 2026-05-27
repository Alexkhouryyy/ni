@echo off
REM ============================================================
REM  Apex Resident - quick launcher
REM  Double-click to start Apex in the background (no console).
REM  Use this if autostart didn't fire, or after you quit Apex.
REM ============================================================

cd /d "%~dp0"
start "" pyw -3 main.py --resident
exit /b 0
