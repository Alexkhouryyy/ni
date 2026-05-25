"""Local webcam capture — single-frame grab for Claude vision.

Mirror of tools/computer.py screenshot pattern: returns (b64_jpeg, (w, h)).
The frame is wrapped as a Claude image content block in agent/core.py's
_make_tool_result_content so the model can see it.

Setup:
  pip install opencv-python
  Set CAMERA_ENABLED=true in .env (off by default).
  CAMERA_DEVICE_INDEX picks which camera (0 = default).
"""
import base64
import io
from typing import Tuple

import config


def is_enabled() -> bool:
    return bool(getattr(config, "CAMERA_ENABLED", False))


def capture(device_index: int | None = None, jpeg_quality: int = 85) -> Tuple[str, Tuple[int, int]]:
    """Grab one frame from the webcam. Returns (base64_jpeg, (width, height))."""
    if not is_enabled():
        raise RuntimeError("Camera is disabled. Set CAMERA_ENABLED=true in .env.")

    try:
        import cv2  # type: ignore
    except ImportError as e:
        raise RuntimeError("opencv-python not installed. Run: pip install opencv-python") from e

    idx = device_index if device_index is not None else getattr(config, "CAMERA_DEVICE_INDEX", 0)
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera at index {idx}")

    try:
        # Discard a few frames — many webcams need warmup for proper exposure
        for _ in range(3):
            cap.read()
        ok, frame = cap.read()
    finally:
        cap.release()

    if not ok or frame is None:
        raise RuntimeError("Failed to capture frame from camera")

    # frame is BGR; encode as JPEG
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")

    h, w = frame.shape[:2]
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return b64, (w, h)
