#!/usr/bin/env bash
# One-time setup for a stable Cloudflare named tunnel for Apex.
#
# Walks through every step interactively and is fully idempotent — safe to
# re-run if you need to change the hostname or if a step was interrupted.
#
# After this script completes, start the tunnel with:
#   ./scripts/tunnel-cloudflared.sh --named
#
# The tunnel will always surface Apex at the same public URL, so your QR
# pairing links, push notification click-throughs, and phone bookmarks never
# break across restarts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
CF_DIR="${HOME}/.cloudflared"
TUNNEL_NAME="apex"

# ── colours ──────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; GREEN=$'\e[32m'; CYAN=$'\e[36m'; YELLOW=$'\e[33m'; RED=$'\e[31m'; RESET=$'\e[0m'
else
  BOLD=''; GREEN=''; CYAN=''; YELLOW=''; RED=''; RESET=''
fi

step()  { echo; echo "${BOLD}${CYAN}▶ $*${RESET}"; }
ok()    { echo "${GREEN}✓ $*${RESET}"; }
warn()  { echo "${YELLOW}⚠ $*${RESET}"; }
die()   { echo "${RED}✗ $*${RESET}" >&2; exit 1; }
ask()   { printf "${BOLD}%s${RESET} " "$*"; read -r REPLY; }

# ── step 0: check cloudflared ─────────────────────────────────────────────
step "Checking for cloudflared"
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Install it first:"
  echo
  echo "  macOS:   brew install cloudflared"
  echo "  Ubuntu:  curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null"
  echo "           echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list"
  echo "           sudo apt update && sudo apt install cloudflared"
  echo "  Other:   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  die "Install cloudflared and re-run this script."
fi
ok "cloudflared $(cloudflared --version 2>&1 | head -1 | awk '{print $3}')"

# ── step 1: cloudflare login ──────────────────────────────────────────────
step "Cloudflare login"
if [[ -f "${CF_DIR}/cert.pem" ]]; then
  ok "Already logged in (cert.pem found — skipping)"
else
  echo "A browser window will open to authorise with your Cloudflare account."
  echo "The domain you select here is where the tunnel's CNAME will be created."
  echo
  ask "Press Enter to open the browser..."
  cloudflared tunnel login
  [[ -f "${CF_DIR}/cert.pem" ]] || die "Login did not write cert.pem. Check cloudflared output."
  ok "Login complete"
fi

# ── step 2: create tunnel ─────────────────────────────────────────────────
step "Creating named tunnel '${TUNNEL_NAME}'"
EXISTING_UUID=$(cloudflared tunnel list --output json 2>/dev/null \
  | python3 -c "import sys,json; ts=[t for t in json.load(sys.stdin) if t.get('name')=='${TUNNEL_NAME}']; print(ts[0]['id'] if ts else '')" 2>/dev/null || true)

if [[ -n "${EXISTING_UUID}" ]]; then
  TUNNEL_UUID="${EXISTING_UUID}"
  ok "Tunnel '${TUNNEL_NAME}' already exists (${TUNNEL_UUID}) — skipping create"
else
  CREATE_OUT=$(cloudflared tunnel create "${TUNNEL_NAME}" 2>&1)
  echo "${CREATE_OUT}"
  TUNNEL_UUID=$(echo "${CREATE_OUT}" | grep -oP '(?<=with id )[0-9a-f-]+' || true)
  [[ -n "${TUNNEL_UUID}" ]] || die "Could not parse tunnel UUID from output above."
  ok "Tunnel created: ${TUNNEL_UUID}"
fi

CREDS_FILE="${CF_DIR}/${TUNNEL_UUID}.json"
[[ -f "${CREDS_FILE}" ]] || die "Expected credentials file not found: ${CREDS_FILE}"

# ── step 3: hostname + port ───────────────────────────────────────────────
step "Hostname configuration"
PORT="${DASHBOARD_PORT:-7860}"

echo "Enter the public hostname for Apex (must be on a domain managed by Cloudflare)."
echo "Example: apex.yourdomain.com"
echo
ask "Hostname:"
HOSTNAME="${REPLY}"
[[ -n "${HOSTNAME}" ]] || die "Hostname cannot be empty."

echo
ask "Local Apex port [${PORT}]:"
[[ -n "${REPLY}" ]] && PORT="${REPLY}"

# ── step 4: write config.yml ──────────────────────────────────────────────
step "Writing ~/.cloudflared/config.yml"
CONFIG_FILE="${CF_DIR}/config.yml"
NEW_CONFIG="tunnel: ${TUNNEL_UUID}
credentials-file: ${CREDS_FILE}
ingress:
  - hostname: ${HOSTNAME}
    service: http://localhost:${PORT}
  - service: http_status:404
