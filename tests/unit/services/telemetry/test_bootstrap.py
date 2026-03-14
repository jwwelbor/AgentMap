"""Unit tests for bootstrap_standalone_tracer_provider().

TC-400 through TC-405, TC-410-411, TC-420-422, TC-480-482.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from agentmap.services.telemetry.bootstrap import (
    bootstrap_standalone_tracer_provider,
)

_B = "agentmap.services.telemetry.bootstrap"


@pytest.fixture()
def mock_logger():
    """Provide a mock logger for bootstrap calls."""
    return MagicMock(spec=logging.Logger)


def _make_proxy_trace():
    """Return a mock trace module where get_tracer_provider() returns a
    ProxyTracerProvider instance."""
    mock_trace = MagicMock()
    proxy = MagicMock()
    mock_trace.ProxyTracerProvider = type(proxy)
    mock_trace.get_tracer_provider.return_value = proxy
    return mock_trace


class TestOTLPGrpcExporter:
    """TC-400, TC-405: OTLP gRPC exporter setup."""

    def test_otlp_grpc_creates_tracer_provider_with_exporter(
        self, mock_logger: MagicMock
    ) -> None:
        """TC-400: TracerProvider created with OTLPSpanExporter and
        BatchSpanProcessor for gRPC protocol."""
        mock_trace = _make_proxy_trace()
        mock_tp_cls = MagicMock()
        mock_tp_instance = MagicMock()
        mock_tp_cls.return_value = mock_tp_instance
        mock_bsp_cls = MagicMock()
        mock_grpc_exp = MagicMock()
        mock_resource = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider", mock_tp_cls),
            patch(f"{_B}.BatchSpanProcessor", mock_bsp_cls),
            patch(f"{_B}.GrpcOTLPSpanExporter", mock_grpc_exp),
            patch(f"{_B}.Resource", mock_resource),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_grpc_exp.assert_called_once_with(endpoint="http://localhost:4317")
        mock_bsp_cls.assert_called_once_with(mock_grpc_exp.return_value)
        mock_tp_instance.add_span_processor.assert_called_once_with(
            mock_bsp_cls.return_value
        )
        mock_trace.set_tracer_provider.assert_called_once_with(mock_tp_instance)

    def test_otlp_grpc_returns_true_on_success(self, mock_logger: MagicMock) -> None:
        """TC-405: Bootstrap returns True after successful setup."""
        mock_trace = _make_proxy_trace()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.GrpcOTLPSpanExporter"),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True


class TestOTLPHttpExporter:
    """TC-401: OTLP HTTP/protobuf exporter setup."""

    def test_otlp_http_uses_http_exporter(self, mock_logger: MagicMock) -> None:
        """TC-401: HTTP/protobuf OTLP exporter used when protocol is
        http/protobuf."""
        mock_trace = _make_proxy_trace()
        mock_http_exp = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.HttpOTLPSpanExporter", mock_http_exp),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4318",
                protocol="http/protobuf",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_http_exp.assert_called_once_with(endpoint="http://localhost:4318")


class TestConsoleExporter:
    """TC-410, TC-411: Console exporter setup."""

    def test_console_exporter_configured(self, mock_logger: MagicMock) -> None:
        """TC-410: ConsoleSpanExporter used when exporter='console'."""
        mock_trace = _make_proxy_trace()
        mock_tp_cls = MagicMock()
        mock_tp_instance = MagicMock()
        mock_tp_cls.return_value = mock_tp_instance
        mock_bsp_cls = MagicMock()
        mock_console_exp = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider", mock_tp_cls),
            patch(f"{_B}.BatchSpanProcessor", mock_bsp_cls),
            patch(f"{_B}.ConsoleSpanExporter", mock_console_exp),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_console_exp.assert_called_once()
        mock_bsp_cls.assert_called_once_with(mock_console_exp.return_value)
        mock_tp_instance.add_span_processor.assert_called_once()
        mock_trace.set_tracer_provider.assert_called_once()

    def test_console_exporter_ignores_endpoint_and_protocol(
        self, mock_logger: MagicMock
    ) -> None:
        """TC-411: Console exporter ignores endpoint and protocol params."""
        mock_trace = _make_proxy_trace()
        mock_console_exp = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter", mock_console_exp),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="http://example.com:4317",
                protocol="http/protobuf",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        # ConsoleSpanExporter called with no arguments
        mock_console_exp.assert_called_once_with()


class TestResourceAttributes:
    """TC-402, TC-403, TC-404: Resource building."""

    def test_agentmap_version_always_included(self, mock_logger: MagicMock) -> None:
        """TC-402: Resource includes agentmap.version regardless of user
        attrs."""
        mock_trace = _make_proxy_trace()
        mock_resource = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource", mock_resource),
        ):
            bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        call_args = mock_resource.create.call_args
        attrs = call_args[0][0]
        assert "agentmap.version" in attrs
        assert isinstance(attrs["agentmap.version"], str)
        assert len(attrs["agentmap.version"]) > 0

    def test_user_resource_attributes_applied(self, mock_logger: MagicMock) -> None:
        """TC-403: User resource attributes applied to TracerProvider."""
        mock_trace = _make_proxy_trace()
        mock_resource = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource", mock_resource),
        ):
            bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={
                    "service.name": "my-app",
                    "deployment.environment": "staging",
                },
                logger=mock_logger,
            )

        call_args = mock_resource.create.call_args
        attrs = call_args[0][0]
        assert attrs["service.name"] == "my-app"
        assert attrs["deployment.environment"] == "staging"

    def test_service_name_defaults_to_agentmap(self, mock_logger: MagicMock) -> None:
        """TC-404: service.name defaults to 'agentmap' when not provided."""
        mock_trace = _make_proxy_trace()
        mock_resource = MagicMock()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource", mock_resource),
        ):
            bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        call_args = mock_resource.create.call_args
        attrs = call_args[0][0]
        assert attrs["service.name"] == "agentmap"


class TestStandaloneDetection:
    """TC-420, TC-421, TC-422: Standalone vs embedded detection."""

    def test_skips_when_real_tracer_provider_exists(
        self, mock_logger: MagicMock
    ) -> None:
        """TC-420: Bootstrap skips when real TracerProvider exists."""
        mock_trace = MagicMock()
        # Return a non-ProxyTracerProvider
        real_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = real_provider
        mock_trace.ProxyTracerProvider = type("ProxyTracerProvider", (), {})

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_trace.set_tracer_provider.assert_not_called()
        mock_logger.info.assert_called()

    def test_proceeds_when_proxy_tracer_provider_detected(
        self, mock_logger: MagicMock
    ) -> None:
        """TC-421: Bootstrap proceeds when ProxyTracerProvider detected."""
        mock_trace = _make_proxy_trace()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_trace.set_tracer_provider.assert_called_once()

    def test_idempotent_second_call_skips(self, mock_logger: MagicMock) -> None:
        """TC-422: Second call detects existing real TracerProvider and
        skips."""
        mock_trace = _make_proxy_trace()
        mock_tp_cls = MagicMock()
        real_tp = MagicMock()
        mock_tp_cls.return_value = real_tp

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider", mock_tp_cls),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource"),
        ):
            # First call: standalone (ProxyTracerProvider)
            result1 = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )
            assert result1 is True

            # Simulate that the first call set a real provider
            mock_trace.get_tracer_provider.return_value = real_tp
            mock_trace.set_tracer_provider.reset_mock()

            # Second call: detects existing real provider
            result2 = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )
            assert result2 is True
            mock_trace.set_tracer_provider.assert_not_called()


class TestNoneExporter:
    """AC8: 'none' exporter returns True immediately."""

    def test_none_exporter_returns_true_no_provider(
        self, mock_logger: MagicMock
    ) -> None:
        """exporter='none' returns True immediately with no TracerProvider
        created."""
        mock_trace = _make_proxy_trace()

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="none",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is True
        mock_trace.set_tracer_provider.assert_not_called()


class TestGracefulDegradation:
    """TC-480, TC-481, TC-482: Error handling."""

    def test_exporter_error_returns_false(self, mock_logger: MagicMock) -> None:
        """TC-480: Bootstrap catches exporter errors and returns False."""
        mock_trace = _make_proxy_trace()
        mock_grpc_exp = MagicMock()
        mock_grpc_exp.side_effect = ConnectionError("Connection refused")

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.GrpcOTLPSpanExporter", mock_grpc_exp),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is False
        mock_logger.warning.assert_called()

    def test_warning_includes_error_details(self, mock_logger: MagicMock) -> None:
        """TC-481: Warning log includes error details."""
        mock_trace = _make_proxy_trace()
        mock_grpc_exp = MagicMock()
        error_msg = "Connection refused"
        mock_grpc_exp.side_effect = ConnectionError(error_msg)

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider"),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.GrpcOTLPSpanExporter", mock_grpc_exp),
            patch(f"{_B}.Resource"),
        ):
            bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://unreachable:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        # Verify warning was called with error info
        warning_call = mock_logger.warning.call_args
        assert warning_call is not None
        # The log message format string and args should contain the error
        log_msg = warning_call[0][0] % warning_call[0][1:]
        assert "Connection refused" in log_msg

    def test_unexpected_exception_returns_false(self, mock_logger: MagicMock) -> None:
        """TC-482: Any unexpected exception returns False, no crash."""
        mock_trace = _make_proxy_trace()
        mock_tp_cls = MagicMock()
        mock_tp_cls.side_effect = RuntimeError("Unexpected OTEL error")

        with (
            patch(f"{_B}._load_otel_imports"),
            patch(f"{_B}.trace", mock_trace),
            patch(f"{_B}.TracerProvider", mock_tp_cls),
            patch(f"{_B}.BatchSpanProcessor"),
            patch(f"{_B}.ConsoleSpanExporter"),
            patch(f"{_B}.Resource"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="console",
                endpoint="",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is False
        mock_logger.warning.assert_called()


class TestModuleImportability:
    """Verify module can be imported without opentelemetry-sdk."""

    def test_module_importable(self) -> None:
        """Bootstrap module importable without SDK installed."""
        # If we get here, the module imported successfully at top of file
        assert callable(bootstrap_standalone_tracer_provider)


class TestSdkNotAvailable:
    """Test behavior when OTEL SDK is not installed."""

    def test_returns_false_when_sdk_missing(self, mock_logger: MagicMock) -> None:
        """Bootstrap returns False and logs warning when SDK imports fail."""
        with patch(
            f"{_B}._load_otel_imports",
            side_effect=ImportError("No module named 'opentelemetry.sdk'"),
        ):
            result = bootstrap_standalone_tracer_provider(
                exporter="otlp",
                endpoint="http://localhost:4317",
                protocol="grpc",
                resource_attributes={},
                logger=mock_logger,
            )

        assert result is False
        mock_logger.warning.assert_called()
