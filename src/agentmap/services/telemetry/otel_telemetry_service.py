"""
OpenTelemetry-backed TelemetryService implementation.

This is the primary implementation used when ``opentelemetry-api`` is
installed.  It delegates every operation to the standard OTEL API and
wraps all calls in try/except so that **no telemetry failure ever
propagates to the caller**.

All ``opentelemetry`` imports in the AgentMap codebase are confined to
this module and ``di/container_parts/telemetry.py``.
"""

from __future__ import annotations

import logging
from typing import Any, ContextManager, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

# Obtain AgentMap version at import time -- fallback to "unknown".
try:
    from importlib.metadata import version as _pkg_version

    _agentmap_version: str = _pkg_version("agentmap")
except Exception:
    _agentmap_version = "unknown"


class OTELTelemetryService:
    """Telemetry service backed by the OpenTelemetry tracing API.

    The constructor calls ``trace.get_tracer("agentmap", version=...)``
    which automatically participates in the host application's
    ``TracerProvider``.  When no SDK is configured the OTEL API returns a
    built-in no-op tracer.
    """

    def __init__(self) -> None:
        self._tracer = trace.get_tracer(
            "agentmap", instrumenting_library_version=_agentmap_version
        )

    # -- Protocol methods ---------------------------------------------------

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: Optional[Any] = None,
    ) -> ContextManager[Any]:
        """Start a span using the OTEL tracer.

        Delegates to ``tracer.start_as_current_span()``.
        """
        kwargs: Dict[str, Any] = {}
        if attributes is not None:
            kwargs["attributes"] = attributes
        if kind is not None:
            kwargs["kind"] = kind
        return self._tracer.start_as_current_span(name, **kwargs)

    def record_exception(self, span: Any, exception: BaseException) -> None:
        """Record *exception* on *span* and set status to ERROR."""
        try:
            span.record_exception(exception)
            span.set_status(StatusCode.ERROR, str(exception))
        except Exception as exc:
            logger.warning("Failed to record exception on span: %s", exc)

    def set_span_attributes(self, span: Any, attributes: Dict[str, Any]) -> None:
        """Set each key-value pair as an attribute on *span*.

        Individual failures (``TypeError``, ``ValueError``) are logged as
        warnings; they never propagate.
        """
        for key, value in attributes.items():
            try:
                span.set_attribute(key, value)
            except (TypeError, ValueError) as exc:
                logger.warning("Failed to set span attribute %r: %s", key, exc)
            except Exception as exc:
                logger.warning(
                    "Unexpected error setting span attribute %r: %s",
                    key,
                    exc,
                )

    def add_span_event(
        self,
        span: Any,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an event to *span*."""
        try:
            kwargs: Dict[str, Any] = {}
            if attributes is not None:
                kwargs["attributes"] = attributes
            span.add_event(name, **kwargs)
        except Exception as exc:
            logger.warning("Failed to add span event %r: %s", name, exc)

    def get_tracer(self) -> Any:
        """Return the underlying OTEL tracer."""
        return self._tracer
