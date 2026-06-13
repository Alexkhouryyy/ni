#!/usr/bin/env bash
# Expose your local Apex over your private Tailscale network (most private), or
# publicly via Tailscale Funnel.
#
# `tailscale serve`  → reachable only by your own devices on your tailnet (the
#                      phone must have the Tailscale app + be logged in). No
#                      public exposure at all.
# `tailscale funnel` → reachable from the public internet over HTTPS.
#
# ALWAYS set DASHBOARD_TOKEN before exposing Apex — it can run commands.
#
# Usage:
#   DASHBOARD_PORT=7860 ./scripts/tunnel-tailscale.sh          # private (serve)
#   ./scripts/tunnel-tailscale.sh --funnel                     # public (funnel)
set -euo pipefail

PORT="${DASHBOARD_PORT:-7860}"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale not found. Install from https://tailscale.com/download, then 'tailscale up'."
  exit 1
fi

DNSNAME="$(tailscale status --json 2>/dev/null | grep -o '"DNSName":"[^"]*"' | head -1 | cut -d'"' -f4 | sed 's/\.$//' || true)"

if [[ "${1:-}" == "--funnel" ]]; then
  echo "→ Publishing Apex publicly via Tailscale Funnel (port ${PORT})"
  [[ -n "$DNSNAME" ]] && echo "  Public URL: https://${DNSNAME}  → set PUBLIC_BASE_URL to this in .env"
  exec tailscale funnel "${PORT}"
else
  echo "→ Serving Apex privately on your tailnet (port ${PORT})"
  [[ -n "$DNSNAME" ]] && echo "  Private URL: https://${DNSNAME}  → set PUBLIC_BASE_URL to this in .env"
  echo "  Only your logged-in Tailscale devices can reach it."
  exec tailscale serve "${PORT}"
fi
