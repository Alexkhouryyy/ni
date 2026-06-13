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

if [[ "${1:-}" == "--named" && -n "${2:-}" ]]; then
  HOSTNAME="$2"
  echo "→ Routing ${HOSTNAME} to ${LOCAL}"
  echo "  (one-time setup: 'cloudflared tunnel login' then 'cloudflared tunnel create apex'"
  echo "   and add a CNAME for ${HOSTNAME}. See docs/OMNIPRESENCE.md.)"
  echo
  echo "Set PUBLIC_BASE_URL=https://${HOSTNAME} in your .env so pairing/push URLs match."
  exec cloudflared tunnel run --url "${LOCAL}" apex
else
  echo "→ Starting a quick Cloudflare tunnel to ${LOCAL}"
  echo "  A https://<random>.trycloudflare.com URL will print below."
  echo "  Put that URL in PUBLIC_BASE_URL (.env) and reload, so QR pairing + push"
  echo "  click-throughs use the public address."
  echo
  exec cloudflared tunnel --url "${LOCAL}"
fi
