"""FastAPI dashboard for the voice AI agent.

Read/write endpoints over the existing modules (longterm, scheduler,
knowledge, orchestrator, self_mod, goals). WebSocket pushes live activity
events from the awareness log.

Runs in a background thread on DASHBOARD_PORT (default 7860).
"""
import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from agent import longterm, knowledge, self_mod, goals, orchestrator
from agent import scheduler as sched

STATIC_DIR = Path(__file__).parent / "static"

# Will be set when the dashboard is started — gives us a handle to the live agent state
_agent_ref = None
_awareness_log = None


def set_agent(agent, awareness_log=None) -> None:
    global _agent_ref, _awareness_log
    _agent_ref = agent
    _awareness_log = awareness_log


# === WebSocket connection manager ===
class WSManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    def broadcast_threadsafe(self, payload: dict) -> None:
        """Called from any thread — schedules a broadcast on the dashboard's loop."""
        if not self.loop or not self.active:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(payload), self.loop)
        except Exception:
            pass

    async def _broadcast(self, payload: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WSManager()


# === FastAPI app ===
app = FastAPI(title="Voice Agent Dashboard")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>Dashboard static files missing</h1>")


# --- Status ---
@app.get("/api/status")
def status():
    return {
        "model": config.AGENT_MODEL,
        "proactive_enabled": config.PROACTIVE_ENABLED,
        "awareness_enabled": config.AWARENESS_ENABLED,
        "tools_count": len(_agent_ref._all_tools()) if _agent_ref else 0,
        "uptime_s": int(time.time() - _START_TIME),
    }


# --- Memories ---
@app.get("/api/memories")
def list_memories(q: str = "", kind: str = "", limit: int = 50):
    return longterm.recall(query=q, kind=kind, limit=limit, semantic=bool(q))


@app.post("/api/memories")
def add_memory(payload: dict):
    return {"result": longterm.remember(
        payload["content"],
        kind=payload.get("kind", "fact"),
        importance=payload.get("importance", 5),
        tags=payload.get("tags", ""),
    )}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    return {"result": longterm.forget(memory_id)}


# --- Scheduler ---
@app.get("/api/tasks")
def list_tasks():
    return sched.list_tasks()


@app.post("/api/tasks")
def add_task(payload: dict):
    return {"result": sched.schedule(
        description=payload["description"],
        trigger_type=payload["trigger_type"],
        trigger_params=payload["trigger_params"],
    )}


@app.delete("/api/tasks/{task_id}")
def cancel_task(task_id: str):
    return {"result": sched.cancel(task_id)}


# --- Knowledge ---
@app.get("/api/knowledge/stats")
def kb_stats():
    return knowledge.stats()


@app.post("/api/knowledge/reindex")
def kb_reindex(payload: dict):
    return {"result": knowledge.reindex(payload["paths"], force=payload.get("force", False))}


@app.get("/api/knowledge/search")
def kb_search(q: str, k: int = 6):
    return knowledge.search(q, top_k=k)


# --- Goals ---
@app.get("/api/goals")
def list_goals_endpoint(active_only: bool = True):
    return goals.list_goals(active_only=active_only)


@app.post("/api/goals")
def add_goal(payload: dict):
    return {"result": goals.set_goal(
        title=payload["title"],
        description=payload.get("description", ""),
        horizon=payload.get("horizon", "week"),
        deadline_iso=payload.get("deadline_iso"),
    )}


@app.patch("/api/goals/{goal_id}")
def update_goal_endpoint(goal_id: int, payload: dict):
    return {"result": goals.update_goal(
        goal_id,
        status=payload.get("status"),
        progress_note=payload.get("progress_note"),
        score=payload.get("score"),
    )}


# --- Sub-agents ---
@app.get("/api/subagents")
def list_subagents():
    out = {}
    for sid, info in orchestrator.list_all().items():
        out[sid] = {
            "role": info.get("role"),
            "task": (info.get("task") or "")[:140],
            "status": info.get("status"),
            "started": info.get("started"),
            "ended": info.get("ended"),
            "result_preview": (info.get("result") or "")[:200] if info.get("result") else None,
            "error": info.get("error"),
        }
    return out


# --- Self-mod ---
@app.get("/api/selfmod")
def get_selfmod():
    return self_mod.show()


@app.post("/api/selfmod/prompt")
def update_prompt(payload: dict):
    return {"result": self_mod.update_system_prompt(payload["addition"], replace=payload.get("replace", False))}


@app.post("/api/selfmod/revert")
def revert_selfmod(payload: dict = None):
    return {"result": self_mod.revert(restore_backup=(payload or {}).get("restore_backup", False))}


# --- Awareness events ---
@app.get("/api/events")
def recent_events(seconds: float = 300.0):
    if _awareness_log is None:
        return []
    return _awareness_log.recent(since_seconds=seconds)


# --- WebSocket live stream ---
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws_manager.connect(ws)
    if ws_manager.loop is None:
        ws_manager.loop = asyncio.get_event_loop()
    try:
        # Send initial snapshot
        await ws.send_json({"type": "snapshot", "ts": time.time(), "data": {
            "subagents": orchestrator.list_all(),
            "tasks": sched.list_tasks(),
            "events_recent": _awareness_log.recent(60) if _awareness_log else [],
        }})
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


_START_TIME = time.time()


# === Public API: start in a background thread ===
def start_in_background(port: int = 7860, host: str = "127.0.0.1") -> threading.Thread:
    import uvicorn

    def runner():
        cfg = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(cfg)
        server.run()

    t = threading.Thread(target=runner, daemon=True, name="DashboardServer")
    t.start()
    return t
