"""Nightly closed-loop learning.

`consolidate(client, hours=24)` reviews the last N hours of activity:
  - session summaries
  - awareness events
  - sub-agent outputs
  - completed scheduled tasks
  - goal progress
  - existing memories (for staleness checks)

Then asks Claude to extract durable patterns and writes them to the `reflections`
table. High-confidence reflections (≥0.85) auto-apply: new memories saved,
stale ones forgotten, implicit goal progress recorded, entities inserted into
the knowledge graph. Lower-confidence go to the dashboard for approval.
"""
import json
import time
from typing import Callable, Optional

import config
from agent import longterm, goals, entities, telemetry


_awareness_drain: Optional[Callable[[], list[dict]]] = None


def set_awareness_drain(fn: Callable[[], list[dict]]) -> None:
    """Wire the awareness monitor's drain so reflection can pull events."""
    global _awareness_drain
    _awareness_drain = fn


def _gather(hours: int) -> dict:
    cutoff = time.time() - hours * 3600
    with longterm._conn() as c:
        sessions = c.execute(
            "SELECT id, started_at, ended_at, summary FROM sessions WHERE started_at >= ?",
            (cutoff,),
        ).fetchall()
        memories = c.execute(
            "SELECT id, ts, kind, content, importance FROM memories ORDER BY importance DESC, ts DESC LIMIT 50"
        ).fetchall()
        goal_rows = c.execute(
            "SELECT id, title, status, horizon FROM goals WHERE status IN ('active','done','paused')"
        ).fetchall()
        progress = c.execute(
            "SELECT g.title, gp.ts, gp.note FROM goal_progress gp JOIN goals g ON g.id = gp.goal_id "
            "WHERE gp.ts >= ? ORDER BY gp.ts",
            (cutoff,),
        ).fetchall()
        tasks = c.execute(
            "SELECT description, last_run, run_count FROM scheduled_tasks WHERE last_run >= ?",
            (cutoff,),
        ).fetchall()
        ent_rows = c.execute(
            "SELECT name, kind FROM entities ORDER BY importance DESC, last_seen DESC LIMIT 30"
        ).fetchall()

    awareness_events = []
    if _awareness_drain:
        try:
            awareness_events = _awareness_drain()
        except Exception:
            pass

    return {
        "sessions": [{"id": s[0], "started_at": s[1], "ended_at": s[2], "summary": s[3]} for s in sessions],
        "memories": [{"id": m[0], "kind": m[2], "content": m[3], "importance": m[4]} for m in memories],
        "goals": [{"id": g[0], "title": g[1], "status": g[2], "horizon": g[3]} for g in goal_rows],
        "progress": [{"goal_title": p[0], "ts": p[1], "note": p[2]} for p in progress],
        "tasks": [{"description": t[0], "last_run": t[1], "run_count": t[2]} for t in tasks],
        "entities": [{"name": e[0], "kind": e[1]} for e in ent_rows],
        "awareness_events": awareness_events[-200:],  # cap
    }


def _build_digest(data: dict) -> str:
    lines = []

    if data["sessions"]:
        lines.append(f"## Sessions ({len(data['sessions'])})")
        for s in data["sessions"][-10:]:
            if s["summary"]:
                lines.append(f"  - {s['summary'][:250]}")

    if data["memories"]:
        lines.append("\n## Existing top memories (assess for staleness)")
        for m in data["memories"][:30]:
            lines.append(f"  - #{m['id']} [{m['kind']} imp={m['importance']}] {m['content'][:160]}")

    if data["goals"]:
        lines.append("\n## Goals")
        for g in data["goals"]:
            lines.append(f"  - #{g['id']} [{g['horizon']}/{g['status']}] {g['title']}")

    if data["progress"]:
        lines.append("\n## Goal progress in window")
        for p in data["progress"]:
            lines.append(f"  - ({p['goal_title']}) {p['note'][:160]}")

    if data["tasks"]:
        lines.append("\n## Scheduled tasks fired")
        for t in data["tasks"]:
            lines.append(f"  - {t['description'][:120]} (x{t['run_count']})")

    if data["entities"]:
        lines.append("\n## Known entities")
        for e in data["entities"]:
            lines.append(f"  - {e['name']} ({e['kind']})")

    if data["awareness_events"]:
        lines.append(f"\n## Awareness events ({len(data['awareness_events'])} drained)")
        for e in data["awareness_events"][-50:]:
            lines.append(f"  - [{e.get('source','?')}] {str(e.get('content',''))[:160]}")

    return "\n".join(lines) if lines else "(no recent activity)"


