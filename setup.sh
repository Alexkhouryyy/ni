#!/usr/bin/env bash
# Setup helper for the voice AI agent.
set -e

cd "$(dirname "$0")"

echo "==> Voice AI Agent setup"

# 1. Python deps
echo "==> Installing Python dependencies..."
pip3 install -r requirements.txt

# 2. System deps (Linux only)
if [[ "$(uname)" == "Linux" ]]; then
    if ! command -v xdotool &> /dev/null; then
        echo "==> Installing xdotool (sudo required)..."
        sudo apt-get update && sudo apt-get install -y xdotool espeak portaudio19-dev
    fi
fi

# 3. Playwright Chromium
echo "==> Installing Playwright Chromium..."
python3 -m playwright install chromium 2>&1 | tail -5 || echo "    (Playwright install skipped — install manually if browser tools fail)"

# 4. .env file
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo "==> Created .env from template."
    echo "    Open .env and add your ANTHROPIC_API_KEY before running."
    echo ""
else
    echo "==> .env exists, leaving it alone."
fi

# 5. Verify key
if grep -q "your_key_here" .env 2>/dev/null; then
    echo "WARNING: ANTHROPIC_API_KEY still set to placeholder in .env"
    echo "         Edit .env and add your real key."
    exit 1
fi

echo "==> Setup complete."
echo ""
echo "Run with:"
echo "    python3 main.py --text       # text mode (works without mic/speakers)"
echo "    python3 main.py              # voice mode"
echo ""
