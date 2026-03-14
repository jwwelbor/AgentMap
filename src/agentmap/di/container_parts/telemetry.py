"""Telemetry container part with graceful OTEL / NoOp degradation.

Reads telemetry configuration via ``AppConfigService`` and calls
``bootstrap_standalone_tracer_provider()`` when telemetry is enabled,
the OTEL SDK is available, and no host TracerProvider exists.
"""

from __future__ import annotations

from dependency_injector import containers, providers

# Deferred import -- kept at module level for easy patching in tests.
# The actual function is only called when telemetry is enabled.
try:
    from agentmap.services.telemetry.bootstrap import (
        bootstrap_standalone_tracer_provider,
    )
except ImportError:
    bootstrap_standalone_tracer_provider = None  # type: ignore[assignment,misc]


class TelemetryContainer(containers.DeclarativeContainer):
    """Provides the TelemetryService singleton.

    Reads telemetry configuration from ``app_config_service`` and calls
    ``bootstrap_standalone_tracer_provider()`` when enabled.  Falls back
    to ``NoOpTelemetryService`` when the OTEL SDK is not installed or
    any error occurs during bootstrap.
    """

    logging_service = providers.Dependency()
    app_config_service = providers.Dependency()
    app_config_service.set_default(providers.Object(None))

    @staticmethod
    def _create_telemetry_service(  # type: ignore[no-untyped-def]
        logging_service,
        app_config_service=None,
    ):
        try:
            logger = logging_service.get_logger("agentmap.di.telemetry")
        except Exception:
            logger = None

        # Step 1: Read telemetry config
        telemetry_config = _read_telemetry_config(app_config_service, logger)
        enabled = telemetry_config.get("enabled", False)

        # Step 2: If not enabled, return service without bootstrap
        if not enabled:
            return _create_service_no_bootstrap(logging_service, telemetry_config)

        # Step 3: If enabled, check SDK availability
        try:
            import opentelemetry.sdk  # noqa: F401
        except ImportError:
            if logger:
                logger.warning(
                    "Telemetry enabled in config but opentelemetry-sdk "
                    "is not installed. "
                    "Install with: pip install agentmap[telemetry]"
                )
            return _create_service_no_bootstrap(logging_service, telemetry_config)

        # Step 4: Call bootstrap
        try:
            if bootstrap_standalone_tracer_provider is not None:
                bootstrap_standalone_tracer_provider(
                    exporter=telemetry_config.get("exporter", "none"),
                    endpoint=telemetry_config.get("endpoint", "http://localhost:4317"),
                    protocol=telemetry_config.get("protocol", "grpc"),
                    resource_attributes=telemetry_config.get("resource", {}),
                    logger=logger,
                )
        except Exception as exc:
            if logger:
                logger.warning(
                    "Telemetry bootstrap failed, continuing with "
                    "default provider: %s",
                    exc,
                )

        # Step 5: Create service and store content capture flags
        return _create_service_with_flags(logging_service, telemetry_config)

    telemetry_service = providers.Singleton(
        _create_telemetry_service,
        logging_service,
        app_config_service,
    )


def _read_telemetry_config(app_config_service, logger):
    """Read telemetry config from app_config_service, with safe defaults."""
    defaults = {
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
    if app_config_service is None:
        return defaults
    try:
        return app_config_service.get_telemetry_config()
    except Exception as exc:
        if logger:
            logger.warning(
                "Failed to read telemetry config, using defaults: %s",
                exc,
            )
        return defaults


def _create_otel_service():
    """Attempt to create OTELTelemetryService, return None on failure."""
    try:
        import opentelemetry.trace  # noqa: F401

        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        return OTELTelemetryService()
    except (ImportError, AttributeError, Exception):
        return None


def _create_noop_service():
    """Create a NoOpTelemetryService."""
    from agentmap.services.telemetry.noop_telemetry_service import (
        NoOpTelemetryService,
    )

    return NoOpTelemetryService()


def _create_service_no_bootstrap(logging_service, telemetry_config):
    """Create telemetry service without bootstrap, storing content flags."""
    service = _create_otel_service()
    if service is None:
        try:
            logger = logging_service.get_logger("agentmap.di.telemetry")
            logger.warning("OpenTelemetry not available, using NoOp telemetry")
        except Exception:
            pass
        service = _create_noop_service()
    # Store content capture flags
    traces = telemetry_config.get("traces", {})
    service._content_capture_flags = {
        "agent_inputs": traces.get("agent_inputs", False),
        "agent_outputs": traces.get("agent_outputs", False),
        "llm_prompts": traces.get("llm_prompts", False),
        "llm_responses": traces.get("llm_responses", False),
    }
    return service


def _create_service_with_flags(logging_service, telemetry_config):
    """Create telemetry service and store content capture flags."""
    service = _create_otel_service()
    if service is None:
        try:
            logger = logging_service.get_logger("agentmap.di.telemetry")
            logger.warning("OpenTelemetry not available, using NoOp telemetry")
        except Exception:
            pass
        service = _create_noop_service()
    # Store content capture flags
    traces = telemetry_config.get("traces", {})
    service._content_capture_flags = {
        "agent_inputs": traces.get("agent_inputs", False),
        "agent_outputs": traces.get("agent_outputs", False),
        "llm_prompts": traces.get("llm_prompts", False),
        "llm_responses": traces.get("llm_responses", False),
    }
    return service
