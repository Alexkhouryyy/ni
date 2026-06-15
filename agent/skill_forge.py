"""Skill Forge — Apex writes its own tools when it hits a capability gap.

When the agent can't do something, skill_forge.attempt_forge(client, gap) asks
Claude to write a Python tool, validates it in a subprocess sandbox, then either:
  - auto-registers it (read-only tools, trusted allowlist 'always')
  - stages it and pushes a notification for user approval (write/external tools)

Approved tools are registered via agent/self_mod.register_new_tool() and persist
across restarts in ~/.voice_agent_overlay.json.
"""
import json
import subprocess
import sys
import textwrap
import time
from typing import Optional, Callable

import config
from agent import longterm, telemetry

_NOTIFY_FN: Optional[Callable] = None


def set_notify_fn(fn: Callable) -> None:
    global _NOTIFY_FN
    _NOTIFY_FN = fn


def init_db() -> None:
    with longterm._conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS forged_tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                code TEXT NOT NULL,
                test_case TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                approved_at REAL
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_forged_status ON forged_tools(status, created_at DESC)"
        )


def list_forged(status: Optional[str] = None) -> list[dict]:
    try:
        with longterm._conn() as c:
            if status:
                rows = c.execute(
                    "SELECT id, name, description, status, created_at FROM forged_tools "
                    "WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, name, description, status, created_at FROM forged_tools "
                    "ORDER BY created_at DESC"
                ).fetchall()
    except Exception:
        return []
    return [
        {"id": r[0], "name": r[1], "description": r[2], "status": r[3], "created_at": r[4]}
        for r in rows
    ]


def approve_forged(tool_id: int) -> str:
    """Register an approved forged tool via self_mod. Returns status message."""
    try:
        with longterm._conn() as c:
            row = c.execute(
                "SELECT name, description, code FROM forged_tools "
                "WHERE id = ? AND status = 'pending'",
                (tool_id,),
            ).fetchone()
    except Exception as e:
        return f"DB error: {e}"
    if not row:
        return f"Tool #{tool_id} not found or not pending."
    name, description, code = row

    try:
        from agent import self_mod
        result = self_mod.register_new_tool(
            name=name,
            description=description,
            input_schema={"type": "object", "properties": {}, "required": []},
            code=code,
        )
        with longterm._conn() as c:
            c.execute(
                "UPDATE forged_tools SET status = 'approved', approved_at = ? WHERE id = ?",
                (time.time(), tool_id),
            )
        return result
    except Exception as e:
        return f"Registration failed: {e}"


def reject_forged(tool_id: int) -> str:
    with longterm._conn() as c:
        c.execute(
            "UPDATE forged_tools SET status = 'rejected' WHERE id = ?", (tool_id,)
        )
    return f"Tool #{tool_id} rejected."


_FORGE_PROMPT = """\
The user's AI agent needs a new tool to fill this capability gap:

CAPABILITY GAP: {gap}

Write a Python tool function that fills this gap. Requirements:
- Function named `run` with signature `def run(inputs: dict) -> str:`
- Accept a dict of inputs and return a string result
- Use ONLY the Python standard library — no pip installs
- Handle all errors gracefully and return an error string (never raise)
- Be safe to run in a sandboxed subprocess

Also provide:
- tool_name: short snake_case name (e.g. "read_rss_feed", "parse_json_file")
- description: one clear sentence describing what it does
- test_case: a minimal inputs dict that tests the function (it will be run)
- is_read_only: true if the tool only reads/computes (no writes, no network mutations)

Output ONLY valid JSON, no markdown fences:
{{
  "tool_name": "...",
  "description": "...",
  "code": "def run(inputs: dict) -> str:\\n    ...",
  "test_case": {{}},
  "is_read_only": true
}}
"""


def _validate_in_sandbox(code: str, test_inputs: dict) -> tuple[bool, str]:
    """Run the tool's test case in an isolated subprocess. Returns (passed, output)."""
    script = textwrap.dedent(f"""\
        import json, sys
        inputs = {json.dumps(test_inputs)}
        {code}
        try:
            result = run(inputs)
            print(json.dumps({{"ok": True, "result": str(result)[:300]}}))
        except Exception as e:
            print(json.dumps({{"ok": False, "error": str(e)}}))
    """)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        out = proc.stdout.strip()
        if not out:
            return False, (proc.stderr[:200] or "no output")
        data = json.loads(out)
        if data.get("ok"):
            return True, data.get("result", "")
        return False, data.get("error", "unknown error")
    except subprocess.TimeoutExpired:
        return False, "sandbox timed out (10s)"
    except Exception as e:
        return False, str(e)


def attempt_forge(client, gap_description: str) -> Optional[dict]:
    """Ask Claude to write a tool for the gap. Returns the staged tool dict or None."""
    prompt = _FORGE_PROMPT.format(gap=gap_description)
    try:
        resp = telemetry.create(
            client,
            call_site="agent.skill_forge/forge",
            model=config.AGENT_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
    except Exception as e:
        print(f"[SkillForge] Claude call failed: {e}")
        return None

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return None

    try:
        proposal = json.loads(text[start:end])
    except Exception:
        return None

    name = proposal.get("tool_name", "").strip()
    description = proposal.get("description", "").strip()
    code = proposal.get("code", "").strip()
    test_case = proposal.get("test_case", {})
    is_read_only = bool(proposal.get("is_read_only", False))

    if not name or not code or not name.isidentifier():
        return None

    passed, output = _validate_in_sandbox(code, test_case)
    if not passed:
        print(f"[SkillForge] Sandbox failed for '{name}': {output}")
        return None

    now = time.time()
    try:
        with longterm._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO forged_tools "
                "(name, description, code, test_case, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (name, description, code, json.dumps(test_case), now),
            )
            tool_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        print(f"[SkillForge] DB insert failed: {e}")
        return None

    if is_read_only:
        result = approve_forged(tool_id)
        print(f"[SkillForge] Auto-approved '{name}': {result}")
        proposal["auto_approved"] = True
    else:
        if _NOTIFY_FN:
            try:
                _NOTIFY_FN(
                    title="New tool ready to install",
                    body=f"'{name}': {description}",
                    kind="skill_forge",
                    priority="normal",
                    url=f"/?tab=skills",
                )
            except Exception:
                pass
        print(f"[SkillForge] Staged '{name}' for user approval (id={tool_id})")
        proposal["auto_approved"] = False

    proposal["id"] = tool_id
    proposal["sandbox_output"] = output
    return proposal
