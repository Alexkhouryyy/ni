# Apex

A voice-and-text AI agent that talks, sees your screen, controls your computer,
researches the web, and runs a persistent memory. It supports multiple model
providers (Anthropic Claude, OpenAI GPT, Google Gemini), a multi-model
**council** that debates a question to the best answer, a web dashboard, and
phone reach via Telegram / Discord / SMS.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys
python main.py --text         # text mode (no mic/speakers needed)
```

`python main.py` alone runs full voice mode. The web dashboard starts
automatically — watch the console for `[Dashboard] http://127.0.0.1:7860`.

### Keys

Only `ANTHROPIC_API_KEY` is required. Add `OPENAI_API_KEY` and/or
`GEMINI_API_KEY` to unlock GPT/Gemini models and the 3-way council. All keys
live in `.env`, which is gitignored — see **Security** below.

### Switching models

- At launch: `python main.py --text --model gpt-4o`
- At runtime: type `/model gemini-2.5-flash` (or `/model` to list options)
- Council debate: type `/council <your question>`

## Remote Access (Tailscale)

Use the dashboard from your phone anywhere — no shared Wi-Fi required.
[Tailscale](https://tailscale.com) is a private WireGuard mesh that links only
your own devices; it is safer than exposing the dashboard to the public
internet.

**1. Install Tailscale** on the host computer and on your phone, and sign both
into the **same account**.

**2. Get the host's Tailscale IP** — on the computer:
```bash
tailscale ip -4        # e.g. 100.x.y.z
```

**3. Configure Apex** — in `.env`:
```
DASHBOARD_HOST=0.0.0.0
DASHBOARD_TOKEN=pick-a-strong-password
```
`DASHBOARD_TOKEN` is your backstop password — always set it when binding to
`0.0.0.0`. Start Apex.

**4. Open it on your phone's browser:**
```
http://100.x.y.z:7860
```

**Nicer — HTTPS with a name instead of an IP.** On the host run:
```bash
tailscale serve 7860
```
Then open `https://<machine-name>.<your-tailnet>.ts.net` (MagicDNS, on by
default). No port, no IP, proper TLS.

> The host computer must stay on and running Apex. Tailscale connects your
> devices — it does not keep Apex alive.

## Security

API keys never belong in the repo. They live only in `.env`, which is
gitignored. `.env.example` (placeholders only) is the template.

### Pre-commit secret guard

A version-controlled hook blocks commits that contain a key or an env file.
Activate it once per clone:

```bash
git config core.hooksPath .githooks
```

It rejects staged `.env` / `*.key` / `*.pem` files and scans added lines for
live key patterns. Bypass a verified false positive with
`git commit --no-verify`. For a heavier industry-standard scanner, install
[`gitleaks`](https://github.com/gitleaks/gitleaks) and run
`gitleaks protect --staged`.

### Before making this repo public

1. Scan all history: `gitleaks detect` (or `trufflehog git file://.`) — expect 0 leaks.
2. Confirm no tracked secrets: `git ls-files | grep -E '\.env$|\.db$'` should be empty.
3. Enable GitHub **Secret Scanning + Push Protection** (Settings → Code security) — free on public repos.
4. **Rotate every API key** and update `.env`. Rotation is the only true fix for any key that was ever pasted, screenshotted, or shared.
5. Verify `.env.example` still holds only placeholders.
