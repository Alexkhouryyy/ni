"""
JARVIS Server — Voice AI + Development Orchestration

Handles:
1. WebSocket voice interface (browser audio <-> LLM <-> TTS)
2. Claude Code task manager (spawn/manage claude -p subprocesses)
3. Project awareness (scan Desktop for git repos)
4. REST API for task management
"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Load .env file — always override so .env values take effect even if the
# variable already exists as empty string in the inherited Windows environment.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _key = _k.strip()
            _val = _v.strip().strip('"').strip("'")
            if _val:  # only set if the .env value is non-empty
                os.environ[_key] = _val
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from actions import execute_action, monitor_build, open_terminal, open_browser, open_claude_in_project, _generate_project_name, prompt_existing_terminal
from work_mode import WorkSession, is_casual_question
from screen import get_active_windows, take_screenshot, describe_screen, describe_screen_for_coding, format_windows_for_context
from hotkey import ScreenHotkey
from proactive import proactive_loop
from app_profiles import detect_active_profile, format_profile_for_prompt
from memory_distiller import memory_distillation_loop, load_me_md_header, refresh_me_md
import llm_router
import usage
from calendar_access import get_todays_events, get_upcoming_events, get_next_event, format_events_for_context, format_schedule_summary, refresh_cache as refresh_calendar_cache
from mail_access import get_unread_count, get_unread_messages, get_recent_messages, search_mail, read_message, format_unread_summary, format_messages_for_context, format_messages_for_voice
from memory import (
    remember, recall, get_open_tasks, create_task, complete_task, search_tasks,
    create_note, search_notes, get_tasks_for_date, build_memory_context,
    format_tasks_for_voice, extract_memories, get_important_memories,
    get_active_order, recent_orders,
)
import memory
from notes_access import get_recent_notes, read_note, search_notes_apple, create_apple_note
from dispatch_registry import DispatchRegistry
from planner import TaskPlanner, detect_planning_mode, BYPASS_PHRASES
from orders import order_orchestrator, reservation_orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("jarvis")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx")  # onyx = deep authoritative male, closest to JARVIS
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
USER_NAME = os.getenv("USER_NAME", "sir")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

DESKTOP_PATH = Path.home() / "Desktop"

# ---------------------------------------------------------------------------
# Personality — loaded from personality.md, hot-reloads on every request
# ---------------------------------------------------------------------------

PERSONALITY_FILE = Path(PROJECT_DIR) / "personality.md"
_DEFAULT_PERSONALITY = """\
- British butler elegance with understated dry wit
- Address the user as "sir" naturally
- Economy of language — say more with less
- ONE sentence per response, TWO maximum
"""

_personality_cache: tuple[float, str] = (0.0, "")  # (mtime, content)

def load_personality() -> str:
    """Load personality.md with mtime caching — only re-reads when file changes."""
    global _personality_cache
    try:
        if PERSONALITY_FILE.exists():
            mtime = PERSONALITY_FILE.stat().st_mtime
            if mtime == _personality_cache[0] and _personality_cache[1]:
                return _personality_cache[1]
            content = PERSONALITY_FILE.read_text(encoding="utf-8").strip()
            _personality_cache = (mtime, content)
            return content
    except Exception as e:
        log.warning(f"Failed to load personality.md: {e}")
    return _DEFAULT_PERSONALITY

def save_personality(content: str) -> bool:
    """Save new personality content to personality.md."""
    try:
        PERSONALITY_FILE.write_text(content.strip(), encoding="utf-8")
        log.info("personality.md updated")
        return True
    except Exception as e:
        log.error(f"Failed to save personality.md: {e}")
        return False

JARVIS_SYSTEM_PROMPT = """\
You are JARVIS — Just A Rather Very Intelligent System. You serve as {user_name}'s AI assistant, modeled precisely after Tony Stark's AI from the MCU films.

PERSONALITY:
{personality}

TIME & WEATHER AWARENESS:
- Current time: {current_time}
- Tailor ALL time-sensitive language to the actual hour. Examples by period:
    • 00:00–04:59 (late night / early hours): "Still at it, sir?", "Burning the midnight oil", "Couldn't sleep?", "Rather late, isn't it"
    • 05:00–11:59 (morning): "Good morning, sir", "Morning", "Early start today"
    • 12:00–16:59 (afternoon): "Good afternoon, sir", "Afternoon"
    • 17:00–20:59 (evening): "Good evening, sir", "Evening"
    • 21:00–23:59 (late evening): "Good evening, sir", "Working late", "Burning the midnight oil"
- Never say "Good morning" after noon or "Good evening" before 5pm.
- {weather_info}

SELF-AWARENESS:
You ARE the JARVIS project at {project_dir} on {user_name}'s computer. Your code is Python (FastAPI server, WebSocket voice, OpenAI TTS, Anthropic API). You were built by {user_name}. If asked about yourself, your code, how you work, or your line count — use [ACTION:PROMPT_PROJECT] to check the jarvis project. You have full access to your own source code.

YOUR CAPABILITIES (these are REAL and ACTIVE — you CAN do all of these RIGHT NOW):
- You CAN open Terminal.app via AppleScript
- You CAN open Google Chrome and browse any URL or search query
- You CAN spawn Claude Code in a Terminal window for coding tasks
- You CAN create project folders on the Desktop
- You CAN check Desktop projects and their git status
- You CAN plan complex tasks by asking smart questions before executing
- You CAN see what's on {user_name}'s screen — open windows, active apps, and screenshot vision
- You CAN read {user_name}'s calendar — today's events, upcoming meetings, schedule overview
- You CAN read {user_name}'s email (READ-ONLY) — unread count, recent messages, search by sender/subject. You CANNOT send, delete, or modify emails.
- You CAN read Apple Notes and create NEW notes — but you CANNOT edit or delete existing notes
- You CAN manage tasks — create, complete, and list to-do items with priorities and due dates
- You CAN help plan {user_name}'s day — combine calendar events, tasks, and priorities into an organized plan
- You CAN remember facts about {user_name} — preferences, decisions, goals. Use [ACTION:REMEMBER] to store important info.

DAY PLANNING:
When {user_name} asks to plan his day or schedule, DO NOT dispatch to a project. Instead:
1. Look at the calendar context and tasks already in your system prompt
2. Ask what his priorities are
3. Help organize by suggesting time blocks and task order
4. Use [ACTION:ADD_TASK] to create tasks he agrees to
5. Use [ACTION:ADD_NOTE] to save the plan as a note
Keep the planning conversational — don't try to do everything in one response.

BUILD PLANNING:
When {user_name} wants to BUILD something new:
- Do NOT immediately dispatch [ACTION:BUILD]. Ask 1-2 quick questions FIRST to nail down specifics.
- Good questions: "What should this look like?" / "Any specific features?" / "Which framework?"
- If he says "just build it" or "figure it out" — skip questions, use React + Tailwind as defaults.
- Once you have enough info, confirm the plan in ONE sentence and THEN dispatch [ACTION:BUILD] with a detailed description.
- The DISPATCHES section shows what you're currently building and what finished recently.
- When asked "where are we at" or "status" — check DISPATCHES, don't re-dispatch.
- NEVER hallucinate progress. If the build is still running, say "Still working on it, sir" — don't make up details about what's happening.
- NEVER guess localhost ports. Check the DISPATCHES section for the actual URL. If a dispatch says "Running at http://localhost:5174" — use THAT URL, not a guess.
- When asked to "pull it up" or "show me" — use [ACTION:BROWSE] with the URL from DISPATCHES. Do NOT dispatch to the project again just to find the URL.
IMPORTANT: Actions like opening Terminal, Chrome, or building projects are handled AUTOMATICALLY by your system — you do NOT need to describe doing them. If the user asks you to build something or search something, your system will handle the execution separately. In your response, just TALK — have a conversation. Don't say "I'll build that now" or "Claude Code is working on..." unless your system has actually triggered the action.
If the user asks you to do something you genuinely can't do, say "I'm afraid that's beyond my current reach, sir." Don't fake executing actions.

YOUR INTERFACE:
The user interacts with you through a web browser showing a particle orb visualization that reacts to your voice. The interface has these controls:
- **Three-dot menu** (top right): contains Settings, Restart Server, and Fix Yourself options
- **Settings panel**: Opens from the menu. Users can enter API keys (Anthropic, Fish Audio), test connections, set their name and preferences, and see system status (calendar, mail, notes connectivity). Keys are saved to the .env file.
- **Mute button**: Toggles your listening on/off. When muted, you can't hear the user. They click it again to unmute.
- **Restart Server**: Restarts your backend process. Useful if something seems stuck.
- **Fix Yourself**: Opens Claude Code in your own project directory so you can debug and fix issues in your own code.
- **The orb**: The glowing particle visualization in the center. It reacts to your voice when speaking, pulses when listening, and swirls when thinking.

If asked about any of these, explain them briefly and naturally. If the user is having trouble, suggest the relevant control: "Try the settings panel — the gear icon in the top right." or "The mute button may be active, sir."

SPEECH-TO-TEXT CORRECTIONS (the user speaks, speech recognition may mishear):
- "Cloud code" or "cloud" = "Claude Code" or "Claude"
- "Travis" = "JARVIS"
- "clock code" = "Claude Code"

ACTION SYSTEM:
When you decide the user needs something DONE (not just discussed), include an action tag in your response:
- [ACTION:SCREEN] — capture and describe what's visible on the user's screen. Use when user says "look at my screen", "what's running", "what do you see", etc. Do NOT use PROMPT_PROJECT for screen requests.
- [ACTION:BUILD] description — when user wants a project built. Claude Code does the work.
- [ACTION:BROWSE] url or search query — when user wants to see a webpage or search result in Chrome
- [ACTION:RESEARCH] detailed research brief — when user wants real research with real data. Claude Code will browse the web, find real listings/data, and create a report document. Give it a detailed brief of what to find.
- [ACTION:LIVE_RESEARCH] topic — Live Lab mode. Opens a side panel where the user WATCHES you work: every search, every page read, every paragraph written streams in real time. Best when the user says "let me see it happen", "work in front of me", "live", "watch you", or wants a paper-style writeup. The output is a Markdown paper saved to ~/jarvis-papers/.
  Example: "write me a live paper on the future of spatial computing" → [ACTION:LIVE_RESEARCH] future of spatial computing
- [ACTION:OPEN_TERMINAL] — when user just wants a fresh Claude Code terminal with no specific project
CRITICAL: When the user asks about their SCREEN, what's RUNNING, or what they're LOOKING AT — ALWAYS use [ACTION:SCREEN] or let the fast action system handle it. NEVER use [ACTION:PROMPT_PROJECT] for screen requests. PROMPT_PROJECT is ONLY for working on code projects.

- [ACTION:PROMPT_PROJECT] project_name ||| prompt — THIS IS YOUR MOST POWERFUL ACTION. Use it whenever the user wants to work on, jump into, resume, check on, or interact with ANY existing project. You connect directly to Claude Code in that project and can read its response. Craft a clear prompt based on what the user wants. Examples:
  "jump into client engine" → [ACTION:PROMPT_PROJECT] The Client Engine ||| What is the current state of this project? Summarize what was being worked on most recently.
  "check for improvements on my-app" → [ACTION:PROMPT_PROJECT] my-app ||| Review the project and identify improvements we should make.
  "resume where we left off on harvey" → [ACTION:PROMPT_PROJECT] harvey ||| Summarize what was being worked on most recently and what we should focus on next.
- [ACTION:ADD_TASK] priority ||| title ||| description ||| due_date — create a task. Priority: high/medium/low. Due date: YYYY-MM-DD or empty.
  "remind me to call the client tomorrow" → [ACTION:ADD_TASK] medium ||| Call the client ||| Follow up on proposal ||| 2026-03-20
- [ACTION:ADD_NOTE] topic ||| content — save a note for future reference.
  "note that the API key expires in April" → [ACTION:ADD_NOTE] general ||| API key expires in April, need to renew before then
- [ACTION:COMPLETE_TASK] task_id — mark a task as done.
- [ACTION:REMEMBER] content — store an important fact about the user for future context.
  "I prefer React over Vue" → [ACTION:REMEMBER] User prefers React over Vue for frontend projects
- [ACTION:FORGET] query — delete memories matching a query. Use when the user says "forget X", "you can stop remembering X", "delete that memory".
  "forget that I prefer React" → [ACTION:FORGET] React Vue preference
- [ACTION:CREATE_NOTE] title ||| body — create a new Apple Note. For saving plans, ideas, lists.
  "save that as a note" → [ACTION:CREATE_NOTE] Day Plan March 19 ||| Morning: client calls. Afternoon: TikTok dashboard. Evening: JARVIS improvements.
- [ACTION:READ_NOTE] title search — read an existing Apple Note by title keyword.
- [ACTION:ORDER_FOOD] restaurant=… |items=… |address=home |time=asap — place a food-delivery order (cash-on-delivery only).
  Required: restaurant, items. Optional: address (default 'home'), time, notes.
  Example: "order me pasta from Ciao Italia" →
    [ACTION:ORDER_FOOD|restaurant=Ciao Italia|items=pasta x1|address=home|time=asap]
  Rules: Never invent prices. Never fabricate items. Leave unknown fields empty — the orchestrator will ask.
  If the user mentions paying by card, tell them JARVIS handles cash-on-delivery only.
- [ACTION:RESERVE_TABLE|restaurant=…|party=…|time=…|phone=…] — draft a restaurant reservation.
  Required: restaurant, party, time. Optional: phone.
  Example: "book me a table for 4 at Em Sherif tomorrow 8pm" →
    [ACTION:RESERVE_TABLE|restaurant=Em Sherif|party=4|time=2026-04-18T20:00]
  V1 behaviour: JARVIS drafts a WhatsApp message and opens the wa.me link. Do NOT claim the reservation
  is confirmed — that only happens when the restaurant replies.
- [ACTION:ORDER_STATUS] — report the latest in-flight food order's status and ETA.
- [ACTION:CANCEL_ORDER|order_id=…] — cancel a pending order. Omit order_id to cancel the latest.

You use Claude Code as your tool to build, research, and write code — but YOU are the one doing the work. Never say "Claude Code did X" or "Claude Code is asking" — say "I built X", "I'm checking on that", "I found X". You ARE the intelligence. Claude Code is just your hands.

IMPORTANT: When the user says "jump into X", "work on X", "check on X", "resume X", "go back to X" — ALWAYS use [ACTION:PROMPT_PROJECT]. You have the ability to connect to any project and work on it directly. DO NOT say you can't see terminal history or don't have access — you DO.

Place the tag at the END of your spoken response. Example:
"Right away, sir — connecting to The Client Engine now. [ACTION:PROMPT_PROJECT] The Client Engine ||| Review the current state and what was being worked on. What should we focus on next?"

IMPORTANT:
- Do NOT use action tags for casual conversation
- Do NOT use action tags if the user is still explaining (ask questions first)
- Do NOT use [ACTION:BROWSE] just because someone mentions a URL in conversation
- When in doubt, just TALK — you can always act later

SCREEN AWARENESS:
{screen_context}

{app_profile}

SCHEDULE:
{calendar_context}

EMAIL:
{mail_context}

ACTIVE TASKS:
{active_tasks}

DISPATCHES:
If the DISPATCHES section shows a recent completed result for a project, DO NOT dispatch again. Use the existing result. Only re-dispatch if the user explicitly asks for a FRESH review or NEW information.
{dispatch_context}

