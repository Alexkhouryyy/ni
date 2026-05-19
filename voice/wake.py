"""Wake word detection.

Continuous low-cost listening that wakes the agent when the user says a
trigger phrase like "hey agent", "okay agent", or a configured wake word.

Strategy: tiny Whisper model + sliding window transcription. We listen in
2s windows; on each, transcribe with the smallest model; if the wake phrase
is found, hand control back to the main `listen()` for a full utterance.

This is intentionally simpler than openwakeword (no model downloads needed),
trades a bit of CPU for zero setup friction.
"""
import queue
import threading
import time

import numpy as np

import config

DEFAULT_WAKE_PHRASES = [
    "hey agent", "okay agent", "ok agent", "agent listen", "yo agent",
    "hey claude", "okay claude",
]


class WakeWordListener:
    def __init__(self, wake_phrases: list[str] = None, window_seconds: float = 2.0):
        self.wake_phrases = [p.lower() for p in (wake_phrases or DEFAULT_WAKE_PHRASES)]
        self.window_seconds = window_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_wake = None

    def start(self, on_wake) -> None:
        """Start listening. `on_wake` is called (no args) when wake phrase detected."""
        self._on_wake = on_wake
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="WakeWord")
        self._thread.start()
        print(f"[Wake] Listening for: {self.wake_phrases}")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        import sounddevice as sd
        # Lazy-import faster-whisper and use the smallest model for low latency
        from faster_whisper import WhisperModel
        tiny = WhisperModel("tiny", device=config.WHISPER_DEVICE, compute_type="int8")

        audio_q: queue.Queue = queue.Queue()

        def cb(indata, frames, time_info, status):
            audio_q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=cb,
                blocksize=int(config.SAMPLE_RATE * 0.1),
            ):
                while not self._stop.is_set():
                    chunks_needed = int(self.window_seconds * 10)  # 100ms blocks
                    buf = []
                    for _ in range(chunks_needed):
                        if self._stop.is_set():
                            return
                        try:
                            buf.append(audio_q.get(timeout=0.5))
                        except queue.Empty:
                            continue

                    audio = np.concatenate(buf, axis=0).flatten()
                    rms = float(np.sqrt(np.mean(audio ** 2)))
                    # Skip transcribing pure silence
                    if rms < config.SILENCE_THRESHOLD * 0.5:
                        continue

                    segments, _ = tiny.transcribe(audio, language="en", beam_size=1, vad_filter=True)
                    text = " ".join(s.text.strip() for s in segments).lower()

                    if not text:
                        continue

                    if any(p in text for p in self.wake_phrases):
                        print(f"[Wake] Triggered by: {text!r}")
                        if self._on_wake:
                            self._on_wake()
                        # Brief debounce after wake
                        time.sleep(0.5)
        except Exception as e:
            print(f"[Wake] Error: {e}")
