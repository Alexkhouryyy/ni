"""Safe bash execution tool.

Execution is delegated to the configured backend (host or Docker sandbox) — see
``tools/sandbox.py``. The return shape is unchanged so every caller is unaffected.
"""
import config
from tools import sandbox


def run(command: str, timeout: int = None, cwd: str = None) -> dict:
    """Run a shell command. Returns {stdout, stderr, returncode, success}."""
    timeout = timeout or config.BASH_TIMEOUT
    return sandbox.get_backend().run_shell(command, timeout=timeout, cwd=cwd)


def format_result(result: dict) -> str:
    parts = []
    if result["stdout"]:
        parts.append(f"STDOUT:\n{result['stdout']}")
    if result["stderr"]:
        parts.append(f"STDERR:\n{result['stderr']}")
    parts.append(f"Exit code: {result['returncode']}")
    return "\n".join(parts)