_PROMPT = """You are reviewing your own recent work as the user's AI agent.
Your job: extract durable patterns from the past period and propose changes to your own memory + behavior.

Below is a digest of activity. For each insight, output a JSON object with these fields:
  - kind: one of "pattern" | "insight" | "correction" | "stale_memory_flag" | "entity_extract" | "goal_progress"
  - content: short human-readable description
  - confidence: 0.0-1.0 (how sure you are this is durable / actionable)
  - action: a structured action to apply if accepted. Schema by kind:
      pattern/insight: {"type": "remember", "content": str, "kind": "fact|preference|project|decision|note", "importance": 1-10}
      correction: {"type": "remember", "content": str, "kind": "...", "importance": ..., "supersedes_id": int}
      stale_memory_flag: {"type": "forget", "memory_id": int}
      entity_extract: {"type": "entity", "name": str, "kind": "person|project|place|concept|tool|file|event|org", "properties": {...}}
                       OR {"type": "relate", "from": str, "from_kind": "...", "to": str, "to_kind": "...", "kind": "verb-phrase"}
      goal_progress: {"type": "goal_progress", "goal_id": int, "note": str, "score": 1-10}

Output ONLY a JSON array. No prose. Example:
[
  {"kind": "pattern", "content": "User prefers concise responses under 100 words", "confidence": 0.9,
   "action": {"type": "remember", "content": "Prefers responses under 100 words.", "kind": "preference", "importance": 8}},
  {"kind": "entity_extract", "content": "Sam is Alex's co-founder", "confidence": 0.95,
   "action": {"type": "relate", "from": "Alex", "from_kind": "person", "to": "Sam", "to_kind": "person", "kind": "co-founder"}}
]

Be conservative — only flag patterns supported by the evidence. If nothing meaningful, return [].

DIGEST:
"""


