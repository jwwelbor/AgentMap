"""
Null-object TelemetryService implementation.

This module provides a ``NoOpTelemetryService`` that satisfies
``TelemetryServiceProtocol`` while performing no actual work.  It is used
as a fallback when the OTEL API package is not installed.

**This module has zero OTEL imports.**
"""

from __future__ import annotations

import contextlib
from typing import Any, ContextManager, Dict, Optional


class _NoOpCounter:
    """Counter-like object that silently accepts all add calls."""

    def add(self, amount: Any = 0, attributes: Any = None, **kwargs: Any) -> None:
        """No-op."""


class _NoOpHistogram:
    """Histogram-like object that silently accepts all record calls."""

    def record(self, value: Any = 0, attributes: Any = None, **kwargs: Any) -> None:
        """No-op."""


class _NoOpUpDownCounter:
    """UpDownCounter-like object that silently accepts all add calls."""

    def add(self, amount: Any = 0, attributes: Any = None, **kwargs: Any) -> None:
        """No-op."""


# Pre-allocated singletons for no-op metric instruments.
_NOOP_COUNTER = _NoOpCounter()
_NOOP_HISTOGRAM = _NoOpHistogram()
_NOOP_UP_DOWN_COUNTER = _NoOpUpDownCounter()


class _NoOpSpan:
    """Span-like object that silently accepts all method calls."""

    def set_attribute(self, key: Any, value: Any) -> None:
        """No-op."""

    def add_event(self, name: Any, attributes: Any = None, **kwargs: Any) -> None:
        """No-op."""

    def record_exception(self, exception: Any, **kwargs: Any) -> None:
        """No-op."""

    def set_status(self, status: Any, description: Any = None) -> None:
        """No-op."""


# Pre-allocated singleton -- reused by every ``start_span()`` call.
_NOOP_SPAN = _NoOpSpan()


class NoOpTelemetryService:
    """Telemetry service that performs no operations.

    All methods conform to ``TelemetryServiceProtocol`` but produce no
    side-effects.  The class has zero ``OTEL`` dependencies.
    """

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: Optional[Any] = None,
    ) -> ContextManager[Any]:
        """Return a ``nullcontext`` yielding the pre-allocated no-op span."""
        return contextlib.nullcontext(_NOOP_SPAN)

    def record_exception(self, span: Any, exception: BaseException) -> None:
        """No-op."""

    def set_span_attributes(self, span: Any, attributes: Dict[str, Any]) -> None:
        """No-op."""

    def add_span_event(
        self,
        span: Any,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """No-op."""

    def get_tracer(self) -> Any:
        """Return ``None`` -- no tracer available."""
        return None

    # -- Metrics methods ----------------------------------------------------

    def get_meter(self, name: str = "agentmap", version: Optional[str] = None) -> Any:
        """Return ``None`` -- no meter available."""
        return None

    def create_counter(self, name: str, unit: str = "", description: str = "") -> Any:
        """Return the pre-allocated no-op counter singleton."""
        return _NOOP_COUNTER

    def create_histogram(self, name: str, unit: str = "", description: str = "") -> Any:
        """Return the pre-allocated no-op histogram singleton."""
        return _NOOP_HISTOGRAM

    def create_up_down_counter(
        self, name: str, unit: str = "", description: str = ""
    ) -> Any:
        """Return the pre-allocated no-op up-down counter singleton."""
        return _NOOP_UP_DOWN_COUNTER
