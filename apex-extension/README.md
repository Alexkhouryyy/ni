# Apex browser extension

Apex, present in every tab. Invoke the side panel with **Ctrl/Cmd+Shift+A**, ask
about the page you're on, and (optionally) push the page into Apex's awareness.

## Install (unpacked)

1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this `apex-extension/` folder.
4. Click the Apex icon → **⚙ settings**, then either:
   - paste the **pairing link** from the dashboard's *Devices → Pair a phone* QR
     (fills the URL + token automatically), or
   - enter your Apex **server URL** (e.g. `http://localhost:7860` or your tunnel
     HTTPS URL) and **dashboard token**.

## Use

- **Ctrl/Cmd+Shift+A** — open the side panel.
- Type a question. With *Use this page as context* on, Apex receives the page
  title, URL, and any selected text alongside your message.
- **＋ awareness** — drop the current page into Apex's live awareness stream
  (`/api/awareness/ingest`), so it shows up in the Live feed and informs
  proactive features.

## Notes

- The extension talks to the same `/api/chat` the dashboard uses; the server's
  CORS layer allows `chrome-extension://` origins. Auth is the bearer token.
- `host_permissions` is broad (`http://*/*`, `https://*/*`) so the panel can read
  the active page's title/selection and reach an Apex server on any host. For a
  locked-down setup, narrow these to your Apex origin.
