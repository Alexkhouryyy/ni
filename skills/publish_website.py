"""Skill: publish_website — build a static site from files and deploy it live to Netlify.

The calling expert writes the actual HTML/CSS/JS itself and passes it in as a
{path: contents} map. This skill writes those files into the Apex vault under
Sites/<slug>/, then (if a Netlify token is configured) zips and deploys them to
Netlify and returns the live HTTPS URL. Re-deploying the same site_name updates
the existing Netlify site in place (the site id is remembered per slug).

Trusted, hand-written skill — pure stdlib (urllib + zipfile), no pip installs.
Set NETLIFY_TOKEN in .env to enable live deploys (otherwise it just writes the
files locally and tells you how to finish).
"""
from __future__ import annotations

import io
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DESCRIPTION = (
    "Build and deploy a static website. Pass {site_name, files:{'index.html':...}} "
    "and it writes the files and deploys them live to Netlify, returning the URL."
)
VERSION = "1.0"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "site_name": {
            "type": "string",
            "description": "Short slug for the site, e.g. 'portfolio' or 'cafe-landing'.",
        },
        "files": {
            "type": "object",
            "description": (
                "Map of relative path -> file contents. MUST include 'index.html'. "
                "Add 'style.css', 'script.js', subpaths like 'about/index.html', etc."
            ),
        },
        "deploy": {
            "type": "boolean",
            "description": "Deploy live to Netlify (default true). If false, only writes files locally.",
        },
    },
    "required": ["site_name", "files"],
}

_API = "https://api.netlify.com/api/v1"


def _sites_root() -> Path:
    root = Path.home() / "Documents" / "Apex" / "Sites"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", (name or "site").strip().lower()).strip("-")
    return s or "site"


def _token() -> str | None:
    tok = os.environ.get("NETLIFY_TOKEN") or os.environ.get("NETLIFY_AUTH_TOKEN")
    if not tok:
        try:
            import config
            tok = getattr(config, "NETLIFY_TOKEN", None)
        except Exception:
            tok = None
    return (tok or "").strip() or None


def _api_call(method: str, path: str, token: str, *, body: bytes | None = None,
              content_type: str = "application/json") -> tuple[int, dict | bytes]:
    url = path if path.startswith("http") else f"{_API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return e.code, {"error": f"HTTP {e.code}: {detail}"}
    except Exception as e:
        return 0, {"error": str(e)}


def _zip_dir(site_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in site_dir.rglob("*"):
            if p.is_file() and p.name != ".netlify.json":
                z.write(p, p.relative_to(site_dir).as_posix())
    return buf.getvalue()


def _get_or_create_site(token: str, slug: str, site_dir: Path) -> tuple[str | None, str]:
    """Return (site_id, note). Reuses a remembered site id for this slug."""
    meta_path = site_dir / ".netlify.json"
    if meta_path.exists():
        try:
            sid = json.loads(meta_path.read_text()).get("site_id")
            if sid:
                # Confirm it still exists.
                status, _ = _api_call("GET", f"/sites/{sid}", token)
                if status == 200:
                    return sid, "updating existing site"
        except Exception:
            pass

    # Try to claim a friendly subdomain; fall back to an auto-named site if taken.
    for payload in ({"name": f"apex-{slug}"}, {}):
        status, data = _api_call(
            "POST", "/sites", token, body=json.dumps(payload).encode()
        )
        if status in (200, 201) and isinstance(data, dict) and data.get("id"):
            sid = data["id"]
            try:
                meta_path.write_text(json.dumps({"site_id": sid, "name": data.get("name")}))
            except Exception:
                pass
            return sid, "created new site"
    return None, (data.get("error") if isinstance(data, dict) else "site creation failed")


def run(inputs: dict) -> str:
    site_name = inputs.get("site_name") or "site"
    files = inputs.get("files") or {}
    deploy = inputs.get("deploy", True)

    if not isinstance(files, dict) or not files:
        return "publish_website: 'files' must be a non-empty {path: contents} map including 'index.html'."
    if not any(k.lower() in ("index.html", "/index.html") for k in files):
        return "publish_website: 'files' must include an 'index.html' entry."

    slug = _slugify(site_name)
    site_dir = _sites_root() / slug
    site_dir.mkdir(parents=True, exist_ok=True)

    # Write every file, guarding against path escapes.
    written = []
    for rel, content in files.items():
        rel = str(rel).lstrip("/").replace("\\", "/")
        if ".." in rel.split("/"):
            return f"publish_website: unsafe path {rel!r}."
        dest = site_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content if isinstance(content, str) else str(content), encoding="utf-8")
        written.append(rel)

    local = f"Wrote {len(written)} file(s) to {site_dir}: {', '.join(sorted(written))}."

    if not deploy:
        return local + " (deploy=false — files saved locally only.)"

    token = _token()
    if not token:
        return (
            local
            + " To go live, add NETLIFY_TOKEN to your .env (a personal access token "
            "from app.netlify.com → User settings → Applications), restart Apex, and "
            f"ask me to deploy '{slug}' again. The files are ready to ship."
        )

    site_id, note = _get_or_create_site(token, slug, site_dir)
    if not site_id:
        return local + f" But Netlify deploy failed: {note}."

    zip_bytes = _zip_dir(site_dir)
    status, data = _api_call(
        "POST", f"/sites/{site_id}/deploys", token,
        body=zip_bytes, content_type="application/zip",
    )
    if status not in (200, 201) or not isinstance(data, dict):
        err = data.get("error") if isinstance(data, dict) else f"HTTP {status}"
        return local + f" But the Netlify deploy upload failed: {err}."

    url = data.get("ssl_url") or data.get("url") or ""
    state = data.get("state", "")
    # Give Netlify a moment to finish processing the zip deploy.
    if state and state not in ("ready", "current"):
        deploy_id = data.get("id")
        for _ in range(10):
            time.sleep(2)
            s2, d2 = _api_call("GET", f"/sites/{site_id}/deploys/{deploy_id}", token)
            if isinstance(d2, dict) and d2.get("state") in ("ready", "current"):
                url = d2.get("ssl_url") or url
                state = d2.get("state")
                break

    return (
        f"✅ Deployed '{slug}' to Netlify ({note}). Live at: {url}\n"
        f"{local} State: {state or 'submitted'}. Re-deploying '{slug}' updates this same site."
    )
