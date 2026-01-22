"""Decorators for storage service handlers."""

from functools import wraps


def ensure_handlers_initialized(func):
    """
    Decorator to ensure handlers are initialized before method execution.

    This reduces repetition across FileStorageService methods that delegate
    to specialized handlers.

    Args:
        func: Method to wrap

    Returns:
        Wrapped method that initializes handlers first
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self._initialize_handlers()
        return func(self, *args, **kwargs)

    return wrapper
