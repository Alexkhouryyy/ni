"""Vision precision — OCR + element detection + set-of-marks.

Gives the agent reliable clicks: instead of "guess the pixel for Submit",
the agent calls click_on("Submit") and we OCR the screen to find it.
"""
import base64
import io
import json
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from tools import computer
import config

_OCR_AVAILABLE = None


def _check_ocr():
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is not None:
        return _OCR_AVAILABLE
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception:
        _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


def _grab_screen_pil() -> Image.Image:
    """Capture screen as a PIL Image (uses mss directly)."""
    import mss
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _ocr_data(img: Image.Image) -> list[dict]:
    """Run OCR and return list of {text, x, y, w, h, conf}."""
    if not _check_ocr():
        return []
    import pytesseract
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    boxes = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i]) if data["conf"][i] != "-1" else -1.0
        if not text or conf < 30:
            continue
        boxes.append({
            "text": text,
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "w": int(data["width"][i]),
            "h": int(data["height"][i]),
            "conf": conf,
        })
    return boxes


def find_on_screen(query: str, exact: bool = False) -> list[dict]:
    """Find text on screen. Returns list of matches with bounding boxes.
    Match is case-insensitive substring by default; set exact=True for whole-word equality.
    """
    if not _check_ocr():
        return [{"error": "OCR not available. Install tesseract-ocr."}]

    img = _grab_screen_pil()
    boxes = _ocr_data(img)
    q = query.strip().lower()

    matches = []
    for b in boxes:
        text_lower = b["text"].lower()
        if (exact and text_lower == q) or (not exact and q in text_lower):
            matches.append({
                **b,
                "center_x": b["x"] + b["w"] // 2,
                "center_y": b["y"] + b["h"] // 2,
            })

    # If no exact substring match, try phrase: join adjacent boxes on same line
    if not matches and not exact and " " in q:
        # Group boxes by approximate y (line)
        boxes_sorted = sorted(boxes, key=lambda b: (b["y"] // 20, b["x"]))
        line: list[dict] = []
        last_y = -100
        lines: list[list[dict]] = []
        for b in boxes_sorted:
            if abs(b["y"] - last_y) > 15:
                if line:
                    lines.append(line)
                line = [b]
            else:
                line.append(b)
            last_y = b["y"]
        if line:
            lines.append(line)

        for ln in lines:
            phrase = " ".join(b["text"] for b in ln).lower()
            if q in phrase:
                # bounding box of whole line
                xs = [b["x"] for b in ln] + [b["x"] + b["w"] for b in ln]
                ys = [b["y"] for b in ln] + [b["y"] + b["h"] for b in ln]
                matches.append({
                    "text": " ".join(b["text"] for b in ln),
                    "x": min(xs),
                    "y": min(ys),
                    "w": max(xs) - min(xs),
                    "h": max(ys) - min(ys),
                    "conf": min(b["conf"] for b in ln),
                    "center_x": (min(xs) + max(xs)) // 2,
                    "center_y": (min(ys) + max(ys)) // 2,
                })

    return matches


def click_on(query: str, occurrence: int = 0, button: str = "left", double: bool = False) -> str:
    """Find text on screen and click its center. `occurrence` lets you pick the Nth match."""
    matches = find_on_screen(query)
    if not matches or "error" in matches[0]:
        return f"Could not find {query!r} on screen."
    if occurrence >= len(matches):
        return f"Found {len(matches)} matches for {query!r}, but occurrence={occurrence} out of range."
    m = matches[occurrence]
    computer.click(m["center_x"], m["center_y"], button=button, double=double)
    return f"Clicked {query!r} (match {occurrence+1}/{len(matches)}) at ({m['center_x']}, {m['center_y']})"


def annotate_screenshot() -> tuple[str, dict]:
    """Return (base64_png, marks_map) — screenshot with numbered visual marks on every text region.

    marks_map maps numeric label -> {text, bbox: (x,y,w,h), center: (cx,cy)}.
    Claude can then say `click_mark(7)` instead of guessing pixels.
    """
    if not _check_ocr():
        return "", {}

    img = _grab_screen_pil().copy()
    boxes = _ocr_data(img)

    # Filter to high-confidence, reasonably-sized boxes — these are real UI elements
    filtered = [b for b in boxes if b["conf"] > 50 and b["w"] > 12 and b["h"] > 8]

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    marks: dict = {}
    for i, b in enumerate(filtered, 1):
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        # Draw bounding box
        draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0), width=2)
        # Draw numbered label
        label = str(i)
        label_bg = (255, 255, 0)
        bbox = draw.textbbox((0, 0), label, font=font)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle([x, y, x + lw + 4, y + lh + 4], fill=label_bg)
        draw.text((x + 2, y + 1), label, fill=(0, 0, 0), font=font)

        marks[i] = {
            "text": b["text"],
            "bbox": [x, y, w, h],
            "center": [x + w // 2, y + h // 2],
        }

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, marks


_last_marks: dict = {}


def annotate_for_agent() -> str:
    """Wrapper that stores marks for click_mark() to use."""
    global _last_marks
    b64, marks = annotate_screenshot()
    _last_marks = marks
    return json.dumps({
        "__screenshot__": b64,
        "size": [_grab_screen_pil().size[0], _grab_screen_pil().size[1]],
        "marks_count": len(marks),
        "_marks_summary": {k: marks[k]["text"][:40] for k in list(marks)[:30]},
    })


def click_mark(mark_number: int, button: str = "left", double: bool = False) -> str:
    if mark_number not in _last_marks:
        return f"Mark {mark_number} not found. Call annotate_screenshot first."
    m = _last_marks[mark_number]
    cx, cy = m["center"]
    computer.click(cx, cy, button=button, double=double)
    return f"Clicked mark {mark_number} ({m['text']!r}) at ({cx}, {cy})"
