"""Outcome tracking — correlate 👍/👎 feedback with skills and reflections.

Three measurement axes:

  skill_outcomes()      — per-skill approval rate for turns where the skill ran
  reflection_outcomes() — pre/post approval rate around each applied reflection
  overall()             — aggregate summary for the telemetry dashboard

The skill join works through (session_id, turn_index) added to skill_usage in
Phase 7.  The reflection join uses timestamps: we find the wall-clock time of
each rated turn via turn_log (role='user'), then compare turns that happened in
a configurable window before vs. after each applied reflection.

All functions are read-only; nothing writes to the DB.
"""
import time
from typing import Optional

from agent import longterm


def skill_outcomes(name: Optional[str] = None, days: int = 7) -> list[dict]:
    """Per-skill approval rate for rated turns.

    Only turns where the skill ran AND the user left feedback count toward
    `rated_runs`.  Turns without feedback count toward `total_runs` only.

    Returns one dict per skill, sorted by rated_runs desc.
    """
    cutoff = time.time() - days * 86400
    name_filter = "AND s.name = ?" if name else ""
    params = [cutoff]
    if name:
        params.append(name)

    with longterm._conn() as c:
        rows = c.execute(
            f"""
            SELECT
                s.name,
                COUNT(DISTINCT s.id)                                              AS total_runs,
                COUNT(f.id)                                                       AS rated_runs,
                COALESCE(SUM(CASE WHEN f.rating =  1 THEN 1 ELSE 0 END), 0)     AS ups,
                COALESCE(SUM(CASE WHEN f.rating = -1 THEN 1 ELSE 0 END), 0)     AS downs
            FROM skill_usage s
            LEFT JOIN turn_feedback f
                   ON f.session_id = s.session_id
                  AND f.turn_index = s.turn_index
            WHERE s.ts >= ? {name_filter}
            GROUP BY s.name
            ORDER BY rated_runs DESC, total_runs DESC
            """,
            params,
        ).fetchall()

    out = []
    for row in rows:
        rated = row[2]
        ups = row[3]
        out.append({
            "name": row[0],
            "total_runs": row[1],
            "rated_runs": rated,
            "thumbs_up": ups,
            "thumbs_down": row[4],
            "approval_rate": round(ups / rated, 3) if rated else None,
        })
    return out


def reflection_outcomes(days: int = 30, window_hours: int = 168) -> list[dict]:
    """Pre/post approval rate for every applied reflection in the window.

    For each reflection with status='applied' in the last `days` days:
      - pre_rate: approval rate for rated turns whose wall-clock time falls in
                  [reflection.ts - window_hours, reflection.ts)
      - post_rate: approval rate for rated turns in
                   [reflection.ts, reflection.ts + window_hours)
      - delta: post_rate - pre_rate (positive = improvement)

    Turn timestamps come from turn_log (role='user'), which is written at the
    start of each turn — before the agent responds — so it reliably anchors
    *when* a conversation turn occurred, independent of when feedback arrived.
    """
    cutoff = time.time() - days * 86400
    window_secs = window_hours * 3600

    with longterm._conn() as c:
        reflections = c.execute(
            "SELECT id, ts, kind, content, confidence FROM reflections "
            "WHERE status = 'applied' AND ts >= ? ORDER BY ts DESC",
            (cutoff,),
        ).fetchall()

    out = []
    for refl_id, refl_ts, kind, content, confidence in reflections:
        pre_start = refl_ts - window_secs
        post_end = refl_ts + window_secs

        with longterm._conn() as c:
            pre = c.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN f.rating = 1 THEN 1 ELSE 0 END) AS ups
                FROM turn_feedback f
                JOIN (
                    SELECT session_id, turn_index, MIN(ts) AS turn_ts
                    FROM turn_log WHERE role = 'user'
                    GROUP BY session_id, turn_index
                ) tl ON tl.session_id = f.session_id AND tl.turn_index = f.turn_index
                WHERE tl.turn_ts >= ? AND tl.turn_ts < ?
                """,
                (pre_start, refl_ts),
            ).fetchone()

            post = c.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN f.rating = 1 THEN 1 ELSE 0 END) AS ups
                FROM turn_feedback f
                JOIN (
                    SELECT session_id, turn_index, MIN(ts) AS turn_ts
                    FROM turn_log WHERE role = 'user'
                    GROUP BY session_id, turn_index
                ) tl ON tl.session_id = f.session_id AND tl.turn_index = f.turn_index
                WHERE tl.turn_ts >= ? AND tl.turn_ts < ?
                """,
                (refl_ts, post_end),
            ).fetchone()

        pre_total, pre_ups = (pre[0] or 0), (pre[1] or 0)
        post_total, post_ups = (post[0] or 0), (post[1] or 0)
        pre_rate = (pre_ups / pre_total) if pre_total else None
        post_rate = (post_ups / post_total) if post_total else None
        delta = round(post_rate - pre_rate, 3) if (pre_rate is not None and post_rate is not None) else None

        out.append({
            "reflection_id": refl_id,
            "ts": refl_ts,
            "kind": kind,
            "content": content[:160],
            "confidence": confidence,
            "pre_turns": pre_total,
            "pre_rate": round(pre_rate, 3) if pre_rate is not None else None,
            "post_turns": post_total,
            "post_rate": round(post_rate, 3) if post_rate is not None else None,
            "delta": delta,
        })

    return out


def overall(days: int = 7) -> dict:
    """Dashboard-ready aggregate: approval rate + worst skills + best reflections."""
    from agent.feedback import summary as fb_summary

    fb = fb_summary(days=days)
    skills = skill_outcomes(days=days)
    refls = reflection_outcomes(days=days * 4)  # wider window for reflections

    # Skills with enough data, sorted by approval_rate ascending (worst first)
    rated_skills = [s for s in skills if s["rated_runs"] >= 3]
    worst_skills = sorted(
        rated_skills,
        key=lambda s: s["approval_rate"] if s["approval_rate"] is not None else 1.0,
    )[:5]
    best_skills = sorted(
        rated_skills,
        key=lambda s: s["approval_rate"] if s["approval_rate"] is not None else 0.0,
        reverse=True,
    )[:3]

    # Reflections with measured delta, sorted best first
    delta_refls = [r for r in refls if r["delta"] is not None]
    best_reflections = sorted(delta_refls, key=lambda r: r["delta"], reverse=True)[:3]
    worst_reflections = sorted(delta_refls, key=lambda r: r["delta"])[:3]

    return {
        "days": days,
        "approval_rate": fb["approval_rate"],
        "thumbs_up": fb["thumbs_up"],
        "thumbs_down": fb["thumbs_down"],
        "total_rated_turns": fb["total"],
        "skill_coverage": len([s for s in skills if s["rated_runs"] > 0]),
        "total_skills_run": len(skills),
        "worst_skills": worst_skills,
        "best_skills": best_skills,
        "applied_reflections_in_window": len(refls),
        "reflections_with_delta": len(delta_refls),
        "best_reflections": best_reflections,
        "worst_reflections": worst_reflections,
    }
