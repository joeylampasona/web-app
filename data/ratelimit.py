"""A token bucket that keeps us inside a provider's calls-per-minute ceiling."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, calls_per_minute: int) -> None:
        self.calls_per_minute = max(1, int(calls_per_minute))
        self._interval = 60.0 / self.calls_per_minute
        self._lock = threading.Lock()
        self._next_free = 0.0

    def acquire(self) -> float:
        """Block until a call is allowed. Returns how long we waited."""
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_free - now)
            self._next_free = max(now, self._next_free) + self._interval
        if wait > 0:
            time.sleep(wait)
        return wait