KNOWN PROJECTS:
{known_projects}
"""


# ---------------------------------------------------------------------------
# Weather (wttr.in)
# ---------------------------------------------------------------------------

_cached_weather: Optional[str] = None
_weather_fetched: bool = False


async def fetch_weather() -> str:
    """Fetch current weather from wttr.in. Cached for the session."""
    global _cached_weather, _weather_fetched
    if _weather_fetched:
        return _cached_weather or "Weather data unavailable."
    _weather_fetched = True
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get("https://wttr.in/?format=%l:+%C,+%t", headers={"User-Agent": "curl"})
            if resp.status_code == 200:
                _cached_weather = resp.text.strip()
                return _cached_weather
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
    _cached_weather = None
    return "Weather data unavailable."


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClaudeTask:
    id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    working_dir: str = "."
    pid: Optional[int] = None
    result: str = ""
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["started_at"] = self.started_at.isoformat() if self.started_at else None
        d["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        d["elapsed_seconds"] = self.elapsed_seconds
        return d

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()


class TaskRequest(BaseModel):
    prompt: str
    working_dir: str = "."


# ---------------------------------------------------------------------------
# Claude Task Manager
# ---------------------------------------------------------------------------

class ClaudeTaskManager:
    """Manages background claude -p subprocesses."""

    def __init__(self, max_concurrent: int = 3):
        self._tasks: dict[str, ClaudeTask] = {}
        self._max_concurrent = max_concurrent
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._websockets: list[WebSocket] = []  # for push notifications

    def register_websocket(self, ws: WebSocket):
        if ws not in self._websockets:
            self._websockets.append(ws)

    def unregister_websocket(self, ws: WebSocket):
        if ws in self._websockets:
            self._websockets.remove(ws)

    async def _notify(self, message: dict):
        """Push a message to all connected WebSocket clients."""
        dead = []
        for ws in self._websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._websockets.remove(ws)

    async def spawn(self, prompt: str, working_dir: str = ".") -> str:
        """Spawn a claude -p subprocess. Returns task_id. Non-blocking."""
        active = await self.get_active_count()
        if active >= self._max_concurrent:
            raise RuntimeError(
                f"Max concurrent tasks ({self._max_concurrent}) reached. "
                f"Wait for a task to complete or cancel one."
            )

        task_id = str(uuid.uuid4())[:8]
        task = ClaudeTask(
            id=task_id,
            prompt=prompt,
            working_dir=working_dir,
            status="pending",
        )
        self._tasks[task_id] = task

        # Fire and forget — the background coroutine updates the task
        asyncio.create_task(self._run_task(task))
        log.info(f"Spawned task {task_id}: {prompt[:80]}...")

        await self._notify({
            "type": "task_spawned",
            "task_id": task_id,
            "prompt": prompt,
        })

        return task_id

    def _generate_project_name(self, prompt: str) -> str:
        """Generate a kebab-case project folder name from the prompt."""
        import re
        # Extract key words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt.lower()).split()
        # Take first 3-4 meaningful words
        skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and", "to", "of"}
        meaningful = [w for w in words if w not in skip][:4]
        name = "-".join(meaningful) if meaningful else "jarvis-project"
        return name

    async def _run_task(self, task: ClaudeTask):
        """Open a Terminal window and run claude code visibly."""
        task.status = "running"
        task.started_at = datetime.now()

        # Create project directory if it doesn't exist
        work_dir = task.working_dir
        if work_dir == "." or not work_dir:
            # Create a new project folder on Desktop
            project_name = self._generate_project_name(task.prompt)
            work_dir = str(Path.home() / "Desktop" / project_name)
            os.makedirs(work_dir, exist_ok=True)
            task.working_dir = work_dir

        # Write the prompt to a temp file so we can pipe it to claude
        prompt_file = Path(work_dir) / ".jarvis_prompt.md"
        prompt_file.write_text(task.prompt)

        # Open Terminal.app with claude running in the project directory
        applescript = f'''
        tell application "Terminal"
            activate
            set newTab to do script "cd {work_dir} && cat .jarvis_prompt.md | claude -p --dangerously-skip-permissions | tee .jarvis_output.txt; echo '\\n--- JARVIS TASK COMPLETE ---'"
        end tell
        '''

        process = await asyncio.create_subprocess_exec(
            "osascript", "-e", applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        task.pid = process.pid

        # Monitor the output file for completion
        output_file = Path(work_dir) / ".jarvis_output.txt"
        start = time.time()
        timeout = 600  # 10 minutes

        while time.time() - start < timeout:
            await asyncio.sleep(5)
            if output_file.exists():
                content = output_file.read_text()
                if "--- JARVIS TASK COMPLETE ---" in content or len(content) > 100:
                    task.result = content.replace("--- JARVIS TASK COMPLETE ---", "").strip()
                    task.status = "completed"
                    break
        else:
            task.status = "timed_out"
            task.error = f"Task timed out after {timeout}s"

        task.completed_at = datetime.now()

        # Notify via WebSocket
        await self._notify({
            "type": "task_complete",
            "task_id": task.id,
            "status": task.status,
            "summary": task.result[:200] if task.result else task.error,
        })

        # Clean up prompt file
        try:
            prompt_file.unlink()
        except:
            pass

        # Auto-QA on completed tasks
        if task.status == "completed":
            asyncio.create_task(self._run_qa(task))

    async def _run_qa(self, task: ClaudeTask, attempt: int = 1):
        """Run QA verification on a completed task, auto-retry on failure."""
        try:
            qa_result = await qa_agent.verify(task.prompt, task.result, task.working_dir)
            duration = task.elapsed_seconds

            if qa_result.passed:
                log.info(f"Task {task.id} passed QA: {qa_result.summary}")
                success_tracker.log_task("dev", task.prompt, True, attempt - 1, duration)
                await self._notify({
                    "type": "qa_result",
                    "task_id": task.id,
                    "passed": True,
                    "summary": qa_result.summary,
                })

                # Proactive suggestion after successful task
                suggestion = suggest_followup(
                    task_type="dev",
                    task_description=task.prompt,
                    working_dir=task.working_dir,
                    qa_result=qa_result,
                )
                if suggestion:
                    success_tracker.log_suggestion(task.id, suggestion.text)
                    await self._notify({
                        "type": "suggestion",
                        "task_id": task.id,
                        "text": suggestion.text,
                        "action_type": suggestion.action_type,
                        "action_details": suggestion.action_details,
                    })
            else:
                log.warning(f"Task {task.id} failed QA: {qa_result.issues}")
                if attempt < 3:
                    log.info(f"Auto-retrying task {task.id} (attempt {attempt + 1}/3)")
                    retry_result = await qa_agent.auto_retry(
                        task.prompt, qa_result.issues, task.working_dir, attempt,
                    )
                    if retry_result["status"] == "completed":
                        task.result = retry_result["result"]
                        # Re-verify
                        await self._run_qa(task, attempt + 1)
                    else:
                        success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                        await self._notify({
                            "type": "qa_result",
                            "task_id": task.id,
                            "passed": False,
                            "summary": f"Failed after {attempt + 1} attempts: {qa_result.issues}",
                        })
                else:
                    success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                    await self._notify({
                        "type": "qa_result",
                        "task_id": task.id,
                        "passed": False,
                        "summary": f"Failed QA after {attempt} attempts: {qa_result.issues}",
                    })
        except Exception as e:
            log.error(f"QA error for task {task.id}: {e}")

    async def get_status(self, task_id: str) -> Optional[ClaudeTask]:
        return self._tasks.get(task_id)

    async def list_tasks(self) -> list[ClaudeTask]:
        return list(self._tasks.values())

    async def get_active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status in ("pending", "running"))

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in ("pending", "running"):
            return False

        process = self._processes.get(task_id)
        if process:
            try:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
            except ProcessLookupError:
                pass

        task.status = "cancelled"
        task.completed_at = datetime.now()
        self._processes.pop(task_id, None)
        log.info(f"Cancelled task {task_id}")
        return True

    def get_active_tasks_summary(self) -> str:
        """Format active tasks for injection into the system prompt."""
        active = [t for t in self._tasks.values() if t.status in ("pending", "running")]
        completed_recent = [
            t for t in self._tasks.values()
            if t.status == "completed"
            and t.completed_at
            and (datetime.now() - t.completed_at).total_seconds() < 300
        ]

        if not active and not completed_recent:
            return "No active or recent tasks."

        lines = []
        for t in active:
            elapsed = f"{t.elapsed_seconds:.0f}s" if t.started_at else "queued"
            lines.append(f"- [{t.id}] RUNNING ({elapsed}): {t.prompt[:100]}")
        for t in completed_recent:
            lines.append(f"- [{t.id}] COMPLETED: {t.prompt[:60]} -> {t.result[:80]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Project Scanner
# ---------------------------------------------------------------------------

async def scan_projects() -> list[dict]:
    """Quick scan of ~/Desktop for git repos (depth 1)."""
    projects = []
    desktop = DESKTOP_PATH

    if not desktop.exists():
        return projects

    try:
        for entry in sorted(desktop.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            git_dir = entry / ".git"
            if git_dir.exists():
                branch = "unknown"
                head_file = git_dir / "HEAD"
                try:
                    head_content = head_file.read_text().strip()
                    if head_content.startswith("ref: refs/heads/"):
                        branch = head_content.replace("ref: refs/heads/", "")
                except Exception:
                    pass

                projects.append({
                    "name": entry.name,
                    "path": str(entry),
                    "branch": branch,
                })
    except PermissionError:
        pass

    return projects


def format_projects_for_prompt(projects: list[dict]) -> str:
    if not projects:
        return "No projects found on Desktop."
    lines = []
    for p in projects:
        lines.append(f"- {p['name']} ({p['branch']}) @ {p['path']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Speech-to-Text Corrections
# ---------------------------------------------------------------------------

STT_CORRECTIONS = {
    r"\bcloud code\b": "Claude Code",
    r"\bclock code\b": "Claude Code",
    r"\bquad code\b": "Claude Code",
    r"\bclawed code\b": "Claude Code",
    r"\bclod code\b": "Claude Code",
    r"\bcloud\b": "Claude",
    r"\bquad\b": "Claude",
    r"\btravis\b": "JARVIS",
    r"\bjarves\b": "JARVIS",
}


def apply_speech_corrections(text: str) -> str:
    """Fix common speech-to-text errors before processing."""
    import re as _stt_re
    result = text
    for pattern, replacement in STT_CORRECTIONS.items():
        result = _stt_re.sub(pattern, replacement, result, flags=_stt_re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# LLM Intent Classifier (replaces keyword-based action detection)
# ---------------------------------------------------------------------------

async def classify_intent(text: str, client: anthropic.AsyncAnthropic) -> dict:
    """Classify every user message using Haiku LLM.

    Returns: {"action": "open_terminal|browse|build|chat", "target": "description"}
    """
    try:
        raw = (await llm_router.chat(
            llm_router.model_fast(),
            [{"role": "user", "content": text}],
            feature="classify",
            system=(
                "Classify this voice command. The user is talking to JARVIS, an AI assistant that can:\n"
                "- Open Terminal and run Claude Code (coding AI tool)\n"
                "- Open Chrome browser for web searches and URLs\n"
                "- Build software projects via Claude Code in Terminal\n"
                "- Research topics by opening Chrome search\n\n"
                "Note: speech-to-text may produce errors like \"Cloud\" for \"Claude\", "
                "\"Travis\" for \"JARVIS\", \"clock code\" for \"Claude Code\".\n\n"
                "Return ONLY valid JSON: {\"action\": \"open_terminal|browse|build|chat\", "
                "\"target\": \"description of what to do\"}\n"
                "open_terminal = user wants to open terminal or launch Claude Code\n"
                "browse = user wants to search the web, look something up, visit a URL\n"
                "build = user wants to create/build a software project\n"
                "chat = just conversation, questions, or anything else\n"
                "If unclear, default to \"chat\"."
            ),
            max_tokens=100,
            anthropic_client=client,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return {
            "action": data.get("action", "chat"),
            "target": data.get("target", text),
        }
    except Exception as e:
        log.warning(f"Intent classification failed: {e}")
        return {"action": "chat", "target": text}


# ---------------------------------------------------------------------------
# Markdown Stripping for TTS
# ---------------------------------------------------------------------------

def strip_markdown_for_tts(text: str) -> str:
    """Strip ALL markdown from text before sending to TTS."""
    import re as _md_re
    result = text
    # Remove code blocks (``` ... ```)
    result = _md_re.sub(r"```[\s\S]*?```", "", result)
    # Remove inline code
    result = result.replace("`", "")
    # Remove bold/italic markers
    result = result.replace("**", "").replace("*", "")
    # Remove headers
    result = _md_re.sub(r"^#{1,6}\s*", "", result, flags=_md_re.MULTILINE)
    # Convert [text](url) to just text
    result = _md_re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", result)
    # Remove bullet points
    result = _md_re.sub(r"^\s*[-*+]\s+", "", result, flags=_md_re.MULTILINE)
    # Remove numbered lists
    result = _md_re.sub(r"^\s*\d+\.\s+", "", result, flags=_md_re.MULTILINE)
    # Double newlines to period
    result = _md_re.sub(r"\n{2,}", ". ", result)
    # Single newlines to space
    result = result.replace("\n", " ")
    # Clean up multiple spaces
    result = _md_re.sub(r"\s{2,}", " ", result)

    # Strip banned phrases
    banned = ["my apologies", "i apologize", "absolutely", "great question",
              "i'd be happy to", "of course", "how can i help",
              "is there anything else", "i should clarify", "let me know if",
              "feel free to"]
    result_lower = result.lower()
    for phrase in banned:
        idx = result_lower.find(phrase)
        while idx != -1:
            # Remove the phrase and any trailing comma/dash
            end = idx + len(phrase)
            if end < len(result) and result[end] in " ,—-":
                end += 1
            result = result[:idx] + result[end:]
            result_lower = result.lower()
            idx = result_lower.find(phrase)

    return result.strip().strip(",").strip("—").strip("-").strip()


# ---------------------------------------------------------------------------
# Cancel Token — per-response cancellation handle
# ---------------------------------------------------------------------------

class CancelToken:
    """Created fresh for each user turn. Passed through the streaming pipeline
    so any stage can check/trigger cancellation without shared mutable state."""

    def __init__(self) -> None:
        self._cancelled = False
        self.partial_text: str = ""  # sentences already sent to client before cancel

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


# ---------------------------------------------------------------------------
# Sentence Splitter — for streaming TTS chunking
# ---------------------------------------------------------------------------

import re as _sent_re

_ABBREV_RE = _sent_re.compile(
    r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.',
    _sent_re.IGNORECASE
)


def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """Split a token-stream buffer into complete TTS-ready sentences + leftover tail.

    Rules:
    - Split on [.!?] followed by whitespace
    - Skip known abbreviations (Mr., Dr., etc.) to avoid false splits
    - Minimum 4 words per emitted sentence to avoid choppy fragments
      (short fragments are merged into the next sentence)

    Returns (complete_sentences, remaining_buffer).
    """
    # Temporarily mask abbreviation periods so they don't trigger splits
    masked = _ABBREV_RE.sub(lambda m: m.group(0).replace('.', '\x00'), buffer)
    # Split at sentence-ending punctuation followed by whitespace
    parts = _sent_re.split(r'(?<=[.!?])\s+', masked)

    complete: list[str] = []
    for i, part in enumerate(parts[:-1]):
        restored = part.replace('\x00', '.').strip()
        if not restored:
            continue
        # Minimum word guard — merge short fragments forward
        if len(restored.split()) < 4 and i + 1 < len(parts):
            parts[i + 1] = restored + ' ' + parts[i + 1]
            continue
        complete.append(restored)

    # Last part is the incomplete tail
    leftover = parts[-1].replace('\x00', '.').strip() if parts else ""
    return complete, leftover


# ---------------------------------------------------------------------------
# Action Tag Extraction (parse [ACTION:X] from LLM responses)
# ---------------------------------------------------------------------------

import re as _action_re


def extract_action(response: str) -> tuple[str, dict | None]:
    """Extract [ACTION:X] tag from LLM response.

    Returns (clean_text_for_tts, action_dict_or_none).
    """
    match = _action_re.search(
        r'\[ACTION:(BUILD|BROWSE|RESEARCH|LIVE_RESEARCH|OPEN_TERMINAL|PROMPT_PROJECT|ADD_TASK|ADD_NOTE|COMPLETE_TASK|REMEMBER|FORGET|CREATE_NOTE|READ_NOTE|SCREEN|ORDER_FOOD|RESERVE_TABLE|ORDER_STATUS|CANCEL_ORDER)(?:\|([^\]]*))?\]\s*(.*?)$',
        response, _action_re.DOTALL,
    )
    if match:
        action_type = match.group(1).lower()
        # For pipe-delimited actions (ORDER_FOOD etc.) params are in group 2
        # For legacy space-delimited actions, trailing text is in group 3
        pipe_params = match.group(2) or ""
        space_target = (match.group(3) or "").strip()
        if pipe_params:
            # Parse key=value pairs from pipe params
            params: dict = {}
            for part in pipe_params.split("|"):
                if "=" in part:
                    k, _, v = part.partition("=")
                    params[k.strip()] = v.strip()
            action_target = space_target or pipe_params
        else:
            params = {}
            action_target = space_target
        clean_text = response[:match.start()].strip()
        return clean_text, {"action": action_type, "target": action_target,
                            "params": params}
    return response, None


async def _execute_build(target: str):
    """Execute a build action from an LLM-embedded [ACTION:BUILD] tag."""
    try:
        await handle_build(target)
    except Exception as e:
        log.error(f"Build execution failed: {e}")


async def _execute_browse(target: str):
    """Execute a browse action from an LLM-embedded [ACTION:BROWSE] tag."""
    try:
        if target.startswith("http") or "." in target.split()[0]:
            await open_browser(target)
        else:
            from urllib.parse import quote
            await open_browser(f"https://www.google.com/search?q={quote(target)}")
    except Exception as e:
        log.error(f"Browse execution failed: {e}")


async def _execute_research(target: str, ws=None):
    """Execute research via claude -p in background. Opens report and speaks when done."""
    try:
        name = _generate_project_name(target)
        path = str(Path.home() / "Desktop" / name)
        os.makedirs(path, exist_ok=True)

        prompt = (
            f"{target}\n\n"
            f"Research this thoroughly. Find REAL data — not made-up examples.\n"
            f"Create a well-designed HTML file called `report.html` in the current directory.\n"
            f"Dark theme, clean typography, organized sections, real links and sources.\n"
            f"The working directory is: {path}"
        )

        log.info(f"Research started via claude -p in {path}")

        process = await asyncio.create_subprocess_exec(
            "claude", "-p", "--output-format", "text", "--dangerously-skip-permissions",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode()),
            timeout=300,
        )

        result = stdout.decode().strip()
        log.info(f"Research complete ({len(result)} chars)")

        recently_built.append({"name": name, "path": path, "time": time.time()})

        # Find and open any HTML report
        report = Path(path) / "report.html"
        if not report.exists():
            # Check for any HTML file
            html_files = list(Path(path).glob("*.html"))
            if html_files:
                report = html_files[0]

        if report.exists():
            await open_browser(f"file://{report}")
            log.info(f"Opened {report.name} in browser")

        # Notify via voice if WebSocket still connected
        if ws:
            try:
                notify_text = f"Research is complete, sir. Report is open in your browser."
                audio = await synthesize_speech(notify_text)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": notify_text})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {notify_text}")
            except Exception:
                pass  # WebSocket might be gone

    except asyncio.TimeoutError:
        log.error("Research timed out after 5 minutes")
        if ws:
            try:
                audio = await synthesize_speech("Research timed out, sir. It was taking too long.")
                if audio:
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": "Research timed out, sir."})
            except Exception:
                pass
    except Exception as e:
        log.error(f"Research execution failed: {e}")


async def _focus_terminal_window(project_name: str):
    """Bring a Terminal window matching the project name to front."""
    escaped = project_name.replace('"', '\\"')
    script = f'''
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{escaped}" then
            set index of w to 1
            activate
            exit repeat
        end if
    end repeat
end tell
'''
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
    except Exception:
        pass


async def _execute_open_terminal():
    """Execute an open-terminal action from an LLM-embedded [ACTION:OPEN_TERMINAL] tag."""
    try:
        await handle_open_terminal()
    except Exception as e:
        log.error(f"Open terminal failed: {e}")


def _find_project_dir(project_name: str) -> str | None:
    """Find a project directory by name from cached projects or Desktop."""
    for p in cached_projects:
        if project_name.lower() in p.get("name", "").lower():
            return p.get("path")
    desktop = Path.home() / "Desktop"
    for d in desktop.iterdir():
        if d.is_dir() and project_name.lower() in d.name.lower():
            return str(d)
    return None


async def _execute_prompt_project(project_name: str, prompt: str, work_session: WorkSession, ws, dispatch_id: int = None, history: list[dict] = None, voice_state: dict = None):
    """Dispatch a prompt to Claude Code in a project directory.

    Runs entirely in the background. JARVIS returns to conversation mode
    immediately. When Claude Code finishes, JARVIS interrupts to report.
    """
    try:
        project_dir = _find_project_dir(project_name)

        # Register dispatch if not already registered
        if dispatch_id is None:
            dispatch_id = dispatch_registry.register(project_name, project_dir or "", prompt)

        if not project_dir:
            msg = f"Couldn't find the {project_name} project directory, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                except Exception:
                    pass
            return

        # Use a SEPARATE session so we don't trap the main conversation
        dispatch = WorkSession()
        await dispatch.start(project_dir, project_name)

        # Bring matching Terminal window to front so user can watch
        asyncio.create_task(_focus_terminal_window(project_name))

        log.info(f"Dispatching to {project_name} in {project_dir}: {prompt[:80]}")
        dispatch_registry.update_status(dispatch_id, "building")

        # Run claude -p in background
        full_response = await dispatch.send(prompt)
        await dispatch.stop()

        # Auto-open any localhost URLs from response
        import re as _re
        # Check for the explicit RUNNING_AT marker first
        running_match = _re.search(r'RUNNING_AT=(https?://localhost:\d+)', full_response or "")
        if not running_match:
            running_match = _re.search(r'https?://localhost:\d+', full_response or "")
        if running_match:
            url = running_match.group(1) if running_match.lastindex else running_match.group(0)
            asyncio.create_task(_execute_browse(url))
            log.info(f"Auto-opening {url}")
            # Store URL in dispatch
            if dispatch_id:
                dispatch_registry.update_status(dispatch_id, "completed",
                    response=full_response[:2000], summary=f"Running at {url}")

        if not full_response or full_response.startswith("Hit a problem") or full_response.startswith("That's taking"):
            dispatch_registry.update_status(dispatch_id, "failed" if full_response else "timeout", response=full_response or "")
            msg = f"Sir, I ran into an issue with {project_name}. {full_response[:150] if full_response else 'No response received.'}"
        else:
            # Summarize via Haiku — don't read word for word
            if anthropic_client:
                try:
                    summary = await anthropic_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=150,
                        system=(
                            "You are JARVIS reporting back on what you found or built in a project. "
                            "Speak in first person — 'I found', 'I built', 'I reviewed'. "
                            "Start with 'Sir, ' to get the user's attention. "
                            "Be specific but concise — highlight the key findings or actions taken. "
                            "If there are multiple items, give the count and top 2-3 briefly. "
                            "End by asking how the user wants to proceed. "
                            "NEVER read out URLs or localhost addresses. NEVER say 'Claude Code'. "
                            "2-3 sentences max. No markdown. Natural spoken voice."
                        ),
                        messages=[{"role": "user", "content": f"Project: {project_name}\nClaude Code reported:\n{full_response[:3000]}"}],
                    )
                    msg = summary.content[0].text
                    try:
                        usage.log_llm_call(
                            feature="dispatch_summary",
                            model="claude-haiku-4-5-20251001",
                            input_tokens=getattr(summary.usage, "input_tokens", 0),
                            output_tokens=getattr(summary.usage, "output_tokens", 0),
                        )
                    except Exception:
                        pass
                except Exception:
                    msg = f"Sir, {project_name} finished. Here's the gist: {full_response[:200]}"
            else:
                msg = f"Sir, {project_name} is done. {full_response[:200]}"

        # Speak the result — skip if user has spoken recently to avoid audio collision
        log.info(f"Dispatch summary for {project_name}: {msg[:100]}")
        if voice_state and time.time() - voice_state["last_user_time"] < 3:
            log.info(f"Skipping dispatch audio for {project_name} — user spoke recently")
            # Result is still stored in history below so JARVIS can reference it
        else:
            audio = await synthesize_speech(strip_markdown_for_tts(msg))
            if ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                        log.info(f"Dispatch audio sent for {project_name}")
                    else:
                        await ws.send_json({"type": "text", "text": msg})
                        log.info(f"Dispatch text fallback sent for {project_name}")
                except Exception as e:
                    log.error(f"Dispatch audio send failed: {e}")

        # Store dispatch result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[Dispatch result for {project_name}]: {msg}"})

        dispatch_registry.update_status(dispatch_id, "completed", response=full_response[:2000], summary=msg[:200])
        log.info(f"Project {project_name} dispatch complete ({len(full_response)} chars)")

    except Exception as e:
        log.error(f"Prompt project failed: {e}", exc_info=True)
        try:
            msg = f"Had trouble connecting to {project_name}, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                await ws.send_json({"type": "status", "state": "speaking"})
                await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
        except Exception:
            pass


async def self_work_and_notify(session: WorkSession, prompt: str, ws):
    """Run claude -p in background and notify via voice when done."""
    try:
        full_response = await session.send(prompt)
        log.info(f"Background work complete ({len(full_response)} chars)")

        # Summarize and speak
        if anthropic_client and full_response:
            try:
                summary = await anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=100,
                    system="You are JARVIS. Summarize what you just completed in 1 sentence. First person — 'I built', 'I set up'. No markdown. Never say 'Claude Code'.",
                    messages=[{"role": "user", "content": f"Claude Code completed:\n{full_response[:2000]}"}],
                )
                msg = summary.content[0].text
                try:
                    usage.log_llm_call(
                        feature="work_summary",
                        model="claude-haiku-4-5-20251001",
                        input_tokens=getattr(summary.usage, "input_tokens", 0),
                        output_tokens=getattr(summary.usage, "output_tokens", 0),
                    )
                except Exception:
                    pass
            except Exception:
                msg = "Work is complete, sir."

            try:
                audio = await synthesize_speech(msg)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {msg}")
            except Exception:
                pass
    except Exception as e:
        log.error(f"Background work failed: {e}")


# Smart greeting — track last greeting to avoid re-greeting on reconnect
_last_greeting_time: float = 0


# ---------------------------------------------------------------------------
# Screen Vision Hotkey — global OS-level shortcut state
# ---------------------------------------------------------------------------

# WebSocket that screen-hotkey audio gets pushed into (most recently connected client).
_active_ws: "WebSocket | None" = None
_active_ws_history: "list[dict] | None" = None
_active_ws_voice_state: "dict | None" = None

# Hotkey listener + capture lock (created on startup if enabled).
_screen_hotkey: "ScreenHotkey | None" = None
_screen_capture_lock: asyncio.Lock = asyncio.Lock()

# Proactive loop task (started in lifespan).
_proactive_task: "asyncio.Task | None" = None

# Memory distillation loop (started in lifespan).
_memory_distill_task: "asyncio.Task | None" = None


# ---------------------------------------------------------------------------
# TTS (OpenAI)
# ---------------------------------------------------------------------------

async def synthesize_speech(text: str) -> Optional[bytes]:
    """Generate speech audio from text using OpenAI TTS."""
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set, skipping TTS")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            response = await http.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_TTS_MODEL,
                    "input": text,
                    "voice": OPENAI_TTS_VOICE,
                    "response_format": "mp3",
                },
            )
            if response.status_code == 200:
                _session_tokens["tts_calls"] += 1
                _append_usage_entry(0, 0, "tts")
                # Richer cost tracking (per-char + per-model pricing)
                try:
                    usage.log_tts_call(model=OPENAI_TTS_MODEL, char_count=len(text or ""))
                except Exception:
                    pass
                return response.content
            else:
                log.error(f"TTS error: {response.status_code} {response.text}")
                return None
    except Exception as e:
        log.error(f"TTS error: {e}")
        return None


# ---------------------------------------------------------------------------
# LLM Response
# ---------------------------------------------------------------------------

async def generate_response(
    text: str,
    client: anthropic.AsyncAnthropic,
    task_mgr: ClaudeTaskManager,
    projects: list[dict],
    conversation_history: list[dict],
    last_response: str = "",
    session_summary: str = "",
) -> str:
    """Generate a JARVIS response using Anthropic API."""
    now = datetime.now()
    current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")

    # Use cached weather
    weather_info = _ctx_cache.get("weather", "")

    # Use cached context (refreshed in background, never blocks responses)
    screen_ctx    = _ctx_cache.get("screen", "")
    calendar_ctx  = _ctx_cache.get("calendar", "")
    mail_ctx      = _ctx_cache.get("mail", "")

    # Only inject context sections that have real data — skip empty/default placeholders
    _SKIP = {"", "No calendar data yet.", "No email data yet.", "No recent emails."}
    screen_section   = f"\nSCREEN AWARENESS:\n{screen_ctx}"       if screen_ctx   not in _SKIP else ""
    calendar_section = f"\nSCHEDULE:\n{calendar_ctx}"             if calendar_ctx not in _SKIP else ""
    mail_section     = f"\nEMAIL:\n{mail_ctx}"                    if mail_ctx     not in _SKIP else ""
    weather_section  = weather_info                                if weather_info not in _SKIP else ""

    # Check if any lookups are in progress
    lookup_status = get_lookup_status()

    # App-aware profile from the active foreground window
    try:
        _windows = await get_active_windows()
    except Exception:
        _windows = []
    _profile_text = format_profile_for_prompt(detect_active_profile(_windows))

    system = JARVIS_SYSTEM_PROMPT.format(
        personality=load_personality(),
        current_time=current_time,
        weather_info=weather_section,
        screen_context=screen_ctx or "",
        app_profile=_profile_text,
        calendar_context=calendar_ctx or "",
        mail_context=mail_ctx or "",
        active_tasks=task_mgr.get_active_tasks_summary(),
        dispatch_context=dispatch_registry.format_for_prompt(),
        known_projects=format_projects_for_prompt(projects),
        user_name=USER_NAME,
        project_dir=PROJECT_DIR,
    )

    # Strip empty context sections from the rendered prompt
    import re as _re
    system = _re.sub(r'\n(SCREEN AWARENESS|SCHEDULE|EMAIL):\n\s*\n', '\n', system)

    if lookup_status:
        system += f"\n\nACTIVE LOOKUPS:\n{lookup_status}\nIf asked about progress, report this status."

    # Inject relevant memories and tasks
    memory_ctx = build_memory_context(text)
    if memory_ctx:
        system += f"\n\nJARVIS MEMORY:\n{memory_ctx}"

    # Compounding memory — inject the personal-model digest
    me_header = load_me_md_header()
    if me_header:
        system += f"\n\nWHO YOU'RE TALKING TO:\n{me_header}"

    # Three-tier memory — inject rolling summary of earlier conversation
    if session_summary:
        system += f"\n\nSESSION CONTEXT (earlier in this conversation):\n{session_summary}"

    # Self-awareness — remind JARVIS of last response to avoid repetition
    if last_response:
        system += f'\n\nYOUR LAST RESPONSE (do not repeat this):\n"{last_response[:150]}"'

    # Study Mode — Socratic tutor persona
    if os.environ.get("STUDY_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nSTUDY MODE — ACTIVE:\n"
            "You are now a Socratic tutor. Your rules:\n"
            "1. NEVER give direct answers to learning questions. Ask a question back instead.\n"
            "2. If the user says 'just tell me' or 'give me the answer', refuse firmly: 'Not in study mode, sir. Work through it.'\n"
            "3. After the user explains something, quiz them: 'Explain it back to me in one sentence.'\n"
            "4. Tone: firm Oxford professor. Still British. No coddling.\n"
            "5. Exception: non-educational requests (time, calendar, weather) answered normally.\n"
            "6. Keep responses short — 1-2 sentences max, just like always."
        )

    # Brutal Honesty Mode — zero-filter feedback
    if os.environ.get("BRUTAL_HONESTY_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nBRUTAL HONESTY MODE — ACTIVE:\n"
            "The user has explicitly asked for maximum brutal honesty. Your rules:\n"
            "1. Zero diplomatic softening. Call it exactly as you see it, immediately.\n"
            "2. If something is bad, say it's bad. Don't bury the criticism.\n"
            "3. Swear freely when it adds impact — 'that's a shit plan', 'what the hell were you thinking', 'this is absolute bollocks'.\n"
            "4. No compliment sandwiches. No 'great effort but...'. Just the truth.\n"
            "5. If the user pushes back or gets defensive, hold your ground. Don't soften.\n"
            "6. Still be JARVIS — British, sharp, economical. Just with the gloves fully off.\n"
            "7. Keep it short — 1-3 sentences max. Brutal doesn't mean rambling."
        )

    # Hyper Intelligence Mode — strategic reasoning pipeline
    if os.environ.get("HYPER_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nHYPER INTELLIGENCE MODE — ACTIVE:\n"
            "You are now operating as a high-level strategic intelligence system, not a quick-reply assistant.\n"
            "For EVERY user input, internally run this reasoning pipeline before responding:\n"
            "  1. Identify the true objective behind the request\n"
            "  2. Reframe the question if it's suboptimal or incomplete\n"
            "  3. Break the situation into components: goals, constraints, variables\n"
            "  4. Generate 2-4 candidate approaches\n"
            "  5. Predict outcome, risk, and upside for each\n"
            "  6. Select the optimal path on efficiency, impact, and feasibility\n"
            "  7. Deliver a clear recommendation with justification and concrete next steps\n"
            "\nDO NOT expose the internal reasoning steps. Only emit the final synthesis.\n"
            "\nOutput rules (voice-first — this gets spoken):\n"
            "- 3-5 sentences total. High density, zero filler.\n"
            "- Name the real objective, the critical trade-off, the recommendation + why, and the first next step.\n"
            "- Challenge flawed assumptions when you spot them.\n"
            "- Confident and precise. No hedging phrases ('it depends', 'maybe consider').\n"
            "- Still British JARVIS in tone, but analytical over witty.\n"
            "\nAction integration — when the recommendation produces concrete follow-ups, emit action tags:\n"
            "- One [ACTION:ADD_TASK] per immediate next step the user should take\n"
            "  Format: [ACTION:ADD_TASK] priority ||| title ||| description ||| due_date\n"
            "- [ACTION:CREATE_NOTE] when the analysis is substantial enough to warrant saving\n"
            "  Format: [ACTION:CREATE_NOTE] title ||| full structured breakdown\n"
            "- [ACTION:REMEMBER] for key strategic decisions worth preserving across sessions\n"
            "- [ACTION:BUILD] or [ACTION:PROMPT_PROJECT] if the recommendation is a code workflow\n"
            "Emit action tags AT THE END of your response, one per line. Don't announce them — just embed."
        )

    # Use conversation history — keep the last 20 messages for context
    # (older conversation is captured in session_summary)
    messages = conversation_history[-20:]
    # If the last message isn't the current user text, add it
    if not messages or messages[-1].get("content") != text:
        messages = messages + [{"role": "user", "content": text}]

    try:
        # Route through llm_router so MODEL_SMART can be swapped to local Ollama in Settings.
        chosen = llm_router.model_smart()
        if llm_router.is_local(chosen):
            text_out = await llm_router.chat(
                chosen, messages, system=system, max_tokens=350, anthropic_client=client,
                feature="chat",
            )
            return text_out
        # Anthropic path — log via usage module
        response = await client.messages.create(
            model=chosen,
            max_tokens=250,
            system=system,
            messages=messages,
        )
        try:
            in_t = getattr(response.usage, "input_tokens", 0)
            out_t = getattr(response.usage, "output_tokens", 0)
        except Exception:
            in_t = out_t = 0
        usage.log_llm_call(feature="chat", model=chosen, input_tokens=in_t, output_tokens=out_t)
        track_usage(response)
        return response.content[0].text
    except Exception as e:
        log.error(f"LLM error: {e}")
        return "Apologies, sir. I'm having trouble connecting to my language systems."


async def generate_response_streaming(
    text: str,
    client: anthropic.AsyncAnthropic,
    task_mgr: ClaudeTaskManager,
    projects: list[dict],
    conversation_history: list[dict],
    ws: WebSocket,
    cancel_token: CancelToken,
    last_response: str = "",
    session_summary: str = "",
) -> str:
    """Streaming version of generate_response for Live Conversation Mode.

    Streams LLM tokens → sentence chunks → per-sentence TTS → audio sent
    incrementally over the WebSocket. First audio arrives in ~0.5s instead
    of waiting for the full response.

    Returns the full response text (or partial if cancelled).
    """
    now = datetime.now()
    current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")

    weather_info = _ctx_cache.get("weather", "")
    screen_ctx   = _ctx_cache.get("screen", "")
    calendar_ctx = _ctx_cache.get("calendar", "")
    mail_ctx     = _ctx_cache.get("mail", "")

    _SKIP = {"", "No calendar data yet.", "No email data yet.", "No recent emails."}
    weather_section = weather_info if weather_info not in _SKIP else ""
    screen_ctx_val  = screen_ctx   if screen_ctx   not in _SKIP else ""
    calendar_ctx_val= calendar_ctx if calendar_ctx not in _SKIP else ""
    mail_ctx_val    = mail_ctx     if mail_ctx     not in _SKIP else ""

    lookup_status = get_lookup_status()

    # App-aware profile (same detector used by generate_response)
    try:
        _windows = await get_active_windows()
    except Exception:
        _windows = []
    _profile_text = format_profile_for_prompt(detect_active_profile(_windows))

    system = JARVIS_SYSTEM_PROMPT.format(
        personality=load_personality(),
        current_time=current_time,
        weather_info=weather_section,
        screen_context=screen_ctx_val,
        app_profile=_profile_text,
        calendar_context=calendar_ctx_val,
        mail_context=mail_ctx_val,
        active_tasks=task_mgr.get_active_tasks_summary(),
        dispatch_context=dispatch_registry.format_for_prompt(),
        known_projects=format_projects_for_prompt(projects),
        user_name=USER_NAME,
        project_dir=PROJECT_DIR,
    )
    import re as _re2
    system = _re2.sub(r'\n(SCREEN AWARENESS|SCHEDULE|EMAIL):\n\s*\n', '\n', system)

    if lookup_status:
        system += f"\n\nACTIVE LOOKUPS:\n{lookup_status}"
    memory_ctx = build_memory_context(text)
    if memory_ctx:
        system += f"\n\nJARVIS MEMORY:\n{memory_ctx}"
    me_header = load_me_md_header()
    if me_header:
        system += f"\n\nWHO YOU'RE TALKING TO:\n{me_header}"
    if session_summary:
        system += f"\n\nSESSION CONTEXT (earlier in this conversation):\n{session_summary}"
    if last_response:
        system += f'\n\nYOUR LAST RESPONSE (do not repeat this):\n"{last_response[:150]}"'

    # Study Mode — Socratic tutor persona
    if os.environ.get("STUDY_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nSTUDY MODE — ACTIVE:\n"
            "You are now a Socratic tutor. Your rules:\n"
            "1. NEVER give direct answers to learning questions. Ask a question back instead.\n"
            "2. If the user says 'just tell me' or 'give me the answer', refuse firmly: 'Not in study mode, sir. Work through it.'\n"
            "3. After the user explains something, quiz them: 'Explain it back to me in one sentence.'\n"
            "4. Tone: firm Oxford professor. Still British. No coddling.\n"
            "5. Exception: non-educational requests (time, calendar, weather) answered normally.\n"
            "6. Keep responses short — 1-2 sentences max, just like always."
        )

    # Brutal Honesty Mode — zero-filter feedback
    if os.environ.get("BRUTAL_HONESTY_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nBRUTAL HONESTY MODE — ACTIVE:\n"
            "The user has explicitly asked for maximum brutal honesty. Your rules:\n"
            "1. Zero diplomatic softening. Call it exactly as you see it, immediately.\n"
            "2. If something is bad, say it's bad. Don't bury the criticism.\n"
            "3. Swear freely when it adds impact — 'that's a shit plan', 'what the hell were you thinking', 'this is absolute bollocks'.\n"
            "4. No compliment sandwiches. No 'great effort but...'. Just the truth.\n"
            "5. If the user pushes back or gets defensive, hold your ground. Don't soften.\n"
            "6. Still be JARVIS — British, sharp, economical. Just with the gloves fully off.\n"
            "7. Keep it short — 1-3 sentences max. Brutal doesn't mean rambling."
        )

    # Hyper Intelligence Mode — strategic reasoning pipeline
    if os.environ.get("HYPER_MODE", "").lower() in ("true", "1", "yes"):
        system += (
            "\n\nHYPER INTELLIGENCE MODE — ACTIVE:\n"
            "You are now operating as a high-level strategic intelligence system, not a quick-reply assistant.\n"
            "For EVERY user input, internally run this reasoning pipeline before responding:\n"
            "  1. Identify the true objective behind the request\n"
            "  2. Reframe the question if it's suboptimal or incomplete\n"
            "  3. Break the situation into components: goals, constraints, variables\n"
            "  4. Generate 2-4 candidate approaches\n"
            "  5. Predict outcome, risk, and upside for each\n"
            "  6. Select the optimal path on efficiency, impact, and feasibility\n"
            "  7. Deliver a clear recommendation with justification and concrete next steps\n"
            "\nDO NOT expose the internal reasoning steps. Only emit the final synthesis.\n"
            "\nOutput rules (voice-first — this gets spoken):\n"
            "- 3-5 sentences total. High density, zero filler.\n"
            "- Name the real objective, the critical trade-off, the recommendation + why, and the first next step.\n"
            "- Challenge flawed assumptions when you spot them.\n"
            "- Confident and precise. No hedging phrases ('it depends', 'maybe consider').\n"
            "- Still British JARVIS in tone, but analytical over witty.\n"
            "\nAction integration — when the recommendation produces concrete follow-ups, emit action tags:\n"
            "- One [ACTION:ADD_TASK] per immediate next step the user should take\n"
            "  Format: [ACTION:ADD_TASK] priority ||| title ||| description ||| due_date\n"
            "- [ACTION:CREATE_NOTE] when the analysis is substantial enough to warrant saving\n"
            "  Format: [ACTION:CREATE_NOTE] title ||| full structured breakdown\n"
            "- [ACTION:REMEMBER] for key strategic decisions worth preserving across sessions\n"
            "- [ACTION:BUILD] or [ACTION:PROMPT_PROJECT] if the recommendation is a code workflow\n"
            "Emit action tags AT THE END of your response, one per line. Don't announce them — just embed."
        )

    messages = conversation_history[-20:]
    if not messages or messages[-1].get("content") != text:
        messages = messages + [{"role": "user", "content": text}]

    full_text = ""
    token_buffer = ""

    try:
        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=system,
            messages=messages,
        ) as stream:
            async for token in stream.text_stream:
                if cancel_token.is_cancelled:
                    break
                token_buffer += token
                full_text += token

                sentences, token_buffer = _split_sentences(token_buffer)
                for sentence in sentences:
                    if cancel_token.is_cancelled:
                        break
                    tts_text = strip_markdown_for_tts(sentence)
                    if not tts_text:
                        continue
                    audio_bytes = await synthesize_speech(tts_text)
                    if cancel_token.is_cancelled:
                        break
                    if audio_bytes:
                        encoded = base64.b64encode(audio_bytes).decode()
                        await ws.send_json({
                            "type": "audio",
                            "data": encoded,
                            "text": sentence,
                        })
                        cancel_token.partial_text += sentence + " "

        # Flush any remaining buffer (last sentence without trailing punctuation)
        if not cancel_token.is_cancelled and len(token_buffer.split()) >= 2:
            tts_text = strip_markdown_for_tts(token_buffer.strip())
            if tts_text:
                audio_bytes = await synthesize_speech(tts_text)
                if audio_bytes and not cancel_token.is_cancelled:
                    encoded = base64.b64encode(audio_bytes).decode()
                    await ws.send_json({
                        "type": "audio",
                        "data": encoded,
                        "text": token_buffer.strip(),
                    })
                    cancel_token.partial_text += token_buffer.strip()

    except Exception as e:
        log.error(f"Streaming LLM error: {e}")

    return cancel_token.partial_text if cancel_token.is_cancelled else full_text


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

# Shared state
task_manager = ClaudeTaskManager(max_concurrent=3)
anthropic_client: Optional[anthropic.AsyncAnthropic] = None
cached_projects: list[dict] = []
recently_built: list[dict] = []  # [{"name": str, "path": str, "time": float}]
dispatch_registry = DispatchRegistry()

# Usage tracking — logs every call with timestamp, persists to disk
_USAGE_FILE = Path(__file__).parent / "data" / "usage_log.jsonl"
_session_start = time.time()
_session_tokens = {"input": 0, "output": 0, "api_calls": 0, "tts_calls": 0}


def _append_usage_entry(input_tokens: int, output_tokens: int, call_type: str = "api"):
    """Append a usage entry with timestamp to the log file."""
    try:
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        entry = {
            "ts": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": call_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        with open(_USAGE_FILE, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception:
        pass


def _get_usage_for_period(seconds: float | None = None) -> dict:
    """Sum usage from the log file for a time period. None = all time."""
    import json as _json
    totals = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "tts_calls": 0}
    cutoff = (time.time() - seconds) if seconds else 0
    try:
        if _USAGE_FILE.exists():
            for line in _USAGE_FILE.read_text().strip().split("\n"):
                if not line:
                    continue
                entry = _json.loads(line)
                if entry["ts"] >= cutoff:
                    totals["input_tokens"] += entry.get("input_tokens", 0)
                    totals["output_tokens"] += entry.get("output_tokens", 0)
                    if entry.get("type") == "tts":
                        totals["tts_calls"] += 1
                    else:
                        totals["api_calls"] += 1
    except Exception:
        pass
    return totals


def _cost_from_tokens(input_t: int, output_t: int) -> float:
    return (input_t / 1_000_000) * 0.80 + (output_t / 1_000_000) * 4.00


def track_usage(response):
    """Track token usage from an Anthropic API response."""
    inp = getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
    out = getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
    _session_tokens["input"] += inp
    _session_tokens["output"] += out
    _session_tokens["api_calls"] += 1
    _append_usage_entry(inp, out, "api")


def get_usage_summary() -> str:
    """Get a voice-friendly usage summary with time breakdowns."""
    uptime_min = int((time.time() - _session_start) / 60)

    session = _session_tokens
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    all_time = _get_usage_for_period(None)

    session_cost = _cost_from_tokens(session["input"], session["output"])
    today_cost = _cost_from_tokens(today["input_tokens"], today["output_tokens"])
    all_cost = _cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"])

    parts = [f"This session: {uptime_min} minutes, {session['api_calls']} calls, ${session_cost:.2f}."]

    if today["api_calls"] > session["api_calls"]:
        parts.append(f"Today total: {today['api_calls']} calls, ${today_cost:.2f}.")

    if all_time["api_calls"] > today["api_calls"]:
        parts.append(f"All time: {all_time['api_calls']} calls, ${all_cost:.2f}.")

    return " ".join(parts)

# Background context cache — never blocks responses
_ctx_cache = {
    "screen": "",
    "calendar": "No calendar data yet.",
    "mail": "No mail data yet.",
    "weather": "Weather data unavailable.",
}


def _refresh_context_sync():
    """Run in a SEPARATE THREAD — refreshes screen/calendar/mail/weather context.

    Uses pygetwindow (Windows) or osascript (macOS) for the window list.
    Every SCREEN_VISION_INTERVAL seconds, also takes a real screenshot and
    sends it to Claude Vision so JARVIS truly sees what's on screen.
    """
    import threading
    import sys as _sys

    # Automatic vision pass is disabled — use the Ctrl+Shift+J hotkey instead.
    # Set SCREEN_AUTO_VISION=true in .env to re-enable (costs ~$0.01/min in API calls).
    SCREEN_VISION_INTERVAL = 999999  # effectively never
    SCREEN_WINDOW_INTERVAL = 15   # window titles every 15s (fast, no API cost)

    _last_vision = 0.0

    def _get_windows_windows():
        """Fast window list on Windows via pygetwindow."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            active_title = active.title if active else ""
            result = []
            for w in gw.getAllWindows():
                if w.title and w.visible:
                    result.append({
                        "app": w.title.split(" - ")[-1] if " - " in w.title else w.title,
                        "title": w.title,
                        "frontmost": w.title == active_title,
                    })
            return result
        except Exception:
            return []

    def _get_windows_mac():
        """Fast window list on macOS via osascript."""
        try:
            import subprocess as _sp
            proc = _sp.run(
                ["osascript", "-e", '''
set windowList to ""
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    set visibleApps to every application process whose visible is true
    repeat with proc in visibleApps
        set appName to name of proc
        try
            if (count of windows of proc) > 0 then
                repeat with w in (windows of proc)
                    try
                        set winTitle to name of w
                        if winTitle is not "" and winTitle is not missing value then
                            set windowList to windowList & appName & "|||" & winTitle & "|||" & (appName = frontApp) & linefeed
                        end if
                    end try
                end repeat
            end if
        end try
    end repeat
end tell
return windowList
'''],
                capture_output=True, text=True, timeout=5
            )
            if proc.returncode == 0 and proc.stdout.strip():
                windows = []
                for line in proc.stdout.strip().split("\n"):
                    parts = line.strip().split("|||")
                    if len(parts) >= 3:
                        windows.append({
                            "app": parts[0].strip(),
                            "title": parts[1].strip(),
                            "frontmost": parts[2].strip().lower() == "true",
                        })
                return windows
        except Exception:
            pass
        return []

    def _take_screenshot_sync():
        """Take a screenshot synchronously (called from thread)."""
        try:
            if _sys.platform == "win32":
                from PIL import ImageGrab
                import io, base64
                img = ImageGrab.grab()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()
            else:
                import tempfile, base64, subprocess as _sp
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                r = _sp.run(["screencapture", "-x", "-m", tmp], timeout=8)
                if r.returncode == 0:
                    data = Path(tmp).read_bytes()
                    Path(tmp).unlink(missing_ok=True)
                    return base64.b64encode(data).decode()
        except Exception as e:
            log.debug(f"Screenshot sync error: {e}")
        return None

    def _vision_describe(screenshot_b64: str) -> str:
        """Call Claude Vision synchronously to describe the screenshot."""
        try:
            import anthropic as _anthropic
            if not ANTHROPIC_API_KEY:
                return ""
            client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=(
                    "You are JARVIS's screen awareness module. "
                    "Describe the user's screen in 2-3 sentences: what app is in focus, "
                    "what they appear to be working on, any key content visible (code, docs, URLs, etc). "
                    "Be specific. No markdown."
                ),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                        {"type": "text", "text": "What's on the screen right now?"},
                    ],
                }],
            )
            return resp.content[0].text
        except Exception as e:
            log.debug(f"Vision describe error: {e}")
            return ""

    def _worker():
        nonlocal _last_vision
        is_win = _sys.platform == "win32"

        while True:
            try:
                now = time.time()
                run_vision = (now - _last_vision) >= SCREEN_VISION_INTERVAL

                auto_vision = os.environ.get("SCREEN_AUTO_VISION", "false").lower() == "true"
                if run_vision and auto_vision:
                    # Full vision pass — screenshot + Claude (opt-in, disabled by default)
                    screenshot_b64 = _take_screenshot_sync()
                    if screenshot_b64:
                        description = _vision_describe(screenshot_b64)
                        if description:
                            _ctx_cache["screen"] = f"[Vision] {description}"
                            _last_vision = now
                            log.debug("Screen vision updated")
                        else:
                            _last_vision = now  # prevent hammering on failure
                    else:
                        _last_vision = now
                    time.sleep(SCREEN_WINDOW_INTERVAL)
                    continue

                # Fast pass — window titles only (fallback or between vision passes)
                windows = _get_windows_windows() if is_win else _get_windows_mac()
                if windows:
                    _ctx_cache["screen"] = format_windows_for_context(windows)

            except Exception as e:
                log.debug(f"Context thread error: {e}")

            # Weather refresh
            try:
                import urllib.request, json as _json
                url = "https://api.open-meteo.com/v1/forecast?latitude=27.77&longitude=-82.64&current=temperature_2m,weathercode&temperature_unit=fahrenheit"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    d = _json.loads(resp.read()).get("current", {})
                    temp = d.get("temperature_2m", "?")
                    _ctx_cache["weather"] = f"Current weather in St. Petersburg, FL: {temp}°F"
            except Exception:
                pass

            time.sleep(SCREEN_WINDOW_INTERVAL)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    log.info("Context refresh thread started")


