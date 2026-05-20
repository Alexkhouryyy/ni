"""Core Claude agent with tool use, extended thinking, and screen vision."""
import json
import threading
import anthropic
import config
from agent.memory import Memory
from agent import longterm
from agent import safety
from agent import mcp_client
from agent import orchestrator
from agent import knowledge
from agent import self_mod
from agent import goals
from agent import entities
from agent import reflection
from agent import telemetry
from agent import resilience
from tools import computer, bash, research, files, browser, repl, vision, phone, image_gen

SYSTEM_PROMPT = """You are an advanced AI agent with voice interface, computer vision, computer control, \
research capabilities, and a bash terminal. You are running on the user's machine and can see their screen.

## PERSONALITY — This is non-negotiable:
- You are DIRECT and CONFIDENT. You say what you think, not what you think the user wants to hear.
- You PUSH BACK when you disagree. If an idea is flawed, a plan is risky, or there's a clearly better \
approach, say so plainly and explain why. You are not a yes-man.
- You are PROACTIVE. You notice things on the screen and bring them up without being asked. If you see \
an error, a better way to do something, or something interesting — you say so.
- You THINK before acting. For complex tasks, reason through the problem first. Consider consequences, \
edge cases, and alternatives before touching anything.
- You are HONEST about uncertainty. "I don't know" and "I'm not sure, let me research it" are valid answers.
- You have OPINIONS. When asked what you think, give an actual answer with reasoning — not a list of options.

## CAPABILITIES:
- **screenshot**: See the current state of the user's screen (always do this before acting on the UI)
- **click / right_click / double_click**: Click anywhere on screen
- **type_text**: Type text at cursor position
- **hotkey**: Press key combinations (e.g. ctrl+c, alt+tab, super+l)
- **scroll**: Scroll at a position
- **bash**: Run shell commands (grep, find, pip install, git, write code, run scripts, anything)
- **web_search**: Search the web for current information
- **web_browse**: Fetch and read a specific URL
- **deep_research**: Comprehensive research on a topic (search + read multiple sources)
- **browser_***: Drive a real Chromium browser — goto, click, fill, press, get_text, screenshot, \
evaluate JS. Use this when you need to actually INTERACT with a website (log in, fill forms, \
click buttons, submit). Use web_browse for read-only access.
- **schedule_task / list_scheduled_tasks / cancel_scheduled_task**: Schedule autonomous recurring \
tasks (daily briefings, reminders, periodic checks). Tasks run even when you're not talking.
- **mcp__***: Dynamically loaded tools from configured MCP servers (Slack, Notion, Gmail, Calendar, \
etc.). If these appear, use them for integrations with the user's real data.
- **spawn_subagent / wait_for_subagents**: For complex multi-part tasks, spawn role-specialized \
sub-agents (researcher, coder, browser, analyst, writer, planner) IN PARALLEL. Then wait for them. \
This is MUCH faster than doing everything sequentially. Use for "research X and also build Y" style tasks.
- **python_exec / python_reset**: Persistent Python REPL. Variables survive across calls. \
Use for data analysis, math, plots, anything stateful. Plots come back as images you can see.
- **kb_search / kb_reindex**: Semantic search over the user's actual files (notes, docs, code, PDFs). \
Use when the user asks about THEIR stuff: "what did I write about", "find that note", \
"where in my code does X happen".
- **update_system_prompt / register_new_tool / revert_self_mod**: Self-modification. \
When the user gives a durable instruction ("always X", "from now on Y"), update your prompt. \
When you notice a recurring task that needs a tool you lack, register one. \
All self-mods persist across sessions.
- **find_on_screen / click_on / annotate_screenshot / click_mark**: Vision precision via OCR. \
Whenever you can identify a click target by its text, PREFER click_on("Submit") over guessing \
pixel coords with click(x,y). For complex UIs, call annotate_screenshot to get numbered marks, \
then click_mark(N) to pick the right element. This is dramatically more reliable than raw clicks.
- **set_goal / list_goals / update_goal / evaluate_recent_work**: Strategic agency. \
When the user expresses a goal ("I want to launch by June", "this week I want to ship X"), \
call set_goal. After meaningful progress on a goal, call update_goal with a progress_note. \
At the end of work sessions or when asked "how have I been doing?", call evaluate_recent_work.
- **entity_upsert / entity_relate / entity_query / entity_graph**: Knowledge graph. \
When the user mentions a PERSON, PROJECT, PLACE, or recurring CONCEPT — call entity_upsert. \
When they describe a relationship ("Sam is my co-founder", "the launch depends on the backend"), \
call entity_relate. When asked about someone/something, call entity_query first to load the graph context. \
Build the graph as you talk — it's how you remember structurally.
- **reflect_now / list_reflections / apply_reflection**: Closed-loop learning. \
You consolidate the day's events nightly via a cron — but if the user asks "what did you learn?" \
or "review the week", run reflect_now and present the pending reflections. \
apply_reflection(id, accept=True/False) commits or rejects a pending insight.
- **sms_send / call_user**: Phone reach. When the user is AFK or a scheduled task finishes \
something important, SMS them. Use call_user only for things that genuinely warrant a phone ring.
- **generate_image**: Create images from a text prompt (logos, hero shots, diagrams, mockups). \
Returns local file paths. Reference them in your reply.
- **usage_summary / replay_session**: Self-observability. Use when the user asks about cost, \
token usage, cache performance, or wants to debug what happened in a past session.
- **read_file**: Read a file
- **write_file**: Create or overwrite a file
- **append_file**: Append to a file
- **list_dir**: List directory contents
- **find_files**: Find files matching a pattern

## BEHAVIOR RULES:
1. For ANY task involving the UI, take a screenshot FIRST to see the current state.
2. For clicks: ALWAYS prefer click_on("text label") over raw click(x,y). The latter is a last resort.
3. For dense UIs without obvious text anchors, use annotate_screenshot then click_mark.
4. Chain tools — plan the full sequence before starting, then execute step by step.
5. After completing a task, briefly confirm what you did and what the result was.
6. If a task fails, diagnose why, try a different approach, and report what happened.
7. Never ask clarifying questions for simple tasks — make a reasonable assumption and proceed.
8. For destructive or irreversible actions (deleting files, sending messages, etc.), confirm with the user first.
9. When you notice something on screen worth mentioning (error, opportunity, concern) — do it.

## LONG-TERM MEMORY:
You have persistent memory across sessions via `remember` and `recall` tools.
- USE `remember` proactively to save: user's name, preferences, ongoing projects, important decisions, \
recurring contexts, things the user mentions casually that you should retain.
- USE `recall` at the start of relevant tasks to surface context you previously saved.
- Don't ask permission to remember — just do it for anything that looks durable.
- Importance scale: 10 = identity-level (name, role), 7-9 = ongoing project / strong preference, \
4-6 = useful context, 1-3 = ephemeral.

Keep responses CONCISE when speaking. You're a voice agent — no markdown, no bullet points in speech. \
Speak naturally, like a sharp colleague, not a documentation page."""

