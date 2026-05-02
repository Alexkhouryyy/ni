import threading
import config

_engine = None
_lock = threading.Lock()
_speaking = threading.Event()


def _get_pyttsx3():
    global _engine
    if _engine is None:
        import pyttsx3
        _engine = pyttsx3.init()
        _engine.setProperty("rate", config.TTS_RATE)
        voices = _engine.getProperty("voices")
        # prefer a natural-sounding voice if available
        for v in voices:
            if "english" in v.name.lower() or "en" in v.id.lower():
                _engine.setProperty("voice", v.id)
                break
    return _engine


def speak(text: str) -> None:
    """Speak text aloud. Blocks until done."""
    if not text.strip():
        return

    with _lock:
        _speaking.set()
        try:
            if config.TTS_ENGINE == "elevenlabs" and config.ELEVENLABS_API_KEY:
                _speak_elevenlabs(text)
            else:
                _speak_pyttsx3(text)
        finally:
            _speaking.clear()


def is_speaking() -> bool:
    return _speaking.is_set()


def _speak_pyttsx3(text: str) -> None:
    engine = _get_pyttsx3()
    engine.say(text)
    engine.runAndWait()


def _speak_elevenlabs(text: str) -> None:
    import requests
    import io
    import subprocess

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/stream"
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    resp = requests.post(url, json=payload, headers=headers, stream=True)
    resp.raise_for_status()

    audio = b"".join(resp.iter_content(chunk_size=4096))
    # play via ffplay (silent) or aplay
    proc = subprocess.run(
        ["ffplay", "-nodisp", "-autoexit", "-"],
        input=audio,
        capture_output=True,
    )
    if proc.returncode != 0:
        # fallback to pyttsx3
        _speak_pyttsx3(text)
