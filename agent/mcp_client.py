"""MCP client — discovers and connects to MCP servers configured in Claude Code settings.

Reads mcpServers from ~/.claude/settings.json (or project .claude/settings.json),
starts each server as a subprocess, handshakes, and exposes their tools to the agent.

Tool calls are dispatched synchronously via the MCP SDK's stdio transport.
"""
import asyncio
import json
import os
import threading
from pathlib import Path
from typing import Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_sessions: dict = {}       # server_name -> (session, tools)
_tool_registry: dict = {}  # full_tool_name -> (server_name, original_tool_name)


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop is not None and _loop.is_running():
        return _loop
    _loop = asyncio.new_event_loop()

    def runner():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _loop_thread = threading.Thread(target=runner, daemon=True, name="MCPLoop")
    _loop_thread.start()
    return _loop


def _run(coro):
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)


def _find_settings_files() -> list[Path]:
    candidates = [
        Path.cwd() / "mcp_servers.json",                                          # project config (our primary)
        Path.home() / ".claude" / "settings.json",                                # Claude Code
        Path.home() / ".config" / "Claude" / "claude_desktop_config.json",        # Claude Desktop (Linux)
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # Mac
        Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",  # Windows
        Path("/home/user/.claude/settings.json"),
    ]
    return [p for p in candidates if p.exists()]


def _load_mcp_configs() -> dict:
    """Return merged mcpServers dict from all settings files. Skips _example_* entries."""
    servers = {}
    for path in _find_settings_files():
        try:
            data = json.loads(path.read_text())
            for k, v in data.get("mcpServers", {}).items():
                if not k.startswith("_"):
                    servers[k] = v
        except Exception as e:
            print(f"[MCP] Could not read {path}: {e}")
    return servers


async def _connect_server(name: str, config: dict) -> list[dict]:
    """Connect to an MCP server, return its tool definitions."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    cmd = config.get("command", "")
    args = config.get("args", [])
    env_extra = config.get("env", {})
    env = {**os.environ, **env_extra}

    params = StdioServerParameters(command=cmd, args=args, env=env)
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = [
                    {
                        "name": f"mcp__{name}__{t.name}",
                        "description": t.description or "",
                        "input_schema": t.inputSchema or {"type": "object", "properties": {}, "required": []},
                        "_server": name,
                        "_original": t.name,
                    }
                    for t in (tools_result.tools or [])
                ]
                print(f"[MCP] {name}: {len(tools)} tools")
                return tools
    except Exception as e:
        print(f"[MCP] {name}: failed to connect — {e}")
        return []


async def _call_tool(server_name: str, tool_name: str, inputs: dict, config: dict) -> str:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    cmd = config.get("command", "")
    args = config.get("args", [])
    env_extra = config.get("env", {})
    env = {**os.environ, **env_extra}

    params = StdioServerParameters(command=cmd, args=args, env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=inputs)
            parts = []
            for c in (result.content or []):
                if hasattr(c, "text"):
                    parts.append(c.text)
                else:
                    parts.append(str(c))
            return "\n".join(parts) or "(no output)"


# Cached configs to avoid re-reading on every call
_mcp_configs: dict = {}


def discover() -> list[dict]:
    """Connect to all configured MCP servers, return their tool definitions for Claude."""
    global _mcp_configs, _tool_registry
    _mcp_configs = _load_mcp_configs()

    if not _mcp_configs:
        print("[MCP] No MCP server configs found.")
        return []

    all_tools = []
    for name, config in _mcp_configs.items():
        tools = _run(_connect_server(name, config))
        for t in tools:
            _tool_registry[t["name"]] = (name, t["_original"])
        # Strip internal keys before passing to Claude
        for t in tools:
            t.pop("_server", None)
            t.pop("_original", None)
        all_tools.extend(tools)

    return all_tools


def call(full_tool_name: str, inputs: dict) -> str:
    """Call an MCP tool by its full prefixed name."""
    if full_tool_name not in _tool_registry:
        return f"Unknown MCP tool: {full_tool_name}"
    server_name, original_name = _tool_registry[full_tool_name]
    config = _mcp_configs.get(server_name, {})
    try:
        return _run(_call_tool(server_name, original_name, inputs, config))
    except Exception as e:
        return f"MCP call error ({full_tool_name}): {e}"


def get_registered_names() -> list[str]:
    return list(_tool_registry.keys())
