"""Background proactive monitor — watches the screen and speaks up unprompted."""
import threading
import time
import config


class ProactiveMonitor:
    def __init__(self, agent_core, speak_fn, interval: int = None):
        self.agent = agent_core
        self.speak = speak_fn
        self.interval = interval or config.PROACTIVE_INTERVAL
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_observation: str = ""

    def start(self) -> None:
        if not config.PROACTIVE_ENABLED:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ProactiveMonitor")
        self._thread.start()
        print("[Proactive] Monitor started.")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(timeout=self.interval):
            try:
                self._check()
            except Exception as e:
                print(f"[Proactive] Error: {e}")

    def _check(self) -> None:
        from tools.computer import screenshot
        b64, _ = screenshot()
        observation = self.agent.proactive_check(b64)

        if observation and observation != self._last_observation:
            self._last_observation = observation
            print(f"[Proactive] Speaking up: {observation}")
            self.speak(f"Hey, I noticed something. {observation}")
