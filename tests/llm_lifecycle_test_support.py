"""Thread synchronization helpers for governed-client lifecycle tests."""

from threading import Event, Lock


def signalling_lock_factory(waiting: Event):
    """Return a lock factory that signals when acquisition blocks."""

    class SignallingLock:
        def __init__(self):
            self.lock = Lock()

        def __enter__(self):
            if not self.lock.acquire(blocking=False):
                waiting.set()
                if not self.lock.acquire(timeout=5):
                    raise TimeoutError("same-key wait timed out")
            return self

        def __exit__(self, *_):
            self.lock.release()

    return SignallingLock
