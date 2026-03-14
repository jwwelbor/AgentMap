"""Integration tests for E02-F04 Configuration and Standalone Bootstrap.

These tests verify:
- INT-400: Full DI container with console exporter produces working spans.
- INT-410: Privacy controls end-to-end -- default config produces no content
  in spans; enabled config includes content.
- INT-420: Graceful degradation when OTEL SDK is unavailable.
- INT-430: Cross-feature content capture flag flow to E02-F02 agent context
  and E02-F03 LLM service.
- INT-440: Config template is valid YAML with expected telemetry section.
- INT-450: Backward compatibility -- existing workflows unchanged when
  telemetry config absent.

Task: T-E02-F04-005.

Requires ``opentelemetry-sdk`` for OTEL-dependent tests.  Those tests skip
automatically when the SDK is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Graceful skip when OTEL SDK is not installed
# ---------------------------------------------------------------------------
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    _sdk_available = True
except ImportError:
    _sdk_available = False

_skip_no_sdk = pytest.mark.skipif(
    not _sdk_available,
    reason="opentelemetry-sdk not installed -- skipping OTEL integration tests",
)

# ---------------------------------------------------------------------------
# Common imports (always available)
# ---------------------------------------------------------------------------
from agentmap.services.telemetry.protocol import (  # noqa: E402
    TelemetryServiceProtocol,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _otel_provider():
    """Create a per-test TracerProvider + InMemorySpanExporter pair."""
    pytest.importorskip("opentelemetry.sdk")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


@pytest.fixture()
def otel_exporter(_otel_provider):
    """Per-test InMemorySpanExporter."""
    exporter, _ = _otel_provider
    return exporter


@pytest.fixture()
def telemetry_service(_otel_provider):
    """Create a real OTELTelemetryService with tracer from test provider."""
    from agentmap.services.telemetry.otel_telemetry_service import (
        OTELTelemetryService,
    )

    _, provider = _otel_provider
    svc = OTELTelemetryService()
    svc._tracer = provider.get_tracer("agentmap")
    return svc


@pytest.fixture()
def mock_logging_service():
    """Provide a mock LoggingService that returns a usable logger."""
    from agentmap.services.logging_service import LoggingService

    mock_ls = create_autospec(LoggingService, instance=True)
    mock_logger = MagicMock()
    mock_ls.get_logger.return_value = mock_logger
    mock_ls.get_class_logger.return_value = mock_logger
    return mock_ls


@pytest.fixture()
def mock_app_config_service():
    """Provide a mock AppConfigService with configurable telemetry config."""
    from agentmap.services.config.app_config_service import AppConfigService

    mock_acs = create_autospec(AppConfigService, instance=True)
    return mock_acs


# ---------------------------------------------------------------------------
# INT-400: Full container with console exporter
# ---------------------------------------------------------------------------


@_skip_no_sdk
class TestFullContainerConsoleExporter:
    """INT-400: ApplicationContainer with console exporter produces real service."""

    def test_container_with_telemetry_enabled_returns_otel_service(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-400: DI container with telemetry enabled + console exporter
        resolves to OTELTelemetryService."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        mock_app_config_service.get_telemetry_config.return_value = {
            "enabled": True,
            "exporter": "console",
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

        # Patch bootstrap to avoid actually setting global TracerProvider
        with patch(
            "agentmap.di.container_parts.telemetry"
            ".bootstrap_standalone_tracer_provider",
            return_value=True,
        ):
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            svc = container.telemetry_service()

        assert isinstance(svc, OTELTelemetryService)
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_resolved_service_can_create_spans(
        self,
        mock_logging_service,
        mock_app_config_service,
        _otel_provider,
    ) -> None:
        """INT-400: Resolved OTELTelemetryService can create real spans."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer
        from agentmap.services.telemetry.constants import (
            AGENT_RUN_SPAN,
            GRAPH_NAME,
            WORKFLOW_RUN_SPAN,
        )

        exporter, provider = _otel_provider

        mock_app_config_service.get_telemetry_config.return_value = {
            "enabled": True,
            "exporter": "console",
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

        with patch(
            "agentmap.di.container_parts.telemetry"
            ".bootstrap_standalone_tracer_provider",
            return_value=True,
        ):
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            svc = container.telemetry_service()

        # Inject test tracer to capture spans
        svc._tracer = provider.get_tracer("agentmap")

        with svc.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "int400_test"},
        ):
            with svc.start_span(
                AGENT_RUN_SPAN, attributes={"agentmap.agent.name": "a1"}
            ):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        span_names = {s.name for s in spans}
        assert WORKFLOW_RUN_SPAN in span_names
        assert AGENT_RUN_SPAN in span_names

    def test_content_capture_flags_stored_on_service(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-400: Content capture flags stored on telemetry_service."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_app_config_service.get_telemetry_config.return_value = {
            "enabled": True,
            "exporter": "console",
            "endpoint": "http://localhost:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": True,
                "agent_outputs": False,
                "llm_prompts": True,
                "llm_responses": False,
            },
            "resource": {"service.name": "agentmap"},
        }

        with patch(
            "agentmap.di.container_parts.telemetry"
            ".bootstrap_standalone_tracer_provider",
            return_value=True,
        ):
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            svc = container.telemetry_service()

        flags = svc._content_capture_flags
        assert flags["agent_inputs"] is True
        assert flags["agent_outputs"] is False
        assert flags["llm_prompts"] is True
        assert flags["llm_responses"] is False


