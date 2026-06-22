"""
JARVIS LLM Router — one chat() call, route to Anthropic or local Ollama.

Model naming convention:
    "claude-haiku-4-5"          → Anthropic
    "claude-opus-4-6"           → Anthropic
    "ollama:llama3.1:8b"        → local Ollama at http://localhost:11434
    "ollama:deepseek-r1:14b"    → local Ollama

The router accepts the same `messages` shape Anthropic uses and returns plain
text. Streaming returns an async iterator of text chunks.

DeepSeek-R1 quirk: it emits <think>...</think> blocks before its answer.
We strip those automatically.

Cost: Ollama calls are FREE (local GPU). Anthropic calls bill normally.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import AsyncIterator, Optional

import httpx
import anthropic

import usage

log = logging.getLogger("jarvis.llm_router")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


# ---------------------------------------------------------------------------
# Output post-processing
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


def strip_reasoning_blocks(text: str) -> str:
    """Remove <think>...</think> blocks (DeepSeek-R1 internal reasoning).

    Handles both:
      - Complete blocks: <think>foo</think> → removed
      - Truncated open blocks: <think>foo (no close tag) → everything from
        <think> to end-of-string removed. If that leaves nothing, the model
        only thought aloud — return the original text so the caller sees
        something rather than empty.
    """
    out = _THINK_RE.sub("", text)
    stripped = _OPEN_THINK_RE.sub("", out).strip()
    return stripped if stripped else out.strip()


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

async def _ollama_chat(
    model: str,
    messages: list[dict],
    system: Optional[str],
    max_tokens: int,
) -> str:
    """Single-shot chat against Ollama. Returns final text (reasoning stripped)."""
    payload: dict = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            r = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return strip_reasoning_blocks(content)
    except Exception as e:
        log.error(f"Ollama call failed for {model}: {e}")
        raise


async def _ollama_stream(
    model: str,
    messages: list[dict],
    system: Optional[str],
    max_tokens: int,
) -> AsyncIterator[str]:
    """Streaming chat against Ollama. Yields text chunks (reasoning stripped)."""
    payload = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "stream": True,
        "options": {"num_predict": max_tokens},
    }
    in_think = False
    async with httpx.AsyncClient(timeout=None) as http:
        async with http.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                piece = chunk.get("message", {}).get("content", "")
                if not piece:
                    continue
                # Cheap streaming-friendly think-strip
                if "<think>" in piece:
                    in_think = True
                    piece = piece.split("<think>")[0]
                if "</think>" in piece:
                    in_think = False
                    piece = piece.split("</think>", 1)[1]
                if in_think:
                    continue
                if piece:
                    yield piece


# ---------------------------------------------------------------------------
# Anthropic backend
# ---------------------------------------------------------------------------

async def _anthropic_chat(
    client: anthropic.AsyncAnthropic,
    model: str,
    messages: list[dict],
    system: Optional[str],
    max_tokens: int,
) -> str:
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    resp = await client.messages.create(**kwargs)
    return resp.content[0].text


async def _anthropic_stream(
    client: anthropic.AsyncAnthropic,
    model: str,
    messages: list[dict],
    system: Optional[str],
    max_tokens: int,
) -> AsyncIterator[str]:
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    async with client.messages.stream(**kwargs) as stream:
        async for chunk in stream.text_stream:
            yield chunk


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    model: str,
    messages: list[dict],
    *,
    system: Optional[str] = None,
    max_tokens: int = 500,
    anthropic_client: Optional[anthropic.AsyncAnthropic] = None,
    feature: str = "other",
) -> str:
    """Single-shot chat. Returns plain text. Auto-logs usage with the given feature tag."""
    if model.startswith("ollama:"):
        ollama_model = model.split(":", 1)[1]
        out = await _ollama_chat(ollama_model, messages, system, max_tokens)
        usage.log_llm_call(feature=feature, model=model, input_tokens=0, output_tokens=0)
        return out
    if anthropic_client is None:
        raise RuntimeError("Anthropic client required for non-ollama models")
    # Direct Anthropic call — capture token counts from response.usage
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    resp = await anthropic_client.messages.create(**kwargs)
    try:
        in_t = getattr(resp.usage, "input_tokens", 0)
        out_t = getattr(resp.usage, "output_tokens", 0)
    except Exception:
        in_t = out_t = 0
    usage.log_llm_call(feature=feature, model=model, input_tokens=in_t, output_tokens=out_t)
    return resp.content[0].text


async def stream(
    model: str,
    messages: list[dict],
    *,
    system: Optional[str] = None,
    max_tokens: int = 500,
    anthropic_client: Optional[anthropic.AsyncAnthropic] = None,
    feature: str = "other",
) -> AsyncIterator[str]:
    """Streaming chat. Async iterator of text chunks. Logs usage after the stream completes."""
    if model.startswith("ollama:"):
        ollama_model = model.split(":", 1)[1]
        async for piece in _ollama_stream(ollama_model, messages, system, max_tokens):
            yield piece
        usage.log_llm_call(feature=feature, model=model, input_tokens=0, output_tokens=0)
        return
    if anthropic_client is None:
        raise RuntimeError("Anthropic client required for non-ollama models")
    # We need to wrap to capture final usage; use anthropic stream context directly
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    async with anthropic_client.messages.stream(**kwargs) as s:
        async for chunk in s.text_stream:
            yield chunk
        # After the stream finishes, the final message has usage info
        try:
            final = await s.get_final_message()
            in_t = getattr(final.usage, "input_tokens", 0)
            out_t = getattr(final.usage, "output_tokens", 0)
        except Exception:
            in_t = out_t = 0
        usage.log_llm_call(feature=feature, model=model, input_tokens=in_t, output_tokens=out_t)


def is_local(model: str) -> bool:
    return model.startswith("ollama:")


def model_fast() -> str:
    """Cheap-tier model (classification, summaries, intent). Read from env every call."""
    return os.environ.get("MODEL_FAST", "claude-haiku-4-5")


def model_smart() -> str:
    """Main-chat model (conversation, reasoning). Read from env every call."""
    return os.environ.get("MODEL_SMART", "claude-opus-4-6")
