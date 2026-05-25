"""Tests for tools/camera.py — opt-in gate, error paths, JSON result shape."""
import json
from unittest.mock import patch, MagicMock
import pytest


class TestCameraGate:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr("config.CAMERA_ENABLED", False)
        from tools import camera
        with pytest.raises(RuntimeError, match="disabled"):
            camera.capture()

    def test_is_enabled_reads_config(self, monkeypatch):
        from tools import camera
        monkeypatch.setattr("config.CAMERA_ENABLED", True)
        assert camera.is_enabled() is True
        monkeypatch.setattr("config.CAMERA_ENABLED", False)
        assert camera.is_enabled() is False


class TestCameraCapture:
    def test_missing_opencv_returns_actionable_error(self, monkeypatch):
        monkeypatch.setattr("config.CAMERA_ENABLED", True)
        import sys
        # Hide cv2 if present, simulate ImportError
        monkeypatch.setitem(sys.modules, "cv2", None)
        from tools import camera
        with pytest.raises(RuntimeError, match="opencv-python"):
            camera.capture()

    def test_capture_returns_b64_and_size(self, monkeypatch):
        import numpy as np
        monkeypatch.setattr("config.CAMERA_ENABLED", True)
        monkeypatch.setattr("config.CAMERA_DEVICE_INDEX", 0)

        # Fake cv2 module
        fake_cv2 = MagicMock()
        fake_cv2.IMWRITE_JPEG_QUALITY = 1
        # frame: 480x640x3 uint8 BGR
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fake_cap = MagicMock()
        fake_cap.isOpened.return_value = True
        fake_cap.read.return_value = (True, fake_frame)
        fake_cv2.VideoCapture.return_value = fake_cap
        fake_cv2.imencode.return_value = (True, np.array([0xFF, 0xD8, 0xFF], dtype=np.uint8))

        import sys
        monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
        from tools import camera
        b64, (w, h) = camera.capture()
        assert isinstance(b64, str) and b64
        assert (w, h) == (640, 480)
        fake_cap.release.assert_called_once()

    def test_capture_fails_when_camera_unopenable(self, monkeypatch):
        monkeypatch.setattr("config.CAMERA_ENABLED", True)
        fake_cv2 = MagicMock()
        fake_cap = MagicMock()
        fake_cap.isOpened.return_value = False
        fake_cv2.VideoCapture.return_value = fake_cap
        import sys
        monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
        from tools import camera
        with pytest.raises(RuntimeError, match="Could not open camera"):
            camera.capture()


class TestCameraInToolList:
    def test_camera_tool_registered(self):
        from agent.core import TOOLS
        names = [t["name"] for t in TOOLS]
        assert "camera_capture" in names

    def test_camera_tool_has_optional_device_index(self):
        from agent.core import TOOLS
        tool = next(t for t in TOOLS if t["name"] == "camera_capture")
        props = tool["input_schema"]["properties"]
        assert "device_index" in props
        # Should be optional — never appear in required list
        assert "device_index" not in tool["input_schema"].get("required", [])
