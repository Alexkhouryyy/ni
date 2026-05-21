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
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
from agent import longterm, knowledge, self_mod, goals, orchestrator
from agent import scheduler as sched
from agent import entities as ent_mod
from agent import reflection as refl_mod
from agent import telemetry as tel_mod
from tools import phone as phone_mod
from tools import telegram as telegram_mod
from tools import discord as discord_mod

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

_chat_lock: Optional[asyncio.Lock] = None


class ChatStreamer:
    """Minimal streamer that forwards token deltas to dashboard WebSocket clients."""
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def feed(self, text: str):
        ws_manager.broadcast_threadsafe({
            "type": "chat_token",
            "delta": text,
            "chat_id": self.chat_id,
        })

    def start(self): pass
    def finish(self): pass


# === FastAPI app ===
app = FastAPI(title="Voice Agent Dashboard")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def _auth(request: Request, call_next):
    token = config.DASHBOARD_TOKEN
    if not token:
        return await call_next(request)
    if request.url.path == "/health":
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return await call_next(request)
    if request.url.path == "/ws/live" and request.query_params.get("token") == token:
        return await call_next(request)
    return Response("Unauthorized", status_code=401)


@app.get("/health")
async def health():
    return {"status": "ok"}


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
        "model": _agent_ref._model if _agent_ref else config.AGENT_MODEL,
        "proactive_enabled": config.PROACTIVE_ENABLED,
        "awareness_enabled": config.AWARENESS_ENABLED,
        "tools_count": len(_agent_ref._all_tools()) if _agent_ref else 0,
        "uptime_s": int(time.time() - _START_TIME),
    }


# --- Models ---
@app.get("/api/models")
def list_models():
    from agent.provider import KNOWN_MODELS, provider_for
    have_key = {
        "anthropic": bool(config.ANTHROPIC_API_KEY),
        "openai": bool(config.OPENAI_API_KEY),
        "gemini": bool(config.GEMINI_API_KEY),
    }
    models = [
        {"model": m, "provider": provider_for(m), "available": have_key.get(provider_for(m), False)}
        for m in sorted(KNOWN_MODELS)
    ]
    return {
        "current": _agent_ref._model if _agent_ref else config.AGENT_MODEL,
        "models": models,
    }


@app.post("/api/model")
async def set_model_endpoint(request: Request):
    if not _agent_ref:
        return JSONResponse({"error": "agent not ready"}, status_code=503)
    body = await request.json()
    model = (body.get("model") or "").strip()
    if not model:
        return JSONResponse({"error": "no model given"}, status_code=400)
    message = _agent_ref.set_model(model)
    ok = message.startswith("Switched")
    return JSONResponse(
        {"ok": ok, "message": message, "model": _agent_ref._model},
        status_code=200 if ok else 400,
    )


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


# --- Tier-4: Reflections ---
@app.get("/api/reflections")
def list_reflections_endpoint(status: str = "pending", limit: int = 100):
    return refl_mod.list_reflections(status=status, limit=limit)


@app.post("/api/reflections/{reflection_id}/apply")
def apply_reflection_endpoint(reflection_id: int, payload: dict = None):
    accept = (payload or {}).get("accept", True)
    return {"result": refl_mod.apply_reflection(reflection_id, accept=accept)}


@app.post("/api/reflections/run")
def run_reflection_endpoint(payload: dict = None):
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    hours = (payload or {}).get("hours", 24)
    return refl_mod.consolidate(client, hours=int(hours))


# --- Tier-4: Knowledge Graph ---
@app.get("/api/entities")
def list_entities(kind: str = "", limit: int = 100):
    if kind:
        return ent_mod.query_by_kind(kind, limit=limit)
    return ent_mod.subgraph(limit_nodes=limit)


@app.get("/api/entities/query")
def query_entity_endpoint(name: str, hops: int = 1):
    return ent_mod.query_entity(name, hops=hops)


@app.post("/api/entities")
def upsert_entity_endpoint(payload: dict):
    return ent_mod.upsert_entity(
        payload["name"],
        kind=payload.get("kind", "concept"),
        properties=payload.get("properties") or {},
        importance=int(payload.get("importance", 5)),
    )


@app.post("/api/entities/relate")
def relate_endpoint(payload: dict):
    return ent_mod.relate(
        payload["from_name"], payload["to_name"], payload["kind"],
        from_kind=payload.get("from_kind", "concept"),
        to_kind=payload.get("to_kind", "concept"),
        properties=payload.get("properties") or {},
        confidence=float(payload.get("confidence", 1.0)),
    )


@app.delete("/api/entities/{entity_id}")
def delete_entity_endpoint(entity_id: int):
    return {"result": ent_mod.delete_entity(entity_id)}


# --- Tier-4: Telemetry & Replay ---
@app.get("/api/telemetry")
def telemetry_summary(days: int = 7):
    return tel_mod.summary(days=days)


@app.get("/api/telemetry/sessions")
def telemetry_sessions(limit: int = 30):
    return tel_mod.list_recent_sessions(limit=limit)


@app.get("/api/replay/{session_id}")
def replay_session_endpoint(session_id: int):
    return tel_mod.replay_session(session_id)


@app.get("/api/turns/search")
def search_turns_endpoint(q: str, limit: int = 20, session_id: int = None):
    return longterm.search_turns(q, limit=limit, session_id=session_id)


