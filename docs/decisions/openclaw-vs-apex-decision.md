# OpenClaw × Apex — Decision Report (v2, autonomy-weighted, evidence-based)

_Analysis date: 2026-06-26 · Subject: openclaw/openclaw vs Apex · Lens: "Apex must work without the user being there"_

> **This is a full rewrite of v1.** v1 was written from architectural assumptions and got three verdicts wrong. v2 is grounded in a code-level audit of Apex's actual autonomous infrastructure (4 parallel auditor agents + direct file verification). Where v1 said "PORT daemon mode" and "PORT off-device execution," the audit proved **Apex already ships both** — and surfaced three real latent bugs that matter far more than any OpenClaw feature.

---

## Executive Summary

**Verdict: PORT exactly ONE OpenClaw capability (sandboxed execution). Build two more later. Everything else autonomy-related, Apex already has — but three bugs are quietly breaking it.**

The "works without you there" lens does not point at OpenClaw. It points back at Apex's own code. Apex already has a $0 always-on deployment that is *better* than OpenClaw's laptop daemon: an Oracle Cloud free-tier VM running `main.py --text` under systemd with `Restart=always`, reachable from your phone with the laptop off. The honest finding is not "Apex is missing autonomy" — it's "**Apex's autonomy is built but partially disconnected, and the gaps are bugs, not missing features.**"

| What v1 claimed | What the audit proved |
|---|---|
| PORT daemon mode (score 9.0) | **Already shipped** — `scripts/apex.service`, `Restart=always`, `systemctl enable`, boot-start, headless |
| PORT off-device execution (8.0) | **Already shipped** — Oracle Cloud free VM + Tailscale + Cloudflare tunnel + hybrid mode (`docs/OMNIPRESENCE.md`, `scripts/setup-oracle-cloud.md`) |
| (not assessed) session handoff | **Already shipped** — omnipresence model: one SQLite brain, every device a window into it |
| PORT sandboxed execution (9.25) | **Confirmed — still the one true port (8.40)** |

---

## 1. What "works without you there" actually requires — and where Apex stands

| Requirement | Apex status | Evidence |
|---|---|---|
| Runs when laptop is closed/off | ✅ Oracle Cloud free VM (Ampere A1, 2 OCPU/12GB, free forever) | `scripts/setup-oracle-cloud.md`, `scripts/bootstrap-oracle.sh` |
| Starts on boot, no GUI login | ✅ systemd `WantedBy=multi-user.target` + `systemctl enable` | `scripts/apex.service:20`, `bootstrap-oracle.sh:132` |
| Auto-restarts on crash | ✅ systemd `Restart=always` / `RestartSec=10` | `scripts/apex.service:12-13` |
| Autonomous decision loop runs unattended | ⚠️ **Only on cloud (`--text`), NOT on laptop (`--resident`)** | `main.py:239-310,384` vs `app/resident.py` (no cortex) |
| Reachable from phone while away | ✅ Tailscale (private) + Cloudflare tunnel (public) | `docs/OMNIPRESENCE.md §3` |
| Proactive outreach when away | ✅ Web Push (VAPID) → all devices; Telegram fallback | `agent/notify.py:140-205` |
| Same context across devices | ✅ Omnipresence: one server brain = one SQLite DB | `docs/OMNIPRESENCE.md` |
| Scheduled tasks survive restart | ⚠️ **Schedule definition survives; missed fires are lost** | `agent/scheduler.py` (in-memory jobstore) |
| Unattended actions are safe | ❌ **No sandbox; cortex auto-runs `run_python` on host** | `agent/cortex.py:131-138` |
| Staged risky actions can be approved+run | ❌ **Approval path can't execute `bash`/`write_file`/`send_email`** | `agent/cortex.py:117-142` |

Seven of ten are solved. The three that aren't are **bugs in existing code**, plus one genuine missing capability (sandbox) that OpenClaw teaches.

---

## 2. The three bugs the audit found (higher priority than any port)

