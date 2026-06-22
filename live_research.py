"""
JARVIS Live Research — watch JARVIS work in real time.

A research orchestrator that streams every step over WebSocket so the user
can watch JARVIS think, search, read, and write — instead of waiting for a
black-box result.

Event protocol (sent over WebSocket as `{"type": "live_lab", ...}`):

- session_start  { id, topic }                   → opens the Live Lab panel
- step           { id, kind, text }              → adds a line to the activity feed
                   kind ∈ {search, read, note, plan, write, render}
- doc_chunk      { id, text }                    → appends text to the live document
- doc_replace    { id, text }                    → replaces the entire document (e.g. on outline approval)
- session_end    { id, success, path? }          → closes the panel, optionally points to saved file
- session_error  { id, error }                   → shows error in the panel
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import anthropic

from browser import JarvisBrowser
import llm_router

log = logging.getLogger("jarvis.live_research")

# Where finished papers are saved
PAPERS_DIR = Path.home() / "jarvis-papers"
PAPERS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Event emitter — wraps WebSocket sends so the orchestrator stays simple
# ---------------------------------------------------------------------------

class LiveLabEmitter:
    """Single sink for live_lab events; serializes to JSON over WebSocket."""

    def __init__(self, ws, session_id: str):
        self.ws = ws
        self.id = session_id

    async def _send(self, **payload) -> None:
        if self.ws is None:
            return
        try:
            await self.ws.send_json({"type": "live_lab", "id": self.id, **payload})
        except Exception as e:
            log.debug(f"live_lab send failed (ws probably closed): {e}")

    async def session_start(self, topic: str) -> None:
        await self._send(event="session_start", topic=topic)

    async def step(self, kind: str, text: str) -> None:
        log.info(f"[live] {kind}: {text[:100]}")
        await self._send(event="step", kind=kind, text=text)

    async def doc_chunk(self, text: str) -> None:
        await self._send(event="doc_chunk", text=text)

    async def doc_replace(self, text: str) -> None:
        await self._send(event="doc_replace", text=text)

    async def session_end(self, success: bool, path: Optional[str] = None) -> None:
        await self._send(event="session_end", success=success, path=path)

    async def session_error(self, error: str) -> None:
        await self._send(event="session_error", error=error)


# ---------------------------------------------------------------------------
# The research orchestrator
# ---------------------------------------------------------------------------

class LiveResearcher:
    """Multi-phase live research: gather → outline → write → save."""

    def __init__(self, anthropic_client: anthropic.AsyncAnthropic, ws):
        self.client = anthropic_client
        self.ws = ws
        self.session_id = str(uuid.uuid4())[:8]
        self.emit = LiveLabEmitter(ws, self.session_id)
        self.browser = JarvisBrowser()

    async def run(self, topic: str) -> str:
        """Top-level entry. Returns the path of the saved paper, or empty string on failure."""
        await self.emit.session_start(topic)

        try:
            # ── Phase 1: Gather sources ────────────────────────────────────
            await self.emit.step("plan", f"Researching: {topic}")
            search_queries = await self._plan_searches(topic)
            sources: list[dict] = []

            for q in search_queries[:3]:
                await self.emit.step("search", q)
                try:
                    results = await self.browser.search(q)
                except Exception as e:
                    await self.emit.step("note", f"Search failed: {e}")
                    continue

                for r in results[:2]:
                    await self.emit.step("read", r.url)
                    try:
                        page = await self.browser.visit(r.url)
                    except Exception:
                        continue
                    if page.text_content and len(page.text_content) > 200:
                        sources.append({
                            "title": page.title,
                            "url": r.url,
                            "snippet": page.text_content[:3000],
                        })
                        await self.emit.step(
                            "note",
                            f"Captured {page.word_count} words from {r.title[:60]}",
                        )

            if not sources:
                await self.emit.session_error("No usable sources found.")
                return ""

            # ── Phase 2: Outline ───────────────────────────────────────────
            await self.emit.step("plan", "Outlining the paper...")
            outline = await self._build_outline(topic, sources)
            await self.emit.doc_replace(f"# {topic}\n\n## Outline\n\n{outline}\n\n")

            # ── Phase 3: Write each section, streaming ─────────────────────
            await self.emit.step("write", "Writing the full paper, section by section...")
            full_doc = f"# {topic}\n\n"
            await self.emit.doc_replace(full_doc)

            sections = self._parse_outline(outline)
            for sec in sections:
                await self.emit.step("write", f"Section: {sec}")
                section_text = await self._write_section(topic, sec, sources)
                full_doc += f"\n## {sec}\n\n{section_text}\n"
                # Send the new section as a chunk (live-update the doc panel)
                await self.emit.doc_chunk(f"\n## {sec}\n\n{section_text}\n")

            # ── Phase 4: Citations footer ──────────────────────────────────
            citations = "\n\n## Sources\n\n" + "\n".join(
                f"- [{s['title']}]({s['url']})" for s in sources
            )
            full_doc += citations
            await self.emit.doc_chunk(citations)

            # ── Phase 5: Save ──────────────────────────────────────────────
            await self.emit.step("render", "Saving to disk...")
            slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60] or "paper"
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            out_path = PAPERS_DIR / f"{timestamp}-{slug}.md"
            out_path.write_text(full_doc, encoding="utf-8")
            log.info(f"Paper saved: {out_path}")
            await self.emit.session_end(success=True, path=str(out_path))
            return str(out_path)

        except Exception as e:
            log.error(f"Live research failed: {e}", exc_info=True)
            await self.emit.session_error(str(e))
            return ""
        finally:
            try:
                await self.browser.close()
            except Exception:
                pass

    # -- LLM helpers ---------------------------------------------------------

    async def _plan_searches(self, topic: str) -> list[str]:
        prompt = (
            f"For the research topic '{topic}', produce 3 specific web search queries "
            "that would surface the most useful sources. One per line. No numbering, "
            "no extra commentary."
        )
        text = await llm_router.chat(
            llm_router.model_fast(),
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            anthropic_client=self.client,
            feature="live_research",
        )
        return [q.strip("- •*").strip() for q in text.splitlines() if q.strip()]

    async def _build_outline(self, topic: str, sources: list[dict]) -> str:
        snippets = "\n\n".join(
            f"### {s['title']}\n{s['snippet'][:600]}" for s in sources[:6]
        )
        prompt = (
            f"You are JARVIS drafting a paper on: {topic}\n\n"
            "Based on these sources, produce an outline of 4-6 sections "
            "(just the section titles, one per line, no numbering, no extra commentary):\n\n"
            f"{snippets}"
        )
        text = await llm_router.chat(
            llm_router.model_fast(),
            [{"role": "user", "content": prompt}],
            max_tokens=300,
            anthropic_client=self.client,
            feature="live_research",
        )
        return text.strip()

    def _parse_outline(self, outline: str) -> list[str]:
        sections = []
        for line in outline.splitlines():
            line = line.strip("-•*# ").strip()
            line = re.sub(r"^\d+[.)]\s*", "", line)  # strip numbering
            if 3 < len(line) < 120:
                sections.append(line)
        return sections[:6]

    async def _write_section(self, topic: str, section: str, sources: list[dict]) -> str:
        ctx = "\n\n".join(
            f"### {s['title']}\n{s['snippet'][:800]}" for s in sources[:5]
        )
        prompt = (
            f"You are JARVIS writing the section titled '{section}' of a paper on '{topic}'. "
            "Write 3-5 paragraphs of substantive content grounded in these sources. "
            "Don't restate the section title. No markdown headers. Plain paragraphs.\n\n"
            f"Sources:\n{ctx}"
        )
        # Stream the section so the doc panel updates word-by-word
        accumulated: list[str] = []
        async for chunk in llm_router.stream(
            llm_router.model_fast(),
            [{"role": "user", "content": prompt}],
            max_tokens=1200,
            anthropic_client=self.client,
            feature="live_research",
        ):
            accumulated.append(chunk)
            if chunk:
                await self.emit.doc_chunk(chunk)
        return "".join(accumulated).strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_live_research(anthropic_client, ws, topic: str) -> str:
    """Run a full live-research session. Returns saved-file path or empty string."""
    researcher = LiveResearcher(anthropic_client, ws)
    return await researcher.run(topic)
