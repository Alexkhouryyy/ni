@echo off
REM ============================================================
REM  Apex Resident - Windows one-shot installer
REM  Double-click this file. Setup runs once; after that Apex
REM  starts automatically every time you log into Windows.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   APEX RESIDENT - WINDOWS INSTALLER
echo ============================================================
echo.

REM ---- 1/6: locate Python ----
echo [1/6] Looking for Python...
where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed.
    echo.
    echo   1. Download Python 3.11 or newer from:
    echo      https://www.python.org/downloads/
    echo   2. During install, CHECK the box "Add Python to PATH"
    echo   3. Re-run this installer.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('py -3 --version 2^>nul') do set PYVER=%%v
echo       Found: !PYVER!

REM ---- 2/6: install dependencies ----
echo.
echo [2/6] Installing Python packages (2-3 minutes, please wait)...
py -3 -m pip install --upgrade pip --quiet
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Package install failed. Scroll up to see what broke.
    pause
    exit /b 1
)
echo       Packages installed.

REM ---- 3/6: set up .env ----
echo.
echo [3/6] Setting up config file (.env)...
if not exist .env (
    copy .env.example .env >nul
    echo       Created .env from template.
) else (
    echo       .env already exists - leaving alone.
)

REM Check if API keys are still placeholders
findstr /C:"your_key_here" .env >nul
if not errorlevel 1 (
    echo.
    echo  ----------------------------------------------------------
    echo   YOUR API KEYS ARE NOT SET YET.
    echo  ----------------------------------------------------------
    echo   Notepad will open. At the top of the file, replace:
    echo     ANTHROPIC_API_KEY=your_key_here    -^>  your real key
    echo     OPENAI_API_KEY=your_openai_key...  -^>  your real key
    echo.
    echo   Then save (Ctrl+S) and close Notepad to continue.
    echo  ----------------------------------------------------------
    timeout /t 4 >nul
    notepad .env
)

REM ---- 4/6: log folder ----
echo.
echo [4/6] Creating log folder...
if not exist "%USERPROFILE%\.apex" mkdir "%USERPROFILE%\.apex"
echo       Logs will go to %USERPROFILE%\.apex\

REM ---- 5/6: register autostart ----
echo.
echo [5/6] Registering autostart on login...
py -3 -m app.autostart install
if errorlevel 1 (
    echo       WARN: autostart registration failed - manual launch still works.
)

REM ---- 6/6: launch ----
echo.
echo [6/6] Launching Apex Resident in the background...
start "" pyw -3 main.py --resident

echo.
echo ============================================================
echo   SETUP COMPLETE
echo ============================================================
echo.
echo Apex is now running in the background. Look for the tray
echo icon near your clock (bottom-right of the taskbar; click the
echo ^^ arrow if hidden).
echo.
echo You can close this window. From now on Apex starts
echo automatically every time you log into Windows.
echo.
echo Try this:
echo   - Say:    "Apex, what time is it?"
echo   - Press:  Ctrl + Space     (wake without speaking)
echo   - Press:  Ctrl + Alt + M   (mute / unmute)
echo   - Visit:  http://localhost:5000   (dashboard)
echo.
echo If you ever need to start it again manually, double-click
echo start-apex.bat in this folder.
echo.
pause
