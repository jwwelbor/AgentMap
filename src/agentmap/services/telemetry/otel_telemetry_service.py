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
import re
from typing import Any, ContextManager, Dict, Optional

from opentelemetry import metrics, trace
from opentelemetry.trace import StatusCode

# TD-030 / F2 fix: reuse the provider-key-*prefixed* pattern already relied
# on by ``classify_llm_error`` (llm_error_utils.py) instead of inventing a
# second one -- it covers the provider key shapes
# (``sk-...``/``key-...``/``AIza...``/``ant-api...``). Deliberately does
# NOT use that module's ``_SENSITIVE_RE``, whose bare long-opaque-token
# catch-all is safe only for LLM-domain messages: ``record_exception()``
# below is a *shared* telemetry boundary used by every span in the app
# (storage, graph-runner, etc.), and the catch-all false-positives on
# ordinary UUIDs/hashes/thread-ids in those non-LLM exception messages.
# This is the only cross-module import in this file besides
# ``opentelemetry`` itself; ``llm_error_utils`` has no reverse dependency on
# telemetry, so there is no import cycle.
from agentmap.services.llm_error_utils import CREDENTIAL_PREFIXED_RE

logger = logging.getLogger(__name__)

# TD-030: exception messages recorded onto a telemetry span are not
# guaranteed to be credential-safe -- callers across all three telemetry
# wrappers (sync, async, streaming) delegate to `record_exception()` below
# without scrubbing, and a provider SDK exception (outside our control) may
# embed an api key or bearer token in its message. In addition to the
# shared ``CREDENTIAL_PREFIXED_RE`` pattern (provider-key-prefixed shapes),
# these cover two shapes it does not: labelled `key=`/`token=`/`secret=`/`password=`
# assignments with shorter values, and `Authorization: Bearer <token>`
# headers. Deliberately pragmatic, not exhaustive.
_CREDENTIAL_LABELLED_RE = re.compile(
    r"(?i)\b((?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?)"
    r"([A-Za-z0-9\-_.]{6,})"
)
_CREDENTIAL_BEARER_RE = re.compile(r"(?i)\b(bearer\s+)(\S+)")
_REDACTED = "***REDACTED***"


def _redact_credentials(text: str) -> str:
    """Scrub credential-shaped substrings from *text* (TD-030).

    Pattern-based and intentionally not exhaustive -- see module-level
    comment for the exact shapes covered. Used as the single centralized
    guard before any exception text reaches ``span.record_exception()`` /
    ``span.set_status()``.
    """
    redacted = _CREDENTIAL_LABELLED_RE.sub(lambda m: m.group(1) + _REDACTED, text)
    redacted = _CREDENTIAL_BEARER_RE.sub(lambda m: m.group(1) + _REDACTED, redacted)
    redacted = CREDENTIAL_PREFIXED_RE.sub(_REDACTED, redacted)
    return redacted


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
        """Record *exception* on *span* and set status to ERROR.

        TD-030 credential-safety guarantee: this is the single centralized
        point all telemetry wrappers (sync ``_call_llm_with_telemetry``,
        async ``_call_llm_async_with_telemetry``, streaming
        ``_call_llm_stream_async_with_telemetry`` -- all funnel through
        ``LLMService._record_span_exception_safe()`` into this method)
        route exceptions through before they reach the span. The exception
        message is scrubbed for credential-shaped substrings (labelled
        ``api_key=``/``token=``/``secret=``/``password=`` values,
        ``Authorization: Bearer <token>`` headers, provider-key-prefixed
        tokens such as ``sk-...``/``AIza...``) via ``_redact_credentials()``.
        Deliberately does not use the bare long-opaque-token catch-all from
        ``llm_error_utils._SENSITIVE_RE`` -- this method is a shared
        telemetry boundary for every span in the app (not just LLM ones),
        and that catch-all false-positives on ordinary UUIDs/hashes/
        thread-ids in non-LLM exception messages. When scrubbing changes the message, a
        bare ``Exception`` carrying only the redacted text is recorded
        instead of *exception* itself, so no unredacted ``__cause__``/
        traceback chain reaches the span (mirrors ``telemetry_safe_marker``
        in ``_budget_guard_refusal.py``). When no credential pattern
        matches, *exception* is recorded unchanged. Callers do not need to
        pre-sanitize exceptions before calling this method.
        """
        try:
            message = str(exception)
            redacted_message = _redact_credentials(message)
            if redacted_message != message:
                span.record_exception(Exception(redacted_message))
                span.set_status(StatusCode.ERROR, redacted_message)
            else:
                span.record_exception(exception)
                span.set_status(StatusCode.ERROR, message)
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