### BUG 1 — The autonomous cortex doesn't run in `--resident`/laptop-autostart mode

The cortex OODA loop (`agent/cortex.py:tick`) has exactly **one caller**: `AwarenessMonitor._review_loop` (`awareness.py:341`). That monitor is built and started **only** in the `main.py` flow (`main.py:239-310`, `monitor.start()` at `:384`). `app/resident.py` — the target of laptop login-autostart (`app/autostart.py` execs `main.py --resident`) — never imports `AwarenessMonitor`, never sets `monitor.cortex`, and explicitly passes `awareness_log=None` to the dashboard (`resident.py:193`).

**Consequence:** if you rely on laptop autostart, you get the scheduler, channels, and dashboard — but the autonomous cortex, world-model rebuild, Guardian Angel, and Time Capsule **never tick**. The cloud VM (which runs `--text`) is fine; the laptop resident path is silently half-awake.

**Fix (~20 lines):** have `resident.py` build and start an `AwarenessMonitor` with `cortex` + `world_model_client` wired, exactly as `main.py:267-310` does — or unify the two entry points so there is one startup path.

### BUG 2 — APScheduler uses an in-memory jobstore; missed fires are lost forever

`agent/scheduler.py` creates a `BackgroundScheduler` with the default `MemoryJobStore` — no `SQLAlchemyJobStore`, no `misfire_grace_time`, no `coalesce`. The `scheduled_tasks` SQLite table is only the agent's own re-registration list, replayed at boot by `_restore_tasks()`. So "survives restart" means *the schedule definition* survives — **not** that a run due during downtime is caught up. A `date` task whose time passed while the VM rebooted is gone; cron/interval silently resume at the next future occurrence.

**Fix:** add a `SQLAlchemyJobStore` pointing at the longterm DB and set `misfire_grace_time` + `coalesce=True` so downtime-missed fires execute on restart. This is the difference between "scheduled" and "reliably scheduled" for an always-on agent.

### BUG 3 — The approval path can't execute the dangerous tools it stages

`cortex.approve_action` re-runs `_execute_tool`, which only implements the read-only `always` tools (`cortex.py:117-142`). For a staged `confirm`-tier tool — `write_file`, `bash`, `send_email`, `sms_send` — there is no executor branch, so approving it returns `"[cortex] no executor for ..."` **and does nothing.** Apex correctly stages dangerous autonomous actions and pushes you a notification — but if you tap "approve," nothing happens.

**Fix:** route `approve_action` through the real tool dispatcher (`agent/core._execute_tool` / `agent/approvals._apply`) instead of cortex's read-only stub, so an approved action actually runs.

---

## 3. Weighted decision matrix (autonomy-weighted)

**Weights:** Net-new 30% · Fit 25% · Low effort 15% · Low risk 15% · Low redundancy 15% · Integrate threshold ≥ 7.0
Scores below are from the audit-grounded scoring agents (9 of 16 completed before a session rate limit; the rest scored by direct judgment, marked †). OpenClaw is TypeScript, so every "port" is a Python reimplementation — effort is penalized accordingly.

