"""Skills registry — additive capability modules stored as Python files.

Each skill is a .py file under skills/ (project root) and must define:
  DESCRIPTION: str           — one-line summary shown in list_skills
  def run(inputs: dict) -> str  — main entrypoint

Optionally:
  INPUT_SCHEMA: dict          — JSON Schema for inputs (shown to the agent)
  VERSION: str                — semver string, default "1.0"

Skills are safer than self_mod: each skill is its own auditable file,
discoverable by humans, reloadable without touching the overlay blob.
"""
import importlib.util
import time
from pathlib import Path
from typing import Optional

SKILLS_DIR = Path(__file__).parent.parent / "skills"

_registry: dict[str, dict] = {}


def _skill_path(name: str) -> Path:
    return SKILLS_DIR / f"{name}.py"


def discover() -> list[str]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.stem for p in SKILLS_DIR.glob("*.py") if not p.name.startswith("_"))


def load_all() -> int:
    SKILLS_DIR.mkdir(exist_ok=True)
    count = 0
    for name in discover():
        try:
            _load(name)
            count += 1
        except Exception as e:
            print(f"[Skills] Failed to load {name!r}: {e}")
    return count


def _load(name: str) -> dict:
    path = _skill_path(name)
    spec = importlib.util.spec_from_file_location(f"skills.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "run") or not callable(mod.run):
        raise ValueError(f"Skill {name!r} must define def run(inputs: dict) -> str")

    entry = {
        "name": name,
        "description": getattr(mod, "DESCRIPTION", "No description."),
        "version": getattr(mod, "VERSION", "1.0"),
        "input_schema": getattr(mod, "INPUT_SCHEMA", {"type": "object", "properties": {}, "required": []}),
        "run": mod.run,
    }
    _registry[name] = entry
    return entry


def list_skills() -> list[dict]:
    return [
        {"name": e["name"], "description": e["description"], "version": e["version"]}
        for e in _registry.values()
    ]


def run_skill(name: str, inputs: dict) -> str:
    if name not in _registry:
        if _skill_path(name).exists():
            try:
                _load(name)
            except Exception as e:
                return f"[Skills] Failed to load {name!r}: {e}"
        else:
            known = [e["name"] for e in list_skills()]
            hint = f" Known: {known}" if known else " No skills installed yet."
            return f"[Skills] No skill named {name!r}.{hint}"
    start = time.perf_counter()
    try:
        result = str(_registry[name]["run"](inputs))
        _log_usage(name, True, time.perf_counter() - start)
        return result
    except Exception as e:
        _log_usage(name, False, time.perf_counter() - start, str(e))
        return f"[Skills] Skill {name!r} error: {e}"


def _log_usage(name: str, success: bool, duration: float, error: Optional[str] = None) -> None:
    """Record one skill run to skill_usage. Best-effort — never raises."""
    try:
        from agent import longterm
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO skill_usage (ts, name, success, duration, error) VALUES (?, ?, ?, ?, ?)",
                (time.time(), name, 1 if success else 0, duration, error),
            )
    except Exception:
        pass


def failure_stats(hours: int = 24, min_failures: int = 3) -> list[dict]:
    """Skills that failed at least `min_failures` times in the window, with recent errors."""
    try:
        from agent import longterm
        cutoff = time.time() - hours * 3600
        with longterm._conn() as c:
            rows = c.execute(
                "SELECT name, COUNT(*), SUM(success) FROM skill_usage WHERE ts >= ? GROUP BY name",
                (cutoff,),
            ).fetchall()
            out = []
            for name, total, succ in rows:
                fails = total - (succ or 0)
                if fails >= min_failures:
                    errs = c.execute(
                        "SELECT error FROM skill_usage WHERE name = ? AND success = 0 AND ts >= ? "
                        "ORDER BY ts DESC LIMIT 5",
                        (name, cutoff),
                    ).fetchall()
                    out.append({
                        "name": name, "failures": fails, "total": total,
                        "errors": [e[0] for e in errs if e[0]],
                    })
            return out
    except Exception:
        return []


def read_source(name: str) -> Optional[str]:
    """Return the raw source of a skill file, or None if it doesn't exist."""
    path = _skill_path(name)
    return path.read_text() if path.exists() else None


def get_description(name: str) -> str:
    entry = _registry.get(name)
    return entry["description"] if entry else f"Skill {name}"


def create_skill(name: str, description: str, code: str, version: str = "1.0") -> str:
    if not name.isidentifier():
        return f"Invalid skill name: {name!r} — must be a valid Python identifier."
    SKILLS_DIR.mkdir(exist_ok=True)
    path = _skill_path(name)

    ns: dict = {}
    try:
        exec(compile(code, f"<skill:{name}>", "exec"), ns)
    except SyntaxError as e:
        return f"Syntax error in skill code: {e}"
    if "run" not in ns or not callable(ns["run"]):
        return "Skill code must define: def run(inputs: dict) -> str"

    source = (
        f'"""Skill: {name} — {description}"""\n'
        f"DESCRIPTION = {description!r}\n"
        f"VERSION = {version!r}\n\n"
        f"{code}\n"
    )
    old_source = path.read_text() if path.exists() else None
    path.write_text(source)
    try:
        _load(name)
    except Exception as e:
        if old_source is not None:
            # Overwrite failed — restore the previously working version so a bad
            # rewrite (e.g. from refine_skills) can never destroy a good skill.
            path.write_text(old_source)
            try:
                _load(name)
            except Exception:
                pass
            return f"Skill {name!r} kept at previous version — new code failed to import: {e}"
        path.unlink(missing_ok=True)
        return f"Skill written but import failed: {e}"
    return f"Skill {name!r} created and loaded from {path}."


def get_schema(name: str) -> Optional[dict]:
    entry = _registry.get(name)
    return entry["input_schema"] if entry else None
