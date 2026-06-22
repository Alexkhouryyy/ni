"""
JARVIS Usage & Cost Tracking.

Every LLM and TTS call is logged here with a `feature` tag (what we were
doing), a `model` tag (which model we used), and a `provider` tag
(anthropic / ollama / openai). The dashboard reads from this single source.

Storage: `data/usage_log.jsonl` — one JSON object per line, append-only.
Old entries that pre-date the richer schema fall back to sensible defaults
when read, so historical data isn't lost.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("jarvis.usage")

# ---------------------------------------------------------------------------
# Pricing tables (USD)
# ---------------------------------------------------------------------------

# Per million tokens, (input, output)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5":              (1.00,  5.00),
    "claude-haiku-4-5-20251001":     (1.00,  5.00),  # legacy alias
    "claude-sonnet-4-6":             (3.00, 15.00),
    "claude-opus-4-6":              (15.00, 75.00),
    # Older models that may appear in legacy logs:
    "claude-3-haiku-20240307":       (0.25,  1.25),
    "claude-3-5-haiku-20241022":     (1.00,  5.00),
    "claude-3-5-sonnet-20241022":    (3.00, 15.00),
}

# Per 1k chars
TTS_PRICING_PER_1K_CHAR: dict[str, float] = {
    "tts-1":     0.015,
    "tts-1-hd":  0.030,
    "gpt-4o-mini-tts": 0.015,
}

DEFAULT_LLM_RATE = (1.00, 5.00)  # fall-back to Haiku pricing
DEFAULT_TTS_RATE = 0.015


# ---------------------------------------------------------------------------
# File location + in-memory session counter
# ---------------------------------------------------------------------------

_USAGE_FILE = Path(__file__).parent / "data" / "usage_log.jsonl"
_session_start = time.time()
_session: dict[str, float | int] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "tts_chars": 0,
    "api_calls": 0,
    "tts_calls": 0,
    "cost_usd": 0.0,
}


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

def cost_for_llm(model: str, in_t: int, out_t: int) -> float:
    if not model:
        return 0.0
    if model.startswith("ollama:"):
        return 0.0
    rate_in, rate_out = MODEL_PRICING.get(model, DEFAULT_LLM_RATE)
    return (in_t / 1_000_000) * rate_in + (out_t / 1_000_000) * rate_out


def cost_for_tts(model: str, chars: int) -> float:
    rate = TTS_PRICING_PER_1K_CHAR.get(model, DEFAULT_TTS_RATE)
    return (chars / 1000) * rate


def provider_for(model: str) -> str:
    if not model:
        return "anthropic"
    if model.startswith("ollama:"):
        return "ollama"
    if model.startswith("tts") or model in TTS_PRICING_PER_1K_CHAR:
        return "openai"
    return "anthropic"


# ---------------------------------------------------------------------------
# Append helpers — call after every LLM / TTS interaction
# ---------------------------------------------------------------------------

def _write_entry(entry: dict[str, Any]) -> None:
    try:
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_USAGE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.debug(f"usage write failed: {e}")


def log_llm_call(*, feature: str, model: str, input_tokens: int, output_tokens: int) -> None:
    cost = cost_for_llm(model, input_tokens, output_tokens)
    _session["input_tokens"] += input_tokens
    _session["output_tokens"] += output_tokens
    _session["api_calls"] += 1
    _session["cost_usd"] += cost
    _write_entry({
        "ts": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": "llm",
        "feature": feature or "other",
        "model": model or "unknown",
        "provider": provider_for(model),
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "char_count": 0,
        "cost_usd": round(cost, 6),
    })


def log_tts_call(*, model: str, char_count: int, feature: str = "tts") -> None:
    cost = cost_for_tts(model, char_count)
    _session["tts_chars"] += char_count
    _session["tts_calls"] += 1
    _session["cost_usd"] += cost
    _write_entry({
        "ts": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": "tts",
        "feature": feature or "tts",
        "model": model or "tts-1",
        "provider": "openai",
        "input_tokens": 0,
        "output_tokens": 0,
        "char_count": int(char_count or 0),
        "cost_usd": round(cost, 6),
    })


# ---------------------------------------------------------------------------
# Reader / aggregator
# ---------------------------------------------------------------------------

def _iter_entries():
    if not _USAGE_FILE.exists():
        return
    try:
        with open(_USAGE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except Exception:
                    continue
                # Back-compat: old entries have type:"api"|"tts" and no feature/model/provider
                if "feature" not in raw:
                    raw["feature"] = "other"
                if "model" not in raw:
                    raw["model"] = "claude-haiku-4-5" if raw.get("type") != "tts" else "tts-1"
                if "provider" not in raw:
                    raw["provider"] = provider_for(raw["model"])
                if "cost_usd" not in raw:
                    if raw.get("type") == "tts":
                        raw["cost_usd"] = cost_for_tts(raw["model"], raw.get("char_count", 0))
                    else:
                        raw["cost_usd"] = cost_for_llm(
                            raw["model"],
                            raw.get("input_tokens", 0),
                            raw.get("output_tokens", 0),
                        )
                yield raw
    except Exception as e:
        log.debug(f"usage read failed: {e}")


def _aggregate(seconds: Optional[float] = None) -> dict[str, Any]:
    cutoff = (time.time() - seconds) if seconds else 0
    totals = {"cost_usd": 0.0, "calls": 0, "in_tokens": 0, "out_tokens": 0, "tts_chars": 0}
    for e in _iter_entries():
        if e["ts"] < cutoff:
            continue
        totals["cost_usd"] += e.get("cost_usd", 0.0)
        totals["calls"] += 1
        totals["in_tokens"] += e.get("input_tokens", 0)
        totals["out_tokens"] += e.get("output_tokens", 0)
        totals["tts_chars"] += e.get("char_count", 0)
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return totals


def detailed_summary() -> dict[str, Any]:
    """Produce the dashboard's JSON payload."""
    by_day: dict[str, float] = defaultdict(float)
    today_by_feature: dict[str, float] = defaultdict(float)
    today_by_provider: dict[str, float] = defaultdict(float)
    recent: list[dict[str, Any]] = []

    today_str = datetime.now().strftime("%Y-%m-%d")
    seven_day_cutoff = time.time() - 7 * 86400

    for e in _iter_entries():
        # Week-by-day
        if e["ts"] >= seven_day_cutoff:
            by_day[e["date"]] += e.get("cost_usd", 0.0)
        # Today buckets
        if e["date"] == today_str:
            today_by_feature[e["feature"]] += e.get("cost_usd", 0.0)
            today_by_provider[e["provider"]] += e.get("cost_usd", 0.0)
        # Recent (oldest first; we trim at end)
        recent.append({
            "ts": e["ts"],
            "feature": e["feature"],
            "model": e["model"],
            "provider": e["provider"],
            "in": e.get("input_tokens", 0),
            "out": e.get("output_tokens", 0),
            "chars": e.get("char_count", 0),
            "cost_usd": round(e.get("cost_usd", 0.0), 6),
        })

    recent = recent[-30:]  # last 30
    recent.reverse()       # newest first

    return {
        "today":     {**_aggregate(86400),     "label": "Today"},
        "week":      {**_aggregate(7 * 86400), "label": "This week"},
        "month":     {**_aggregate(30 * 86400), "label": "This month"},
        "all_time":  {**_aggregate(None),       "label": "All time"},
        "session":   {**_session, "uptime_seconds": int(time.time() - _session_start)},
        "week_by_day":      [{"date": d, "cost_usd": round(v, 4)} for d, v in sorted(by_day.items())],
        "today_by_feature": {k: round(v, 4) for k, v in sorted(today_by_feature.items(), key=lambda x: -x[1])},
        "today_by_provider": {k: round(v, 4) for k, v in sorted(today_by_provider.items(), key=lambda x: -x[1])},
        "recent_calls": recent,
    }


