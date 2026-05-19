"""Streaming TTS queue — speaks sentences as they arrive, in order.

Producer (agent loop) pushes text deltas. We buffer until we hit a sentence
boundary, then enqueue the sentence for speaking. A background worker drains
the queue, calling tts.speak() on each chunk. Interrupts flush everything.
"""
import queue
import re
import threading

from voice import tts, interrupt as interrupt_mod

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n\n")


class StreamingSpeaker:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._buffer: str = ""
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._interrupted = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        self._interrupted.clear()
        self._buffer = ""
        self._worker = threading.Thread(target=self._run, daemon=True, name="StreamSpeaker")
        self._worker.start()

    def feed(self, text_delta: str) -> None:
        """Push a chunk of streamed text. Sentences get flushed to the queue."""
        if self._interrupted.is_set():
            return
        self._buffer += text_delta

        while True:
            match = _SENTENCE_END.search(self._buffer)
            if not match:
                break
            sentence = self._buffer[:match.end()].strip()
            self._buffer = self._buffer[match.end():]
            if sentence:
                self._queue.put(sentence)

    def flush_remaining(self) -> None:
        """Push any trailing text (no terminal punctuation)."""
        if self._buffer.strip() and not self._interrupted.is_set():
            self._queue.put(self._buffer.strip())
        self._buffer = ""

    def finish(self) -> bool:
        """Signal end of stream, wait for queue drain. Returns True if completed, False if interrupted."""
        self.flush_remaining()
        self._queue.put(None)  # sentinel
        if self._worker:
            self._worker.join()
        return not self._interrupted.is_set()

    def interrupt(self) -> None:
        self._interrupted.set()
        # Drain queue
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._queue.put(None)

    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                return
            if self._interrupted.is_set():
                continue
            completed = tts.speak(item, interruptible=True)
            if not completed:
                self._interrupted.set()
                return
