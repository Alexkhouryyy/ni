import numpy as np
import queue
import threading
import time

import config

_model = None


def _transcribe(audio: np.ndarray) -> str:
    """Transcribe a float32 mono numpy array using the configured engine."""
    if config.OPENAI_STT_ENGINE == "openai" and config.OPENAI_API_KEY:
        return _transcribe_openai(audio)
    m = _get_model()
    segs, _ = m.transcribe(audio, language="en", beam_size=5)
    return " ".join(seg.text.strip() for seg in segs).strip()


def _transcribe_openai(audio: np.ndarray) -> str:
    import os as _os
    import tempfile
    import wave
    from openai import OpenAI

    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())
        oai = OpenAI(api_key=config.OPENAI_API_KEY)
        with open(tmp.name, "rb") as f:
            transcript = oai.audio.transcriptions.create(model="whisper-1", file=f, language="en")
        return transcript.text.strip()
    finally:
        _os.unlink(tmp.name)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"[STT] Loading Whisper '{config.WHISPER_MODEL}' model...")
        _model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type="int8")
        print("[STT] Model ready.")
    return _model


def listen() -> str:
    """Record from mic until silence, return transcribed text."""
    import sounddevice as sd

    audio_queue: queue.Queue = queue.Queue()
    recording = []
    stop_event = threading.Event()

    def callback(indata, frames, time_info, status):
        audio_queue.put(indata.copy())

    stream = sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
        blocksize=int(config.SAMPLE_RATE * 0.1),  # 100ms chunks
    )

    print("[STT] Listening... (speak now)")
    silence_start = None
    total_duration = 0.0
    has_speech = False

    with stream:
        while True:
            chunk = audio_queue.get()
            recording.append(chunk)
            total_duration += len(chunk) / config.SAMPLE_RATE

            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if rms > config.SILENCE_THRESHOLD:
                has_speech = True
                silence_start = None
            elif has_speech:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= config.SILENCE_DURATION:
                    break

            if total_duration >= config.MAX_RECORD_SECONDS:
                break

    if not has_speech:
        return ""

    audio = np.concatenate(recording, axis=0).flatten()
    text = _transcribe(audio)
    print(f"[STT] Heard: {text!r}")
    return text


def warm_up() -> None:
    """Pre-load and pre-run Whisper on a silent buffer so the first real call is fast."""
    try:
        model = _get_model()
        silence = np.zeros(int(config.SAMPLE_RATE * 0.5), dtype=np.float32)
        # Burn one transcribe call so the kernel is hot
        try:
            segments, _ = model.transcribe(silence, language="en", beam_size=1)
            for _ in segments:
                pass
        except Exception:
            pass
        print("[STT] Pre-warm complete.")
    except Exception as e:
        print(f"[STT] Pre-warm skipped: {e}")


def listen_streaming(
    on_partial=None,
    on_final=None,
    partial_interval_ms: int = None,
    end_silence_s: float = None,
) -> str:
    """Record from mic with rolling partial transcription.

    Calls `on_partial(text)` every `partial_interval_ms` while you speak.
    Returns the final transcript once silence ≥ end_silence_s AND last two
    partials are stable. Calls `on_final(text)` once before returning.

    Falls back to plain `listen()` if streaming deps aren't available.
    """
    import sounddevice as sd

    partial_interval = (partial_interval_ms or getattr(config, "PARTIAL_INTERVAL_MS", 500)) / 1000.0
    end_silence = end_silence_s if end_silence_s is not None else config.SILENCE_DURATION

    audio_queue: queue.Queue = queue.Queue()
    recording: list = []

    def callback(indata, frames, time_info, status):
        audio_queue.put(indata.copy())

    stream = sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
        blocksize=int(config.SAMPLE_RATE * 0.1),
    )

    model = _get_model()
    print("[STT] Streaming listen... (speak now)")
    silence_start = None
    total_duration = 0.0
    has_speech = False
    last_partial = ""
    second_last_partial = None
    last_partial_at = time.time()
    stable_streak = 0

    with stream:
        while True:
            chunk = audio_queue.get()
            recording.append(chunk)
            total_duration += len(chunk) / config.SAMPLE_RATE

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms > config.SILENCE_THRESHOLD:
                has_speech = True
                silence_start = None
            elif has_speech:
                if silence_start is None:
                    silence_start = time.time()

            # Periodically transcribe what we have so far
            now = time.time()
            if has_speech and (now - last_partial_at) >= partial_interval:
                audio = np.concatenate(recording, axis=0).flatten()
                try:
                    segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
                    partial = " ".join(seg.text.strip() for seg in segments).strip()
                except Exception:
                    partial = last_partial
                if partial and partial != last_partial:
                    if on_partial:
                        try:
                            on_partial(partial)
                        except Exception:
                            pass
                    second_last_partial = last_partial
                    last_partial = partial
                    stable_streak = 0
                elif partial == last_partial and partial:
                    stable_streak += 1
                last_partial_at = now

            # End-of-utterance: silence elapsed AND partials stable
            if has_speech and silence_start is not None:
                if (now - silence_start) >= end_silence and stable_streak >= 1:
                    break
                if (now - silence_start) >= (end_silence + 1.0):
                    break  # hard fallback

            if total_duration >= config.MAX_RECORD_SECONDS:
                break

    if not has_speech:
        return ""

    # Final clean transcription with higher beam size
    audio = np.concatenate(recording, axis=0).flatten()
    text = _transcribe(audio) or last_partial
    print(f"[STT] Final: {text!r}")
    if on_final:
        try:
            on_final(text)
        except Exception:
            pass
    return text


def listen_for_wake_word(wake_words: list[str] = None) -> str:
    """Keep listening until a wake word is detected, then do a full listen."""
    if wake_words is None:
        wake_words = ["hey", "agent", "okay agent", "listen"]

    import sounddevice as sd

    model = _get_model()
    print(f"[STT] Waiting for wake word {wake_words}...")

    while True:
        audio_queue: queue.Queue = queue.Queue()
        buf = []

        def callback(indata, frames, time_info, status):
            audio_queue.get if False else audio_queue.put(indata.copy())

        with sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
            blocksize=int(config.SAMPLE_RATE * 0.1),
        ):
            for _ in range(20):  # 2 seconds of audio
                buf.append(audio_queue.get())

        audio = np.concatenate(buf, axis=0).flatten()
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < config.SILENCE_THRESHOLD * 0.5:
            continue

        segments, _ = model.transcribe(audio, language="en", beam_size=1)
        snippet = " ".join(seg.text.strip() for seg in segments).lower()

        if any(w in snippet for w in wake_words):
            print(f"[STT] Wake word detected: {snippet!r}")
            return listen()