def consolidate(client, hours: int = 24, autosave: bool = True) -> dict:
    """Run a consolidation pass. Returns counts of created/auto-applied reflections."""
    data = _gather(hours)
    digest = _build_digest(data)

    try:
        resp = telemetry.create(
            client,
            call_site="agent.reflection/consolidate",
            model=config.AGENT_MODEL,
            max_tokens=4000,
            thinking={"type": "enabled", "budget_tokens": config.THINKING_BUDGET},
            messages=[{"role": "user", "content": _PROMPT + digest}],
        )
    except Exception as e:
        return {"error": f"Claude call failed: {e}", "created": 0, "applied": 0}

    text = ""
    for b in resp.content:
        if getattr(b, "type", "") == "text":
            text += b.text
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end <= start:
        return {"error": "no JSON array in response", "raw": text[:400], "created": 0, "applied": 0}
    try:
        arr = json.loads(text[start:end])
    except Exception as e:
        return {"error": f"JSON parse failed: {e}", "raw": text[start:end][:400], "created": 0, "applied": 0}

    session_ids = ",".join(str(s["id"]) for s in data["sessions"])
    created = 0
    now = time.time()
    pending_actions: list[dict] = []

    # Insert all reflection rows in one transaction, collect actions to apply after.
    # Applying actions inside the same write transaction causes "database is locked"
    # because _apply_action() opens its own connection.
    with longterm._conn() as c:
        for item in arr:
            kind = (item.get("kind") or "insight").strip()
            content = (item.get("content") or "").strip()
            confidence = float(item.get("confidence") or 0.5)
            action = item.get("action") or {}
            should_apply = autosave and confidence >= config.REFLECTION_AUTO_APPLY_THRESHOLD
            status = "applied" if should_apply else "pending"
            c.execute(
                """INSERT INTO reflections (ts, kind, content, source_session_ids, confidence, status, action_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (now, kind, content, session_ids, confidence, status, json.dumps(action)),
            )
            created += 1
            if should_apply:
                pending_actions.append(action)

    # Apply actions after the write transaction has been committed and closed.
    applied = 0
    for action in pending_actions:
        try:
            _apply_action(action)
            applied += 1
        except Exception as e:
            print(f"[Reflection] auto-apply failed: {e}")

    # Self-improving skills: rewrite any skill that has been failing repeatedly.
    skills_refined = 0
    try:
        skills_refined = refine_skills(client, hours=hours).get("refined", 0)
    except Exception as e:
        print(f"[Reflection] skill refinement failed: {e}")

    # Auto-rollback: check whether any recent skill rewrite hurt approval rate.
    rollback_summary = {}
    try:
        from agent import rollback as rollback_mod
        rollback_summary = rollback_mod.check_rewrites()
    except Exception as e:
        print(f"[Reflection] rollback check failed: {e}")

    return {
        "created": created, "applied": applied, "pending": created - applied,
        "skills_refined": skills_refined,
        "rollback": rollback_summary,
    }


_SKILL_REFINE_PROMPT = """One of your installed skills has been failing repeatedly. \
Rewrite its `run` function to fix the errors below.

SKILL: {name}

CURRENT SOURCE:
{source}

RECENT ERRORS ({count} failures):
{errors}

Output ONLY a JSON object:
  {{"code": "def run(inputs: dict) -> str:\\n    ..."}}
The code must define `def run(inputs: dict) -> str`, keep the same input contract, \
and use only the Python standard library. If you cannot determine a safe fix, \
output {{"code": ""}}."""


def refine_skills(client, hours: int = 24) -> dict:
    """Rewrite skills that failed repeatedly in the window. Returns counts."""
    from agent import skills as skills_mod

    candidates = skills_mod.failure_stats(hours=hours, min_failures=3)
    refined = 0
    for cand in candidates:
        name = cand["name"]
        source = skills_mod.read_source(name)
        if not source:
            continue
        prompt = _SKILL_REFINE_PROMPT.format(
            name=name,
            source=source[:6000],
            count=cand["failures"],
            errors="\n".join(f"  - {e}" for e in cand["errors"]) or "  (no error text captured)",
        )
        try:
            resp = telemetry.create(
                client,
                call_site="agent.reflection/refine_skill",
                model=config.AGENT_MODEL,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            print(f"[Reflection] skill refine call failed for {name!r}: {e}")
            continue
        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
        s, e = text.find("{"), text.rfind("}") + 1
        if s < 0 or e <= s:
            continue
        try:
            new_code = json.loads(text[s:e]).get("code", "")
        except Exception:
            continue
        if not new_code.strip():
            continue
        result = skills_mod.create_skill(name, skills_mod.get_description(name), new_code, _trigger="reflection")
        print(f"[Reflection] refined skill {name!r}: {result}")
        if "created and loaded" in result:
            refined += 1
    return {"candidates": len(candidates), "refined": refined}


def _apply_action(action: dict) -> None:
    t = (action.get("type") or "").lower()
    if t == "remember":
        longterm.remember(
            action["content"],
            kind=action.get("kind", "note"),
            importance=int(action.get("importance", 5)),
        )
        supers = action.get("supersedes_id")
        if supers:
            try:
                longterm.forget(int(supers))
            except Exception:
                pass
    elif t == "forget":
        longterm.forget(int(action["memory_id"]))
    elif t == "entity":
        entities.upsert_entity(
            action["name"], kind=action.get("kind", "concept"),
            properties=action.get("properties") or {},
        )
    elif t == "relate":
        entities.relate(
            action["from"], action["to"], action.get("kind", "related_to"),
            from_kind=action.get("from_kind", "concept"),
            to_kind=action.get("to_kind", "concept"),
        )
    elif t == "goal_progress":
        goals.update_goal(
            int(action["goal_id"]),
            progress_note=action.get("note", ""),
            score=action.get("score"),
        )


def list_reflections(status: str = "pending", limit: int = 50) -> list[dict]:
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, ts, kind, content, source_session_ids, confidence, status, action_json "
            "FROM reflections WHERE status = ? ORDER BY ts DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    out = []
    for r in rows:
        try:
            action = json.loads(r[7] or "{}")
        except Exception:
            action = {}
        out.append({
            "id": r[0], "ts": r[1], "kind": r[2], "content": r[3],
            "source_session_ids": r[4], "confidence": r[5], "status": r[6],
            "action": action,
        })
    return out


def apply_reflection(reflection_id: int, accept: bool = True) -> str:
    with longterm._conn() as c:
        row = c.execute(
            "SELECT status, action_json FROM reflections WHERE id = ?",
            (reflection_id,),
        ).fetchone()
    if row is None:
        return f"No reflection #{reflection_id}."
    if row[0] != "pending":
        return f"Reflection #{reflection_id} already {row[0]}."

    if not accept:
        with longterm._conn() as c:
            c.execute("UPDATE reflections SET status = 'rejected' WHERE id = ?", (reflection_id,))
        return f"Rejected reflection #{reflection_id}."

    try:
        action = json.loads(row[1] or "{}")
    except Exception:
        action = {}
    try:
        _apply_action(action)
    except Exception as e:
        return f"Apply failed: {e}"
    with longterm._conn() as c:
        c.execute("UPDATE reflections SET status = 'applied' WHERE id = ?", (reflection_id,))
    return f"Applied reflection #{reflection_id}."
