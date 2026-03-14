"""
TelemetryService protocol for AgentMap's dependency injection architecture.

This module defines the ``TelemetryServiceProtocol`` that all telemetry
service implementations must satisfy.  It is the single contract layer
between instrumented code (agents, services, runners) and the concrete
telemetry backend.

The protocol deliberately uses ``typing.Any`` for span and tracer
references so that it can be imported and used without any OpenTelemetry
packages installed.  Concrete implementations (``OTELTelemetryService``,
``NoOpTelemetryService``) provide the real or no-op behaviour
respectively.

The DI container resolves exactly one implementation as a singleton and
injects it into every consumer that declares a ``telemetry_service``
constructor parameter.
"""

from __future__ import annotations

from typing import Any, ContextManager, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class TelemetryServiceProtocol(Protocol):
    """Protocol defining the telemetry service interface for AgentMap.

    All telemetry consumers depend on this protocol, never on a concrete
    implementation.  The DI container resolves the appropriate
    implementation (OTEL or NoOp) at application startup.
    """

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: Optional[Any] = None,
    ) -> ContextManager[Any]:
        """Create and start a span as a context manager.

        The yielded object is a span-like object supporting
        ``set_attribute()``, ``add_event()``, ``record_exception()``,
        and ``set_status()`` calls.

        Args:
            name: Span name (use constants from ``constants.py``).
            attributes: Optional initial attributes for the span.
            kind: Optional span kind (e.g. OTEL ``SpanKind`` value).

        Returns:
            A context manager yielding a span-like object.
        """
        ...

    def record_exception(self, span: Any, exception: BaseException) -> None:
        """Record an exception on *span* and set its status to error.

        Args:
            span: The span object yielded by ``start_span()``.
            exception: The exception to record.
        """
        ...

    def set_span_attributes(self, span: Any, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes on *span*.

        Each key-value pair is recorded individually.

        Args:
            span: The span object yielded by ``start_span()``.
            attributes: Mapping of attribute names to values.
        """
        ...

    def add_span_event(
        self,
        span: Any,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a named event to *span*.

        Args:
            span: The span object yielded by ``start_span()``.
            name: Event name.
            attributes: Optional event attributes.
        """
        ...

    def get_tracer(self) -> Any:
        """Return the underlying tracer object.

        Returns:
            The tracer instance (or ``None`` for the no-op implementation).
        """
        ...

    # -- Metrics methods ----------------------------------------------------

    def get_meter(
        self,
        name: str = "agentmap",
        version: Optional[str] = None,
    ) -> Any:
        """Return a meter object for creating metric instruments.

        Args:
            name: Meter name (typically the instrumentation scope).
            version: Optional version string for the meter.

        Returns:
            A meter instance (or ``None`` for the no-op implementation).
        """
        ...

    def create_counter(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create a counter instrument.

        Args:
            name: Counter metric name (use constants from ``constants.py``).
            unit: Unit of measurement.
            description: Human-readable description.

        Returns:
            A counter instrument supporting ``add(amount, attributes)``.
        """
        ...

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create a histogram instrument.

        Args:
            name: Histogram metric name (use constants from ``constants.py``).
            unit: Unit of measurement.
            description: Human-readable description.

        Returns:
            A histogram instrument supporting ``record(value, attributes)``.
        """
        ...

    def create_up_down_counter(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create an up-down counter instrument.

        Args:
            name: UpDownCounter metric name.
            unit: Unit of measurement.
            description: Human-readable description.

        Returns:
            An up-down counter supporting ``add(amount, attributes)``.
        """
        ...
