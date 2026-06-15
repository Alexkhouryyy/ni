@echo off
REM Double-click this once to create Apex shortcuts on your Desktop + Start Menu.
REM It calls the PowerShell installer with execution policy bypassed so you don't
REM have to change any system settings.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-shortcut.ps1"

echo.
pause
