# Creates Apex shortcuts on the Desktop and in the Start Menu, with the Apex icon.
# Run via install-apex-shortcut.bat (double-click) — no need to touch PowerShell directly.

$ErrorActionPreference = "Stop"

# Repo root = parent of the scripts folder this file lives in
# $PSScriptRoot is the directory containing this .ps1 (reliable on PowerShell 3.0+)
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = (Resolve-Path (Join-Path $scriptDir "..")).Path

$target = Join-Path $repo "scripts\start-apex.bat"
$icon   = Join-Path $repo "dashboard\static\icons\apex.ico"

if (-not (Test-Path $target)) {
    Write-Host "ERROR: launcher not found at $target" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $icon)) {
    Write-Host "WARNING: icon not found at $icon — shortcut will use the default icon." -ForegroundColor Yellow
    $icon = $null
}

function New-ApexShortcut($linkPath) {
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($linkPath)
    $sc.TargetPath       = $target
    $sc.WorkingDirectory = $repo
    $sc.WindowStyle      = 7          # 7 = minimized (no console window pops up)
    $sc.Description       = "Launch Apex AI and open the dashboard"
    if ($icon) { $sc.IconLocation = $icon }
    $sc.Save()
}

# 1) Desktop shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$desktopLink = Join-Path $desktop "Apex.lnk"
New-ApexShortcut $desktopLink
Write-Host "[OK] Desktop shortcut created: $desktopLink" -ForegroundColor Green

# 2) Start Menu shortcut (makes Apex searchable — just press Start and type "Apex")
$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
$startLink = Join-Path $startMenu "Apex.lnk"
New-ApexShortcut $startLink
Write-Host "[OK] Start Menu shortcut created: $startLink" -ForegroundColor Green

Write-Host ""
Write-Host "Done. You can now:" -ForegroundColor Cyan
Write-Host "  - Double-click the Apex icon on your Desktop, or"
Write-Host "  - Press the Start key and type 'Apex'"
Write-Host ""
Write-Host "To pin it to the taskbar (Windows blocks this via script):" -ForegroundColor Cyan
Write-Host "  Right-click the Desktop 'Apex' icon  ->  Show more options  ->  Pin to taskbar"
