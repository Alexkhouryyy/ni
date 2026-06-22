"""
JARVIS Memory Distiller — turn conversations into compounding knowledge.

A background loop that periodically reads recent conversation turns, asks an
LLM to extract stable facts/preferences/decisions, and stores them in the
SQLite memories table. Also maintains a human-readable digest at
`~/.jarvis/me.md` that the user can open, read, and edit.

Cost shape: zero user-facing latency. Runs every ~10 min in the background.
One Haiku call per tick (~$0.001) or $0 if routed to Ollama.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import memory
import llm_router

log = logging.getLogger("jarvis.memory_distiller")

# How often to run a distillation pass (seconds)
DEFAULT_INTERVAL = 600

# Minimum number of new turns before we bother distilling
MIN_NEW_TURNS = 4

# Where the human-readable digest lives
ME_MD_PATH = Path.home() / ".jarvis" / "me.md"
ME_MD_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Distillation
# ---------------------------------------------------------------------------

_DISTILL_SYSTEM = (
    "You are JARVIS's memory subsystem. Read recent conversation turns and "
    "extract STABLE facts about the user — preferences, projects, decisions, "
    "relationships, ongoing commitments. Skip transient chitchat (e.g. 'user "
    "is hungry right now').\n\n"
    "Return STRICT JSON: {\"memories\": [{\"type\": ..., \"content\": ..., "
    "\"importance\": ...}, ...]}\n\n"
    "Rules:\n"
    "- type must be one of: fact | preference | project | person | decision | commitment\n"
    "- content: short third-person statement, max 140 chars\n"
    "- importance: 1-10 (10 = identity-level / unforgettable)\n"
    "- Skip anything already in EXISTING MEMORIES (passed below)\n"
    "- Skip anything that will be untrue in a week\n"
    "- One fact per memory; no compound statements\n"
    "- If nothing worth remembering, return {\"memories\": []}"
)


def _format_history(turns: list[dict]) -> str:
    """Render a slice of conversation history for the distiller LLM."""
    lines = []
    for t in turns[-40:]:  # cap at last 40 turns to keep prompt small
        role = t.get("role", "?")
        content = (t.get("content") or "")
        if isinstance(content, list):  # multimodal content
            content = " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
        content = str(content).strip().replace("\n", " ")
        if content:
            lines.append(f"{role.upper()}: {content[:400]}")
    return "\n".join(lines)


def _format_existing(memories: list[dict], limit: int = 30) -> str:
    if not memories:
        return "(none yet)"
    lines = []
    for m in memories[:limit]:
        lines.append(f"- [{m.get('type','fact')}] {m.get('content','')[:140]}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """Best-effort: pull the first JSON object out of an LLM response."""
    if not text:
        return {}
    # Try the whole thing first
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Fall back to first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


async def distill_turns(turns: list[dict], anthropic_client) -> list[dict]:
    """Run one distillation pass. Returns list of {type, content, importance} dicts."""
    if not turns:
        return []

    # Show the distiller what's already known so it can dedupe
    existing = memory.get_recent_memories(limit=30) if hasattr(memory, "get_recent_memories") else []
    user_prompt = (
        f"EXISTING MEMORIES:\n{_format_existing(existing)}\n\n"
        f"RECENT CONVERSATION TURNS:\n{_format_history(turns)}\n\n"
        "Extract new stable facts (JSON):"
    )

    try:
        raw = await llm_router.chat(
            llm_router.model_fast(),
            [{"role": "user", "content": user_prompt}],
            system=_DISTILL_SYSTEM,
            max_tokens=800,
            anthropic_client=anthropic_client,
            feature="memory_distill",
        )
    except Exception as e:
        log.warning(f"distillation LLM call failed: {e}")
        return []

    data = _extract_json(raw)
    mems = data.get("memories", []) if isinstance(data, dict) else []
    valid: list[dict] = []
    seen = set()
    for m in mems:
        if not isinstance(m, dict):
            continue
        content = (m.get("content") or "").strip()
        mem_type = (m.get("type") or "fact").strip().lower()
        importance = m.get("importance", 5)
        if not content or content.lower() in seen:
            continue
        if mem_type not in {"fact", "preference", "project", "person", "decision", "commitment"}:
            mem_type = "fact"
        try:
            importance = max(1, min(10, int(importance)))
        except Exception:
            importance = 5
        seen.add(content.lower())
        valid.append({"type": mem_type, "content": content[:200], "importance": importance})

    return valid


# ---------------------------------------------------------------------------
# me.md — human-readable digest
# ---------------------------------------------------------------------------

ME_MD_SYSTEM = (
    "You are JARVIS curating a personal-model document about the user. "
    "Given a list of structured memories, produce a clean markdown digest "
    "with the sections: Identity & Context, Active Projects, Preferences, "
    "Decisions Made, Open Commitments, Other. Use short bullets. Skip "
    "trivial / contradictory entries. Output ONLY the markdown — no preamble."
)


async def refresh_me_md(anthropic_client) -> None:
    """Regenerate ~/.jarvis/me.md from current memories. Cheap, runs occasionally."""
    try:
        all_mems = memory.get_recent_memories(limit=200)
    except Exception:
        all_mems = []

    if not all_mems:
        # Write an empty stub so users can find it
        ME_MD_PATH.write_text(
            "# About You\n\n*JARVIS hasn't learned anything stable yet. "
            "Have a few conversations and check back.*\n",
            encoding="utf-8",
        )
        return

    listing = "\n".join(
        f"- [{m.get('type','fact')}] {m.get('content','')}" for m in all_mems
    )
    prompt = (
        f"Memories:\n{listing}\n\n"
        "Produce the personal-model markdown digest now."
    )

    try:
        md = await llm_router.chat(
            llm_router.model_fast(),
            [{"role": "user", "content": prompt}],
            system=ME_MD_SYSTEM,
            max_tokens=1200,
            anthropic_client=anthropic_client,
            feature="memory_consolidation",
        )
    except Exception as e:
        log.warning(f"me.md refresh failed: {e}")
        return

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"*Last consolidated: {stamp}*\n\n{md.strip()}\n"
    try:
        ME_MD_PATH.write_text(body, encoding="utf-8")
        log.info(f"me.md refreshed ({len(body)} chars)")
    except Exception as e:
        log.warning(f"failed to write me.md: {e}")


def load_me_md_header(max_chars: int = 600) -> str:
    """Return the first slice of me.md to inject into the system prompt."""
    try:
        if not ME_MD_PATH.exists():
            return ""
        text = ME_MD_PATH.read_text(encoding="utf-8")
        return text[:max_chars].strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def memory_distillation_loop(
    get_history: Callable[[], list[dict]],
    anthropic_client,
) -> None:
    """Run forever. Distill new conversation turns every DEFAULT_INTERVAL seconds."""
    log.info("Memory distillation loop starting")
    last_index = 0
    last_me_md_refresh = 0.0

    while True:
        try:
            interval = int(os.environ.get("MEMORY_DISTILL_INTERVAL", str(DEFAULT_INTERVAL)))
            await asyncio.sleep(interval)

            if os.environ.get("MEMORY_DISTILL_ENABLED", "true").lower() not in ("true", "1", "yes"):
                continue

            history = get_history() or []
            if last_index > len(history):
                # Session reset / new WebSocket — reset our index too
                last_index = 0
            new_turns = history[last_index:]

            if len(new_turns) < MIN_NEW_TURNS:
                continue

            log.info(f"Distilling {len(new_turns)} new turns")
            extracted = await distill_turns(new_turns, anthropic_client)
            for m in extracted:
                try:
                    memory.remember(
                        content=m["content"],
                        mem_type=m["type"],
                        source=f"distilled-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                        importance=m["importance"],
                    )
                except Exception as e:
                    log.debug(f"failed to store distilled memory: {e}")

            last_index = len(history)
            log.info(f"Distillation stored {len(extracted)} new memories")

            # Refresh me.md at most once an hour (cheap but not free)
            now = time.time()
            if extracted and (now - last_me_md_refresh > 3600):
                await refresh_me_md(anthropic_client)
                last_me_md_refresh = now

        except asyncio.CancelledError:
            log.info("Memory distillation loop cancelled")
            raise
        except Exception as e:
            log.error(f"distill tick failed: {e}", exc_info=True)