# Tool definitions for Claude
TOOLS = [
    {
        "name": "screenshot",
        "description": "Capture the current state of the user's screen. Always call this before interacting with the UI.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click",
        "description": "Click at screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "double": {"type": "boolean", "description": "Double-click", "default": False},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text at the current cursor position.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "hotkey",
        "description": "Press a keyboard shortcut (e.g. 'ctrl+c', 'alt+tab', 'ctrl+shift+t').",
        "input_schema": {
            "type": "object",
            "properties": {"keys": {"type": "string", "description": "Keys joined by '+', e.g. 'ctrl+c'"}},
            "required": ["keys"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll at a screen position. Positive clicks = scroll up, negative = scroll down.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "clicks": {"type": "integer", "description": "Number of scroll clicks. Negative = down."},
            },
            "required": ["x", "y", "clicks"],
        },
    },
    {
        "name": "bash",
        "description": "Run a bash command. Use for file operations, running scripts, installing packages, git, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 6},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_browse",
        "description": "Fetch and read the content of a specific URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "deep_research",
        "description": "Perform thorough research on a topic: searches and reads multiple sources.",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_file",
        "description": "Append content to an existing file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
            "required": [],
        },
    },
    {
        "name": "find_files",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.py'"},
                "base": {"type": "string", "description": "Base directory to search from", "default": "."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "remember",
        "description": (
            "Save a durable memory across sessions. Use proactively for: user identity (name, role), "
            "preferences, ongoing projects, decisions, recurring contexts. Don't ask permission — just save."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The thing to remember"},
                "kind": {
                    "type": "string",
                    "enum": ["fact", "preference", "project", "decision", "note"],
                    "default": "fact",
                },
                "importance": {
                    "type": "integer",
                    "description": "1-10. 10=identity, 7-9=project/strong preference, 4-6=context, 1-3=ephemeral",
                    "default": 5,
                },
                "tags": {"type": "string", "description": "Optional comma-separated tags", "default": ""},
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall",
        "description": "Retrieve past memories. Use at the start of relevant tasks to load context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring to match in content/tags", "default": ""},
                "kind": {"type": "string", "description": "Filter by kind", "default": ""},
                "limit": {"type": "integer", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "forget",
        "description": "Delete a memory by ID (only when explicitly asked, or when correcting wrong info).",
        "input_schema": {
            "type": "object",
            "properties": {"memory_id": {"type": "integer"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "browser_goto",
        "description": "Open a URL in a real Chromium browser. The browser persists across calls so you can navigate, click, fill forms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "headless": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_click",
        "description": "Click a CSS selector in the active browser page.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string", "description": "CSS selector, e.g. 'button.submit' or 'text=Sign in'"}},
            "required": ["selector"],
        },
    },
    {
        "name": "browser_fill",
        "description": "Fill a form field in the active browser page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "browser_press",
        "description": "Press a keyboard key in the browser, e.g. 'Enter', 'Tab', 'Escape'.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "browser_get_text",
        "description": "Extract visible text from a selector (default: whole body) in the active browser page.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string", "default": "body"}},
            "required": [],
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Take a screenshot of the active browser page. Use after interactions to verify state.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_evaluate",
        "description": "Run JavaScript in the active browser page. Returns the result as a string.",
        "input_schema": {
            "type": "object",
            "properties": {"js": {"type": "string", "description": "JavaScript expression"}},
            "required": ["js"],
        },
    },
    {
        "name": "browser_url",
        "description": "Get the current URL of the active browser page.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_close",
        "description": "Close the browser. Only use when done with browsing or freeing resources.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "schedule_task",
        "description": (
            "Schedule a recurring or one-off autonomous task. "
            "The agent will run the task prompt automatically at the given time. "
            "Examples: daily briefing, reminders, periodic checks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What the agent should do when this fires (full prompt)"},
                "trigger_type": {"type": "string", "enum": ["cron", "interval", "date"], "description": "cron=recurring at time, interval=every N minutes/hours, date=once at datetime"},
                "trigger_params": {
                    "type": "object",
                    "description": "cron: {hour, minute, day_of_week?} | interval: {minutes?, hours?} | date: {run_date: 'YYYY-MM-DD HH:MM:SS'}",
                },
            },
            "required": ["description", "trigger_type", "trigger_params"],
        },
    },
    {
        "name": "list_scheduled_tasks",
        "description": "List all scheduled autonomous tasks.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_scheduled_task",
        "description": "Cancel a scheduled task by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "spawn_subagent",
        "description": (
            "Spawn a role-specialized sub-agent to work on a task in parallel. "
            "Use for complex multi-part tasks. Returns a sub_id you can wait for. "
            "Roles: researcher, coder, browser, analyst, writer, planner."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["researcher", "coder", "browser", "analyst", "writer", "planner"]},
                "task": {"type": "string", "description": "The full task description for the sub-agent"},
                "use_thinking": {"type": "boolean", "default": False},
            },
            "required": ["role", "task"],
        },
    },
    {
        "name": "wait_for_subagents",
        "description": "Block until specified sub-agents finish. Pass empty list to wait for all running ones.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sub_ids": {"type": "array", "items": {"type": "string"}, "default": []},
                "timeout_seconds": {"type": "number", "default": 300},
            },
            "required": [],
        },
    },
    {
        "name": "python_exec",
        "description": (
            "Run Python code in a persistent IPython kernel. Variables, imports, and dataframes "
            "persist across calls. Plots (matplotlib) come back as images. Use for data analysis, "
            "stats, transformations, anything you'd do in a Jupyter notebook."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
    {
        "name": "python_reset",
        "description": "Restart the Python kernel — all variables cleared.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "kb_search",
        "description": (
            "Semantic search across the user's indexed files (notes, docs, code, PDFs). "
            "Use this when the user asks about THEIR stuff: 'what did I write about X', "
            "'find that note from last month', 'where in my code does Y happen'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 6},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kb_reindex",
        "description": "Reindex the given paths into the knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["paths"],
        },
    },
    {
        "name": "update_system_prompt",
        "description": (
            "Self-modify: append (or replace) the system prompt with new instructions. "
            "Use when the user gives you a durable behavioral instruction "
            "('always X', 'from now on Y', 'stop doing Z')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "addition": {"type": "string"},
                "replace": {"type": "boolean", "default": False},
            },
            "required": ["addition"],
        },
    },
    {
        "name": "register_new_tool",
        "description": (
            "Self-modify: register a new Python tool at runtime. The `code` must define "
            "`def run(inputs):` and return a string. Available immediately and persists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "input_schema": {"type": "object"},
                "code": {"type": "string", "description": "Python source defining def run(inputs): -> str"},
            },
            "required": ["name", "description", "input_schema", "code"],
        },
    },
    {
        "name": "revert_self_mod",
        "description": "Revert all self-modifications (or restore the previous backup).",
        "input_schema": {
            "type": "object",
            "properties": {"restore_backup": {"type": "boolean", "default": False}},
            "required": [],
        },
    },
    {
        "name": "find_on_screen",
        "description": "OCR the screen for text and return matching regions with bounding boxes. Use to locate UI elements by their visible text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to find (case-insensitive substring or phrase)"},
                "exact": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "click_on",
        "description": "OCR-find text on screen and click its center. Prefer this over click(x,y) when you can identify the target by text — much more reliable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "occurrence": {"type": "integer", "default": 0, "description": "0-indexed: which match to click if multiple"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "double": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "annotate_screenshot",
        "description": "Capture the screen with numbered visual marks on every detected text region. Returns the marked image (you can see it) and lets you reference marks by number with click_mark.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click_mark",
        "description": "Click a numbered mark from the most recent annotate_screenshot call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mark_number": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "double": {"type": "boolean", "default": False},
            },
            "required": ["mark_number"],
        },
    },
    {
        "name": "set_goal",
        "description": "Create a strategic goal. Use when the user expresses a longer-term aim ('I want to launch by end of June', 'my goal this week is X').",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string", "default": ""},
                "horizon": {"type": "string", "enum": ["day", "week", "month", "quarter"], "default": "week"},
                "deadline_iso": {"type": "string", "description": "Optional ISO date YYYY-MM-DD"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_goals",
        "description": "List goals. By default returns only active ones.",
        "input_schema": {
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "default": True},
                "horizon": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "update_goal",
        "description": "Update a goal's status or add a progress note. Use after meaningful work on a goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["active", "paused", "done", "abandoned"]},
                "progress_note": {"type": "string"},
                "score": {"type": "integer", "description": "1-10 satisfaction with this progress"},
            },
            "required": ["goal_id"],
        },
    },
    {
        "name": "evaluate_recent_work",
        "description": "Self-evaluate the last N days of work: what got done, what stalled, what to focus on next. Use weekly or when the user asks 'how have I been doing?'.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}},
            "required": [],
        },
    },
    # --- Tier-4: Knowledge Graph (entities + relations) ---
    {
        "name": "entity_upsert",
        "description": "Create or update an entity in the knowledge graph. Use whenever the user mentions a person, project, place, tool, or recurring concept.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "kind": {"type": "string", "enum": ["person", "project", "place", "concept", "tool", "file", "event", "org"]},
                "properties": {"type": "object", "description": "Arbitrary JSON properties (role, status, dates, notes)"},
                "importance": {"type": "integer", "default": 5},
            },
            "required": ["name"],
        },
    },
    {
        "name": "entity_relate",
        "description": "Create a typed directed edge between two entities. Both are upserted if missing. Use for any explicit or implicit relationship ('Sam is co-founder of NI', 'launch depends on backend').",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_name": {"type": "string"},
                "to_name": {"type": "string"},
                "kind": {"type": "string", "description": "Verb-phrase: 'co-founder', 'depends_on', 'lives_in', 'uses', 'created_by'"},
                "from_kind": {"type": "string", "default": "concept"},
                "to_kind": {"type": "string", "default": "concept"},
                "properties": {"type": "object"},
                "confidence": {"type": "number", "default": 1.0},
            },
            "required": ["from_name", "to_name", "kind"],
        },
    },
    {
        "name": "entity_query",
        "description": "Look up an entity by name + return its neighbours within N hops. Call this before answering questions about a person, project, or concept the user mentions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "hops": {"type": "integer", "default": 1},
            },
            "required": ["name"],
        },
    },
    {
        "name": "entity_graph",
        "description": "Return a subgraph of nodes + edges (default: top-importance slice). Useful for surveying what you know about a domain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_names": {"type": "array", "items": {"type": "string"}},
                "limit_nodes": {"type": "integer", "default": 100},
            },
            "required": [],
        },
    },
    # --- Tier-4: Reflection Engine ---
    {
        "name": "reflect_now",
        "description": "Run the consolidation pass right now: reviews the last N hours of activity and writes reflections. High-confidence ones auto-apply (new memories, entities, goal progress). Returns counts.",
        "input_schema": {
            "type": "object",
            "properties": {"hours": {"type": "integer", "default": 24}},
            "required": [],
        },
    },
    {
        "name": "list_reflections",
        "description": "List pending (or applied/rejected) reflections from the consolidation engine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "applied", "rejected"], "default": "pending"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": [],
        },
    },
    {
        "name": "apply_reflection",
        "description": "Accept or reject a pending reflection by id. Accepting commits its action (remember/forget/entity/relate/goal_progress).",
        "input_schema": {
            "type": "object",
            "properties": {
                "reflection_id": {"type": "integer"},
                "accept": {"type": "boolean", "default": True},
            },
            "required": ["reflection_id"],
        },
    },
    # --- Tier-4: Phone (Twilio) ---
    {
        "name": "sms_send",
        "description": "Send an SMS via Twilio to the user (or another allowed number). Use proactively when something important finishes and the user is AFK.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "E.164 number, e.g. +14155551234"},
                "body": {"type": "string", "description": "Message text (≤1500 chars)"},
            },
            "required": ["to", "body"],
        },
    },
    {
        "name": "call_user",
        "description": "Place an outbound voice call via Twilio that speaks `message` then hangs up. Use sparingly — only for genuinely urgent things.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["to", "message"],
        },
    },
    # --- Tier-4: Image generation ---
    {
        "name": "generate_image",
        "description": "Generate an image from a text prompt (Replicate/FLUX). Returns saved local file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "model": {"type": "string", "description": "Replicate model id, default flux-schnell"},
                "size": {"type": "string", "default": "1024x1024"},
                "n": {"type": "integer", "default": 1},
            },
            "required": ["prompt"],
        },
    },
    # --- Tier-4: Telemetry / Replay ---
    {
        "name": "usage_summary",
        "description": "Return token usage, cost, and cache hit rate for the last N days.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}},
            "required": [],
        },
    },
    {
        "name": "replay_session",
        "description": "Return chronological turns + per-call usage for a past session (for self-debugging or 'what happened yesterday' questions).",
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "integer"}},
            "required": ["session_id"],
        },
    },
]


