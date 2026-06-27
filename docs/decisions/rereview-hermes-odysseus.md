# Re-review: Hermes & Odysseus — what's actually left to take

_Analysis date: 2026-06-26 · Lens: "works without you there" + dashboard inspiration · Grounded against Apex's current shipped state (incl. the Oracle Cloud always-on path and the new Docker sandbox)._

---

## Part 1 — Hermes, re-examined

The v1 Hermes report flagged serverless persistence (Modal/Daytona) as something it had "buried." Re-examined against what Apex actually ships, **burying it was correct — it's a genuine non-fit, not a miss.** Here is the honest accounting.

### Serverless persistence (Modal/Daytona) — SKIP, and not for the obvious reason

Hermes's pitch: *"your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions."* The headline benefit is **$0 when idle**.

But Apex's always-on path already costs **$0** — the Oracle Cloud Ampere A1 free tier is free forever. So serverless wins nothing on cost. And it actively **loses** on Apex's core design:

- Apex is **proactive**, not purely reactive. The cortex OODA loop ticks every 5 min; reflection runs nightly at 03:00; the scheduler fires daily/weekly jobs. A *hibernating* agent only wakes on an external trigger — so to keep proactivity you'd have to re-architect every always-on loop into discrete platform-cron invocations (Modal scheduled functions). That's a large rewrite to regain a behavior the Oracle VM gives for free.
- Hibernation adds cold-start latency to the first message after idle — the opposite of what a voice-first companion wants.

**Verdict: SKIP.** A free always-on VM beats pay-per-use hibernation for an agent whose whole value is being awake. This is the rare case where the "advanced" feature is worse for our shape.

### Docker execution backend — ✅ SHIPPED today

The one Hermes idea that was genuinely worth taking (scored 7.40 in v1, re-confirmed 8.40 in the OpenClaw v2 audit). Built and committed this session (`f087ddf`): `tools/sandbox.py` with `LocalBackend`/`DockerBackend`, routed through bash, `cortex.run_python`, and forged-skill validation. **Hermes's single highest-value contribution is now done.**

### Everything else Hermes has — already covered or low-value

| Hermes capability | Apex status | Verdict |
|---|---|---|
| Procedural memory / self-improving skills | `skill_forge` + reflection + rollback | Already have (≥ parity) |
| FTS5 session search + LLM summary | `search_turns` + `longterm` semantic recall | Already have (richer) |
| Cron scheduler, unattended jobs | `agent/scheduler.py` | Already have (but see bug #2) |
| Subagent spawning | `agent/orchestrator.py` | Already have |
| MCP integration | `agent/mcp_client.py` | Already have |
| Multi-provider routing (200+ models) | `provider.py` + `router.py` | Already have |
| Honcho dialectic user modeling | `me.md` + longterm memory | Already have (different mechanism) |
| **Natural-language cron** ("daily report at 8am" → schedule) | Scheduler takes structured cron/interval/date only | **Minor win — optional** |
| **agentskills.io / Skills Hub** (portable, shareable skills) | Local skill_forge, no sharing | **DEFER** (same idea as OpenClaw ClawHub; needs a skill corpus first) |
| `/compress`, `/insights`, `/usage` memory commands | Partial (telemetry, no compress) | Minor ergonomics |

**Hermes conclusion: fully harvested.** The Docker backend was the one real port and it shipped. The only remaining nibbles are a natural-language schedule parser (a small ergonomic nicety) and a future skill-sharing standard (deferred, and identical to OpenClaw's ClawHub recommendation — so it's one decision, not two).

---

## Part 2 — Odysseus, re-examined (the dashboard you liked)

Already shipped from Odysseus: **email triage** (`tools/email_box.py`) and **CalDAV calendar** (`tools/calendar_box.py`). The re-review is specifically about the **dashboard/UI**, since that's what you called out.

Odysseus's dashboard is organized as workspace modules: Chat+Agents · Documents · Deep Research · Compare · Model Cookbook · Email · Notes/Tasks/Calendar · Extras (gallery, themes, presets, sessions, 2FA). Mapping each against Apex's dashboard:

| Odysseus module | Apex today | Inspiration verdict |
|---|---|---|
| **Compare — blind side-by-side model testing + synthesis** | Apex has a multi-model **council** + provider routing, but no UI to pit models head-to-head | **★ TOP PICK — BUILD.** Net-new, leverages infra Apex already has, high wow-factor |
| **Documents — writing-first AI editor** (MD/HTML/CSV, inline AI edits + suggestions) | Deferred twice; no editor | **Signature feature — DECIDE.** Biggest frontend, but it's likely *the* thing you admire in Odysseus |
| **Extras → 2FA / per-device sessions** | Single shared `DASHBOARD_TOKEN` | **BUILD SOON.** Apex's own `OMNIPRESENCE.md` already lists "per-device signed tokens" as planned hardening — this aligns exactly |
| **Extras → themes / presets** | Strong fixed identity (3D constellation) | Polish — optional |
| Deep Research | `skills/live_research.py` (streaming, saved MD) | Already have |
| Email / Calendar | Shipped (Odysseus port) | Already have |
| Notes / Tasks | `goals` + Obsidian vault (`~/Documents/Apex`) | Already have (partial) |
| Model Cookbook (hardware-aware local serving) | Cloud-model-first | SKIP — off-axis |
| Gallery / image editor | — | SKIP — off-axis for a voice-first agent |

### The concrete dashboard takeaways, ranked

1. **Compare tab (build).** A blind A/B (or A/B/C) view: ask once, N models answer behind hidden labels, you pick the winner, Apex logs the preference and can synthesize a merged answer. Apex's council + `provider.py` already do the hard part; this is a dashboard surface over existing capability. Highest value-per-effort of anything in either project.
2. **Per-device tokens / 2FA (build soon).** Replaces the single bearer token with revocable per-device credentials — the security upgrade the omnipresence doc already promised. Matters now that Apex runs an internet-exposed always-on VM.
3. **Writing-first Documents editor (decide).** The marquee Odysseus experience and the most likely reason you like its dashboard. It's a real project (rich text + AI inline edits + multi-format), not an afternoon. Worth doing *if* you want Apex to be a writing surface, not just a chat/voice surface — your call.
4. **Themes/presets (polish).** Low priority; Apex's identity is already distinctive.

---

## Combined conclusion

- **Hermes:** harvested. Docker backend shipped; serverless is a correct skip; nothing substantial remains.
- **Odysseus:** the dashboard inspiration is real and concrete — **a Compare tab** (cheap, high-impact) and **per-device 2FA** (security, already planned), with the **writing-first editor** as the one big optional bet.
- **One shared deferred item across Hermes + OpenClaw:** a portable/shareable skill registry (agentskills.io ≈ ClawHub). Treat as a single future decision, not two.

**Recommended next build (if you want to keep going): the Compare tab** — it turns Apex's existing multi-model council into something you can see and steer, and it's the single best idea the dashboard re-review surfaced.
