# JARVIS — Cloudflare Tunnel Setup
# Run this once to get a permanent HTTPS URL for your phone.
# Requires a free Cloudflare account (https://dash.cloudflare.com/sign-up)

$ErrorActionPreference = "Stop"
$TunnelName = "jarvis"
$JarvisUrl  = "https://localhost:8340"
$ConfigDir  = "$env:USERPROFILE\.cloudflared"
$ConfigFile = "$ConfigDir\config.yml"

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "   OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   !! $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  JARVIS Tunnel Setup" -ForegroundColor Cyan
Write-Host "  ===================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Install cloudflared ──────────────────────────────────────────────
Write-Step "Checking cloudflared..."
$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    Write-Host "   Installing cloudflared via winget..." -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared --silent --accept-package-agreements --accept-source-agreements
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $cf) {
        Write-Host "`n   ERROR: cloudflared not found after install. Try restarting this terminal and re-running." -ForegroundColor Red
        exit 1
    }
}
Write-OK "cloudflared $(cloudflared --version 2>&1 | Select-String 'version' | ForEach-Object { $_.ToString().Trim() })"

# ── Step 2: Login ────────────────────────────────────────────────────────────
Write-Step "Checking Cloudflare login..."
$certPath = "$ConfigDir\cert.pem"
if (-not (Test-Path $certPath)) {
    Write-Host ""
    Write-Host "   A browser window will open. Log in to your Cloudflare account." -ForegroundColor Yellow
    Write-Host "   (Free account at https://dash.cloudflare.com/sign-up if you don't have one)" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "   Press ENTER to open the browser"
    cloudflared tunnel login
    if (-not (Test-Path $certPath)) {
        Write-Host "`n   Login failed or was cancelled. Run setup-tunnel.ps1 again." -ForegroundColor Red
        exit 1
    }
}
Write-OK "Logged in"

# ── Step 3: Create tunnel (skip if exists) ───────────────────────────────────
Write-Step "Setting up tunnel '$TunnelName'..."
$existingTunnel = cloudflared tunnel list 2>&1 | Select-String $TunnelName
$TunnelId = $null

if ($existingTunnel) {
    # Parse tunnel ID from the list output
    $TunnelId = ($existingTunnel.ToString().Trim() -split '\s+')[0]
    Write-OK "Tunnel already exists (ID: $TunnelId)"
} else {
    $createOutput = cloudflared tunnel create $TunnelName 2>&1
    Write-Host "   $createOutput"
    # Extract UUID from output like "Created tunnel jarvis with id abc-123-..."
    $match = [regex]::Match($createOutput, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    if ($match.Success) {
        $TunnelId = $match.Value
        Write-OK "Tunnel created (ID: $TunnelId)"
    } else {
        Write-Host "`n   ERROR: Could not parse tunnel ID. Output was:`n$createOutput" -ForegroundColor Red
        exit 1
    }
}

# ── Step 4: Write config.yml ─────────────────────────────────────────────────
Write-Step "Writing config to $ConfigFile..."

# Find credentials file
$credFile = Get-ChildItem "$ConfigDir\*.json" | Where-Object { $_.Name -match $TunnelId } | Select-Object -First 1
if (-not $credFile) {
    # cloudflared stores creds in ~/.cloudflared/<tunnel-id>.json
    $credFile = "$ConfigDir\$TunnelId.json"
}

$configContent = @"
tunnel: $TunnelId
credentials-file: $ConfigDir\$TunnelId.json

ingress:
  - service: $JarvisUrl
    originRequest:
      noTLSVerify: true
"@

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
Set-Content -Path $ConfigFile -Value $configContent
Write-OK "Config written"

# ── Step 5: Get the public URL ───────────────────────────────────────────────
Write-Step "Your permanent JARVIS URL:"
Write-Host ""
Write-Host "   https://$TunnelId.cfargotunnel.com" -ForegroundColor Green
Write-Host ""
Write-Host "   Open this on your phone to install the JARVIS app." -ForegroundColor White

# ── Step 6: Create start script ──────────────────────────────────────────────
Write-Step "Creating start-tunnel.ps1..."
$startScript = @"
# Start JARVIS Cloudflare Tunnel
# Run this whenever you want your phone to connect remotely.
Write-Host "Starting JARVIS tunnel..." -ForegroundColor Cyan
Write-Host "Your URL: https://$TunnelId.cfargotunnel.com" -ForegroundColor Green
cloudflared tunnel run $TunnelName
"@
$startScriptPath = "$PSScriptRoot\start-tunnel.ps1"
Set-Content -Path $startScriptPath -Value $startScript
Write-OK "Created start-tunnel.ps1"

# ── Step 7: Optional auto-start on Windows boot ──────────────────────────────
Write-Step "Auto-start on Windows boot..."
Write-Host ""
$autoStart = Read-Host "   Start the tunnel automatically when Windows starts? (y/n)"
if ($autoStart -eq 'y' -or $autoStart -eq 'Y') {
    cloudflared service install
    Write-OK "Tunnel will start automatically with Windows"
    Write-Warn "To remove auto-start later: cloudflared service uninstall"
} else {
    Write-Host "   Skipped. Run start-tunnel.ps1 manually when you want remote access." -ForegroundColor Yellow
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Make sure JARVIS server is running (python server.py)" -ForegroundColor White
Write-Host "  2. Run start-tunnel.ps1 (or it auto-starts if you chose yes above)" -ForegroundColor White
Write-Host "  3. Open https://$TunnelId.cfargotunnel.com on your phone" -ForegroundColor White
Write-Host "  4. Add to Home Screen -> JARVIS is on your phone permanently" -ForegroundColor White
Write-Host ""