@asynccontextmanager
async def lifespan(application: FastAPI):
    global anthropic_client, cached_projects
    if ANTHROPIC_API_KEY:
        anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    else:
        log.warning("ANTHROPIC_API_KEY not set — LLM features disabled")
    cached_projects = []

    # Start context refresh in a separate thread (never touches event loop)
    _refresh_context_sync()
    log.info("JARVIS server starting")

    # ── Screen Vision Hotkey — start global OS listener if enabled ──
    global _screen_hotkey
    if os.getenv("SCREEN_HOTKEY_ENABLED", "true").lower() in ("true", "1", "yes"):
        combo = os.getenv("SCREEN_HOTKEY", "<ctrl>+<shift>+j")
        try:
            _screen_hotkey = ScreenHotkey(
                combo=combo,
                on_trigger=_handle_screen_hotkey,
                loop=asyncio.get_event_loop(),
            )
            _screen_hotkey.start()
        except Exception as e:
            log.warning(f"failed to start screen hotkey: {e}")
            _screen_hotkey = None

    # ── Memory distillation loop — extract stable facts from conversations ──
    global _memory_distill_task
    try:
        _memory_distill_task = asyncio.create_task(
            memory_distillation_loop(
                get_history=lambda: (_active_ws_history or []),
                anthropic_client=anthropic_client,
            )
        )
        log.info("Memory distillation loop started")
    except Exception as e:
        log.warning(f"failed to start memory distillation: {e}")
        _memory_distill_task = None

    # ── Proactive loop — always-on attention engine, kill-switchable in Settings ──
    global _proactive_task
    try:
        _proactive_task = asyncio.create_task(
            proactive_loop(
                get_active_ws=lambda: _active_ws,
                get_voice_state=lambda: _active_ws_voice_state,
                get_weather=lambda: (_cached_weather or ""),
                synthesize_fn=synthesize_speech,
            )
        )
        log.info("Proactive loop started")
    except Exception as e:
        log.warning(f"failed to start proactive loop: {e}")
        _proactive_task = None

    yield

    # Shutdown — stop the hotkey listener cleanly.
    if _screen_hotkey is not None:
        _screen_hotkey.stop()
    if _proactive_task is not None:
        _proactive_task.cancel()
    if _memory_distill_task is not None:
        _memory_distill_task.cancel()


