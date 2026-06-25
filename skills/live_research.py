"""Skill: live_research — streaming multi-phase research orchestrator.

Phases: search → visit top sources → synthesise → save Markdown report.
Progress events are broadcast to the Apex dashboard live feed via WebSocket
so the user sees a live panel update while research runs.

Trusted, hand-written skill.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

DESCRIPTION = (
    "Research a topic thoroughly: searches the web, reads top sources, and writes "
    "a structured Markdown report saved to ~/Documents/Apex/Research/. "
    "Pass {query, depth} where depth is 'quick' (3 sources), 'standard' (6), or 'deep' (10)."
)
VERSION = "1.0"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Research topic or question.",
        },
        "depth": {
            "type": "string",
            "enum": ["quick", "standard", "deep"],
            "description": "quick=3 sources, standard=6, deep=10.",
            "default": "standard",
        },
    },
    "required": ["query"],
}

_DEPTH_SOURCES = {"quick": 3, "standard": 6, "deep": 10}


def _broadcast(phase: str, detail: str) -> None:
    try:
        from dashboard import server as _srv
        _srv.ws_manager.broadcast_threadsafe({
            "type": "research_phase", "phase": phase, "detail": detail, "ts": time.time(),
        })
    except Exception:
        pass


def _research_dir() -> Path:
    d = Path.home() / "Documents" / "Apex" / "Research"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(query: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", query.lower().strip())[:60].strip("-") or "research"


def run(inputs: dict) -> str:
    query = (inputs.get("query") or "").strip()
    if not query:
        return "live_research: 'query' is required."
    depth = inputs.get("depth", "standard")
    n = _DEPTH_SOURCES.get(depth, 6)

    _broadcast("search", f"Searching: {query}")
    try:
        from tools import research as _res
        results = _res.search(query, num_results=n)
    except Exception as e:
        return f"live_research: search failed: {e}"

    if not results:
        return f"live_research: no results found for '{query}'."

    _broadcast("reading", f"Reading {len(results)} sources…")
    source_texts: list[str] = []
    for r in results[:n]:
        url = r.get("url") or r.get("href") or ""
        if not url:
            continue
        try:
            content = _res.browse(url)
            source_texts.append(f"**Source**: {url}\n\n{content[:3000]}\n\n---\n")
            _broadcast("reading", f"Read: {url[:70]}")
        except Exception:
            continue

    if not source_texts:
        return f"live_research: could not fetch any sources for '{query}'."

    combined = "\n".join(source_texts)
    _broadcast("writing", "Synthesising report…")

    try:
        import config
        import anthropic
        from agent import telemetry
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = telemetry.create(
            client,
            call_site="skills.live_research/synthesise",
            model=config.AGENT_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": (
                f"You are a research analyst. Based on the following web sources, write a thorough "
                f"Markdown report answering: **{query}**\n\n"
                f"Structure: ## Summary, ## Key Findings (bulleted), ## Sources, ## Conclusion\n\n"
                f"Sources:\n{combined[:14000]}"
            )}],
        )
        report = resp.content[0].text.strip()
    except Exception as e:
        return f"live_research: synthesis failed: {e}"

    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = _research_dir() / f"{ts}-{_slug(query)}.md"
    try:
        out_path.write_text(f"# Research: {query}\n_Generated {ts}_\n\n{report}", encoding="utf-8")
    except Exception as e:
        return f"live_research: report save failed: {e}\n\n{report[:600]}"

    _broadcast("done", f"Report saved: {out_path.name}")
    return f"Research complete. Report saved to {out_path}.\n\n{report[:1000]}…"