| Capability | Net | Fit | Eff | Risk | Red | **Score** | Verdict |
|---|---|---|---|---|---|---|---|
| **Sandboxed execution (Docker/SSH backend)** | 9 | 9 | 5 | 8 | 10 | **8.40** | **PORT NOW** |
| Onboarding wizard (`ni onboard`, incl. cloud setup) † | 8 | 9 | 8 | 10 | 9 | **8.40** | **PORT NOW** |
| Per-session sandbox/trust policy for inbound channels | 8 | 9 | 5 | 7 | 8 | **7.65** | **BUILD SOON** |
| iMessage channel adapter (BlueBubbles) | 7 | 7 | 8 | 9 | 5 | **7.15** | **BUILD SOON** |
| Live Canvas † | 8 | 6 | 3 | 7 | 10 | **6.55** | DEFER |
| Per-channel personas | 4 | 6 | 8 | 9 | 5 | **6.00** | DEFER |
| Multi-agent routing (per-channel isolated agents) † | 5 | 5 | 4 | 6 | 5 | **5.45** | DEFER |
| Event triggers (webhooks / Gmail Pub/Sub) | 4 | 7 | 6 | 6 | 4 | **5.35** | DEFER |
| Group/federated channels (Matrix/IRC/Mattermost/Teams) | 5 | 5 | 5 | 7 | 4 | **5.15** | DEFER |
| Daemon mode / install-as-service | 3 | 7 | 7 | 8 | 4 | **5.50** | **SKIP — already have it** |
| Off-device / cloud execution | 2 | 9 | 3 | 7 | 2 | **4.65** | **SKIP — already have it** |
| Session handoff across devices † | 2 | 7 | 5 | 7 | 2 | **4.55** | **SKIP — omnipresence covers it** |
| `sessions_spawn` parallel session control | 3 | 5 | 5 | 6 | 3 | **4.25** | SKIP (orchestrator ~85% covers) |
| Native macOS/iOS/Android apps † | 7 | 6 | 2 | 6 | 8 | **5.80** | SKIP — PWA covers 85% |
| Extra niche channels (Nostr/Twitch/WeChat/QQ/Zalo…) † | 4 | 4 | 5 | 7 | 7 | **5.05** | SKIP |
| Plugin SDK (npm-style) † | 6 | 5 | 2 | 5 | 8 | **5.25** | SKIP — skill_forge is the better model |

† = scored by direct judgment (scoring agent hit the rate limit); all others are audit-grounded agent scores.

---

## 4. The honest takeaways

1. **OpenClaw's autonomy story is already Apex's autonomy story — and Apex's is arguably better.** A free Oracle Ampere VM under systemd beats a launchd agent on a sleeping MacBook. v1's "PORT daemon mode / off-device" was wrong; those shipped weeks ago.

2. **The one real OpenClaw lesson is sandboxing.** On an always-on, internet-exposed VM where the cortex auto-runs `run_python` and any inbound channel message can drive host execution, "no sandbox" is the single biggest liability. Port a `Backend` abstraction (`LocalBackend` default, `DockerBackend` opt-in) behind `tools/bash.py`, `cortex._execute_tool`, and `skill_forge`. This is the only score ≥ 8 that Apex doesn't already cover. **Do it first.**

3. **The per-session trust policy is the natural follow-on.** OpenClaw's "main session = host, non-main = sandboxed with allow/deny lists" is the right model for letting Apex safely talk to group channels unattended. Build it once the Docker backend exists.

4. **iMessage is the one channel worth the TypeScript→Python rewrite** (BlueBubbles bridge), because it's where Apple users actually live. Everything else channel-wise is reach without autonomy payoff.

5. **Fix the three bugs before porting anything.** A disconnected cortex (laptop mode), a lossy scheduler, and a non-functional approval path each silently undercut "works without you there." They are cheap to fix and worth more than any new feature.

---

## 5. Recommended order of work

1. **Fix BUG 1** — wire cortex/awareness into `resident.py` (or unify entry points). ~½ day.
2. **Fix BUG 2** — `SQLAlchemyJobStore` + `misfire_grace_time` + `coalesce`. ~½ day.
3. **Fix BUG 3** — route `approve_action` through the real dispatcher. ~½ day.
4. **PORT: sandboxed execution** — `Backend` interface + `DockerBackend`, gated by `EXECUTION_BACKEND`. ~2–3 days.
5. **PORT: onboarding wizard** — `ni onboard` writing `.env` + offering the Oracle/Tailscale path. ~1 day.
6. **BUILD SOON:** per-session sandbox/trust policy; iMessage adapter.
7. **DEFER / SKIP:** everything else per the matrix.

---

_Decision: PORT sandboxed execution + onboarding wizard. BUILD per-session trust policy + iMessage. SKIP all daemon/off-device/handoff items (already shipped). FIX three latent autonomy bugs first — they matter more than any port._
