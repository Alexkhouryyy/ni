"""Blind model comparison — ask once, judge on merit, log the preference.

This COMPLEMENTS the debating council (agent/council.py), it does not replace it:
  - Council: members debate, a chair synthesizes ONE collaborative answer.
  - Compare: members answer INDEPENDENTLY; answers are shown BLIND (labels hidden,
    order shuffled) so you judge on quality alone, pick a winner, and the choice
    is logged to build a personal model leaderboard. Optional chair synthesis.

Reuses the council's roster/availability and provider.complete — no new model
plumbing, and the council is left completely untouched.
"""
from __future__ import annotations

import concurrent.futures
import json
import random
import time

from agent import provider, longterm, council

_ANSWER_SYS = (
    "Answer the question as well as you possibly can. Be specific and concrete, "
    "and be honest about any uncertainty. Do not mention which model you are."
)

_SYNTH_SYS = (
    "You are given a question and several independent answers to it. Write the "
    "single best answer by integrating the strongest, most correct points from "
    "all of them and discarding the weak ones. Be decisive and concrete."
)

# compare_id -> {"question", "entries"(full, with model/label)}; held until a pick
# or synthesis. In-memory by design: a server restart simply means re-running.
_PENDING: dict[str, dict] = {}
_MAX_PENDING = 50


def init_db() -> None:
    with longterm._conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS model_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                question TEXT NOT NULL,
                winner_model TEXT NOT NULL,
                winner_label TEXT NOT NULL,
                contenders_json TEXT NOT NULL,
                note TEXT
            )
        """)


def _slot(i: int) -> str:
    return chr(ord("A") + i)


def candidates(panel: list[str] | None = None) -> list[tuple[str, str]]:
    """Models available to compare — reuses the council roster's key-availability.
    Optional `panel` limits to specific model ids."""
    members = council.available_members()
    if panel:
        members = [(m, l) for (m, l) in members if m in panel]
    return members


def run(question: str, panel: list[str] | None = None, max_tokens: int = 1200) -> dict:
    """Ask every available model the question in parallel, return a BLIND view
    (slot + text only, labels hidden, order shuffled). The full mapping is held
    server-side under the returned compare_id until pick()/synthesize()."""
    question = (question or "").strip()
    if not question:
        return {"error": "Ask a question to compare."}
    members = candidates(panel)
    if len(members) < 2:
        return {"error": "Need at least 2 models with API keys configured "
                          "(add OPENAI_API_KEY and/or GEMINI_API_KEY, or widen the panel)."}

    results: dict[str, tuple[str, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as ex:
        futs = {
            ex.submit(provider.complete, model, _ANSWER_SYS, question, max_tokens): (model, label)
            for model, label in members
        }
        for fut in concurrent.futures.as_completed(futs):
            model, label = futs[fut]
            try:
                text = fut.result()
            except Exception as e:
                text = f"[{label} failed to respond: {e}]"
            results[model] = (label, text)

    items = [{"model": m, "label": results[m][0], "text": results[m][1]} for m, _ in members]
    random.shuffle(items)
    for i, it in enumerate(items):
        it["slot"] = _slot(i)

    compare_id = f"cmp_{int(time.time() * 1000)}"
    # Bound memory: drop oldest pending comparisons if we accumulate too many.
    if len(_PENDING) >= _MAX_PENDING:
        for k in list(_PENDING.keys())[: len(_PENDING) - _MAX_PENDING + 1]:
            _PENDING.pop(k, None)
    _PENDING[compare_id] = {"question": question, "entries": items}

    blind = [{"slot": it["slot"], "text": it["text"]} for it in items]
    return {"compare_id": compare_id, "question": question,
            "entries": blind, "count": len(items)}


def pick(compare_id: str, slot: str, note: str = "") -> dict:
    """Record the winning slot, reveal which model produced each answer."""
    data = _PENDING.get(compare_id)
    if not data:
        return {"error": "This comparison expired — run it again."}
    winner = next((e for e in data["entries"] if e["slot"] == slot), None)
    if not winner:
        return {"error": f"No answer in slot {slot!r}."}

    with longterm._conn() as c:
        c.execute(
            "INSERT INTO model_preferences (ts, question, winner_model, winner_label, contenders_json, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), data["question"], winner["model"], winner["label"],
             json.dumps([e["model"] for e in data["entries"]]), note or ""),
        )
    reveal = [{"slot": e["slot"], "model": e["model"], "label": e["label"]}
              for e in data["entries"]]
    _PENDING.pop(compare_id, None)
    return {"winner": {"slot": slot, "model": winner["model"], "label": winner["label"]},
            "reveal": reveal}


def synthesize(compare_id: str, max_tokens: int = 1500) -> dict:
    """Optional: merge the blind answers into one best answer via a chair model."""
    data = _PENDING.get(compare_id)
    if not data:
        return {"error": "This comparison expired — run it again."}
    blocks = "\n\n".join(f"--- Answer {e['slot']} ---\n{e['text']}" for e in data["entries"])
    user = f"QUESTION:\n{data['question']}\n\nANSWERS:\n{blocks}"
    try:
        merged = provider.complete(council._CHAIR, _SYNTH_SYS, user, max_tokens=max_tokens)
    except Exception as e:
        return {"error": f"Synthesis failed: {e}"}
    return {"synthesis": merged}


def leaderboard() -> dict:
    """Aggregate wins and appearances per model from logged preferences."""
    try:
        with longterm._conn() as c:
            rows = c.execute(
                "SELECT winner_model, winner_label, contenders_json FROM model_preferences"
            ).fetchall()
    except Exception:
        return {"total": 0, "rows": []}

    wins: dict[str, int] = {}
    labels: dict[str, str] = {}
    appears: dict[str, int] = {}
    for winner_model, winner_label, contenders_json in rows:
        wins[winner_model] = wins.get(winner_model, 0) + 1
        labels[winner_model] = winner_label
        try:
            for m in json.loads(contenders_json):
                appears[m] = appears.get(m, 0) + 1
        except Exception:
            pass

    out = []
    for model, appearances in appears.items():
        w = wins.get(model, 0)
        out.append({
            "model": model,
            "label": labels.get(model, model),
            "wins": w,
            "appearances": appearances,
            "win_rate": round(100.0 * w / appearances) if appearances else 0,
        })
    out.sort(key=lambda r: (r["win_rate"], r["wins"]), reverse=True)
    return {"total": len(rows), "rows": out}
