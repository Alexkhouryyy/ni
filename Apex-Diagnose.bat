@echo off
setlocal
title Apex Diagnostic
cd /d "%~dp0"
set "LOG=%~dp0apex_diagnostic.txt"

echo Apex diagnostic report> "%LOG%"
echo.>> "%LOG%"
echo When: %date% %time%>> "%LOG%"
echo Folder: %cd%>> "%LOG%"
echo.>> "%LOG%"

echo [1] system python version>> "%LOG%"
python --version>> "%LOG%" 2>&1
echo exit code: %errorlevel%>> "%LOG%"
echo.>> "%LOG%"

echo [2] py launcher version>> "%LOG%"
py --version>> "%LOG%" 2>&1
echo exit code: %errorlevel%>> "%LOG%"
echo.>> "%LOG%"

echo [3] files in this folder>> "%LOG%"
dir /b>> "%LOG%" 2>&1
echo.>> "%LOG%"

echo [4] virtual environment python>> "%LOG%"
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" --version>> "%LOG%" 2>&1
if not exist ".venv\Scripts\python.exe" echo venv not created yet>> "%LOG%"
echo.>> "%LOG%"

echo [5] import test>> "%LOG%"
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import config; from agent.core import AgentCore; print('imports OK')">> "%LOG%" 2>&1
if not exist ".venv\Scripts\python.exe" echo skipped - no venv yet>> "%LOG%"
echo.>> "%LOG%"

echo report finished>> "%LOG%"

echo.
echo   Diagnostic saved to: apex_diagnostic.txt
echo   Notepad will open it now - copy ALL the text and send it to Claude.
echo.
notepad "%LOG%"
