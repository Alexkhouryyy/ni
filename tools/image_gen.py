"""Image generation via Replicate (FLUX schnell by default).

Returns local file paths so the agent can reference / show / open the images.
"""
import os
import re
import time
import requests
from typing import Optional

import config


def _output_dir() -> str:
    d = getattr(config, "IMAGE_GEN_OUTPUT_DIR", "~/.voice_agent_images")
    d = os.path.expanduser(d)
    os.makedirs(d, exist_ok=True)
    return d


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:max_len] or "image"


def generate_image(prompt: str, model: Optional[str] = None, size: str = "1024x1024", n: int = 1) -> str:
    """Generate `n` images. Returns a newline-joined list of saved file paths."""
    token = getattr(config, "REPLICATE_API_TOKEN", "") or ""
    if not token:
        return "[image_gen] REPLICATE_API_TOKEN not set in .env."

    model = model or getattr(config, "IMAGE_GEN_MODEL", "black-forest-labs/flux-schnell")
    try:
        import replicate
        client = replicate.Client(api_token=token)
        try:
            w, h = (int(x) for x in size.lower().split("x"))
        except Exception:
            w, h = 1024, 1024
        output = client.run(
            model,
            input={
                "prompt": prompt,
                "num_outputs": max(1, int(n)),
                "width": w,
                "height": h,
                "output_format": "png",
            },
        )
    except Exception as e:
        return f"[image_gen] Replicate call failed: {e}"

    urls = []
    if isinstance(output, list):
        urls = [str(u) for u in output]
    elif isinstance(output, str):
        urls = [output]
    elif hasattr(output, "url"):
        urls = [output.url]
    else:
        urls = [str(output)]

    saved = []
    slug = _slug(prompt)
    out_dir = _output_dir()
    ts = int(time.time())
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            ext = ".png"
            path = os.path.join(out_dir, f"{ts}_{slug}_{i}{ext}")
            with open(path, "wb") as f:
                f.write(r.content)
            saved.append(path)
        except Exception as e:
            saved.append(f"[failed to download {url}: {e}]")

    return "Generated:\n" + "\n".join(saved)
