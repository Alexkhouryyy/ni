import numpy as np
import queue
import threading
import time

import config

_model = None


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
    model = _get_model()
    segments, _ = model.transcribe(audio, language="en", beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    print(f"[STT] Heard: {text!r}")
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
