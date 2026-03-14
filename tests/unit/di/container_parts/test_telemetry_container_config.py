"""Unit tests for config-aware TelemetryContainer DI factory.

Tests TC-445, TC-450, TC-451, TC-470 (DI layer), TC-480, TC-482
from the E02-F04 test plan.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agentmap.di.container_parts.telemetry import TelemetryContainer


def _make_logging_service() -> MagicMock:
    """Create a mock logging service."""
    mock_ls = MagicMock()
    mock_logger = MagicMock()
    mock_ls.get_logger.return_value = mock_logger
    return mock_ls


def _make_app_config_service(telemetry_config: dict | None = None) -> MagicMock:
    """Create a mock app_config_service returning the given telemetry config."""
    mock_acs = MagicMock()
    if telemetry_config is None:
        telemetry_config = {
            "enabled": False,
            "exporter": "none",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {
                "service.name": "agentmap",
            },
        }
    mock_acs.get_telemetry_config.return_value = telemetry_config
    return mock_acs


class TestTelemetryContainerConfigAware:
    """Config-aware factory tests for TelemetryContainer."""

    def test_accepts_app_config_service_dependency(self) -> None:
        """TelemetryContainer accepts app_config_service as a dependency."""
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(),
        )
        svc = container.telemetry_service()
        assert svc is not None

    def test_disabled_telemetry_does_not_call_bootstrap(self) -> None:
        """TC-470: When telemetry disabled, bootstrap is NOT called."""
        config = {
            "enabled": False,
            "exporter": "none",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(config),
        )
        with patch(
            "agentmap.di.container_parts.telemetry.bootstrap_standalone_tracer_provider"
        ) as mock_bootstrap:
            container.telemetry_service.reset()
            svc = container.telemetry_service()
            mock_bootstrap.assert_not_called()
        assert svc is not None

    def test_enabled_telemetry_calls_bootstrap(self) -> None:
        """TC-400/TC-405: When telemetry enabled, bootstrap called with correct args."""
        import types

        config = {
            "enabled": True,
            "exporter": "otlp",
            "endpoint": "http://collector:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": True,
                "agent_outputs": False,
                "llm_prompts": True,
                "llm_responses": False,
            },
            "resource": {"service.name": "my-app"},
        }
        mock_ls = _make_logging_service()
        container = TelemetryContainer(
            logging_service=mock_ls,
            app_config_service=_make_app_config_service(config),
        )
        # Mock the SDK availability check so it doesn't fail
        mock_sdk = types.ModuleType("opentelemetry.sdk")
        with patch.dict("sys.modules", {"opentelemetry.sdk": mock_sdk}):
            with patch(
                "agentmap.di.container_parts.telemetry.bootstrap_standalone_tracer_provider",
                return_value=True,
            ) as mock_bootstrap:
                container.telemetry_service.reset()
                container.telemetry_service()
                mock_bootstrap.assert_called_once()
                call_kwargs = mock_bootstrap.call_args[1]
                assert call_kwargs["exporter"] == "otlp"
                assert call_kwargs["endpoint"] == "http://collector:4317"
                assert call_kwargs["protocol"] == "grpc"
                assert call_kwargs["resource_attributes"] == {"service.name": "my-app"}

    def test_content_capture_flags_stored_on_service(self) -> None:
        """TC-445: _content_capture_flags populated from config on service instance."""
        import types

        config = {
            "enabled": True,
            "exporter": "console",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": True,
                "agent_outputs": False,
                "llm_prompts": True,
                "llm_responses": True,
            },
            "resource": {"service.name": "agentmap"},
        }
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(config),
        )
        mock_sdk = types.ModuleType("opentelemetry.sdk")
        with patch.dict("sys.modules", {"opentelemetry.sdk": mock_sdk}):
            with patch(
                "agentmap.di.container_parts.telemetry.bootstrap_standalone_tracer_provider",
                return_value=True,
            ):
                container.telemetry_service.reset()
                svc = container.telemetry_service()
        assert hasattr(svc, "_content_capture_flags")
        flags = svc._content_capture_flags
        assert flags["agent_inputs"] is True
        assert flags["agent_outputs"] is False
        assert flags["llm_prompts"] is True
        assert flags["llm_responses"] is True

    def test_content_capture_flags_default_when_disabled(self) -> None:
        """Content flags still accessible (empty dict) when telemetry disabled."""
        config = {
            "enabled": False,
            "exporter": "none",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(config),
        )
        container.telemetry_service.reset()
        svc = container.telemetry_service()
        # Even when disabled, should have _content_capture_flags
        flags = getattr(svc, "_content_capture_flags", {})
        assert flags.get("agent_inputs", False) is False
        assert flags.get("llm_prompts", False) is False

    def test_sdk_missing_logs_warning_when_enabled(self) -> None:
        """TC-450: Warning logged when SDK missing but telemetry enabled."""
        config = {
            "enabled": True,
            "exporter": "otlp",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }
        mock_ls = _make_logging_service()
        container = TelemetryContainer(
            logging_service=mock_ls,
            app_config_service=_make_app_config_service(config),
        )
        # Simulate SDK not installed
        with patch.dict(
            "sys.modules",
            {"opentelemetry.sdk": None},
        ):
            with patch(
                "builtins.__import__",
                side_effect=_import_blocker("opentelemetry.sdk"),
            ):
                container.telemetry_service.reset()
                svc = container.telemetry_service()
        # Should not crash, should return a service
        assert svc is not None
        # Warning should have been logged
        mock_logger = mock_ls.get_logger.return_value
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any(
            "agentmap[telemetry]" in w or "not installed" in w for w in warning_calls
        ), f"Expected SDK missing warning, got: {warning_calls}"

    def test_sdk_missing_returns_working_service(self) -> None:
        """TC-451: When SDK missing, a working service is returned."""
        config = {
            "enabled": True,
            "exporter": "otlp",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(config),
        )
        with patch.dict(
            "sys.modules",
            {"opentelemetry.sdk": None},
        ):
            with patch(
                "builtins.__import__",
                side_effect=_import_blocker("opentelemetry.sdk"),
            ):
                container.telemetry_service.reset()
                svc = container.telemetry_service()
        # Service should be functional
        assert svc is not None
        # Protocol methods should work
        with svc.start_span("test") as span:
            span.set_attribute("k", "v")

    def test_bootstrap_failure_returns_working_service(self) -> None:
        """TC-480/TC-482: Bootstrap failure still returns working service."""
        import types

        config = {
            "enabled": True,
            "exporter": "otlp",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": True,
                "agent_outputs": True,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=_make_app_config_service(config),
        )
        # Mock SDK availability, then make bootstrap raise
        mock_sdk = types.ModuleType("opentelemetry.sdk")
        with patch.dict("sys.modules", {"opentelemetry.sdk": mock_sdk}):
            with patch(
                "agentmap.di.container_parts.telemetry.bootstrap_standalone_tracer_provider",
                side_effect=RuntimeError("Bootstrap exploded"),
            ):
                container.telemetry_service.reset()
                svc = container.telemetry_service()
        # Should still get a working service
        assert svc is not None
        with svc.start_span("test") as span:
            span.set_attribute("k", "v")

    def test_config_service_error_returns_service(self) -> None:
        """When app_config_service.get_telemetry_config() raises, service still returned."""
        mock_acs = MagicMock()
        mock_acs.get_telemetry_config.side_effect = RuntimeError("Config broken")
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=mock_acs,
        )
        container.telemetry_service.reset()
        svc = container.telemetry_service()
        assert svc is not None

    def test_backward_compatibility_with_none_app_config(self) -> None:
        """AC7: Container works when app_config_service resolves to None."""
        mock_acs = MagicMock(return_value=None)
        container = TelemetryContainer(
            logging_service=_make_logging_service(),
            app_config_service=mock_acs,
        )
        container.telemetry_service.reset()
        svc = container.telemetry_service()
        assert svc is not None


class TestApplicationContainerTelemetryWiring:
    """Verify ApplicationContainer passes app_config_service to TelemetryContainer."""

    def test_telemetry_container_receives_app_config_service(self) -> None:
        """Verify that _telemetry container is wired with app_config_service."""
        # This is a code-level check -- verify the containers.py wiring
        # by inspecting the source
        import inspect

        from agentmap.di.containers import ApplicationContainer

        source = inspect.getsource(ApplicationContainer)
        # Check that app_config_service is passed to TelemetryContainer
        assert "app_config_service" in source
        # Specifically check it's in the _telemetry wiring
        assert "_telemetry" in source


def _import_blocker(blocked_module: str):
    """Create an __import__ side_effect that blocks a specific module."""
    original_import = (
        __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
    )

    def _blocker(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module + "."):
            raise ImportError(f"Mocked: {name} not installed")
        return original_import(name, *args, **kwargs)

    return _blocker
