#!/usr/bin/env bash
# Expose your local Apex over a public HTTPS URL via Cloudflare Tunnel.
#
# Apex binds 127.0.0.1 by default; a tunnel reaches that loopback port and gives
# you a public https:// URL your phone can use from anywhere. ALWAYS set
# DASHBOARD_TOKEN before exposing Apex — it can run commands on your machine.
#
# Usage:
#   DASHBOARD_PORT=7860 ./scripts/tunnel-cloudflared.sh           # quick tunnel
#   ./scripts/tunnel-cloudflared.sh --named apex.example.com      # stable hostname
set -euo pipefail

PORT="${DASHBOARD_PORT:-7860}"
LOCAL="http://localhost:${PORT}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Install it:"
  echo "  macOS:  brew install cloudflared"
  echo "  Linux:  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

if [[ "${1:-}" == "--named" ]]; then
  CF_CONFIG="${HOME}/.cloudflared/config.yml"
  if [[ ! -f "${CF_CONFIG}" ]]; then
    echo "Named tunnel not configured yet."
    echo "Run the one-time setup first:"
    echo "  ./scripts/setup-cloudflare-tunnel.sh"
    exit 1
  fi
  HOSTNAME=$(grep 'hostname:' "${CF_CONFIG}" | head -1 | awk '{print $2}')
  echo "→ Starting named Cloudflare tunnel (apex)"
  echo "  Public URL : https://${HOSTNAME}"
  echo "  Config     : ${CF_CONFIG}"
  echo
  exec cloudflared tunnel run apex
else
  echo "→ Starting a quick Cloudflare tunnel to ${LOCAL}"
  echo "  A https://<random>.trycloudflare.com URL will print below."
  echo "  Put that URL in PUBLIC_BASE_URL (.env) and reload, so QR pairing + push"
  echo "  click-throughs use the public address."
  echo
  exec cloudflared tunnel --url "${LOCAL}"
fi