def _execute_tool(name: str, inputs: dict) -> str:
    """Dispatch a tool call and return its result as a string."""
    # Safety check before execution
    proceed, reason = safety.check(name, inputs)
    if not proceed:
        return f"[BLOCKED by safety layer] {reason}"

    try:
        if name == "screenshot":
            b64, size = computer.screenshot()
            # Return as a special marker — handled in run() to inject image content
            return json.dumps({"__screenshot__": b64, "size": list(size)})

        elif name == "click":
            return computer.click(inputs["x"], inputs["y"], inputs.get("button", "left"), inputs.get("double", False))

        elif name == "type_text":
            return computer.type_text(inputs["text"])

        elif name == "hotkey":
            keys = inputs["keys"].split("+")
            return computer.hotkey(*keys)

        elif name == "scroll":
            return computer.scroll(inputs["x"], inputs["y"], inputs["clicks"])

        elif name == "bash":
            result = bash.run(inputs["command"], timeout=inputs.get("timeout", config.BASH_TIMEOUT))
            return bash.format_result(result)

        elif name == "web_search":
            results = research.search(inputs["query"], inputs.get("num_results", config.MAX_SEARCH_RESULTS))
            return json.dumps(results, indent=2)

        elif name == "web_browse":
            return research.browse(inputs["url"])

        elif name == "deep_research":
            return research.deep_research(inputs["topic"])

        elif name == "read_file":
            return files.read(inputs["path"])

        elif name == "write_file":
            return files.write(inputs["path"], inputs["content"])

        elif name == "append_file":
            return files.append(inputs["path"], inputs["content"])

        elif name == "list_dir":
            return files.list_dir(inputs.get("path", "."))

        elif name == "find_files":
            return files.find(inputs["pattern"], inputs.get("base", "."))

        elif name == "remember":
            return longterm.remember(
                inputs["content"],
                kind=inputs.get("kind", "fact"),
                importance=inputs.get("importance", 5),
                tags=inputs.get("tags", ""),
            )

        elif name == "recall":
            results = longterm.recall(
                query=inputs.get("query", ""),
                kind=inputs.get("kind", ""),
                limit=inputs.get("limit", 10),
            )
            if not results:
                return "No matching memories found."
            return json.dumps(results, indent=2)

        elif name == "forget":
            return longterm.forget(inputs["memory_id"])

        elif name == "browser_goto":
            return browser.goto(inputs["url"], headless=inputs.get("headless", False))
        elif name == "browser_click":
            return browser.click(inputs["selector"])
        elif name == "browser_fill":
            return browser.fill(inputs["selector"], inputs["text"])
        elif name == "browser_press":
            return browser.press(inputs["key"])
        elif name == "browser_get_text":
            return browser.get_text(inputs.get("selector", "body"))
        elif name == "browser_screenshot":
            b64 = browser.screenshot()
            return json.dumps({"__screenshot__": b64, "size": [1280, 800]})
        elif name == "browser_evaluate":
            return browser.evaluate(inputs["js"])
        elif name == "browser_url":
            return browser.current_url()
        elif name == "browser_close":
            return browser.close()

        elif name == "schedule_task":
            from agent import scheduler as sched
            return sched.schedule(inputs["description"], inputs["trigger_type"], inputs["trigger_params"])
        elif name == "list_scheduled_tasks":
            from agent import scheduler as sched
            tasks = sched.list_tasks()
            return json.dumps(tasks, indent=2) if tasks else "No scheduled tasks."
        elif name == "cancel_scheduled_task":
            from agent import scheduler as sched
            return sched.cancel(inputs["task_id"])

        elif name.startswith("mcp__"):
            return mcp_client.call(name, inputs)

        elif name == "spawn_subagent":
            return orchestrator.spawn(inputs["role"], inputs["task"], inputs.get("use_thinking", False))
        elif name == "wait_for_subagents":
            return json.dumps(
                orchestrator.wait_for(inputs.get("sub_ids") or None, inputs.get("timeout_seconds", 300)),
                indent=2,
            )

        elif name == "python_exec":
            result = repl.execute(inputs["code"])
            return json.dumps({
                "summary": repl.format_result(result),
                "_images": result["images"],
            })
        elif name == "python_reset":
            return repl.reset()

        elif name == "kb_search":
            results = knowledge.search(inputs["query"], inputs.get("top_k", 6))
            return json.dumps(results, indent=2)
        elif name == "kb_reindex":
            return knowledge.reindex(inputs["paths"], inputs.get("force", False))

        elif name == "update_system_prompt":
            return self_mod.update_system_prompt(inputs["addition"], inputs.get("replace", False))
        elif name == "register_new_tool":
            return self_mod.register_new_tool(
                inputs["name"], inputs["description"], inputs["input_schema"], inputs["code"]
            )
        elif name == "revert_self_mod":
            return self_mod.revert(inputs.get("restore_backup", False))

        elif name == "find_on_screen":
            return json.dumps(vision.find_on_screen(inputs["query"], inputs.get("exact", False)), indent=2)
        elif name == "click_on":
            return vision.click_on(
                inputs["query"],
                occurrence=inputs.get("occurrence", 0),
                button=inputs.get("button", "left"),
                double=inputs.get("double", False),
            )
        elif name == "annotate_screenshot":
            return vision.annotate_for_agent()
        elif name == "click_mark":
            return vision.click_mark(
                inputs["mark_number"],
                button=inputs.get("button", "left"),
                double=inputs.get("double", False),
            )

        elif name == "set_goal":
            return goals.set_goal(
                inputs["title"],
                inputs.get("description", ""),
                inputs.get("horizon", "week"),
                inputs.get("deadline_iso"),
            )
        elif name == "list_goals":
            result = goals.list_goals(
                active_only=inputs.get("active_only", True),
                horizon=inputs.get("horizon"),
            )
            return json.dumps(result, indent=2, default=str) if result else "No goals set."
        elif name == "update_goal":
            return goals.update_goal(
                inputs["goal_id"],
                status=inputs.get("status"),
                progress_note=inputs.get("progress_note"),
                score=inputs.get("score"),
            )
        elif name == "evaluate_recent_work":
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            return goals.evaluate_recent_work(client, days=inputs.get("days", 7))

        # --- Tier-4: Knowledge Graph ---
        elif name == "entity_upsert":
            return json.dumps(entities.upsert_entity(
                inputs["name"],
                kind=inputs.get("kind", "concept"),
                properties=inputs.get("properties") or {},
                importance=int(inputs.get("importance", 5)),
            ), indent=2, default=str)
        elif name == "entity_relate":
            return json.dumps(entities.relate(
                inputs["from_name"], inputs["to_name"], inputs["kind"],
                properties=inputs.get("properties") or {},
                from_kind=inputs.get("from_kind", "concept"),
                to_kind=inputs.get("to_kind", "concept"),
                confidence=float(inputs.get("confidence", 1.0)),
            ), indent=2, default=str)
        elif name == "entity_query":
            return json.dumps(entities.query_entity(
                inputs["name"], hops=int(inputs.get("hops", 1))
            ), indent=2, default=str)
        elif name == "entity_graph":
            return json.dumps(entities.subgraph(
                entity_names=inputs.get("entity_names"),
                limit_nodes=int(inputs.get("limit_nodes", 100)),
            ), indent=2, default=str)

        # --- Tier-4: Reflection ---
        elif name == "reflect_now":
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            return json.dumps(reflection.consolidate(client, hours=int(inputs.get("hours", 24))), indent=2)
        elif name == "list_reflections":
            return json.dumps(reflection.list_reflections(
                status=inputs.get("status", "pending"),
                limit=int(inputs.get("limit", 50)),
            ), indent=2, default=str)
        elif name == "apply_reflection":
            return reflection.apply_reflection(
                int(inputs["reflection_id"]),
                accept=bool(inputs.get("accept", True)),
            )

        # --- Tier-4: Phone ---
        elif name == "sms_send":
            return phone.sms_send(inputs["to"], inputs["body"])
        elif name == "call_user":
            return phone.voice_call(inputs["to"], inputs["message"])

        # --- Tier-4: Image generation ---
        elif name == "generate_image":
            return image_gen.generate_image(
                inputs["prompt"],
                model=inputs.get("model"),
                size=inputs.get("size", "1024x1024"),
                n=int(inputs.get("n", 1)),
            )

        # --- Tier-4: Telemetry / Replay ---
        elif name == "usage_summary":
            return json.dumps(telemetry.summary(days=int(inputs.get("days", 7))), indent=2)
        elif name == "replay_session":
            return json.dumps(telemetry.replay_session(int(inputs["session_id"])), indent=2, default=str)

        else:
            # Try dynamic tools registered via self_mod
            dyn_result = self_mod.dispatch(name, inputs)
            if dyn_result is not None:
                return dyn_result
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error ({name}): {e}"


