"""Multi-model council — Claude, GPT, and Gemini debate to reach the best answer.

Flow:
  1. Opening statements — each member answers the question independently.
  2. Debate — each member reads every answer, critiques them, and revises
     or defends its own.
  3. Synthesis — a chair model consolidates the debate into one best answer.

Members are included only when their provider has an API key configured, so
the council degrades gracefully (minimum 2 members required).
"""
from __future__ import annotations
import concurrent.futures
from dataclasses import dataclass, field

import config
from agent import provider


# (model, display label) — one flagship model per provider
_ROSTER = [
    ("claude-opus-4-7", "Claude"),
    ("gpt-4o", "GPT"),
    ("gemini-2.5-pro", "Gemini"),
]
_CHAIR = "claude-opus-4-7"

_OPENING_SYS = (
    "You are one member of an expert council that will debate to find the best "
    "possible answer. Give your strongest, most honest answer to the question. "
    "Be specific and concrete. State any key assumptions or uncertainties."
)

_DEBATE_SYS = (
    "You are {label}, a member of an expert council. You answered a question; so "
    "did the other members. Read every answer critically — including your own. "
    "Point out concrete flaws, gaps, or mistakes. Then give your revised, best "
    "answer. Change your mind if another member is right; defend your position "
    "with reasons if you still disagree. Be direct, not diplomatic."
)

_CHAIR_SYS = (
    "You are the chair of an expert council. The members debated a question. "
    "Read the full transcript and write the single best possible answer. "
    "Integrate the strongest points from every member. Where the council "
    "disagreed and it matters, say so briefly and give your ruling with reasons. "
    "Output only the final answer — clear and decisive."
)


@dataclass
class CouncilResult:
    question: str
    final_answer: str
    transcript: list[dict] = field(default_factory=list)  # [{round, label, text}]
    members: list[str] = field(default_factory=list)


def available_members() -> list[tuple[str, str]]:
    """Return council members whose provider has an API key configured."""
    members = []
    for model, label in _ROSTER:
        p = provider.provider_for(model)
        if p == "anthropic" and config.ANTHROPIC_API_KEY:
            members.append((model, label))
        elif p == "openai" and config.OPENAI_API_KEY:
            members.append((model, label))
        elif p == "gemini" and config.GEMINI_API_KEY:
            members.append((model, label))
    return members


def _ask_all(members, sys_for, user_for, max_tokens=1500) -> dict:
    """Call every member in parallel. Returns {label: text}."""
    out: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as ex:
        futs = {
            ex.submit(provider.complete, model, sys_for(label), user_for(label), max_tokens): label
            for model, label in members
        }
        for fut in concurrent.futures.as_completed(futs):
            label = futs[fut]
            try:
                out[label] = fut.result()
            except Exception as e:
                out[label] = f"[{label} failed to respond: {e}]"
    return out


def _format_answers(answers: dict) -> str:
    return "\n\n".join(f"--- {label} ---\n{text}" for label, text in answers.items())


def convene(question: str, rounds: int = 1, on_progress=None) -> CouncilResult:
    """Run the council. `rounds` = number of debate rounds after the opening."""
    members = available_members()
    if len(members) < 2:
        return CouncilResult(
            question=question,
            final_answer=(
                "The council needs at least 2 providers with API keys configured. "
                "Add OPENAI_API_KEY and/or GEMINI_API_KEY to .env."
            ),
            members=[label for _, label in members],
        )

    def _progress(msg: str):
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    transcript: list[dict] = []

    # Round 0 — opening statements
    _progress(f"Opening round — {len(members)} members answering in parallel...")
    answers = _ask_all(members, sys_for=lambda _l: _OPENING_SYS, user_for=lambda _l: question)
    for label, text in answers.items():
        transcript.append({"round": 0, "label": label, "text": text})

    # Debate rounds
    for r in range(1, max(0, rounds) + 1):
        _progress(f"Debate round {r} — members critiquing and revising...")
        debate_user = (
            f"QUESTION:\n{question}\n\n"
            f"ANSWERS SO FAR:\n{_format_answers(answers)}\n\n"
            "Critique the answers, then give your revised best answer."
        )
        answers = _ask_all(
            members,
            sys_for=lambda label: _DEBATE_SYS.format(label=label),
            user_for=lambda _l: debate_user,
        )
        for label, text in answers.items():
            transcript.append({"round": r, "label": label, "text": text})

    # Synthesis
    _progress("Chair synthesizing the final answer...")
    blocks = []
    for entry in transcript:
        tag = "Opening" if entry["round"] == 0 else f"Debate {entry['round']}"
        blocks.append(f"=== {entry['label']} ({tag}) ===\n{entry['text']}")
    chair_user = f"QUESTION:\n{question}\n\nCOUNCIL TRANSCRIPT:\n\n" + "\n\n".join(blocks)
    try:
        final = provider.complete(_CHAIR, _CHAIR_SYS, chair_user, max_tokens=2000)
    except Exception as e:
        final = f"[Chair synthesis failed: {e}]"

    return CouncilResult(
        question=question,
        final_answer=final,
        transcript=transcript,
        members=[label for _, label in members],
    )