# --- Tier-4: Phone (Twilio webhooks + status) ---
@app.get("/api/phone/status")
def phone_status():
    return {
        "configured": bool(getattr(config, "TWILIO_SID", "")) and bool(getattr(config, "TWILIO_AUTH_TOKEN", "")),
        "from_number": getattr(config, "TWILIO_FROM_NUMBER", ""),
        "allowed_numbers": getattr(config, "PHONE_ALLOWED_NUMBERS", []),
    }


@app.post("/api/phone/sms")
def phone_sms_endpoint(payload: dict):
    return {"result": phone_mod.sms_send(payload["to"], payload["body"])}


@app.post("/twilio/sms")
async def twilio_inbound_sms(request: Request):
    form = await request.form()
    from_number = form.get("From", "")
    body = form.get("Body", "")
    twiml = phone_mod.dispatch_inbound_sms(from_number, body)
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/voice")
async def twilio_inbound_voice(request: Request):
    form = await request.form()
    from_number = form.get("From", "")
    speech_result = form.get("SpeechResult", "")
    twiml = phone_mod.dispatch_inbound_voice(from_number, speech_result or None)
    return Response(content=twiml, media_type="application/xml")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, lambda: telegram_mod.dispatch_inbound(update))
    return {"ok": True}


@app.get("/api/telegram/status")
def telegram_status():
    return {
        "configured": telegram_mod.is_configured(),
        "allowed_chat_ids": getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", []),
    }


@app.post("/discord/interactions")
async def discord_interactions(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Signature-Ed25519", "")
    ts = request.headers.get("X-Signature-Timestamp", "")
    if not discord_mod.verify_signature(sig, ts, body):
        return Response(content="invalid request signature", status_code=401)
    interaction = json.loads(body)
    return JSONResponse(discord_mod.dispatch_interaction(interaction))


@app.get("/api/discord/status")
def discord_status():
    return {
        "configured": discord_mod.is_configured(),
        "allowed_user_ids": getattr(config, "DISCORD_ALLOWED_USER_IDS", []),
    }


# --- Chat ---
@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global _chat_lock
    if _chat_lock is None:
        _chat_lock = asyncio.Lock()

    body = await request.json()
    user_text = (body.get("message") or "").strip()
    chat_id = body.get("chat_id") or str(uuid.uuid4())[:8]

    if not user_text:
        return JSONResponse({"error": "empty message"}, status_code=400)
    if not _agent_ref:
        return JSONResponse({"error": "agent not ready"}, status_code=503)

    async with _chat_lock:
        streamer = ChatStreamer(chat_id)
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: _agent_ref.run(user_text, include_screenshot=False, streamer=streamer, channel_id=f"dashboard:{chat_id}"),
            )
        except Exception as e:
            ws_manager.broadcast_threadsafe({"type": "chat_error", "error": str(e), "chat_id": chat_id})
            return JSONResponse({"error": str(e)}, status_code=500)

    ws_manager.broadcast_threadsafe({"type": "chat_done", "response": response, "chat_id": chat_id})
    return {"ok": True, "response": response, "chat_id": chat_id}


# --- Council: Claude / GPT / Gemini debate ---
@app.post("/api/council")
async def council_endpoint(request: Request):
    body = await request.json()
    question = (body.get("question") or "").strip()
    rounds = max(0, min(3, int(body.get("rounds", 1))))
    if not question:
        return JSONResponse({"error": "empty question"}, status_code=400)

    from agent import council

    def _progress(msg: str):
        ws_manager.broadcast_threadsafe({"type": "council_progress", "message": msg})

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: council.convene(question, rounds=rounds, on_progress=_progress)
        )
    except Exception as e:
        ws_manager.broadcast_threadsafe({"type": "council_error", "error": str(e)})
        return JSONResponse({"error": str(e)}, status_code=500)

    payload = {
        "question": result.question,
        "members": result.members,
        "final_answer": result.final_answer,
        "transcript": result.transcript,
    }
    ws_manager.broadcast_threadsafe({"type": "council_done", **payload})
    return {"ok": True, **payload}


# --- Voice: speech-to-text (OpenAI Whisper) ---
@app.post("/api/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    if not config.OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY not set — voice input needs it"}, status_code=503)
    data = await file.read()
    if not data:
        return JSONResponse({"error": "empty audio"}, status_code=400)

    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    name = file.filename or "speech.webm"
    loop = asyncio.get_event_loop()
    try:
        tr = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(model="whisper-1", file=(name, data)),
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"text": (getattr(tr, "text", "") or "").strip()}


# --- Voice: text-to-speech (OpenAI TTS) ---
@app.post("/api/speak")
async def speak_endpoint(request: Request):
    if not config.OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY not set"}, status_code=503)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)

    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    voice = getattr(config, "OPENAI_TTS_VOICE", "alloy")
    loop = asyncio.get_event_loop()
    try:
        audio = await loop.run_in_executor(
            None,
            lambda: client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000]).content,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return Response(content=audio, media_type="audio/mpeg")


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
def start_in_background(port: int = 7860, host: str | None = None) -> threading.Thread:
    import uvicorn

    def runner():
        _host = host if host is not None else config.DASHBOARD_HOST
        cfg = uvicorn.Config(app, host=_host, port=port, log_level="warning")
        server = uvicorn.Server(cfg)
        server.run()

    t = threading.Thread(target=runner, daemon=True, name="DashboardServer")
    t.start()
    return t