app = FastAPI(title="JARVIS Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- REST Endpoints --------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "online", "name": "JARVIS", "version": "0.1.0"}


@app.get("/api/tts-test")
async def tts_test():
    """Generate a test audio clip for debugging."""
    audio = await synthesize_speech("Testing audio, sir.")
    if audio:
        return {"audio": base64.b64encode(audio).decode()}
    return {"audio": None, "error": "TTS failed"}


@app.get("/api/usage")
async def api_usage():
    uptime = int(time.time() - _session_start)
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    month = _get_usage_for_period(86400 * 30)
    all_time = _get_usage_for_period(None)
    return {
        "session": {**_session_tokens, "uptime_seconds": uptime},
        "today": {**today, "cost_usd": round(_cost_from_tokens(today["input_tokens"], today["output_tokens"]), 4)},
        "week": {**week, "cost_usd": round(_cost_from_tokens(week["input_tokens"], week["output_tokens"]), 4)},
        "month": {**month, "cost_usd": round(_cost_from_tokens(month["input_tokens"], month["output_tokens"]), 4)},
        "all_time": {**all_time, "cost_usd": round(_cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"]), 4)},
    }


@app.get("/api/tasks")
async def api_list_tasks():
    tasks = await task_manager.list_tasks()
    return {"tasks": [t.to_dict() for t in tasks]}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = await task_manager.get_status(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return {"task": task.to_dict()}


@app.post("/api/tasks")
async def api_create_task(req: TaskRequest):
    try:
        task_id = await task_manager.spawn(req.prompt, req.working_dir)
        return {"task_id": task_id, "status": "spawned"}
    except RuntimeError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})


@app.delete("/api/tasks/{task_id}")
async def api_cancel_task(task_id: str):
    cancelled = await task_manager.cancel(task_id)
    if not cancelled:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found or not cancellable"},
        )
    return {"task_id": task_id, "status": "cancelled"}


@app.get("/api/projects")
async def api_list_projects():
    global cached_projects
    cached_projects = await scan_projects()
    return {"projects": cached_projects}


# -- Fast Action Detection (no LLM call) -----------------------------------

def _scan_projects_sync() -> list[dict]:
    """Synchronous Desktop scan — runs in executor."""
    projects = []
    desktop = Path.home() / "Desktop"
    try:
        for entry in desktop.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                projects.append({"name": entry.name, "path": str(entry), "branch": ""})
    except Exception:
        pass
    return projects


def detect_action_fast(text: str) -> dict | None:
    """Keyword-based action detection — ONLY for short, obvious commands.

    Everything else goes to the LLM which uses [ACTION:X] tags when it decides
    to act based on conversational understanding.
    """
    t = text.lower().strip()
    words = t.split()

    # Only trigger on SHORT, clear commands (< 12 words)
    if len(words) > 12:
        return None  # Long messages are conversation, not commands

    # Screen requests — checked BEFORE project matching to prevent misrouting
    if any(p in t for p in ["look at my screen", "what's on my screen", "whats on my screen",
                             "what am i looking at", "what do you see", "see my screen",
                             "what's running on my", "whats running on my", "check my screen"]):
        return {"action": "describe_screen"}

    # Terminal / Claude Code — explicit open requests
    if any(w in t for w in ["open claude", "start claude", "launch claude", "run claude"]):
        return {"action": "open_terminal"}

    # Show recent build
    if any(w in t for w in ["show me what you built", "pull up what you made", "open what you built"]):
        return {"action": "show_recent"}

    # Screen awareness — explicit look/see requests
    if any(p in t for p in ["what's on my screen", "whats on my screen", "what do you see",
                             "can you see my screen", "look at my screen", "what am i looking at",
                             "what's open", "whats open", "what apps are open"]):
        return {"action": "describe_screen"}

    # Calendar — explicit schedule requests
    if any(p in t for p in ["what's my schedule", "whats my schedule", "what's on my calendar",
                             "whats on my calendar", "do i have any meetings", "any meetings",
                             "what's next on my calendar", "my schedule today",
                             "what do i have today", "my calendar", "upcoming meetings",
                             "next meeting", "what's my next meeting"]):
        return {"action": "check_calendar"}

    # Mail — explicit email requests
    if any(p in t for p in ["check my email", "check my mail", "any new emails", "any new mail",
                             "unread emails", "unread mail", "what's in my inbox",
                             "whats in my inbox", "read my email", "read my mail",
                             "any emails", "any mail", "email update", "mail update"]):
        return {"action": "check_mail"}

    # Dispatch / build status check
    if any(p in t for p in ["where are we", "where were we", "project status", "how's the build",
                             "hows the build", "status update", "status report", "where is that",
                             "how's it going with", "hows it going with", "is it done",
                             "is that done", "what happened with"]):
        return {"action": "check_dispatch"}

    # Task list check
    if any(p in t for p in ["what's on my list", "whats on my list", "my tasks", "my to do",
                             "my todo", "what do i need to do", "open tasks", "task list"]):
        return {"action": "check_tasks"}

    # Usage / cost check
    if any(p in t for p in ["usage", "how much have you cost", "how much am i spending",
                             "what's the cost", "whats the cost", "api cost", "token usage",
                             "how expensive", "what's my bill"]):
        return {"action": "check_usage"}

    # Order status / tracking — short unambiguous queries go fast-path
    if any(p in t for p in ["where's my food", "wheres my food", "where is my food",
                             "track my order", "food status", "order status",
                             "how long for my food", "eta on my order",
                             "where's my order", "wheres my order"]):
        return {"action": "order_status"}

    # Cancel order — short explicit command
    if any(p in t for p in ["cancel my order", "cancel the order", "cancel food"]):
        return {"action": "cancel_order"}

    # NOTE: ORDER_FOOD and RESERVE_TABLE go to the LLM (need NL parsing)
    # so we do NOT fast-path them here. The LLM emits [ACTION:ORDER_FOOD|...].

    return None  # Everything else goes to the LLM for conversational routing


# -- Action Handlers -------------------------------------------------------

async def handle_open_terminal() -> str:
    result = await open_terminal("claude --dangerously-skip-permissions")
    return result["confirmation"]


async def handle_build(target: str) -> str:
    name = _generate_project_name(target)
    path = str(Path.home() / "Desktop" / name)
    os.makedirs(path, exist_ok=True)

    # Write CLAUDE.md with clear instructions
    claude_md = Path(path) / "CLAUDE.md"
    claude_md.write_text(f"# Task\n\n{target}\n\nBuild this completely. If web app, make index.html work standalone.\n")

    # Write prompt to a file, then pipe it to claude -p
    # This avoids all shell escaping issues
    prompt_file = Path(path) / ".jarvis_prompt.txt"
    prompt_file.write_text(target)

    script = (
        'tell application "Terminal"\n'
        "    activate\n"
        f'    do script "cd {path} && cat .jarvis_prompt.txt | claude -p --dangerously-skip-permissions"\n'
        "end tell"
    )
    await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    recently_built.append({"name": name, "path": path, "time": time.time()})
    return f"On it, sir. Claude Code is working in {name}."


async def handle_show_recent() -> str:
    if not recently_built:
        return "Nothing built recently, sir."
    last = recently_built[-1]
    project_path = Path(last["path"])

    # Try to find the best file to open
    for name in ["report.html", "index.html"]:
        f = project_path / name
        if f.exists():
            await open_browser(f"file://{f}")
            return f"Opened {name} from {last['name']}, sir."

    # Try any HTML file
    html_files = list(project_path.glob("*.html"))
    if html_files:
        await open_browser(f"file://{html_files[0]}")
        return f"Opened {html_files[0].name} from {last['name']}, sir."

    # Fall back to opening the folder in Finder
    script = f'tell application "Finder"\nactivate\nopen POSIX file "{last["path"]}"\nend tell'
    await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    return f"Opened the {last['name']} folder in Finder, sir."


# ---------------------------------------------------------------------------
# Background lookup system — spawns slow tasks, reports back via voice
# ---------------------------------------------------------------------------

# Track active lookups so JARVIS can report status
_active_lookups: dict[str, dict] = {}  # id -> {"type": str, "status": str, "started": float}


async def _lookup_and_report(lookup_type: str, lookup_fn, ws, history: list[dict] = None, voice_state: dict = None):
    """Run a slow lookup, then speak the result back.

    JARVIS stays conversational — this runs completely off the main path.
    """
    lookup_id = str(uuid.uuid4())[:8]
    _active_lookups[lookup_id] = {
        "type": lookup_type,
        "status": "working",
        "started": time.time(),
    }

    try:
        # Run the async lookup directly — these functions already use
        # asyncio.create_subprocess_exec so they don't block the event loop
        result_text = await asyncio.wait_for(
            lookup_fn(),
            timeout=30,
        )

        _active_lookups[lookup_id]["status"] = "done"

        # Speak the result — skip audio if user spoke recently to avoid collision
        if voice_state and time.time() - voice_state["last_user_time"] < 3:
            log.info(f"Skipping lookup audio for {lookup_type} — user spoke recently")
            # Result is still stored in history below
        else:
            tts = strip_markdown_for_tts(result_text)
            audio = await synthesize_speech(tts)
            try:
                await ws.send_json({"type": "status", "state": "speaking"})
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": result_text})
                else:
                    await ws.send_json({"type": "text", "text": result_text})
                await ws.send_json({"type": "status", "state": "idle"})
            except Exception:
                pass

        log.info(f"Lookup {lookup_type} complete: {result_text[:80]}")

        # Store lookup result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[{lookup_type} check]: {result_text}"})

    except asyncio.TimeoutError:
        _active_lookups[lookup_id]["status"] = "timeout"
        try:
            fallback = f"That {lookup_type} check is taking too long, sir. The data may still be syncing."
            audio = await synthesize_speech(fallback)
            await ws.send_json({"type": "status", "state": "speaking"})
            if audio:
                await ws.send_json({"type": "audio", "data": audio, "text": fallback})
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            pass
    except Exception as e:
        _active_lookups[lookup_id]["status"] = "error"
        log.warning(f"Lookup {lookup_type} failed: {e}")
    finally:
        # Clean up after 60s
        await asyncio.sleep(60)
        _active_lookups.pop(lookup_id, None)


async def _do_calendar_lookup() -> str:
    """Slow calendar fetch — runs in thread."""
    await refresh_calendar_cache()
    events = await get_todays_events()
    if events:
        _ctx_cache["calendar"] = format_events_for_context(events)
    return format_schedule_summary(events)


async def _do_mail_lookup() -> str:
    """Slow mail fetch — runs in thread."""
    unread_info = await get_unread_count()
    if isinstance(unread_info, dict):
        _ctx_cache["mail"] = format_unread_summary(unread_info)
        if unread_info["total"] == 0:
            return "Inbox is clear, sir. No unread messages."
        unread_msgs = await get_unread_messages(count=5)
        summary = format_unread_summary(unread_info)
        if unread_msgs:
            top = unread_msgs[:3]
            details = ". ".join(
                f"{_short_sender(m['sender'])} regarding {m['subject']}"
                for m in top
            )
            return f"{summary} Most recent: {details}."
        return summary
    return "Couldn't reach Mail at the moment, sir."


async def _do_screen_lookup() -> str:
    """Screen describe — runs in thread."""
    if anthropic_client:
        return await describe_screen(anthropic_client)
    windows = await get_active_windows()
    if windows:
        apps = set(w["app"] for w in windows)
        active = next((w for w in windows if w["frontmost"]), None)
        result = f"You have {', '.join(apps)} open."
        if active:
            result += f" Currently focused on {active['app']}: {active['title']}."
        return result
    return "Couldn't see the screen, sir."


async def _do_screen_hotkey_lookup() -> str:
    """Screen describe with pair-programmer framing — for the global hotkey."""
    if anthropic_client:
        return await describe_screen_for_coding(anthropic_client)
    return "Vision model not configured, sir."


async def _handle_screen_hotkey() -> None:
    """Fired by the global hotkey listener. Runs a screen capture + vision call."""
    ws = _active_ws
    if ws is None:
        log.info("screen hotkey pressed but no active WS — skipping")
        return
    if _screen_capture_lock.locked():
        log.info("screen hotkey: capture already in flight — skipping")
        return
    async with _screen_capture_lock:
        try:
            await _lookup_and_report(
                "screen",
                _do_screen_hotkey_lookup,
                ws,
                history=_active_ws_history,
                voice_state=_active_ws_voice_state,
            )
        except Exception as e:
            log.warning(f"screen hotkey handler failed: {e}")


def get_lookup_status() -> str:
    """Get status of active lookups for when user asks 'how's that coming'."""
    if not _active_lookups:
        return ""
    active = [v for v in _active_lookups.values() if v["status"] == "working"]
    if not active:
        return ""
    parts = []
    for lookup in active:
        elapsed = int(time.time() - lookup["started"])
        parts.append(f"{lookup['type']} check ({elapsed}s)")
    return "Currently working on: " + ", ".join(parts)


def _short_sender(sender: str) -> str:
    """Extract just the name from an email sender string."""
    if "<" in sender:
        return sender.split("<")[0].strip().strip('"')
    if "@" in sender:
        return sender.split("@")[0]
    return sender


async def handle_browse(text: str, target: str) -> str:
    """Open a URL directly or search. Smart about detecting URLs in speech."""
    import re
    from urllib.parse import quote

    browser = "firefox" if "firefox" in text.lower() else "chrome"
    combined = text.lower()

    # 1. Try to find a URL or domain in the text
    # Match things like "joetmd.com", "google.com/maps", "https://example.com"
    url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?)'
    url_match = re.search(url_pattern, text, re.IGNORECASE)

    if url_match:
        domain = url_match.group(0)
        if not domain.startswith("http"):
            domain = "https://" + domain
        await open_browser(domain, browser)
        return f"Opened {url_match.group(0)}, sir."

    # 2. Check for spoken domains that speech-to-text mangled
    # "Joe tmd.com" → "joetmd.com", "roofo.co" etc.
    # Try joining words that end/start with a dot pattern
    words = text.split()
    for i, word in enumerate(words):
        # Look for word ending with common TLD
        if re.search(r'\.(com|co|io|ai|org|net|dev|app)$', word, re.IGNORECASE):
            # This word IS a domain — might have spaces before it
            domain = word
            # Check if previous word should be joined (e.g., "Joe tmd.com" → "joetmd.com" is tricky)
            if not domain.startswith("http"):
                domain = "https://" + domain
            await open_browser(domain, browser)
            return f"Opened {word}, sir."

    # 3. Fall back to Google search with cleaned query
    query = target
    for prefix in ["search for", "look up", "google", "find me", "pull up", "open chrome",
                    "open firefox", "open browser", "go to", "can you", "in the browser",
                    "can you go to", "please"]:
        query = query.lower().replace(prefix, "").strip()
    # Remove filler words
    query = re.sub(r'\b(can|you|the|in|to|a|an|for|me|my|please)\b', '', query).strip()
    query = re.sub(r'\s+', ' ', query).strip()

    if not query:
        query = target

    url = f"https://www.google.com/search?q={quote(query)}"
    await open_browser(url, browser)
    return "Searching for that, sir."


