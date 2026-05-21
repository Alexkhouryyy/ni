"""Streamer for the TUI — prints token deltas inline as the agent generates.

Implements the streamer protocol shared with StreamingSpeaker (voice) and
ChatStreamer (dashboard): start / feed / finish, plus interrupt for cancellation.
"""
import sys
import threading


class TUIStreamer:
    """Writes streamed token deltas straight to stdout.

    `interrupt()` sets the shared cancel Event, which AgentCore.run() and
    _stream_turn() check to stop the turn at the next opportunity.
    """

    def __init__(self, cancel_event: threading.Event):
        self._cancel = cancel_event
        self._chunks: list[str] = []

    def start(self) -> None:
        sys.stdout.write("\nAGENT: ")
        sys.stdout.flush()

    def feed(self, delta: str) -> None:
        self._chunks.append(delta)
        sys.stdout.write(delta)
        sys.stdout.flush()

    def finish(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()

    def interrupt(self) -> None:
        self._cancel.set()

    @property
    def text(self) -> str:
        return "".join(self._chunks)
