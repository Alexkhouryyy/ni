"""Persistent task scheduler — lets the agent schedule recurring and one-off autonomous actions.

Tasks are stored in SQLite and survive restarts. APScheduler fires them; each
execution runs the agent with the stored prompt and speaks the result aloud.
"""
import json
import time
import threading
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from agent import longterm

_scheduler: Optional[BackgroundScheduler] = None
_agent_run_fn: Optional[Callable] = None
_speak_fn: Optional[Callable] = None


def init(agent_run_fn: Callable, speak_fn: Callable) -> None:
    """Wire up and start the scheduler. Call once at startup."""
    global _scheduler, _agent_run_fn, _speak_fn
    _agent_run_fn = agent_run_fn
    _speak_fn = speak_fn

    # Ensure the tasks table exists
    import sqlite3
    with longterm._conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                trigger_type TEXT NOT NULL,   -- cron / interval / date
                trigger_params TEXT NOT NULL, -- JSON
                enabled INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                last_run REAL,
                run_count INTEGER DEFAULT 0
            )
        """)

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.start()
    _restore_tasks()
    print(f"[Scheduler] Started. {len(list_tasks())} tasks loaded.")


def schedule(
    description: str,
    trigger_type: str,
    trigger_params: dict,
) -> str:
    """
    Schedule an autonomous agent task.

    trigger_type: 'cron' | 'interval' | 'date'
    trigger_params examples:
      cron:     {"hour": 8, "minute": 0}            — daily at 8am UTC
      cron:     {"day_of_week": "mon-fri", "hour": 9}
      interval: {"hours": 1}                         — every hour
      interval: {"minutes": 30}
      date:     {"run_date": "2026-06-01 09:00:00"}
    """
    if _scheduler is None:
        return "Scheduler not initialised."

    task_id = f"task_{int(time.time() * 1000)}"
    trigger = _make_trigger(trigger_type, trigger_params)
    if trigger is None:
        return f"Unknown trigger_type: {trigger_type!r}. Use cron, interval, or date."

    _scheduler.add_job(
        _fire_task,
        trigger=trigger,
        id=task_id,
        args=[task_id, description],
        replace_existing=True,
    )

    with longterm._conn() as c:
        c.execute(
            """INSERT INTO scheduled_tasks
               (id, description, trigger_type, trigger_params, enabled, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (task_id, description, trigger_type, json.dumps(trigger_params), time.time()),
        )

    return f"Scheduled task {task_id!r}: {description} [{trigger_type}: {trigger_params}]"


def cancel(task_id: str) -> str:
    if _scheduler is None:
        return "Scheduler not initialised."
    try:
        _scheduler.remove_job(task_id)
    except Exception:
        pass
    with longterm._conn() as c:
        c.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
    return f"Cancelled task {task_id!r}"


def list_tasks() -> list[dict]:
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, description, trigger_type, trigger_params, enabled, last_run, run_count FROM scheduled_tasks"
        ).fetchall()
    return [
        {
            "id": r[0], "description": r[1], "trigger_type": r[2],
            "trigger_params": json.loads(r[3]), "enabled": bool(r[4]),
            "last_run": r[5], "run_count": r[6],
        }
        for r in rows
    ]


def _fire_task(task_id: str, description: str) -> None:
    print(f"[Scheduler] Firing task {task_id!r}: {description}")
    with longterm._conn() as c:
        c.execute(
            "UPDATE scheduled_tasks SET last_run = ?, run_count = run_count + 1 WHERE id = ?",
            (time.time(), task_id),
        )
    try:
        response = _agent_run_fn(
            description,
            include_screenshot=True,
            use_thinking=False,
            channel_id=f"scheduler:{task_id}",
        )
        if _speak_fn and response:
            _speak_fn(response)
    except Exception as e:
        print(f"[Scheduler] Task {task_id!r} failed: {e}")


def _make_trigger(trigger_type: str, params: dict):
    try:
        if trigger_type == "cron":
            return CronTrigger(**params, timezone="UTC")
        elif trigger_type == "interval":
            return IntervalTrigger(**params)
        elif trigger_type == "date":
            return DateTrigger(**params)
    except Exception as e:
        print(f"[Scheduler] Bad trigger params: {e}")
    return None


def _restore_tasks() -> None:
    for task in list_tasks():
        if not task["enabled"]:
            continue
        trigger = _make_trigger(task["trigger_type"], task["trigger_params"])
        if trigger:
            try:
                _scheduler.add_job(
                    _fire_task,
                    trigger=trigger,
                    id=task["id"],
                    args=[task["id"], task["description"]],
                    replace_existing=True,
                )
            except Exception as e:
                print(f"[Scheduler] Could not restore {task['id']}: {e}")
