"""Screen capture and computer control via mss + xdotool."""
import base64
import io
import subprocess
import config


def _xdo(*args) -> str:
    result = subprocess.run(["xdotool", *args], capture_output=True, text=True)
    return result.stdout.strip()


def screenshot(region=None) -> tuple[str, tuple[int, int]]:
    """Capture screen. Returns (base64_jpeg, (width, height))."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1] if region is None else region
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=config.SCREENSHOT_QUALITY)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, img.size


def click(x: int, y: int, button: str = "left", double: bool = False) -> str:
    btn_map = {"left": "1", "middle": "2", "right": "3"}
    btn = btn_map.get(button, "1")
    _xdo("mousemove", str(x), str(y))
    if double:
        _xdo("click", "--repeat", "2", btn)
    else:
        _xdo("click", btn)
    return f"Clicked {button} at ({x}, {y})"


def right_click(x: int, y: int) -> str:
    return click(x, y, button="right")


def move_mouse(x: int, y: int) -> str:
    _xdo("mousemove", "--sync", str(x), str(y))
    return f"Moved mouse to ({x}, {y})"


def type_text(text: str, delay_ms: int = 30) -> str:
    _xdo("type", f"--delay={delay_ms}", "--", text)
    return f"Typed: {text!r}"


def hotkey(*keys: str) -> str:
    combo = "+".join(keys)
    _xdo("key", combo)
    return f"Pressed hotkey: {combo}"


def scroll(x: int, y: int, clicks: int) -> str:
    _xdo("mousemove", str(x), str(y))
    btn = "4" if clicks > 0 else "5"  # 4=scroll up, 5=scroll down
    for _ in range(abs(clicks)):
        _xdo("click", btn)
    direction = "up" if clicks > 0 else "down"
    return f"Scrolled {direction} {abs(clicks)} clicks at ({x}, {y})"


def drag(x1: int, y1: int, x2: int, y2: int) -> str:
    _xdo("mousemove", str(x1), str(y1))
    _xdo("mousedown", "1")
    _xdo("mousemove", "--sync", str(x2), str(y2))
    _xdo("mouseup", "1")
    return f"Dragged from ({x1}, {y1}) to ({x2}, {y2})"


def get_screen_size() -> tuple[int, int]:
    out = _xdo("getdisplaygeometry")
    try:
        w, h = out.split()
        return int(w), int(h)
    except Exception:
        return (1920, 1080)
