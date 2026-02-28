import time
from typing import Optional

# --- lightweight circuit breaker --------------------------------------------

# Maximum number of distinct provider:model keys tracked.
# Prevents unbounded memory growth from arbitrary model names.
_MAX_TRACKED_KEYS = 100


class CircuitBreaker:
    """
    Simple per (provider:model) circuit breaker.
    Opens after N failures; resets after cooldown seconds.

    Tracks at most ``_MAX_TRACKED_KEYS`` distinct provider:model
    combinations to prevent memory exhaustion from arbitrary inputs.
    """

    def __init__(self, failures_threshold: int = 3, reset_seconds: int = 60):
        self.threshold = failures_threshold
        self.reset = reset_seconds
        self.failures: dict[str, int] = {}  # key -> count
        self.opened_at: dict[str, float] = {}  # key -> timestamp

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def _evict_stale(self, now: float) -> None:
        """Remove expired entries when nearing the capacity limit."""
        expired = [k for k, ts in self.opened_at.items() if now - ts >= self.reset]
        for k in expired:
            self.opened_at.pop(k, None)
            self.failures.pop(k, None)

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

    def record_success(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        self.failures.pop(key, None)
        self.opened_at.pop(key, None)

    def record_failure(
        self, provider: str, model: str, now: Optional[float] = None
    ) -> None:
        key = self._key(provider, model)
        now = now or time.time()

        # Enforce capacity limit
        if key not in self.failures and len(self.failures) >= _MAX_TRACKED_KEYS:
            self._evict_stale(now)
            # If still at capacity after eviction, drop the oldest entry
            if len(self.failures) >= _MAX_TRACKED_KEYS:
                oldest_key = min(
                    self.failures, key=self.failures.get  # type: ignore[arg-type]
                )
                self.failures.pop(oldest_key, None)
                self.opened_at.pop(oldest_key, None)

        self.failures[key] = self.failures.get(key, 0) + 1
        if self.failures[key] >= self.threshold:
            self.opened_at[key] = now
