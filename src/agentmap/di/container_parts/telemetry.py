"""Telemetry container part with graceful OTEL / NoOp degradation."""

from __future__ import annotations

from dependency_injector import containers, providers


class TelemetryContainer(containers.DeclarativeContainer):
    """Provides the TelemetryService singleton.

    Attempts to instantiate ``OTELTelemetryService`` first.  If
    ``opentelemetry`` is not importable (or instantiation fails for any
    reason), falls back to ``NoOpTelemetryService`` and logs a warning.
    """

    logging_service = providers.Dependency()

    @staticmethod
    def _create_telemetry_service(logging_service):  # type: ignore[no-untyped-def]
        try:
            import opentelemetry.trace  # noqa: F401 -- availability check

            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            return OTELTelemetryService()
        except (ImportError, AttributeError, Exception) as exc:
            try:
                logger = logging_service.get_logger("agentmap.di.telemetry")
                logger.warning(
                    "OpenTelemetry not available, using NoOp telemetry: %s",
                    exc,
                )
            except Exception:
                pass

            from agentmap.services.telemetry.noop_telemetry_service import (
                NoOpTelemetryService,
            )

            return NoOpTelemetryService()

    telemetry_service = providers.Singleton(
        _create_telemetry_service,
        logging_service,
    )