# ---------------------------------------------------------------------------
# Legacy back-compat — used by /api/usage in server.py
# ---------------------------------------------------------------------------

def legacy_summary() -> dict[str, Any]:
    """Match the shape the old /api/usage endpoint used to return."""
    today = _aggregate(86400)
    week = _aggregate(7 * 86400)
    month = _aggregate(30 * 86400)
    all_time = _aggregate(None)
    return {
        "session": {
            "input": _session["input_tokens"],
            "output": _session["output_tokens"],
            "api_calls": _session["api_calls"],
            "tts_calls": _session["tts_calls"],
            "uptime_seconds": int(time.time() - _session_start),
        },
        "today":    {"input_tokens": today["in_tokens"], "output_tokens": today["out_tokens"],
                     "api_calls": today["calls"], "tts_calls": 0, "cost_usd": today["cost_usd"]},
        "week":     {"input_tokens": week["in_tokens"], "output_tokens": week["out_tokens"],
                     "api_calls": week["calls"], "tts_calls": 0, "cost_usd": week["cost_usd"]},
        "month":    {"input_tokens": month["in_tokens"], "output_tokens": month["out_tokens"],
                     "api_calls": month["calls"], "tts_calls": 0, "cost_usd": month["cost_usd"]},
        "all_time": {"input_tokens": all_time["in_tokens"], "output_tokens": all_time["out_tokens"],
                     "api_calls": all_time["calls"], "tts_calls": 0, "cost_usd": all_time["cost_usd"]},
    }
