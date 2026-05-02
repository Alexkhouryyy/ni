"""Safe bash execution tool."""
import subprocess
import os
import config


def run(command: str, timeout: int = None, cwd: str = None) -> dict:
    """Run a shell command. Returns {stdout, stderr, returncode, success}."""
    timeout = timeout or config.BASH_TIMEOUT
    cwd = cwd or os.path.expanduser("~")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "success": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "success": False,
        }


def format_result(result: dict) -> str:
    parts = []
    if result["stdout"]:
        parts.append(f"STDOUT:\n{result['stdout']}")
    if result["stderr"]:
        parts.append(f"STDERR:\n{result['stderr']}")
    parts.append(f"Exit code: {result['returncode']}")
    return "\n".join(parts)
