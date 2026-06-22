@echo off
REM ============================================================
REM  JARVIS — one-click launcher
REM  Double-click this file to start backend, frontend, and the
REM  browser. Closes nothing; safe to run twice.
REM ============================================================

setlocal
set "JARVIS_DIR=%~dp0"
set "JARVIS_DIR=%JARVIS_DIR:~0,-1%"
set "FRONTEND_PORT=5195"
set "BACKEND_PORT=8340"

echo.
echo  J.A.R.V.I.S. Launcher
echo  ----------------------------------------------
echo  Project: %JARVIS_DIR%
echo.

REM --- Backend ---------------------------------------------------
netstat -ano | findstr "LISTENING" | findstr ":%BACKEND_PORT% " >nul
if %ERRORLEVEL%==0 (
    echo  [ok]   Backend already running on port %BACKEND_PORT%
) else (
    echo  [..]  Starting backend on port %BACKEND_PORT% ...
    start "JARVIS Backend" cmd /k "cd /d ""%JARVIS_DIR%"" && python server.py"
)

REM --- Frontend --------------------------------------------------
netstat -ano | findstr "LISTENING" | findstr ":%FRONTEND_PORT% " >nul
if %ERRORLEVEL%==0 (
    echo  [ok]   Frontend already running on port %FRONTEND_PORT%
) else (
    echo  [..]  Starting frontend on port %FRONTEND_PORT% ...
    start "JARVIS Frontend" cmd /k "cd /d ""%JARVIS_DIR%\frontend"" && npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT% --strictPort"
)

REM --- Wait for frontend to come up, then open browser ----------
echo.
echo  [..]  Waiting for frontend to come up ...
set /a "TRIES=0"
:wait_loop
set /a "TRIES+=1"
if %TRIES% GTR 30 (
    echo  [!!]  Frontend did not start within 30 seconds.
    echo        Check the "JARVIS Frontend" window for errors.
    goto end
)
timeout /t 1 /nobreak >nul
netstat -ano | findstr "LISTENING" | findstr ":%FRONTEND_PORT% " >nul
if %ERRORLEVEL% NEQ 0 goto wait_loop

echo  [ok]  Frontend is up. Opening browser ...
start "" "http://localhost:%FRONTEND_PORT%"

:end
echo.
echo  All set, sir. JARVIS is live at http://localhost:%FRONTEND_PORT%
echo  Two windows are now running: "JARVIS Backend" and "JARVIS Frontend".
echo  Closing either of them shuts down that part of JARVIS.
echo.
echo  This launcher window will close in 5 seconds...
timeout /t 5 /nobreak >nul
endlocal