"

if [[ -f "${CONFIG_FILE}" ]]; then
  CURRENT=$(cat "${CONFIG_FILE}")
  if [[ "${CURRENT}" == "${NEW_CONFIG}" ]]; then
    ok "config.yml already up to date"
  else
    warn "config.yml already exists with different content."
    echo "Current content:"
    echo "---"
    cat "${CONFIG_FILE}"
    echo "---"
    echo
    ask "Overwrite with new config? [y/N]:"
    if [[ "${REPLY,,}" == "y" ]]; then
      echo "${NEW_CONFIG}" > "${CONFIG_FILE}"
      ok "config.yml updated"
    else
      warn "Keeping existing config.yml — make sure it routes to ${HOSTNAME}"
    fi
  fi
else
  echo "${NEW_CONFIG}" > "${CONFIG_FILE}"
  ok "config.yml written"
fi

echo
cat "${CONFIG_FILE}"

# ── step 5: DNS CNAME ─────────────────────────────────────────────────────
step "Creating DNS CNAME for ${HOSTNAME}"
echo "This creates a CNAME in Cloudflare DNS pointing ${HOSTNAME} → the tunnel."
echo "(Safe to run again — cloudflared is idempotent here.)"
cloudflared tunnel route dns "${TUNNEL_NAME}" "${HOSTNAME}" \
  && ok "CNAME created (or already exists)" \
  || warn "CNAME creation returned an error — it may already exist, which is fine."

# ── step 6: update .env ───────────────────────────────────────────────────
step "Updating PUBLIC_BASE_URL in .env"
PUBLIC_URL="https://${HOSTNAME}"

if [[ ! -f "${ENV_FILE}" ]]; then
  warn ".env not found at ${ENV_FILE} — skipping auto-update."
  echo "Add this line manually: PUBLIC_BASE_URL=${PUBLIC_URL}"
else
  if grep -q '^PUBLIC_BASE_URL=' "${ENV_FILE}" 2>/dev/null; then
    CURRENT_VAL=$(grep '^PUBLIC_BASE_URL=' "${ENV_FILE}" | cut -d= -f2-)
    if [[ "${CURRENT_VAL}" == "${PUBLIC_URL}" ]]; then
      ok "PUBLIC_BASE_URL already set to ${PUBLIC_URL}"
    else
      sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=${PUBLIC_URL}|" "${ENV_FILE}"
      ok "Updated PUBLIC_BASE_URL → ${PUBLIC_URL}  (was: ${CURRENT_VAL})"
    fi
  else
    echo "PUBLIC_BASE_URL=${PUBLIC_URL}" >> "${ENV_FILE}"
    ok "Appended PUBLIC_BASE_URL=${PUBLIC_URL} to .env"
  fi
fi

# ── step 7: optional auto-start ───────────────────────────────────────────
step "Auto-start (optional)"
OS="$(uname -s)"
if [[ "${OS}" == "Linux" ]]; then
  echo "To start the tunnel automatically on boot (systemd):"
  echo "  sudo cloudflared service install"
  echo "  sudo systemctl enable --now cloudflared"
  echo
  ask "Install as a systemd service now? [y/N]:"
  if [[ "${REPLY,,}" == "y" ]]; then
    sudo cloudflared service install
    sudo systemctl enable --now cloudflared
    ok "cloudflared service installed and started"
  fi
elif [[ "${OS}" == "Darwin" ]]; then
  echo "To start the tunnel automatically on boot (launchd):"
  echo "  sudo cloudflared service install"
  echo
  ask "Install as a launchd service now? [y/N]:"
  if [[ "${REPLY,,}" == "y" ]]; then
    sudo cloudflared service install
    ok "cloudflared service installed"
  fi
fi

# ── done ──────────────────────────────────────────────────────────────────
echo
echo "${BOLD}${GREEN}━━━ Setup complete ━━━${RESET}"
echo
echo "  Public URL : ${BOLD}${PUBLIC_URL}${RESET}"
echo "  Tunnel name: ${TUNNEL_NAME} (${TUNNEL_UUID})"
echo "  Config     : ${CONFIG_FILE}"
echo "  .env       : PUBLIC_BASE_URL=${PUBLIC_URL}"
echo
echo "Start the tunnel:"
echo "  ${CYAN}./scripts/tunnel-cloudflared.sh --named${RESET}"
echo
echo "Then restart Apex so it picks up the new PUBLIC_BASE_URL:"
echo "  ${CYAN}python main.py${RESET}"
echo
echo "Open ${PUBLIC_URL} on your phone, scan the QR from Devices → Pair a phone,"
echo "and you're done. The URL is permanent — no re-pairing needed after restarts."
