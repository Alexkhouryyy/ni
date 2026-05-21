# Apex.ps1 - Windows launcher (PowerShell)
# Double-click Apex-Launch.vbs to run this, or right-click -> Run with PowerShell.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

function Find-Python {
    foreach ($c in @("python", "py", "python3")) {
        try {
            $null = & $c --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch {}
    }
    return $null
}

try {
    Write-Host ""
    Write-Host "  ==========================================="
    Write-Host "    A P E X"
    Write-Host "  ==========================================="
    Write-Host ""

    # 1. Python
    $py = Find-Python
    if (-not $py) {
        Write-Host "  [setup] Python not found - installing via winget..."
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        $py = Find-Python
        if (-not $py) { throw "Python installed but not on PATH yet. Close and rerun Apex-Launch.vbs." }
    }

    # 2. Virtual environment
    $vpy = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $vpy)) {
        Write-Host "  [setup] Creating virtual environment..."
        & $py -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
    }

    # 3. Dependencies
    $marker = Join-Path $scriptDir ".venv\.apex_ready"
    if (-not (Test-Path $marker)) {
        Write-Host "  [setup] Installing dependencies (one-time, ~2 GB, 10-20 min)..."
        Write-Host ""
        & $vpy -m pip install --upgrade pip
        & $vpy -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "pip install failed - see errors above." }
        Write-Host "  [setup] Downloading optional browser engine..."
        & $vpy -m playwright install chromium
        "ready" | Out-File $marker -Encoding ascii
        Write-Host ""
        Write-Host "  [setup] Done. Future launches will be instant."
        Write-Host ""
    }

    # 4. API key
    $envFile = Join-Path $scriptDir ".env"
    $needKey = (-not (Test-Path $envFile)) -or ((Get-Content $envFile -Raw) -match "your_key_here")
    if ($needKey) {
        Write-Host "  Apex needs your Anthropic API key (asked once)."
        Write-Host "  Get one at https://console.anthropic.com/settings/keys"
        Write-Host ""
        $key = Read-Host "  Paste your key and press Enter"
        "ANTHROPIC_API_KEY=$key" | Out-File $envFile -Encoding ascii
        Write-Host "  Saved."
        Write-Host ""
    }

    # 5. Launch
    Write-Host "  Starting Apex. Type 'quit' to exit."
    Write-Host ""
    & $vpy main.py --tui
    Write-Host ""
    Write-Host "  Apex has stopped."

} catch {
    Write-Host ""
    Write-Host "  [ERROR] $_"
} finally {
    Write-Host ""
    Read-Host "  Press Enter to close"
}
