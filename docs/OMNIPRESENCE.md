# Apex Omnipresence — one Apex, every device

Apex runs as a single server (its brain = one SQLite DB). Every device — your
laptop browser, your phone, your browser's tabs — is a **window into that one
brain**. Same memory, same context, everywhere. This guide sets up all of it.

```
                       ┌─────────────────────────┐
   phone PWA  ───────▶ │                         │
   laptop browser ───▶ │   Apex server (main.py) │  ← one SQLite brain
   browser extension ▶ │   FastAPI + WebSocket   │
   Web Push  ◀──────── │   tray · voice · agent  │
                       └─────────────────────────┘
```

## 0. Prerequisites

```bash
pip install -r requirements.txt
```

Set a strong `DASHBOARD_TOKEN` in `.env`. **This is mandatory before exposing
Apex** — it can run commands on your machine, so the token is the gate.

```
DASHBOARD_HOST=127.0.0.1      # keep loopback; a tunnel reaches it
DASHBOARD_TOKEN=<a long random string>
```

The server **fails closed**: it refuses to bind a public interface with an empty
token and falls back to `127.0.0.1`.

---

## 1. Install the mobile app (PWA)

1. Start Apex (`python main.py`) and make it reachable from your phone (see §3).
2. On the phone, open the Apex URL and enter the token (or scan the pairing QR — §2).
3. Browser menu → **Add to Home Screen**. Apex installs with its own icon and
   launches full-screen. Tap the 🎙 button to talk; replies are spoken back.

The app shell is cached by a service worker, so it opens instantly and survives
flaky connections.

---

## 2. Pair a device with a QR (no typing)

On the desktop dashboard: **Telemetry → Devices → Pair a phone**. A QR appears
encoding `<base>/?source=pair#token=…`.

- **Phone:** scan with the camera → Apex opens already authenticated.
- **Browser extension:** copy the same link into the extension's settings — it
  splits out the URL + token automatically.

The QR uses `PUBLIC_BASE_URL` if set, otherwise the address you opened the
dashboard on.

---

## 3. Reach Apex from anywhere (tunnels)

Apex stays bound to loopback; a tunnel publishes it. Pick one:

### Cloudflare Tunnel (stable public HTTPS)
```bash
./scripts/tunnel-cloudflared.sh            # quick → https://<random>.trycloudflare.com
./scripts/tunnel-cloudflared.sh --named apex.example.com   # your own hostname
```

### Tailscale (most private — your devices only)
```bash
./scripts/tunnel-tailscale.sh              # private to your tailnet
./scripts/tunnel-tailscale.sh --funnel     # public over HTTPS
```

Then set the resulting URL in `.env` so pairing + push links match:
```
PUBLIC_BASE_URL=https://apex.example.com
```

---

## 4. Proactive notifications anywhere (Web Push)

So Guardian alerts, Time Capsule callbacks, and briefings reach you even when
Apex isn't open:

1. Generate VAPID keys once:
   ```bash
   python scripts/gen_vapid_keys.py >> .env     # then edit VAPID_SUBJECT
   ```
2. Restart Apex. In the dashboard: **Telemetry → Notifications → Enable
   notifications** (do this on each device you want pushes on). **Send test**
   confirms it.

Routing: urgent alerts (Guardian, safety) fan out to **every** device; ordinary
nudges go to the device you're **actively using**. If no device has subscribed
yet, Apex falls back to **Telegram** (if configured) so you're never unreachable.

---

## 5. Browser extension

Apex in every tab. See `extension/README.md`:

1. `chrome://extensions` → Developer mode → **Load unpacked** → select
   `extension/`.
2. Settings → paste the pairing link (or URL + token).
3. **Ctrl/Cmd+Shift+A** opens the side panel; ask about the page, or push it into
   Apex's awareness with **＋ awareness**.

---

## Security model

- **One shared secret:** `DASHBOARD_TOKEN` (bearer). HTTPS via the tunnel protects
  it in transit. Repeated bad tokens from one IP get rate-limited (429).
- **Web Push payloads** carry only a title/body — never secrets.
- **Secrets stay in `.env`** (git-ignored): `DASHBOARD_TOKEN`, `VAPID_PRIVATE_KEY`,
  and any channel tokens. Never commit them.
- **Fail closed:** no public bind without a token.
- *Future hardening:* per-device signed tokens (so one device can be revoked
  without rotating the shared token).
