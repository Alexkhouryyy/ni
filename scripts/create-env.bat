@echo off
REM One-time script to create your .env file.
REM Run this from C:\Users\alexk\ni\, then DELETE this file.

set ENV_FILE=%~dp0..\. env

(
echo DASHBOARD_TOKEN=whowantstobeking
echo DASHBOARD_HOST=0.0.0.0
echo PUBLIC_BASE_URL=http://100.113.213.123:7860
echo VAPID_PUBLIC_KEY=BO85Dfthavj4eQI7wRCJqfTzYBsZXavZzN9oHcaqCO10nYaoHjRvIWDqEFbtWgnRySBlPXrf1Y0-o6rTJzQsv_8
echo VAPID_PRIVATE_KEY=ivdILszBHFRqT-lndO62FO_Zlw-qqDBckJWX35MvESA
echo VAPID_SUBJECT=mailto:alexkhoury35@gmail.com
) > "%~dp0..\.env"

echo.
echo .env created at %~dp0..\.env
echo Delete this script now: del "%~f0"
