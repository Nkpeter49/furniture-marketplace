"""Small in-process abuse limits for the single-process local MVP.

These limits reset when the app restarts and are not suitable for multiple
workers or public deployment; production should use a shared limiter/store.
"""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class LocalRateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True
