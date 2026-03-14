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

from opentelemetry import metrics, trace
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
        self._meter = metrics.get_meter("agentmap", version=_agentmap_version)

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

    # -- Metrics methods ----------------------------------------------------

    def get_meter(self, name: str = "agentmap", version: Optional[str] = None) -> Any:
        """Return an OTEL Meter via ``metrics.get_meter()``."""
        try:
            return metrics.get_meter(name, version=version)
        except Exception as exc:
            logger.warning("Failed to get meter %r: %s", name, exc)
            return None

    def create_counter(self, name: str, unit: str = "", description: str = "") -> Any:
        """Create an OTEL Counter instrument via the stored meter."""
        try:
            return self._meter.create_counter(name, unit=unit, description=description)
        except Exception as exc:
            logger.warning("Failed to create counter %r: %s", name, exc)
            from agentmap.services.telemetry.noop_telemetry_service import (
                _NOOP_COUNTER,
            )

            return _NOOP_COUNTER

    def create_histogram(self, name: str, unit: str = "", description: str = "") -> Any:
        """Create an OTEL Histogram instrument via the stored meter."""
        try:
            return self._meter.create_histogram(
                name, unit=unit, description=description
            )
        except Exception as exc:
            logger.warning("Failed to create histogram %r: %s", name, exc)
            from agentmap.services.telemetry.noop_telemetry_service import (
                _NOOP_HISTOGRAM,
            )

            return _NOOP_HISTOGRAM

    def create_up_down_counter(
        self, name: str, unit: str = "", description: str = ""
    ) -> Any:
        """Create an OTEL UpDownCounter instrument via the stored meter."""
        try:
            return self._meter.create_up_down_counter(
                name, unit=unit, description=description
            )
        except Exception as exc:
            logger.warning("Failed to create up_down_counter %r: %s", name, exc)
            from agentmap.services.telemetry.noop_telemetry_service import (
                _NOOP_UP_DOWN_COUNTER,
            )

            return _NOOP_UP_DOWN_COUNTER
