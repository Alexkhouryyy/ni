@echo off
title Apex AI

REM Check if Apex is already running on port 7860
netstat -ano | findstr ":7860" | findstr "LISTENING" > NUL 2>&1
if %errorlevel% == 0 (
    echo [Apex] Already running — opening dashboard...
    start http://localhost:7860?token=whowantstobeking
    exit /b 0
)

REM Start Apex in a new window (minimized)
echo [Apex] Starting...
start "Apex AI" /MIN cmd /k "cd /d C:\Users\alexk\ni && uv run python main.py"

REM Wait for the server to be ready (up to 15 seconds)
set /a tries=0
:wait
timeout /t 1 /nobreak > NUL
set /a tries+=1
netstat -ano | findstr ":7860" | findstr "LISTENING" > NUL 2>&1
if %errorlevel% == 0 goto ready
if %tries% lss 15 goto wait

:ready
REM Open the dashboard
start http://localhost:7860?token=whowantstobeking