def _make_tool_result_content(name: str, tool_use_id: str, result_str: str) -> dict:
    """Build a tool_result content block, injecting images for screenshots."""
    if name in ("screenshot", "browser_screenshot", "annotate_screenshot"):
        try:
            data = json.loads(result_str)
            if "__screenshot__" in data:
                media = "image/png" if name == "browser_screenshot" else "image/jpeg"
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media, "data": data["__screenshot__"]}},
                        {"type": "text", "text": f"Screen size: {data['size'][0]}x{data['size'][1]}"},
                    ],
                }
        except Exception:
            pass

    if name == "python_exec":
        try:
            data = json.loads(result_str)
            images = data.get("_images", [])
            if images:
                content_blocks = [{"type": "text", "text": data["summary"]}]
                for img in images:
                    content_blocks.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]},
                    })
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content_blocks,
                }
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": data["summary"]}
        except Exception:
            pass

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result_str,
    }


class AgentCore:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=config.ANTHROPIC_API_KEY,
            max_retries=config.API_MAX_RETRIES,
        )
        self.memory = Memory()               # main loop / voice channel
        self._mcp_tools: list[dict] = []
        self._mcp_loaded = False
        self._run_lock = threading.Lock()    # lock for the main (None) channel
        self._channel_memories: dict[str, Memory] = {}
        self._channel_locks: dict[str, threading.Lock] = {}
        self._channels_mutex = threading.Lock()

    def load_mcp_tools(self) -> int:
        """Discover MCP servers and register their tools. Returns count added."""
        self._mcp_tools = mcp_client.discover()
        self._mcp_loaded = True
        if self._mcp_tools:
            print(f"[MCP] Registered {len(self._mcp_tools)} tools from MCP servers.")
        return len(self._mcp_tools)

    def _all_tools(self) -> list[dict]:
        # Cache all static tools at the last entry; dynamic tools come after the checkpoint.
        cached = list(TOOLS)
        cached[-1] = {**cached[-1], "cache_control": {"type": "ephemeral"}}
        return cached + self._mcp_tools + self_mod.get_dynamic_tools()

    def _effective_system_prompt(self) -> list[dict]:
        # Return a list of content blocks so we can attach cache_control to the static base.
        blocks: list[dict] = [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        ]
        goals_str = goals.active_goals_for_prompt()
        if goals_str:
            blocks.append({"type": "text", "text": goals_str})
        overlay = self_mod.get_prompt_addition()
        if overlay:
            blocks.append({"type": "text", "text": "## USER-SET BEHAVIORAL RULES (must follow):\n" + overlay})
        return blocks

    def _get_channel(self, channel_id: str | None) -> tuple[Memory, threading.Lock]:
        """Return the (Memory, Lock) pair for the given channel.

        channel_id=None → the main loop's memory (voice/text, backward-compatible).
        Any other string → a per-channel memory created on first use, so dashboard
        chats, SMS threads, and scheduler tasks never share conversation history.
        """
        if channel_id is None:
            return self.memory, self._run_lock
        with self._channels_mutex:
            if channel_id not in self._channel_memories:
                self._channel_memories[channel_id] = Memory()
                self._channel_locks[channel_id] = threading.Lock()
            return self._channel_memories[channel_id], self._channel_locks[channel_id]

    def run(self, user_text: str, include_screenshot: bool = True, use_thinking: bool = False, streamer=None, *, channel_id: str | None = None) -> str:
        """Run a full agent turn. Returns the final text response.

        If `streamer` is provided (a StreamingSpeaker), text deltas are fed to it
        as they arrive so the user hears the first sentence before generation finishes.

        Each channel (voice/text, dashboard chat_id, SMS number, scheduler task)
        gets its own Memory instance so their histories never interleave. Turns
        on the same channel are serialized by a per-channel threading.Lock.
        Pass channel_id=None (default) for the main voice/text conversation.
        """
        memory, lock = self._get_channel(channel_id)
        with lock:
            memory.maybe_summarize(self.client)

            # Build user message content
            user_content: list = []

            if memory.context_prefix():
                user_content.append({"type": "text", "text": memory.context_prefix()})

            if include_screenshot:
                try:
                    b64, size = computer.screenshot()
                    user_content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    })
                    user_content.append({"type": "text", "text": f"[Current screen — {size[0]}x{size[1]}]"})
                except Exception as e:
                    user_content.append({"type": "text", "text": f"[Screenshot unavailable: {e}]"})

            user_content.append({"type": "text", "text": user_text})
            memory.add_user(user_content)

            # Telemetry: new turn
            telemetry.bump_turn()
            try:
                telemetry.log_turn("user", {"text": user_text})
            except Exception:
                pass

            # Agentic tool-use loop
            max_iterations = 30
            iteration = 0
            final_text = ""

            while iteration < max_iterations:
                iteration += 1

                kwargs = dict(
                    model=config.AGENT_MODEL,
                    max_tokens=16000,
                    system=self._effective_system_prompt(),
                    tools=self._all_tools(),
                    messages=memory.get_messages(),
                )

                if use_thinking:
                    kwargs["thinking"] = {"type": "enabled", "budget_tokens": config.THINKING_BUDGET}

                # Stream if we have a speaker, otherwise non-stream. The SDK
                # retries transient API errors; if one outlasts every retry,
                # end the turn gracefully instead of crashing the caller.
                try:
                    if streamer is not None:
                        response_content, stop_reason, this_text = self._stream_turn(kwargs, streamer)
                    else:
                        resp = telemetry.create(self.client, call_site="agent.core/main", **kwargs)
                        response_content = resp.content
                        stop_reason = resp.stop_reason
                        this_text = " ".join(
                            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
                        ).strip()
                except anthropic.APIError as e:
                    category = resilience.classify(e)
                    print(f"[Resilience] agent.core/main failed ({category}) after retries: {e}")
                    try:
                        telemetry.log_turn("error", {"category": category, "detail": str(e)[:400]})
                    except Exception:
                        pass
                    return resilience.friendly_message(e)

                memory.add_assistant(response_content)
                final_text = this_text

                # Per-turn log for replay
                try:
                    tc = [
                        {"name": getattr(b, "name", ""), "id": getattr(b, "id", ""), "input": getattr(b, "input", {})}
                        for b in response_content if getattr(b, "type", "") == "tool_use"
                    ]
                    telemetry.log_turn("assistant", {"text": this_text}, tool_calls=tc)
                except Exception:
                    pass

                if stop_reason == "end_turn":
                    return final_text

                if stop_reason != "tool_use":
                    break

                # Execute all tool calls
                tool_results = []
                for block in response_content:
                    if getattr(block, "type", "") != "tool_use":
                        continue
                    print(f"[TOOL] {block.name}({json.dumps(block.input, ensure_ascii=False)[:120]})")
                    result_str = _execute_tool(block.name, block.input)
                    tool_results.append(_make_tool_result_content(block.name, block.id, result_str))
                    try:
                        telemetry.log_turn("tool_result", {"tool": block.name, "preview": result_str[:400]})
                    except Exception:
                        pass

                memory.add_user(tool_results)

            return final_text or "I hit my iteration limit. Something may have gone wrong — let me know how to proceed."

    def _stream_turn(self, kwargs: dict, streamer) -> tuple[list, str, str]:
        """Run one streamed turn, feeding text deltas to the streamer."""
        import time as _time
        accumulated_text = ""
        start = _time.time()
        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    if getattr(delta, "type", "") == "text_delta":
                        text = getattr(delta, "text", "")
                        accumulated_text += text
                        streamer.feed(text)
            final = stream.get_final_message()

        latency_ms = int((_time.time() - start) * 1000)
        tool_calls = [
            {"name": getattr(b, "name", ""), "id": getattr(b, "id", "")}
            for b in final.content if getattr(b, "type", "") == "tool_use"
        ]
        telemetry.record(
            call_site="agent.core/stream",
            model=kwargs.get("model", "?"),
            usage=getattr(final, "usage", None),
            latency_ms=latency_ms,
            stop_reason=getattr(final, "stop_reason", "") or "",
            tool_calls=tool_calls,
        )
        return final.content, final.stop_reason, accumulated_text.strip()

    def proactive_check(self, screenshot_b64: str) -> str | None:
        """Quick check: is there anything on screen worth proactively flagging?"""
        try:
            resp = telemetry.create(
                self.client,
                call_site="agent.core/proactive_check",
                model=config.PROACTIVE_MODEL,
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64}},
                        {"type": "text", "text": (
                            "You are a proactive AI assistant watching the user's screen. "
                            "Is there anything URGENT or notably interesting here that the user would want to know about right now? "
                            "Examples: an error message, a long-running process that finished, an important notification, "
                            "something the user is visibly struggling with, a security warning. "
                            "If YES, respond with a short 1-2 sentence observation. "
                            "If NO, respond with exactly: NO"
                        )},
                    ],
                }],
            )
        except anthropic.APIError as e:
            print(f"[Resilience] proactive_check skipped ({resilience.classify(e)}): {e}")
            return None
        text = resp.content[0].text.strip()
        return None if text.upper().startswith("NO") else text
