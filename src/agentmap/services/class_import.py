"""Shared runtime checks for dynamically imported classes."""

from typing import Any


def require_class(value: Any, class_path: str) -> type[Any]:
    """Return an imported value only when it is a class."""
    if not isinstance(value, type):
        raise ImportError(
            f"Configured class path '{class_path}' does not resolve to a class"
        )
    return value