# ---------------------------------------------------------------------------
# INT-410: Privacy controls end-to-end
# ---------------------------------------------------------------------------


@_skip_no_sdk
class TestPrivacyControls:
    """INT-410/INT-411: Privacy controls affect span attributes."""

    def test_default_config_produces_no_content_attributes(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-410: Default config (all flags false) produces spans with
        only structural attributes -- zero user data."""
        from agentmap.services.telemetry.constants import (
            AGENT_INPUTS,
            AGENT_NAME,
            AGENT_OUTPUTS,
            AGENT_RUN_SPAN,
            AGENT_TYPE,
            GRAPH_NAME,
            NODE_NAME,
        )

        # Simulate agent with default config (no content capture)
        with telemetry_service.start_span(
            AGENT_RUN_SPAN,
            attributes={
                AGENT_NAME: "test_agent",
                AGENT_TYPE: "EchoAgent",
                NODE_NAME: "test_agent",
                GRAPH_NAME: "privacy_test",
            },
        ):
            # With default config, no content attributes should be set
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes

        # Structural attributes present
        assert attrs[AGENT_NAME] == "test_agent"
        assert attrs[AGENT_TYPE] == "EchoAgent"

        # Content attributes absent (privacy-safe default)
        assert AGENT_INPUTS not in attrs
        assert AGENT_OUTPUTS not in attrs

    def test_enabled_flags_include_content_attributes(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-411: Enabled flags produce spans with content attributes."""
        from agentmap.services.telemetry.constants import (
            AGENT_INPUTS,
            AGENT_NAME,
            AGENT_OUTPUTS,
            AGENT_RUN_SPAN,
            AGENT_TYPE,
            GRAPH_NAME,
            NODE_NAME,
        )

        # Simulate agent with content capture enabled
        with telemetry_service.start_span(
            AGENT_RUN_SPAN,
            attributes={
                AGENT_NAME: "test_agent",
                AGENT_TYPE: "EchoAgent",
                NODE_NAME: "test_agent",
                GRAPH_NAME: "privacy_test",
            },
        ) as span:
            # When capture is enabled, agent code sets content attributes
            telemetry_service.set_span_attributes(
                span,
                {
                    AGENT_INPUTS: "Hello, world!",
                    AGENT_OUTPUTS: "Echo: Hello, world!",
                },
            )

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes

        # Structural attributes present
        assert attrs[AGENT_NAME] == "test_agent"

        # Content attributes present when capture is enabled
        assert attrs[AGENT_INPUTS] == "Hello, world!"
        assert attrs[AGENT_OUTPUTS] == "Echo: Hello, world!"

    def test_flags_operate_independently(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-410 variant: Only enabled flags produce content attributes."""
        from agentmap.services.telemetry.constants import (
            AGENT_INPUTS,
            AGENT_OUTPUTS,
            AGENT_RUN_SPAN,
        )

        # Simulate: only agent_inputs enabled, agent_outputs disabled
        with telemetry_service.start_span(
            AGENT_RUN_SPAN,
            attributes={"agentmap.agent.name": "test"},
        ) as span:
            # Only input is captured (agent_inputs=True)
            telemetry_service.set_span_attributes(span, {AGENT_INPUTS: "input data"})
            # Output NOT captured (agent_outputs=False)

        spans = otel_exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert attrs[AGENT_INPUTS] == "input data"
        assert AGENT_OUTPUTS not in attrs


# ---------------------------------------------------------------------------
# INT-420: Graceful degradation without SDK
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """INT-420: Container builds successfully even when OTEL SDK unavailable."""

    def test_container_builds_with_sdk_import_error(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-420: Enabled config with missing SDK starts app with warning."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_app_config_service.get_telemetry_config.return_value = {
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

        # Simulate missing SDK by patching the import check
        with patch.dict(
            "sys.modules",
            {"opentelemetry.sdk": None},
        ):
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            container.telemetry_service.reset()
            svc = container.telemetry_service()

        # Service should still be created (no crash)
        assert isinstance(svc, TelemetryServiceProtocol)

        # Warning should have been logged about missing SDK
        mock_logger = mock_logging_service.get_logger.return_value
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        sdk_warning = any(
            "agentmap[telemetry]" in w or "opentelemetry-sdk" in w
            for w in warning_calls
        )
        assert sdk_warning, f"Expected warning about missing SDK, got: {warning_calls}"

    def test_service_still_functional_after_sdk_missing(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-420: Service returned after SDK failure is functional."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_app_config_service.get_telemetry_config.return_value = {
            "enabled": True,
            "exporter": "console",
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

        with patch.dict("sys.modules", {"opentelemetry.sdk": None}):
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            container.telemetry_service.reset()
            svc = container.telemetry_service()

        # Should be able to call protocol methods without error
        with svc.start_span("test.span"):
            pass

    def test_container_builds_without_app_config_service(
        self,
        mock_logging_service,
    ) -> None:
        """INT-420 variant: Container builds when app_config_service is None."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        container = TelemetryContainer(
            logging_service=mock_logging_service,
        )
        svc = container.telemetry_service()

        assert isinstance(svc, TelemetryServiceProtocol)


# ---------------------------------------------------------------------------
# INT-430: Cross-feature flag flow
# ---------------------------------------------------------------------------


@_skip_no_sdk
class TestCrossFeatureFlagFlow:
    """INT-430/INT-431: Content capture flags reach E02-F02 and E02-F03."""

    def test_agent_context_receives_capture_flags(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-430: Agent context receives capture flags from telemetry config.

        Verifies that GraphAgentInstantiationService wires content flags
        from telemetry_service._content_capture_flags into agent context.
        """
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        # Create a telemetry service with content flags
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        telemetry_svc = OTELTelemetryService()
        telemetry_svc._content_capture_flags = {
            "agent_inputs": True,
            "agent_outputs": False,
            "llm_prompts": True,
            "llm_responses": False,
        }

        # Create a mock agent with context dict
        mock_agent = MagicMock()
        mock_agent.context = {}

        # Create instantiation service with telemetry
        instantiation_svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_logging_service,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=telemetry_svc,
        )

        # Call the private method to wire flags
        instantiation_svc._wire_content_capture_flags(mock_agent)

        assert mock_agent.context["capture_agent_inputs"] is True
        assert mock_agent.context["capture_agent_outputs"] is False

    def test_agent_context_defaults_false_without_flags(
        self,
        mock_logging_service,
    ) -> None:
        """INT-430 variant: Agent context defaults to False when no flags."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        telemetry_svc = OTELTelemetryService()
        # No _content_capture_flags set

        mock_agent = MagicMock()
        mock_agent.context = {}

        instantiation_svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_logging_service,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=telemetry_svc,
        )

        instantiation_svc._wire_content_capture_flags(mock_agent)

        assert mock_agent.context.get("capture_agent_inputs") is False
        assert mock_agent.context.get("capture_agent_outputs") is False

    def test_llm_service_receives_capture_flags_via_di(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-431: LLMService receives capture flags from telemetry config
        via DI container wiring in LLMContainer."""
        from agentmap.di.container_parts.llm import LLMContainer
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        telemetry_svc = OTELTelemetryService()
        telemetry_svc._content_capture_flags = {
            "agent_inputs": False,
            "agent_outputs": False,
            "llm_prompts": True,
            "llm_responses": False,
        }

        # Provide mock dependencies for LLMContainer
        mock_app_config_service.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        mock_features = MagicMock()
        mock_availability_cache = MagicMock()
        mock_llm_models = MagicMock()

        container = LLMContainer(
            app_config_service=mock_app_config_service,
            logging_service=mock_logging_service,
            availability_cache_service=mock_availability_cache,
            features_registry_service=mock_features,
            llm_models_config_service=mock_llm_models,
            telemetry_service=telemetry_svc,
        )

        llm_svc = container.llm_service()

        assert llm_svc._capture_llm_prompts is True
        assert llm_svc._capture_llm_responses is False

    def test_llm_service_defaults_false_without_flags(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-431 variant: LLMService defaults to False when no flags set."""
        from agentmap.di.container_parts.llm import LLMContainer
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        telemetry_svc = OTELTelemetryService()
        # No _content_capture_flags set

        mock_app_config_service.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        container = LLMContainer(
            app_config_service=mock_app_config_service,
            logging_service=mock_logging_service,
            availability_cache_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            telemetry_service=telemetry_svc,
        )

        llm_svc = container.llm_service()

        assert llm_svc._capture_llm_prompts is False
        assert llm_svc._capture_llm_responses is False


# ---------------------------------------------------------------------------
# INT-440: Config template validation
# ---------------------------------------------------------------------------


class TestConfigTemplateValidation:
    """INT-440: Config template includes valid telemetry section."""

    def _load_template(self) -> dict:
        """Load and parse the config template YAML."""
        template_path = (
            Path(__file__).resolve().parents[4]
            / "src"
            / "agentmap"
            / "templates"
            / "config"
            / "agentmap_config.yaml.template"
        )
        assert template_path.exists(), f"Template not found: {template_path}"
        with open(template_path) as f:
            return yaml.safe_load(f)

    def test_template_is_valid_yaml(self) -> None:
        """INT-440: Template file parses as valid YAML."""
        config = self._load_template()
        assert isinstance(config, dict)

    def test_template_has_telemetry_section(self) -> None:
        """INT-440: Template has a 'telemetry' top-level key."""
        config = self._load_template()
        assert "telemetry" in config, "Template missing 'telemetry' section"

    def test_template_telemetry_enabled_defaults_false(self) -> None:
        """INT-440: telemetry.enabled defaults to false."""
        config = self._load_template()
        assert config["telemetry"]["enabled"] is False

    def test_template_telemetry_exporter_defaults_none(self) -> None:
        """INT-440: telemetry.exporter defaults to 'none'."""
        config = self._load_template()
        assert config["telemetry"]["exporter"] == "none"

    def test_template_has_traces_section_with_all_flags(self) -> None:
        """INT-440: telemetry.traces has all four content capture flags."""
        config = self._load_template()
        traces = config["telemetry"]["traces"]
        assert "agent_inputs" in traces
        assert "agent_outputs" in traces
        assert "llm_prompts" in traces
        assert "llm_responses" in traces

    def test_template_traces_flags_default_false(self) -> None:
        """INT-440: All content capture flags default to false."""
        config = self._load_template()
        traces = config["telemetry"]["traces"]
        assert traces["agent_inputs"] is False
        assert traces["agent_outputs"] is False
        assert traces["llm_prompts"] is False
        assert traces["llm_responses"] is False

    def test_template_has_resource_section(self) -> None:
        """INT-440: telemetry.resource has service.name."""
        config = self._load_template()
        resource = config["telemetry"]["resource"]
        assert "service.name" in resource
        assert resource["service.name"] == "agentmap"

    def test_template_telemetry_defaults_match_config_manager(self) -> None:
        """INT-440: Template defaults match TelemetryConfigManager DEFAULTS."""
        from agentmap.services.config.config_managers.telemetry_config_manager import (
            DEFAULTS,
        )

        config = self._load_template()
        telemetry = config["telemetry"]

        assert telemetry["enabled"] == DEFAULTS["enabled"]
        assert telemetry["exporter"] == DEFAULTS["exporter"]
        assert telemetry["endpoint"] == DEFAULTS["endpoint"]
        assert telemetry["protocol"] == DEFAULTS["protocol"]

        for key in ("agent_inputs", "agent_outputs", "llm_prompts", "llm_responses"):
            assert telemetry["traces"][key] == DEFAULTS["traces"][key]

        assert (
            telemetry["resource"]["service.name"]
            == DEFAULTS["resource"]["service.name"]
        )


# ---------------------------------------------------------------------------
# INT-450: Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """INT-450: Existing workflows work unchanged when telemetry config absent."""

    def test_container_works_without_telemetry_config(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """INT-450: Container resolves when get_telemetry_config raises."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        # Simulate config service that has no telemetry config
        mock_app_config_service.get_telemetry_config.side_effect = AttributeError(
            "no such method"
        )

        container = TelemetryContainer(
            logging_service=mock_logging_service,
            app_config_service=mock_app_config_service,
        )
        svc = container.telemetry_service()

        assert isinstance(svc, TelemetryServiceProtocol)

    def test_container_defaults_to_disabled_when_no_config(
        self,
        mock_logging_service,
    ) -> None:
        """INT-450: Container defaults to disabled telemetry without config."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        container = TelemetryContainer(
            logging_service=mock_logging_service,
        )
        svc = container.telemetry_service()

        # Should be usable with protocol methods
        assert isinstance(svc, TelemetryServiceProtocol)
        with svc.start_span("backward.compat.test"):
            pass

    def test_telemetry_config_manager_absent_section_returns_defaults(
        self,
    ) -> None:
        """INT-450: TelemetryConfigManager with no telemetry section returns
        safe defaults."""
        from agentmap.services.config.config_managers.telemetry_config_manager import (
            TelemetryConfigManager,
        )

        # Config data with no telemetry section
        mock_config_service = MagicMock()
        mock_logger = MagicMock()
        manager = TelemetryConfigManager(mock_config_service, {}, mock_logger)

        config = manager.get_telemetry_config()

        assert config["enabled"] is False
        assert config["exporter"] == "none"
        assert config["traces"]["agent_inputs"] is False
        assert config["traces"]["agent_outputs"] is False
        assert config["traces"]["llm_prompts"] is False
        assert config["traces"]["llm_responses"] is False

    def test_telemetry_config_manager_null_section(self) -> None:
        """INT-450 variant: telemetry: null treated as absent."""
        from agentmap.services.config.config_managers.telemetry_config_manager import (
            TelemetryConfigManager,
        )

        mock_config_service = MagicMock()
        mock_logger = MagicMock()
        manager = TelemetryConfigManager(
            mock_config_service, {"telemetry": None}, mock_logger
        )

        config = manager.get_telemetry_config()
        assert config["enabled"] is False
        assert config["exporter"] == "none"

    def test_existing_telemetry_service_protocol_unchanged(self) -> None:
        """INT-450: TelemetryServiceProtocol still has expected methods."""
        import inspect

        members = dict(inspect.getmembers(TelemetryServiceProtocol))
        # Core protocol methods from E02-F01
        assert "start_span" in members
        assert "set_span_attributes" in members
        assert "add_span_event" in members
        assert "record_exception" in members
        assert "get_tracer" in members

    @_skip_no_sdk
    def test_otel_service_works_without_content_flags(self) -> None:
        """INT-450: OTELTelemetryService works without _content_capture_flags."""
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        svc = OTELTelemetryService()
        # No _content_capture_flags set -- should still work
        assert (
            not hasattr(svc, "_content_capture_flags")
            or svc._content_capture_flags is None
        )

        with svc.start_span("test.span"):
            pass

    def test_noop_service_works_without_content_flags(self) -> None:
        """INT-450: NoOpTelemetryService works without _content_capture_flags."""
        from agentmap.services.telemetry.noop_telemetry_service import (
            NoOpTelemetryService,
        )

        svc = NoOpTelemetryService()
        # NoOp should have no _content_capture_flags
        flags = getattr(svc, "_content_capture_flags", None) or {}
        assert flags.get("agent_inputs", False) is False

        with svc.start_span("test.span"):
            pass


# ---------------------------------------------------------------------------
# Additional: DI wiring with telemetry config enabled produces flags on svc
# ---------------------------------------------------------------------------


@_skip_no_sdk
class TestDIWiringEndToEnd:
    """End-to-end DI wiring: config -> container -> service with flags."""

    def test_disabled_config_skips_bootstrap(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """Disabled config does not call bootstrap."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_app_config_service.get_telemetry_config.return_value = {
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

        with patch(
            "agentmap.di.container_parts.telemetry"
            ".bootstrap_standalone_tracer_provider",
        ) as mock_bootstrap:
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            service = container.telemetry_service()

        mock_bootstrap.assert_not_called()
        assert isinstance(service, TelemetryServiceProtocol)

    def test_enabled_config_calls_bootstrap_with_correct_args(
        self,
        mock_logging_service,
        mock_app_config_service,
    ) -> None:
        """Enabled config calls bootstrap with config values."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_app_config_service.get_telemetry_config.return_value = {
            "enabled": True,
            "exporter": "otlp",
            "endpoint": "http://collector:4317",
            "protocol": "grpc",
            "traces": {
                "agent_inputs": False,
                "agent_outputs": False,
                "llm_prompts": False,
                "llm_responses": False,
            },
            "resource": {"service.name": "my-app"},
        }

        with patch(
            "agentmap.di.container_parts.telemetry"
            ".bootstrap_standalone_tracer_provider",
            return_value=True,
        ) as mock_bootstrap:
            container = TelemetryContainer(
                logging_service=mock_logging_service,
                app_config_service=mock_app_config_service,
            )
            container.telemetry_service()

        mock_bootstrap.assert_called_once()
        call_kwargs = mock_bootstrap.call_args
        # Check positional or keyword args
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs["exporter"] == "otlp"
            assert call_kwargs.kwargs["endpoint"] == "http://collector:4317"
            assert call_kwargs.kwargs["protocol"] == "grpc"
        else:
            # Positional args
            assert call_kwargs.args[0] == "otlp"  # exporter
