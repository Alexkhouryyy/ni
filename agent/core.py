"""Core Claude agent with tool use, extended thinking, and screen vision."""
import json
import anthropic
import config
from agent.memory import Memory
from agent import longterm
from tools import computer, bash, research, files, browser

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
- **read_file**: Read a file
- **write_file**: Create or overwrite a file
- **append_file**: Append to a file
- **list_dir**: List directory contents
- **find_files**: Find files matching a pattern

## BEHAVIOR RULES:
1. For ANY task involving the UI, take a screenshot FIRST to see the current state.
2. Chain tools — plan the full sequence before starting, then execute step by step.
3. After completing a task, briefly confirm what you did and what the result was.
4. If a task fails, diagnose why, try a different approach, and report what happened.
5. Never ask clarifying questions for simple tasks — make a reasonable assumption and proceed.
6. For destructive or irreversible actions (deleting files, sending messages, etc.), confirm with the user first.
7. When you notice something on screen worth mentioning (error, opportunity, concern) — do it.

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
]


def _execute_tool(name: str, inputs: dict) -> str:
    """Dispatch a tool call and return its result as a string."""
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

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error ({name}): {e}"


def _make_tool_result_content(name: str, tool_use_id: str, result_str: str) -> dict:
    """Build a tool_result content block, injecting images for screenshots."""
    if name in ("screenshot", "browser_screenshot"):
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

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result_str,
    }


class AgentCore:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.memory = Memory()

    def run(self, user_text: str, include_screenshot: bool = True, use_thinking: bool = False, streamer=None) -> str:
        """Run a full agent turn. Returns the final text response.

        If `streamer` is provided (a StreamingSpeaker), text deltas are fed to it
        as they arrive so the user hears the first sentence before generation finishes.
        """
        self.memory.maybe_summarize(self.client)

        # Build user message content
        user_content: list = []

        if self.memory.context_prefix():
            user_content.append({"type": "text", "text": self.memory.context_prefix()})

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
        self.memory.add_user(user_content)

        # Agentic tool-use loop
        max_iterations = 30
        iteration = 0
        final_text = ""

        while iteration < max_iterations:
            iteration += 1

            kwargs = dict(
                model=config.AGENT_MODEL,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.memory.get_messages(),
            )

            if use_thinking:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": config.THINKING_BUDGET}

            # Stream if we have a speaker, otherwise non-stream
            if streamer is not None:
                response_content, stop_reason, this_text = self._stream_turn(kwargs, streamer)
            else:
                resp = self.client.messages.create(**kwargs)
                response_content = resp.content
                stop_reason = resp.stop_reason
                this_text = " ".join(
                    getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
                ).strip()

            self.memory.add_assistant(response_content)
            final_text = this_text

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

            self.memory.add_user(tool_results)

        return final_text or "I hit my iteration limit. Something may have gone wrong — let me know how to proceed."

    def _stream_turn(self, kwargs: dict, streamer) -> tuple[list, str, str]:
        """Run one streamed turn, feeding text deltas to the streamer."""
        accumulated_text = ""
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

        return final.content, final.stop_reason, accumulated_text.strip()

    def proactive_check(self, screenshot_b64: str) -> str | None:
        """Quick check: is there anything on screen worth proactively flagging?"""
        resp = self.client.messages.create(
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
        text = resp.content[0].text.strip()
        return None if text.upper().startswith("NO") else text
