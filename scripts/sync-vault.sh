#!/usr/bin/env bash
# sync-vault.sh — keep the Obsidian vault in sync between your laptop and the Oracle Cloud VM.
#
# Run this from your LAPTOP (not the Oracle VM).
# Requires: Tailscale running on both machines, rsync.
#
# Usage:
#   bash scripts/sync-vault.sh push          # laptop -> cloud (default)
#   bash scripts/sync-vault.sh pull          # cloud  -> laptop
#   bash scripts/sync-vault.sh watch         # auto-push every 5 min (background loop)
#
# Set ORACLE_IP to your Oracle VM's Tailscale IP.
# Set ORACLE_USER to your VM username (default: ubuntu).
# Either pass them as env vars or edit the defaults below.

set -euo pipefail

ORACLE_IP="${ORACLE_IP:-}"
ORACLE_USER="${ORACLE_USER:-ubuntu}"
LOCAL_VAULT="${LOCAL_VAULT:-$HOME/Documents/Apex}"
REMOTE_VAULT="${REMOTE_VAULT:-/home/${ORACLE_USER}/Documents/Apex}"
WATCH_INTERVAL="${WATCH_INTERVAL:-300}"   # seconds between auto-syncs

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

# Resolve Oracle IP from Tailscale if not set
if [ -z "$ORACLE_IP" ]; then
    ORACLE_IP="$(tailscale status --json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
peers=data.get('Peer',{})
for _,v in peers.items():
    hn=v.get('HostName','')
    if 'oracle' in hn.lower() or 'ubuntu' in hn.lower():
        ips=v.get('TailscaleIPs',[])
        if ips: print(ips[0]); break
" 2>/dev/null || true)"
fi

if [ -z "$ORACLE_IP" ]; then
    echo -e "${RED}[FAIL]${NC} Cannot find Oracle VM on Tailscale."
    echo "  Set ORACLE_IP=100.x.x.x or ensure both machines are on Tailscale."
    echo "  Run: tailscale status   to find your Oracle VM's IP"
    exit 1
fi

REMOTE="${ORACLE_USER}@${ORACLE_IP}:${REMOTE_VAULT}/"

_push() {
    echo -e "${GREEN}[push]${NC} $LOCAL_VAULT/ -> $REMOTE"
    rsync -avz --delete \
        --exclude=".obsidian/workspace*" \
        --exclude=".obsidian/graph.json" \
        --exclude=".trash" \
        "$LOCAL_VAULT/" "$REMOTE"
    echo -e "${GREEN}Done.${NC}"
}

_pull() {
    echo -e "${GREEN}[pull]${NC} $REMOTE -> $LOCAL_VAULT/"
    rsync -avz --delete \
        --exclude=".obsidian/workspace*" \
        --exclude=".obsidian/graph.json" \
        --exclude=".trash" \
        "$REMOTE" "$LOCAL_VAULT/"
    echo -e "${GREEN}Done.${NC}"
}

_watch() {
    echo -e "${GREEN}[watch]${NC} Auto-syncing every ${WATCH_INTERVAL}s. Ctrl+C to stop."
    while true; do
        _push
        sleep "$WATCH_INTERVAL"
    done
}

ACTION="${1:-push}"
case "$ACTION" in
    push)  _push  ;;
    pull)  _pull  ;;
    watch) _watch ;;
    *)
        echo "Usage: $0 [push|pull|watch]"
        exit 1
        ;;
esac
