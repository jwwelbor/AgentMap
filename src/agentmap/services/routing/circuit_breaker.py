import time
from typing import Optional

# --- lightweight circuit breaker --------------------------------------------


class CircuitBreaker:
    """
    Simple per (provider:model) circuit breaker.
    Opens after N failures; resets after cooldown seconds.
    """

    def __init__(self, failures_threshold: int = 3, reset_seconds: int = 60):
        self.threshold = failures_threshold
        self.reset = reset_seconds
        self.failures = {}  # key -> count
        self.opened_at = {}  # key -> timestamp

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def is_open(self, provider: str, model: str, now: Optional[float] = None) -> bool:
        key = self._key(provider, model)
        if key not in self.opened_at:
            return False
        now = now or time.time()
        if now - self.opened_at[key] >= self.reset:
            # half-open: allow a try by closing; next failure will reopen
            self.opened_at.pop(key, None)
            self.failures.pop(key, None)
            return False
        return True

    def record_success(self, provider: str, model: str):
        key = self._key(provider, model)
        self.failures.pop(key, None)
        self.opened_at.pop(key, None)

    def record_failure(self, provider: str, model: str, now: Optional[float] = None):
        key = self._key(provider, model)
        self.failures[key] = self.failures.get(key, 0) + 1
        if self.failures[key] >= self.threshold:
            self.opened_at[key] = now or time.time()