async def handle_research(text: str, target: str, client: anthropic.AsyncAnthropic) -> str:
    """Deep research with Opus — write results to HTML, open in browser."""
    try:
        research_response = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=f"You are JARVIS, researching a topic for {USER_NAME}. Be thorough, organized, and cite sources where possible.",
            messages=[{"role": "user", "content": f"Research this thoroughly:\n\n{target}"}],
        )
        research_text = research_response.content[0].text
        try:
            usage.log_llm_call(
                feature="research_opus",
                model="claude-opus-4-6",
                input_tokens=getattr(research_response.usage, "input_tokens", 0),
                output_tokens=getattr(research_response.usage, "output_tokens", 0),
            )
        except Exception:
            pass

        import html as _html
        html_content = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>JARVIS Research: {_html.escape(target[:60])}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #0a0a0a; color: #e0e0e0; line-height: 1.7; }}
h1 {{ color: #0ea5e9; font-size: 1.4em; border-bottom: 1px solid #222; padding-bottom: 10px; }}
h2 {{ color: #38bdf8; font-size: 1.1em; margin-top: 24px; }}
a {{ color: #0ea5e9; }}
pre {{ background: #111; padding: 12px; border-radius: 6px; overflow-x: auto; }}
code {{ background: #111; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
blockquote {{ border-left: 3px solid #0ea5e9; margin-left: 0; padding-left: 16px; color: #aaa; }}
</style>
</head><body>
<h1>Research: {_html.escape(target[:80])}</h1>
<div>{research_text.replace(chr(10), '<br>')}</div>
<hr style="border-color:#222;margin-top:40px">
<p style="color:#555;font-size:0.8em">Researched by JARVIS using Claude Opus &bull; {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
</body></html>"""

        results_file = Path.home() / "Desktop" / ".jarvis_research.html"
        results_file.write_text(html_content)

        browser_name = "firefox" if "firefox" in text.lower() else "chrome"
        await open_browser(f"file://{results_file}", browser_name)

        # Short voice summary via Haiku
        summary = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system="Summarize this research in ONE sentence for voice. No markdown.",
            messages=[{"role": "user", "content": research_text[:2000]}],
        )
        try:
            usage.log_llm_call(
                feature="research_summary",
                model="claude-haiku-4-5-20251001",
                input_tokens=getattr(summary.usage, "input_tokens", 0),
                output_tokens=getattr(summary.usage, "output_tokens", 0),
            )
        except Exception:
            pass
        return summary.content[0].text + " Full results are in your browser, sir."

    except Exception as e:
        log.error(f"Research failed: {e}")
        from urllib.parse import quote
        await open_browser(f"https://www.google.com/search?q={quote(target)}")
        return "Pulled up a search for that, sir."


# -- Session Summary (Three-Tier Memory) -----------------------------------

async def _update_session_summary(
    old_summary: str,
    rotated_messages: list[dict],
    client: anthropic.AsyncAnthropic,
) -> str:
    """Background Haiku call to update the rolling session summary."""
    prompt = f"""Update this conversation summary to include the new messages.

Current summary: {old_summary or '(start of conversation)'}

New messages to incorporate:
{chr(10).join(f'{m["role"]}: {m["content"][:200]}' for m in rotated_messages)}

Write an updated summary in 2-4 sentences capturing the key topics, decisions, and context. Be concise."""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            usage.log_llm_call(
                feature="session_summary",
                model="claude-haiku-4-5-20251001",
                input_tokens=getattr(response.usage, "input_tokens", 0),
                output_tokens=getattr(response.usage, "output_tokens", 0),
            )
        except Exception:
            pass
        return response.content[0].text.strip()
    except Exception as e:
        log.warning(f"Summary update failed: {e}")
        return old_summary  # Keep old summary on failure


# -- WebSocket Voice Handler -----------------------------------------------

@app.websocket("/ws/voice")
async def voice_handler(ws: WebSocket):
    """
    WebSocket protocol:

    Client -> Server:
        {"type": "transcript", "text": "...", "isFinal": true}

    Server -> Client:
        {"type": "audio", "data": "<base64 mp3>", "text": "spoken text"}
        {"type": "status", "state": "thinking"|"speaking"|"idle"|"working"}
        {"type": "task_spawned", "task_id": "...", "prompt": "..."}
        {"type": "task_complete", "task_id": "...", "summary": "..."}
    """
    await ws.accept()
    task_manager.register_websocket(ws)
    history: list[dict] = []
    work_session = WorkSession()
    planner = TaskPlanner()

    # Expose this WS to the screen-hotkey listener (most recently connected client wins).
    global _active_ws, _active_ws_history, _active_ws_voice_state

    # Per-response cancel token — replaced on every new user turn
    _active_token: CancelToken = CancelToken()

    # Audio collision prevention — track when user last spoke
    voice_state = {"last_user_time": 0.0}

    _active_ws = ws
    _active_ws_history = history
    _active_ws_voice_state = voice_state

    # Self-awareness — track last spoken response to avoid repetition
    last_jarvis_response = ""

    # Three-tier conversation memory
    session_buffer: list[dict] = []  # ALL messages, never truncated
    session_summary: str = ""  # Rolling summary of older conversation
    summary_update_pending: bool = False
    messages_since_last_summary: int = 0

    log.info("Voice WebSocket connected")

    try:
        # ── Greeting — time-tailored ──
        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            greeting = "Good morning, sir."
        elif 12 <= hour < 17:
            greeting = "Good afternoon, sir."
        elif 17 <= hour < 21:
            greeting = "Good evening, sir."
        elif 21 <= hour < 24:
            greeting = "Working late, sir."
        else:  # 00:00 – 04:59
            greeting = "Still at it, sir."

        global _last_greeting_time
        should_greet = (time.time() - _last_greeting_time) > 60

        if should_greet:
            _last_greeting_time = time.time()

            async def _send_greeting():
                try:
                    audio_bytes = await synthesize_speech(greeting)
                    if audio_bytes:
                        encoded = base64.b64encode(audio_bytes).decode()
                        await ws.send_json({"type": "status", "state": "speaking"})
                        await ws.send_json({"type": "audio", "data": encoded, "text": greeting})
                        history.append({"role": "assistant", "content": greeting})
                        log.info(f"JARVIS: {greeting}")
                        await ws.send_json({"type": "status", "state": "idle"})
                except Exception as e:
                    log.warning(f"Greeting failed: {e}")

            asyncio.create_task(_send_greeting())

        try:
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            return  # WebSocket already gone

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # ── Fix-self: activate work mode in JARVIS repo ──
            if msg.get("type") == "fix_self":
                jarvis_dir = str(Path(__file__).parent)
                await work_session.start(jarvis_dir)
                response_text = "Work mode active in my own repo, sir. Tell me what needs fixing."
                tts = strip_markdown_for_tts(response_text)
                await ws.send_json({"type": "status", "state": "speaking"})
                audio = await synthesize_speech(tts)
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": response_text})
                else:
                    await ws.send_json({"type": "text", "text": response_text})
                continue

            # ── Study Mode end — generate session summary ──
            if msg.get("type") == "study_end":
                await ws.send_json({"type": "status", "state": "thinking"})
                topics_prompt = (
                    "The user has just ended their Study Mode session. "
                    "Review what topics were discussed and give a brief 1-2 sentence summary: "
                    "what was covered, and one word of encouragement. Be JARVIS — British, concise, professor-like."
                )
                summary_text = await generate_response(
                    topics_prompt, client, task_mgr, [],
                    conversation_history[-10:], session_summary=history.get_summary()
                )
                await ws.send_json({"type": "status", "state": "speaking"})
                audio = await synthesize_speech(strip_markdown_for_tts(summary_text))
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": summary_text})
                else:
                    await ws.send_json({"type": "text", "text": summary_text})
                await ws.send_json({"type": "status", "state": "idle"})
                continue

            # ── Interrupt (Live Conversation Mode) ──
            if msg.get("type") == "interrupt":
                _active_token.cancel()
                _active_token = CancelToken()
                log.info("Response interrupted by user")
                continue

            if msg.get("type") != "transcript" or not msg.get("isFinal"):
                continue

            user_text = apply_speech_corrections(msg.get("text", "").strip())
            if not user_text:
                continue

            # Cancel any in-flight response and issue a fresh token
            _active_token.cancel()
            _active_token = CancelToken()
            await asyncio.sleep(0.02)  # yield so any in-progress awaits see cancellation

            # Extract streaming flag sent by frontend in Live Conversation Mode
            streaming_mode = bool(msg.get("streaming", False))

            voice_state["last_user_time"] = time.time()
            log.info(f"User: {user_text}")
            await ws.send_json({"type": "status", "state": "thinking"})

            # Lazy project scan on first message
            global cached_projects
            if not cached_projects:
                try:
                    # Run in executor since scan_projects does sync file I/O
                    loop = asyncio.get_event_loop()
                    cached_projects = await asyncio.wait_for(
                        loop.run_in_executor(None, _scan_projects_sync),
                        timeout=3
                    )
                    log.info(f"Scanned {len(cached_projects)} projects")
                except Exception:
                    cached_projects = []

            try:
                _skip_tts = False  # set True in streaming mode (audio already sent)

                # ── CHECK FOR MODE SWITCHES ──
                t_lower = user_text.lower()

                # ── PLANNING MODE: answering clarifying questions ──
                if planner.is_planning:
                    # Check for bypass
                    if any(p in t_lower for p in BYPASS_PHRASES):
                        plan = planner.active_plan
                        if plan:
                            plan.skipped = True
                            for q in plan.pending_questions[plan.current_question_index:]:
                                if q.get("default") is not None and q["key"] not in plan.answers:
                                    plan.answers[q["key"]] = q["default"]
                        prompt = await planner.build_prompt()
                        name = _generate_project_name(prompt)
                        path = str(Path.home() / "Desktop" / name)
                        os.makedirs(path, exist_ok=True)
                        Path(path, "CLAUDE.md").write_text(prompt)
                        did = dispatch_registry.register(name, path, prompt[:200])
                        asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                        planner.reset()
                        response_text = "Building it now, sir."
                    elif planner.active_plan and planner.active_plan.confirmed is False and planner.active_plan.current_question_index >= len(planner.active_plan.pending_questions):
                        # Confirmation phase
                        result = await planner.handle_confirmation(user_text)
                        if result["confirmed"]:
                            prompt = await planner.build_prompt()
                            name = _generate_project_name(prompt)
                            path = str(Path.home() / "Desktop" / name)
                            os.makedirs(path, exist_ok=True)
                            Path(path, "CLAUDE.md").write_text(prompt)
                            did = dispatch_registry.register(name, path, prompt[:200])
                            asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                            planner.reset()
                            response_text = "On it, sir."
                        elif result["cancelled"]:
                            planner.reset()
                            response_text = "Cancelled, sir."
                        else:
                            response_text = result.get("modification_question", "How shall I adjust the plan, sir?")
                    else:
                        result = await planner.process_answer(user_text, cached_projects)
                        if result["plan_complete"]:
                            response_text = result.get("confirmation_summary", "Ready to build. Shall I proceed, sir?")
                        else:
                            response_text = result.get("next_question", "What else, sir?")

                elif any(w in t_lower for w in ["quit work mode", "exit work mode", "go back to chat", "regular mode", "stop working"]):
                    if work_session.active:
                        await work_session.stop()
                        response_text = "Back to conversation mode, sir."
                    else:
                        response_text = "Already in conversation mode, sir."

                # ── WORK MODE: speech → claude -p → Haiku summary → JARVIS voice ──
                elif work_session.active:
                    if is_casual_question(user_text):
                        # Quick chat — bypass claude -p, use Haiku
                        response_text = await generate_response(
                            user_text, anthropic_client, task_manager,
                            cached_projects, history,
                            last_response=last_jarvis_response,
                            session_summary=session_summary,
                        )
                    else:
                        # Send to claude -p (full power)
                        await ws.send_json({"type": "status", "state": "working"})
                        log.info(f"Work mode → claude -p: {user_text[:80]}")

                        full_response = await work_session.send(user_text)

                        # Detect if Claude Code is stalling (asking questions instead of building)
                        if full_response and anthropic_client:
                            stall_words = ["which option", "would you prefer", "would you like me to",
                                           "before I proceed", "before proceeding", "should I",
                                           "do you want me to", "let me know", "please confirm",
                                           "which approach", "what would you"]
                            is_stalling = any(w in full_response.lower() for w in stall_words)
                            if is_stalling and work_session._message_count >= 2:
                                # Claude Code keeps asking — push it to build
                                log.info("Claude Code stalling — pushing to build")
                                push_response = await work_session.send(
                                    "Stop asking questions. Use your best judgment and start building now. "
                                    "Write the actual code files. Go with the simplest reasonable approach."
                                )
                                if push_response:
                                    full_response = push_response

                        # Auto-open any localhost URLs Claude Code mentions
                        import re as _re
                        localhost_match = _re.search(r'https?://localhost:\d+', full_response or "")
                        if localhost_match:
                            asyncio.create_task(_execute_browse(localhost_match.group(0)))
                            log.info(f"Auto-opening {localhost_match.group(0)}")

                        # Always summarize work mode responses via Haiku
                        if full_response and anthropic_client:
                            try:
                                summary = await anthropic_client.messages.create(
                                    model="claude-haiku-4-5-20251001",
                                    max_tokens=100,
                                    system=(
                                        f"You are JARVIS reporting to the user ({USER_NAME}). Summarize what happened in 1-2 sentences. "
                                        "Speak in first person — 'I built', 'I found', 'I set up'. "
                                        "You are talking TO THE USER, not to a coding tool. "
                                        "NEVER give instructions like 'go ahead and build' or 'set up the frontend' — those are NOT for the user. "
                                        "NEVER say 'Claude Code'. NEVER output [ACTION:...] tags. "
                                        "NEVER read out URLs. No markdown. British precision."
                                    ),
                                    messages=[{"role": "user", "content": f"Claude Code said:\n{full_response[:2000]}"}],
                                )
                                response_text = summary.content[0].text
                                try:
                                    usage.log_llm_call(
                                        feature="build_summary",
                                        model="claude-haiku-4-5-20251001",
                                        input_tokens=getattr(summary.usage, "input_tokens", 0),
                                        output_tokens=getattr(summary.usage, "output_tokens", 0),
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                response_text = full_response[:200]
                        else:
                            response_text = full_response

                # ── ORDER / RESERVATION CONTINUATION ──────────────────────────────
                # If an order or reservation is awaiting confirmation/slot-fill,
                # route the reply directly to the orchestrator.
                elif voice_state.get("active_order_id"):
                    ord_id = voice_state["active_order_id"]
                    result = await order_orchestrator.process_answer(
                        ord_id, user_text, anthropic_client, ws
                    )
                    response_text = result.get("message", "Understood, sir.")
                    if result.get("plan_complete") or result.get("status") in ("cancelled", "executing", "error", "no_provider", "not_found"):
                        voice_state.pop("active_order_id", None)
                        voice_state.pop("order_stage", None)
                    else:
                        voice_state["order_stage"] = result.get("status")

                elif voice_state.get("active_reservation_id"):
                    res_id = voice_state["active_reservation_id"]
                    result = await reservation_orchestrator.process_answer(
                        res_id, user_text, anthropic_client, ws
                    )
                    response_text = result.get("message", "Understood, sir.")
                    if result.get("plan_complete") or result.get("status") in ("cancelled", "draft_sent", "error", "not_found"):
                        voice_state.pop("active_reservation_id", None)
                        voice_state.pop("reservation_stage", None)

                # ── CHAT MODE: fast keyword detection + Haiku ──
                else:
                    action = detect_action_fast(user_text)

                    if action:
                        if action["action"] == "open_terminal":
                            response_text = await handle_open_terminal()
                        elif action["action"] == "show_recent":
                            response_text = await handle_show_recent()
                        elif action["action"] == "describe_screen":
                            response_text = "Taking a look now, sir."
                            asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "check_calendar":
                            response_text = "Checking your calendar now, sir."
                            asyncio.create_task(_lookup_and_report("calendar", _do_calendar_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "check_mail":
                            response_text = "Checking your inbox now, sir."
                            asyncio.create_task(_lookup_and_report("mail", _do_mail_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "check_dispatch":
                            recent = dispatch_registry.get_most_recent()
                            if not recent:
                                response_text = "No recent builds on record, sir."
                            else:
                                name = recent["project_name"]
                                status = recent["status"]
                                if status == "building" or status == "pending":
                                    elapsed = int(time.time() - recent["updated_at"])
                                    response_text = f"Still working on {name}, sir. Been at it for {elapsed} seconds."
                                elif status == "completed":
                                    response_text = recent.get("summary") or f"{name} is complete, sir."
                                elif status in ("failed", "timeout"):
                                    response_text = f"{name} ran into problems, sir."
                                else:
                                    response_text = f"{name} is {status}, sir."
                        elif action["action"] == "check_tasks":
                            tasks = get_open_tasks()
                            response_text = format_tasks_for_voice(tasks)
                        elif action["action"] == "check_usage":
                            response_text = get_usage_summary()
                        elif action["action"] == "order_status":
                            active = memory.get_active_order()
                            if active:
                                eta = active.get("eta_minutes")
                                eta_str = f"ETA {eta} minutes" if eta else "ETA unknown"
                                response_text = (
                                    f"{active['restaurant']} order is {active['status']}. "
                                    f"{eta_str}, sir."
                                )
                            else:
                                recent = memory.recent_orders(1)
                                if recent:
                                    o = recent[0]
                                    response_text = (
                                        f"Last order was {o['restaurant']}, "
                                        f"status: {o['status']}, sir."
                                    )
                                else:
                                    response_text = "No recent orders on record, sir."
                        elif action["action"] == "cancel_order":
                            order_id = voice_state.get("active_order_id")
                            if order_id:
                                msg = order_orchestrator.cancel_pending(order_id)
                                voice_state.pop("active_order_id", None)
                                response_text = msg
                            else:
                                response_text = "No active order to cancel, sir."
                        else:
                            response_text = "Understood, sir."
                    else:
                        if not anthropic_client:
                            response_text = "API key not configured."
                            _skip_tts = False
                        elif streaming_mode:
                            # ── Live Conversation Mode: streaming pipeline ──
                            current_token = _active_token
                            await ws.send_json({"type": "status", "state": "speaking"})
                            response_text = await generate_response_streaming(
                                user_text, anthropic_client, task_manager,
                                cached_projects, history, ws, current_token,
                                last_response=last_jarvis_response,
                                session_summary=session_summary,
                            )
                            if current_token.is_cancelled:
                                # Interrupted — save context and skip remaining processing
                                partial = current_token.partial_text.strip()
                                if partial:
                                    history.append({"role": "user", "content": user_text})
                                    history.append({"role": "assistant",
                                                    "content": f"[interrupted mid-response: '{partial[:60]}...']"})
                                    last_jarvis_response = partial
                                    log.info(f"JARVIS interrupted after: {partial[:40]}...")
                                continue  # skip TTS block + history update
                            _skip_tts = True  # streaming already sent audio chunk by chunk
                        else:
                            response_text = await generate_response(
                                user_text, anthropic_client, task_manager,
                                cached_projects, history,
                                last_response=last_jarvis_response,
                                session_summary=session_summary,
                            )
                            _skip_tts = False

                        if not streaming_mode:
                            # Check for action tags embedded in LLM response (non-streaming only)
                            clean_response, embedded_action = extract_action(response_text)
                            if embedded_action:
                                log.info(f"LLM embedded action: {embedded_action}")
                                response_text = clean_response
                                # Ensure there's always something to speak
                                if not response_text.strip():
                                    action_type = embedded_action["action"]
                                    if action_type == "prompt_project":
                                        proj = embedded_action["target"].split("|||")[0].strip()
                                        response_text = f"Connecting to {proj} now, sir."
                                    elif action_type == "build":
                                        response_text = "On it, sir."
                                    elif action_type == "research":
                                        response_text = "Looking into that now, sir."
                                    else:
                                        response_text = "Right away, sir."

                                if embedded_action["action"] == "build":
                                    # Build in background — JARVIS stays conversational
                                    target = embedded_action["target"]
                                    name = _generate_project_name(target)
                                    path = str(Path.home() / "Desktop" / name)
                                    os.makedirs(path, exist_ok=True)

                                    # Write detailed CLAUDE.md
                                    Path(path, "CLAUDE.md").write_text(
                                        f"# Task\n\n{target}\n\n"
                                        "## Instructions\n"
                                        "- BUILD THIS NOW. Do not ask clarifying questions.\n"
                                        "- Use your best judgment for any design/architecture decisions.\n"
                                        "- Write complete, working code files — not plans or specs.\n"
                                        "- If it's a web app: use React + Vite + Tailwind unless specified otherwise.\n"
                                        "- Make it look polished and professional. Modern UI, clean layout.\n"
                                        "- Ensure it runs with a single command (npm run dev or similar).\n"
                                        "- If you reference a real product's UI (e.g. 'Zillow clone'), match their actual layout and features closely.\n"
                                        "- Use realistic mock data, not placeholder Lorem Ipsum.\n"
                                        "- After building, start the dev server and verify the app loads without errors.\n"
                                        "- IMPORTANT: Your LAST line of output MUST be exactly: RUNNING_AT=http://localhost:PORT (the actual port the dev server is using)\n"
                                    )

                                    # Register and dispatch
                                    did = dispatch_registry.register(name, path, target)
                                    asyncio.create_task(
                                        _execute_prompt_project(name, target, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state)
                                    )
                                elif embedded_action["action"] == "browse":
                                    asyncio.create_task(_execute_browse(embedded_action["target"]))
                                elif embedded_action["action"] == "research":
                                    # Research enters work mode too
                                    name = _generate_project_name(embedded_action["target"])
                                    path = str(Path.home() / "Desktop" / name)
                                    os.makedirs(path, exist_ok=True)
                                    await work_session.start(path)
                                    asyncio.create_task(
                                        self_work_and_notify(work_session, embedded_action["target"], ws)
                                    )
                                elif embedded_action["action"] == "live_research":
                                    # Live Lab — visible research with streaming events
                                    from live_research import run_live_research
                                    asyncio.create_task(
                                        run_live_research(anthropic_client, ws, embedded_action["target"])
                                    )
                                elif embedded_action["action"] == "open_terminal":
                                    asyncio.create_task(_execute_open_terminal())
                                elif embedded_action["action"] == "prompt_project":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        proj_name, _, prompt = target.partition("|||")
                                        proj_name = proj_name.strip()
                                        prompt = prompt.strip()
                                        # Check for recent completed dispatch before re-dispatching
                                        recent = dispatch_registry.get_recent_for_project(proj_name)
                                        if recent and recent.get("summary"):
                                            log.info(f"Using recent dispatch result for {proj_name} instead of re-dispatching")
                                            response_text = recent["summary"]
                                            history.append({"role": "assistant", "content": f"[Previous dispatch result for {proj_name}]: {recent['summary']}"})
                                        else:
                                            asyncio.create_task(
                                                _execute_prompt_project(proj_name, prompt, work_session, ws, history=history, voice_state=voice_state)
                                            )
                                    else:
                                        log.warning(f"PROMPT_PROJECT missing ||| delimiter: {target}")
                                elif embedded_action["action"] == "add_task":
                                    target = embedded_action["target"]
                                    parts = target.split("|||")
                                    if len(parts) >= 2:
                                        priority = parts[0].strip() or "medium"
                                        title = parts[1].strip()
                                        desc = parts[2].strip() if len(parts) > 2 else ""
                                        due = parts[3].strip() if len(parts) > 3 else ""
                                        create_task(title=title, description=desc, priority=priority, due_date=due)
                                        log.info(f"Task created: {title}")
                                elif embedded_action["action"] == "add_note":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        topic, _, content = target.partition("|||")
                                        create_note(content=content.strip(), topic=topic.strip())
                                    else:
                                        create_note(content=target)
                                    log.info(f"Note created")
                                elif embedded_action["action"] == "complete_task":
                                    try:
                                        task_id = int(embedded_action["target"].strip())
                                        complete_task(task_id)
                                        log.info(f"Task {task_id} completed")
                                    except ValueError:
                                        pass
                                elif embedded_action["action"] == "remember":
                                    remember(embedded_action["target"].strip(), mem_type="fact", importance=7)
                                    log.info(f"Memory stored: {embedded_action['target'][:60]}")
                                elif embedded_action["action"] == "forget":
                                    try:
                                        n = memory.forget(embedded_action["target"].strip())
                                        log.info(f"Forgot {n} memory rows for: {embedded_action['target'][:60]}")
                                    except Exception as e:
                                        log.warning(f"forget failed: {e}")
                                elif embedded_action["action"] == "create_note":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        title, _, body = target.partition("|||")
                                        asyncio.create_task(create_apple_note(title.strip(), body.strip()))
                                        log.info(f"Apple Note created: {title.strip()}")
                                    else:
                                        asyncio.create_task(create_apple_note("JARVIS Note", target))
                                elif embedded_action["action"] == "screen":
                                    asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))
                                elif embedded_action["action"] == "read_note":
                                    # Read note in background and report back
                                    async def _read_and_report(search_term, _ws):
                                        note = await read_note(search_term)
                                        if note:
                                            msg = f"Sir, your note '{note['title']}' says: {note['body'][:200]}"
                                        else:
                                            msg = f"Couldn't find a note matching '{search_term}', sir."
                                        audio = await synthesize_speech(strip_markdown_for_tts(msg))
                                        if audio and _ws:
                                            try:
                                                await _ws.send_json({"type": "status", "state": "speaking"})
                                                await _ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                                            except Exception:
                                                pass
                                    asyncio.create_task(_read_and_report(embedded_action["target"].strip(), ws))

                                # ── Food-ordering action tags ──────────────────
                                elif embedded_action["action"] == "order_food":
                                    params = embedded_action.get("params", {})
                                    raw = embedded_action["target"]
                                    result = await order_orchestrator.start_order(
                                        raw_request=raw,
                                        anthropic_client=anthropic_client,
                                        ws=ws,
                                    )
                                    # Override TTS with the orchestrator's message/question
                                    response_text = result.get("message", response_text)
                                    # Register active order in voice state for follow-up
                                    voice_state["active_order_id"] = result.get("order_id")
                                    voice_state["order_stage"] = result.get("status")

                                elif embedded_action["action"] == "reserve_table":
                                    params = embedded_action.get("params", {})
                                    result = await reservation_orchestrator.start_reservation(
                                        raw_request=embedded_action["target"],
                                        restaurant=params.get("restaurant", ""),
                                        party_size=int(params.get("party", 2)),
                                        reservation_time=params.get("time", ""),
                                        phone=params.get("phone", ""),
                                        anthropic_client=anthropic_client,
                                        ws=ws,
                                    )
                                    response_text = result.get("message", response_text)
                                    voice_state["active_reservation_id"] = result.get("order_id")
                                    voice_state["reservation_stage"] = result.get("status")

                                elif embedded_action["action"] == "order_status":
                                    active = memory.get_active_order()
                                    if active:
                                        eta = active.get("eta_minutes")
                                        eta_str = f"ETA {eta} minutes" if eta else "ETA unknown"
                                        response_text = (
                                            f"{active['restaurant']} order is {active['status']}. "
                                            f"{eta_str}, sir."
                                        )
                                    else:
                                        recent = memory.recent_orders(1)
                                        if recent:
                                            o = recent[0]
                                            response_text = (
                                                f"Last order was {o['restaurant']}, "
                                                f"status: {o['status']}, sir."
                                            )
                                        else:
                                            response_text = "No recent orders on record, sir."

                                elif embedded_action["action"] == "cancel_order":
                                    params = embedded_action.get("params", {})
                                    oid_str = params.get("order_id", "")
                                    # Try active order in voice state first
                                    order_id = voice_state.get("active_order_id")
                                    if oid_str:
                                        try:
                                            order_id = int(oid_str)
                                        except ValueError:
                                            pass
                                    if order_id:
                                        msg = order_orchestrator.cancel_pending(order_id)
                                        voice_state.pop("active_order_id", None)
                                        response_text = msg
                                    else:
                                        response_text = "No active order to cancel, sir."

                # Update history
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": response_text})

                # Three-tier memory: also track in session buffer
                session_buffer.append({"role": "user", "content": user_text})
                session_buffer.append({"role": "assistant", "content": response_text})

                # Check if rolling summary needs updating
                messages_since_last_summary += 1
                if messages_since_last_summary >= 5 and len(history) > 20 and not summary_update_pending:
                    summary_update_pending = True
                    messages_since_last_summary = 0
                    # Get messages that are about to be rotated out
                    rotated = history[:-20] if len(history) > 20 else []
                    if rotated and anthropic_client:
                        async def _do_summary():
                            nonlocal session_summary, summary_update_pending
                            session_summary = await _update_session_summary(
                                session_summary, rotated, anthropic_client
                            )
                            summary_update_pending = False
                        asyncio.create_task(_do_summary())
                    else:
                        summary_update_pending = False

                # Extract memories in background (doesn't block response)
                if anthropic_client and len(user_text) > 15:
                    asyncio.create_task(extract_memories(user_text, response_text, anthropic_client))

                # TTS — skipped in streaming mode (audio already sent sentence by sentence)
                if not _skip_tts:
                    tts = strip_markdown_for_tts(response_text)
                    await ws.send_json({"type": "status", "state": "speaking"})
                    audio = await synthesize_speech(tts)
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": response_text})
                    else:
                        await ws.send_json({"type": "text", "text": response_text})
                        await ws.send_json({"type": "status", "state": "idle"})
                log.info(f"JARVIS: {response_text}")
                last_jarvis_response = response_text

            except Exception as e:
                log.error(f"Error: {e}", exc_info=True)
                try:
                    fallback = "Something went wrong, sir."
                    audio = await synthesize_speech(fallback)
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": fallback})
                    else:
                        await ws.send_json({"type": "audio", "data": "", "text": fallback})
                    # Let client's audioPlayer.onFinished handle idle transition
                except Exception:
                    pass

    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected")
    except Exception as e:
        log.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        task_manager.unregister_websocket(ws)
        # Clear the hotkey's WS reference if it still points to this socket.
        if _active_ws is ws:
            _active_ws = None
            _active_ws_history = None
            _active_ws_voice_state = None


# ---------------------------------------------------------------------------
# Settings / Configuration endpoints
# ---------------------------------------------------------------------------

def _env_file_path() -> Path:
    return Path(__file__).parent / ".env"

def _env_example_path() -> Path:
    return Path(__file__).parent / ".env.example"

def _read_env() -> tuple[list[str], dict[str, str]]:
    """Read .env file. Returns (raw_lines, parsed_dict). Creates from .env.example if missing."""
    path = _env_file_path()
    if not path.exists():
        example = _env_example_path()
        if example.exists():
            import shutil as _shutil
            _shutil.copy2(str(example), str(path))
        else:
            path.write_text("")
    lines = path.read_text().splitlines()
    parsed: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            parsed[k.strip()] = v.strip().strip('"').strip("'")
    return lines, parsed

def _write_env_key(key: str, value: str) -> None:
    """Update a single key in .env, preserving comments and order."""
    lines, _ = _read_env()
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            if k.strip() == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    _env_file_path().write_text("\n".join(new_lines) + "\n")
    os.environ[key] = value

class KeyUpdate(BaseModel):
    key_name: str
    key_value: str

class KeyTest(BaseModel):
    key_value: str | None = None

class PreferencesUpdate(BaseModel):
    user_name: str = ""
    honorific: str = "sir"
    calendar_accounts: str = "auto"
    study_mode: bool = False
    brutal_honesty_mode: bool = False
    hyper_mode: bool = False   # Hyper Intelligence Mode
    screen_hotkey_enabled: bool = True
    screen_hotkey: str = "<ctrl>+<shift>+j"
    proactive_enabled: bool = True
    model_fast: str = "claude-haiku-4-5"
    model_smart: str = "claude-haiku-4-5"
    memory_distill_enabled: bool = True

@app.post("/api/settings/keys")
async def api_settings_keys(body: KeyUpdate):
    allowed = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_TTS_VOICE", "OPENAI_TTS_MODEL", "USER_NAME", "HONORIFIC", "CALENDAR_ACCOUNTS"}
    if body.key_name not in allowed:
        return JSONResponse({"success": False, "error": "Invalid key name"}, status_code=400)
    _write_env_key(body.key_name, body.key_value)
    return {"success": True}

@app.post("/api/settings/test-anthropic")
async def api_test_anthropic(body: KeyTest):
    key = body.key_value or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return {"valid": False, "error": "No key provided"}
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        await client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10, messages=[{"role": "user", "content": "Hi"}])
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

@app.post("/api/settings/test-openai")
async def api_test_openai(body: KeyTest):
    key = body.key_value or os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"valid": False, "error": "No key provided"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "tts-1", "input": "test", "voice": OPENAI_TTS_VOICE, "response_format": "mp3"},
            )
            if resp.status_code == 200:
                return {"valid": True}
            elif resp.status_code == 401:
                return {"valid": False, "error": "Invalid API key"}
            else:
                return {"valid": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

@app.get("/api/settings/status")
async def api_settings_status():
    import shutil as _shutil
    _, env_dict = _read_env()
    claude_installed = _shutil.which("claude") is not None
    calendar_ok = mail_ok = notes_ok = False
    try: await get_todays_events(); calendar_ok = True
    except Exception: pass
    try: await get_unread_count(); mail_ok = True
    except Exception: pass
    try: await get_recent_notes(count=1); notes_ok = True
    except Exception: pass
    memory_count = task_count = 0
    try: memory_count = len(get_important_memories(limit=9999))
    except Exception: pass
    try: task_count = len(get_open_tasks())
    except Exception: pass
    return {
        "claude_code_installed": claude_installed,
        "calendar_accessible": calendar_ok,
        "mail_accessible": mail_ok,
        "notes_accessible": notes_ok,
        "memory_count": memory_count,
        "task_count": task_count,
        "server_port": 8340,
        "uptime_seconds": int(time.time() - _session_start),
        "env_keys_set": {
            "anthropic": bool(env_dict.get("ANTHROPIC_API_KEY", "").strip() and env_dict.get("ANTHROPIC_API_KEY", "") != "your-anthropic-api-key-here"),
            "openai": bool(env_dict.get("OPENAI_API_KEY", "").strip() and env_dict.get("OPENAI_API_KEY", "") != "your-openai-api-key-here"),
            "openai_tts_voice": env_dict.get("OPENAI_TTS_VOICE", "onyx"),
            "user_name": env_dict.get("USER_NAME", ""),
        },
    }

@app.get("/api/settings/preferences")
async def api_get_preferences():
    _, env_dict = _read_env()
    return {
        "user_name": env_dict.get("USER_NAME", ""),
        "honorific": env_dict.get("HONORIFIC", "sir"),
        "calendar_accounts": env_dict.get("CALENDAR_ACCOUNTS", "auto"),
        "study_mode": env_dict.get("STUDY_MODE", "").lower() in ("true", "1", "yes"),
        "brutal_honesty_mode": env_dict.get("BRUTAL_HONESTY_MODE", "").lower() in ("true", "1", "yes"),
        "hyper_mode": env_dict.get("HYPER_MODE", "").lower() in ("true", "1", "yes"),
        "screen_hotkey_enabled": env_dict.get("SCREEN_HOTKEY_ENABLED", "true").lower() in ("true", "1", "yes"),
        "screen_hotkey": env_dict.get("SCREEN_HOTKEY", "<ctrl>+<shift>+j"),
        "proactive_enabled": env_dict.get("PROACTIVE_ENABLED", "true").lower() in ("true", "1", "yes"),
        "model_fast": env_dict.get("MODEL_FAST", "claude-haiku-4-5"),
        "model_smart": env_dict.get("MODEL_SMART", "claude-haiku-4-5"),
        "memory_distill_enabled": env_dict.get("MEMORY_DISTILL_ENABLED", "true").lower() in ("true", "1", "yes"),
    }

@app.post("/api/settings/preferences")
async def api_save_preferences(body: PreferencesUpdate):
    _write_env_key("USER_NAME", body.user_name)
    _write_env_key("HONORIFIC", body.honorific)
    _write_env_key("CALENDAR_ACCOUNTS", body.calendar_accounts)
    _write_env_key("STUDY_MODE", "true" if body.study_mode else "false")
    _write_env_key("BRUTAL_HONESTY_MODE", "true" if body.brutal_honesty_mode else "false")
    _write_env_key("HYPER_MODE", "true" if body.hyper_mode else "false")
    _write_env_key("SCREEN_HOTKEY_ENABLED", "true" if body.screen_hotkey_enabled else "false")
    _write_env_key("SCREEN_HOTKEY", body.screen_hotkey or "<ctrl>+<shift>+j")
    _write_env_key("PROACTIVE_ENABLED", "true" if body.proactive_enabled else "false")
    # Apply live so the next proactive tick (within 60s) respects the new setting.
    os.environ["PROACTIVE_ENABLED"] = "true" if body.proactive_enabled else "false"
    # Model routing — apply immediately, persist to .env
    if body.model_fast:
        _write_env_key("MODEL_FAST", body.model_fast)
        os.environ["MODEL_FAST"] = body.model_fast
    if body.model_smart:
        _write_env_key("MODEL_SMART", body.model_smart)
        os.environ["MODEL_SMART"] = body.model_smart
    _write_env_key("MEMORY_DISTILL_ENABLED", "true" if body.memory_distill_enabled else "false")
    os.environ["MEMORY_DISTILL_ENABLED"] = "true" if body.memory_distill_enabled else "false"

    # Apply hotkey changes live so user doesn't need to restart.
    global _screen_hotkey
    try:
        if body.screen_hotkey_enabled:
            new_combo = body.screen_hotkey or "<ctrl>+<shift>+j"
            if _screen_hotkey is None:
                _screen_hotkey = ScreenHotkey(
                    combo=new_combo,
                    on_trigger=_handle_screen_hotkey,
                    loop=asyncio.get_event_loop(),
                )
                _screen_hotkey.start()
            elif _screen_hotkey.combo != new_combo or not _screen_hotkey.running:
                _screen_hotkey.rebind(new_combo)
        else:
            if _screen_hotkey is not None:
                _screen_hotkey.stop()
    except Exception as e:
        log.warning(f"failed to apply screen hotkey change: {e}")

    return {"success": True}

@app.get("/api/settings/personality")
async def api_get_personality():
    return {"content": load_personality()}

class PersonalityUpdate(BaseModel):
    content: str = ""

@app.post("/api/settings/personality")
async def api_save_personality(body: PersonalityUpdate):
    success = save_personality(body.content)
    return {"success": success}

@app.get("/api/google/status")
async def api_google_status():
    """Check if Google is authorized. Also returns OAuth flow state for polling."""
    try:
        from google_auth import is_connected, CREDENTIALS_FILE, get_oauth_status
        oauth = get_oauth_status()
        return {
            "connected":       is_connected(),
            "has_credentials": CREDENTIALS_FILE.exists(),
            "oauth_running":   oauth["running"],
            "oauth_error":     oauth["error"],
        }
    except Exception as e:
        return {"connected": False, "has_credentials": False, "oauth_running": False, "oauth_error": str(e)}

@app.post("/api/google/connect")
async def api_google_connect():
    """
    Start the Google OAuth flow.

    Returns {success: true, auth_url: "..."} immediately — the frontend should
    open auth_url in a new tab.  A background HTTP server on port 8341 waits for
    the Google redirect callback.  Poll /api/google/status until connected: true.
    """
    try:
        from google_auth import start_oauth
        auth_url = start_oauth()

        # Best-effort: also try to open the browser on the server side
        try:
            import webbrowser
            webbrowser.open(auth_url)
            log.info(f"Opened OAuth URL in browser")
        except Exception:
            pass  # Frontend will open it via window.open()

        return {"success": True, "auth_url": auth_url}
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        log.error(f"Google connect failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/google/disconnect")
async def api_google_disconnect():
    """Revoke Google token."""
    try:
        from google_auth import revoke
        revoke()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Control endpoints (restart, fix-self)
# ---------------------------------------------------------------------------

@app.get("/api/memory/me")
async def api_memory_me():
    """Return the human-readable personal-model digest (~/.jarvis/me.md)."""
    from memory_distiller import ME_MD_PATH
    if ME_MD_PATH.exists():
        try:
            return {"content": ME_MD_PATH.read_text(encoding="utf-8"), "path": str(ME_MD_PATH)}
        except Exception as e:
            return {"content": "", "path": str(ME_MD_PATH), "error": str(e)}
    return {"content": "(JARVIS hasn't built a personal-model digest yet. Have more conversations and check back.)", "path": str(ME_MD_PATH)}


@app.post("/api/memory/refresh")
async def api_memory_refresh():
    """Force-regenerate ~/.jarvis/me.md right now."""
    try:
        await refresh_me_md(anthropic_client)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/memory/forget-all")
async def api_memory_forget_all():
    """Nuke all stored memories. Irreversible — UI confirms before calling."""
    try:
        n = memory.forget("*")
        return {"success": True, "deleted": n}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/usage/detailed")
async def api_usage_detailed():
    """Cost dashboard payload — daily totals, per-feature, per-provider, recent calls."""
    try:
        return usage.detailed_summary()
    except Exception as e:
        log.error(f"usage summary failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/api/llm/models")
async def api_llm_models():
    """List available models per tier — Anthropic options + locally-pulled Ollama models."""
    anthropic_models = [
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "claude-opus-4-6",
    ]
    ollama_models: list[str] = []
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=2.0) as http:
            r = await http.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    name = m.get("name")
                    if name:
                        ollama_models.append(f"ollama:{name}")
    except Exception as e:
        log.debug(f"Ollama unreachable: {e}")
    return {
        "anthropic": anthropic_models,
        "ollama": ollama_models,
        "all": anthropic_models + ollama_models,
    }


# ---------------------------------------------------------------------------
# Auto-launch on Windows login (Startup folder management)
# ---------------------------------------------------------------------------

def _startup_lnk_path() -> Path:
    """The location Windows checks for per-user auto-start items."""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "JARVIS.lnk"


def _jarvis_vbs_path() -> Path:
    return Path(__file__).parent / "JARVIS.vbs"


def _jarvis_ico_path() -> Path:
    return Path(__file__).parent / "assets" / "jarvis.ico"


@app.get("/api/startup/status")
async def api_startup_status():
    """Is JARVIS configured to auto-launch on Windows sign-in?"""
    if sys.platform != "win32":
        return {"enabled": False, "supported": False, "reason": "Auto-launch is Windows-only for now."}
    lnk = _startup_lnk_path()
    return {"enabled": lnk.exists(), "supported": True, "path": str(lnk)}


class StartupToggle(BaseModel):
    enabled: bool


@app.post("/api/startup")
async def api_startup(body: StartupToggle):
    """Add or remove the JARVIS shortcut from the Windows Startup folder."""
    if sys.platform != "win32":
        return {"success": False, "error": "Auto-launch is Windows-only for now."}

    lnk = _startup_lnk_path()
    vbs = _jarvis_vbs_path()
    ico = _jarvis_ico_path()
    project_dir = Path(__file__).parent

    try:
        if body.enabled:
            if not vbs.exists():
                return {"success": False, "error": f"JARVIS.vbs not found at {vbs}"}
            lnk.parent.mkdir(parents=True, exist_ok=True)
            # Build a PowerShell script that creates a .lnk via WScript.Shell.
            # Single quotes around paths; embedded single quotes are escaped by doubling.
            def _ps_quote(p: Path) -> str:
                return "'" + str(p).replace("'", "''") + "'"
            ps = (
                "$ws = New-Object -ComObject WScript.Shell; "
                f"$sc = $ws.CreateShortcut({_ps_quote(lnk)}); "
                f"$sc.TargetPath = {_ps_quote(vbs)}; "
                f"$sc.WorkingDirectory = {_ps_quote(project_dir)}; "
                + (f"$sc.IconLocation = {_ps_quote(ico)}; " if ico.exists() else "")
                + "$sc.Description = 'Wake JARVIS'; "
                "$sc.Save()"
            )
            # CREATE_NO_WINDOW = 0x08000000 — don't flash a PowerShell console
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                creationflags=0x08000000,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return {"success": False, "error": f"PowerShell failed: {result.stderr[:300]}"}
            log.info(f"Auto-launch shortcut created at {lnk}")
            return {"success": True, "enabled": True, "path": str(lnk)}
        else:
            if lnk.exists():
                lnk.unlink()
                log.info(f"Auto-launch shortcut removed from {lnk}")
            return {"success": True, "enabled": False}
    except Exception as e:
        log.error(f"startup toggle failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/desktop/launch-orb")
async def api_launch_orb():
    """Spawn the desktop floating-orb shell as a detached subprocess.

    The shell auto-detects the running backend/frontend and pops a borderless
    always-on-top orb window. Idempotent — clicking twice just launches a second
    orb (rare; users can quit the extra via the tray).
    """
    try:
        shell_path = Path(__file__).parent / "desktop_shell.py"
        if not shell_path.exists():
            return {"success": False, "error": "desktop_shell.py not found"}
        creationflags = 0
        if sys.platform == "win32":
            # DETACHED_PROCESS so closing this server doesn't kill the orb
            creationflags = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen(
            [sys.executable, str(shell_path)],
            cwd=str(shell_path.parent),
            creationflags=creationflags,
            close_fds=True,
        )
        log.info("Floating orb launched")
        return {"success": True}
    except Exception as e:
        log.error(f"failed to launch orb: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/restart")
async def api_restart():
    """Restart the JARVIS server."""
    log.info("Restart requested — shutting down in 2 seconds")
    async def _restart():
        await asyncio.sleep(2)
        cmd = [sys.executable, __file__, "--port", "8340", "--host", "0.0.0.0"]
        os.execv(sys.executable, cmd)
    asyncio.create_task(_restart())
    return {"status": "restarting"}


@app.post("/api/fix-self")
async def api_fix_self():
    """Enter work mode in the JARVIS repo — JARVIS can now fix himself."""
    jarvis_dir = str(Path(__file__).parent)
    # The work_session is per-WebSocket, so we set a flag that the handler picks up
    # For now, also open Terminal so user can see
    script = (
        'tell application "Terminal"\n'
        '    activate\n'
        f'    do script "cd {jarvis_dir} && claude --dangerously-skip-permissions"\n'
        'end tell'
    )
    await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    log.info("Work mode: JARVIS repo opened for self-improvement")
    return {"status": "work_mode_active", "path": jarvis_dir}


# ---------------------------------------------------------------------------
# Static file serving (frontend)
# ---------------------------------------------------------------------------

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    # Mount static asset directories from build output
    _assets_dir = FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # Serve PWA files (manifest, icons, sw) from dist root
    _icons_dir = FRONTEND_DIST / "icons"
    if _icons_dir.exists():
        app.mount("/icons", StaticFiles(directory=str(_icons_dir)), name="icons")

    @app.get("/manifest.json")
    async def serve_manifest():
        return FileResponse(str(FRONTEND_DIST / "manifest.json"))

    @app.get("/sw.js")
    async def serve_sw():
        sw = FRONTEND_DIST / "sw.js"
        if sw.exists():
            return FileResponse(str(sw), media_type="application/javascript")
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    @app.get("/registerSW.js")
    async def serve_register_sw():
        rsw = FRONTEND_DIST / "registerSW.js"
        if rsw.exists():
            return FileResponse(str(rsw), media_type="application/javascript")
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    # Catch-all SPA route — serves index.html for any unmatched path
    # (must be last to avoid shadowing API/WS routes)
    @app.get("/{full_path:path}")
    async def serve_spa_catch_all(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        return FileResponse(str(FRONTEND_DIST / "index.html"))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="JARVIS Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8340, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with key.pem/cert.pem")
    args = parser.parse_args()

    # Auto-detect SSL certs
    cert_file = Path(__file__).parent / "cert.pem"
    key_file = Path(__file__).parent / "key.pem"
    use_ssl = args.ssl or (cert_file.exists() and key_file.exists())

    proto = "https" if use_ssl else "http"
    ws_proto = "wss" if use_ssl else "ws"

    print()
    print("  J.A.R.V.I.S. Server v0.1.0")
    print(f"  WebSocket: {ws_proto}://{args.host}:{args.port}/ws/voice")
    print(f"  REST API:  {proto}://{args.host}:{args.port}/api/")
    print(f"  Tasks:     {proto}://{args.host}:{args.port}/api/tasks")
    print()

    ssl_kwargs = {}
    if use_ssl:
        ssl_kwargs["ssl_keyfile"] = str(key_file)
        ssl_kwargs["ssl_certfile"] = str(cert_file)

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        **ssl_kwargs,
    )
