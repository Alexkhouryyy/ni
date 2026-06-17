@echo off
setlocal enableextensions
title Apex - Obsidian Vault Setup

REM ============================================================
REM  Opens the Apex vault in Obsidian. Installs Obsidian first
REM  via winget if it is not already present. ASCII-only so
REM  Windows parses it cleanly.
REM ============================================================

set "VAULT=%USERPROFILE%\Documents\Apex"

echo.
echo [Apex] Vault location: %VAULT%
echo.

REM --- Make sure the vault folder exists (Apex creates it on first run,
REM     but create it here too so this script works standalone) ---
if not exist "%VAULT%" (
    echo [Apex] Creating vault folder...
    mkdir "%VAULT%"
    mkdir "%VAULT%\Memory"
    mkdir "%VAULT%\Notes"
    mkdir "%VAULT%\People"
    mkdir "%VAULT%\Projects"
    mkdir "%VAULT%\Daily"
    mkdir "%VAULT%\Skills"
)

REM --- Is Obsidian installed? Check the usual install path + the URI handler ---
set "OBS_FOUND="
if exist "%LOCALAPPDATA%\Obsidian\Obsidian.exe" set "OBS_FOUND=1"
if exist "%PROGRAMFILES%\Obsidian\Obsidian.exe" set "OBS_FOUND=1"

if not defined OBS_FOUND (
    echo [Apex] Obsidian not found. Installing via winget...
    winget install --id Obsidian.Obsidian -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo [Apex] Automatic install failed. Download Obsidian manually from:
        echo        https://obsidian.md/download
        echo        Then re-run this script.
        echo.
        pause
        exit /b 1
    )
)

REM --- Open the vault. The obsidian:// URI auto-registers it as a vault ---
echo [Apex] Opening vault in Obsidian...
start "" "obsidian://open?path=%VAULT%"

REM --- Fallback: if the URI handler is not registered yet, launch the exe ---
timeout /t 2 /nobreak > NUL
echo.
echo [Apex] Done. If Obsidian did not open the vault automatically:
echo        1. Open Obsidian
echo        2. Click "Open folder as vault"
echo        3. Select: %VAULT%
echo.
pause
