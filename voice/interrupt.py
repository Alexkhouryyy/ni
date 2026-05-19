"""Interrupt mechanism — lets the user cut off the agent mid-speech.

Strategies in order of preference:
  1. VAD barge-in: monitor mic while TTS is playing; if user speaks, kill TTS.
  2. Hotkey: press ESC (or configured key) to interrupt.

Both run as background threads when speech starts.
"""
import threading
import time
import queue

import numpy as np

import config

_interrupt_event = threading.Event()
_active = threading.Event()


def is_interrupted() -> bool:
    return _interrupt_event.is_set()


def reset() -> None:
    _interrupt_event.clear()


def trigger() -> None:
    _interrupt_event.set()


def start_listening_for_interrupt(tts_engine=None):
    """Start background watcher for interrupts. Returns a stop() function."""
    _active.set()
    reset()

    stop_event = threading.Event()
    threads = []

    def vad_watcher():
        try:
            import sounddevice as sd
        except Exception:
            return

        def cb(indata, frames, time_info, status):
            audio_q.put(indata.copy())

        audio_q: queue.Queue = queue.Queue()
        # Wait briefly so our own TTS audio doesn't trigger us
        time.sleep(0.4)
        try:
            with sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=cb,
                blocksize=int(config.SAMPLE_RATE * 0.1),
            ):
                while not stop_event.is_set():
                    try:
                        chunk = audio_q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    # Threshold higher than silence to avoid self-triggering
                    if rms > config.SILENCE_THRESHOLD * 4:
                        trigger()
                        if tts_engine is not None:
                            try:
                                tts_engine.stop()
                            except Exception:
                                pass
                        break
        except Exception:
            pass

    def hotkey_watcher():
        # Optional: ESC via stdin. Only works if a terminal is attached.
        # Most reliable approach: termios non-blocking read.
        try:
            import sys, select, termios, tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            try:
                while not stop_event.is_set():
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch = sys.stdin.read(1)
                        if ch == "\x1b" or ch == " ":  # ESC or space
                            trigger()
                            if tts_engine is not None:
                                try:
                                    tts_engine.stop()
                                except Exception:
                                    pass
                            break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass

    t1 = threading.Thread(target=vad_watcher, daemon=True)
    t2 = threading.Thread(target=hotkey_watcher, daemon=True)
    t1.start()
    t2.start()
    threads.extend([t1, t2])

    def stop():
        stop_event.set()
        _active.clear()
        for t in threads:
            t.join(timeout=0.5)

    return stop
