"""Utility helpers for working with dependency-injector providers."""

from __future__ import annotations

from typing import Any


def create_optional_service(
    service_provider: Any, fallback_value: Any = None
) -> Any:
    """Attempt to resolve ``service_provider`` returning ``fallback_value`` on error."""

    try:
        return service_provider()
    except Exception:
        return fallback_value


def safe_get_service(
    container: Any, service_name: str, default: Any = None
) -> Any:
    """Safely resolve a named provider from ``container`` returning ``default`` on failure."""

    try:
        return getattr(container, service_name)()
    except Exception:
        return default
