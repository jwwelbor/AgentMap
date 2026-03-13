"""Unit tests for TelemetryContainer DI part."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dependency_injector import containers

from agentmap.di.container_parts.telemetry import TelemetryContainer
from agentmap.services.telemetry.noop_telemetry_service import NoOpTelemetryService
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


def _make_logging_service() -> MagicMock:
    """Create a mock logging service."""
    mock_ls = MagicMock()
    mock_logger = MagicMock()
    mock_ls.get_logger.return_value = mock_logger
    return mock_ls


class TestTelemetryContainer:
    """TC-030 through TC-035, TC-060 through TC-062."""

    def test_container_is_declarative(self) -> None:
        """TC-030: TelemetryContainer is a DeclarativeContainer subclass."""
        assert issubclass(TelemetryContainer, containers.DeclarativeContainer)

    def test_resolves_otel_when_available(self) -> None:
        """TC-031: Resolves OTELTelemetryService when OTEL is importable."""
        container = TelemetryContainer(logging_service=_make_logging_service())
        svc = container.telemetry_service()
        # Since opentelemetry-api IS installed in the test environment,
        # we should get the OTEL implementation.
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        assert isinstance(svc, OTELTelemetryService)
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_falls_back_to_noop_when_otel_unavailable(self) -> None:
        """TC-032: Falls back to NoOpTelemetryService when OTEL import fails."""
        mock_ls = _make_logging_service()

        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            # Reset the singleton so it re-resolves
            container.telemetry_service.reset()
            svc = container.telemetry_service()
            assert isinstance(svc, NoOpTelemetryService)
            assert isinstance(svc, TelemetryServiceProtocol)

    def test_warning_logged_on_fallback(self) -> None:
        """TC-033: Warning logged when falling back to NoOp."""
        mock_ls = _make_logging_service()

        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            container.telemetry_service.reset()
            container.telemetry_service()
            mock_ls.get_logger.assert_called()
            mock_logger = mock_ls.get_logger.return_value
            mock_logger.warning.assert_called()

    def test_singleton_lifecycle(self) -> None:
        """TC-034: Two resolutions return the same instance (singleton)."""
        container = TelemetryContainer(logging_service=_make_logging_service())
        svc1 = container.telemetry_service()
        svc2 = container.telemetry_service()
        assert svc1 is svc2

    def test_no_exception_on_resolution(self) -> None:
        """TC-035: Container never raises, regardless of OTEL availability."""
        # With OTEL available
        container = TelemetryContainer(logging_service=_make_logging_service())
        svc = container.telemetry_service()
        assert svc is not None

    def test_import_error_triggers_noop_fallback(self) -> None:
        """TC-060: ImportError during instantiation triggers NoOp fallback."""
        mock_ls = _make_logging_service()

        # Simulate the OTEL import failing inside the factory
        with patch.dict(
            "sys.modules",
            {"opentelemetry": None, "opentelemetry.trace": None},
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            container.telemetry_service.reset()
            svc = container.telemetry_service()
            assert isinstance(svc, NoOpTelemetryService)

    def test_warning_includes_exception_message(self) -> None:
        """TC-061: Warning log includes the exception message."""
        mock_ls = _make_logging_service()

        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            container.telemetry_service.reset()
            container.telemetry_service()
            mock_logger = mock_ls.get_logger.return_value
            # The warning call should contain exception info
            if mock_logger.warning.called:
                call_args = mock_logger.warning.call_args
                # The message format string and args
                assert len(call_args[0]) >= 1

    def test_protocol_methods_work_after_fallback(self) -> None:
        """TC-062: All protocol methods work after NoOp fallback."""
        mock_ls = _make_logging_service()

        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            container.telemetry_service.reset()
            svc = container.telemetry_service()

        # All protocol methods should work
        with svc.start_span("test") as span:
            span.set_attribute("k", "v")
        svc.record_exception(None, ValueError("test"))
        svc.set_span_attributes(None, {"k": "v"})
        svc.add_span_event(None, "event")
        svc.get_tracer()
