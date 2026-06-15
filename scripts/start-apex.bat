@echo off
setlocal enableextensions
title Apex AI

REM --- Resolve repo root from this script's location (portable, no hardcoded path) ---
for %%I in ("%~dp0..") do set "REPO=%%~fI"

REM --- Read DASHBOARD_PORT and DASHBOARD_TOKEN from .env (no secrets baked into this file) ---
set "PORT=7860"
set "TOKEN="
if exist "%REPO%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%REPO%\.env") do (
        if /i "%%A"=="DASHBOARD_PORT" set "PORT=%%B"
        if /i "%%A"=="DASHBOARD_TOKEN" set "TOKEN=%%B"
    )
)

REM Trim possible surrounding quotes/whitespace from values
set "PORT=%PORT: =%"
if defined TOKEN set "TOKEN=%TOKEN: =%"

REM Build the dashboard URL (append token only if present)
if defined TOKEN (
    set "URL=http://localhost:%PORT%?token=%TOKEN%"
) else (
    set "URL=http://localhost:%PORT%"
)

REM --- If Apex is already running on the port, just open the dashboard ---
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" > NUL 2>&1
if %errorlevel% == 0 (
    echo [Apex] Already running - opening dashboard...
    start "" "%URL%"
    exit /b 0
)

REM --- Start Apex minimized in its own window (/D sets the working dir cleanly) ---
echo [Apex] Starting from %REPO% ...
start "Apex AI" /MIN /D "%REPO%" cmd /k "uv run python main.py"

REM --- Wait for the server to come up (up to 20 seconds) ---
set /a tries=0
:wait
timeout /t 1 /nobreak > NUL
set /a tries+=1
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" > NUL 2>&1
if %errorlevel% == 0 goto ready
if %tries% lss 20 goto wait

echo [Apex] Server did not respond in time - opening dashboard anyway.

:ready
start "" "%URL%"
endlocal
