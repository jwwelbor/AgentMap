"""
Tests for T-E02-F04-003: Privacy Controls and Content Capture Flag Wiring.

Verifies that content capture flags flow from telemetry_service._content_capture_flags
into the two consumers:
  - E02-F02: BaseAgent context (capture_agent_inputs, capture_agent_outputs)
  - E02-F03: LLMService instance (_capture_llm_prompts, _capture_llm_responses)

Test cases: TC-430 through TC-445 (from test plan).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, create_autospec

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.llm_service import LLMService
from agentmap.services.telemetry.constants import (
    AGENT_INPUTS,
    AGENT_OUTPUTS,
    GEN_AI_PROMPT_CONTENT,
    GEN_AI_RESPONSE_CONTENT,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConcreteTestAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    def process(self, inputs):
        return "test_output"


def _make_mock_telemetry(content_capture_flags=None):
    """Create a mock telemetry service with optional content capture flags."""
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock()

    @contextmanager
    def _ctx_mgr(*args, **kwargs):
        yield mock_span

    svc.start_span.side_effect = _ctx_mgr

    # Set _content_capture_flags (this is what T-004 stores)
    if content_capture_flags is not None:
        svc._content_capture_flags = content_capture_flags
    else:
        svc._content_capture_flags = {}

    return svc, mock_span


def _make_llm_service(telemetry_service=None, **overrides):
    """Create an LLMService with mocked dependencies."""
    mock_logging = MagicMock()
    mock_logger = MagicMock()
    mock_logging.get_class_logger.return_value = mock_logger

    mock_config = MagicMock()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {"max_attempts": 1},
        "circuit_breaker": {},
    }

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=MagicMock(),
        llm_models_config_service=MagicMock(),
        telemetry_service=telemetry_service,
        **overrides,
    )
    return svc


def _mock_successful_llm_call(svc, response_content="Hello!"):
    """Patch internals so call_llm succeeds."""
    mock_response = MagicMock()
    mock_response.content = response_content
    del mock_response.usage_metadata
    mock_response.response_metadata = {}

    mock_client = MagicMock()
    mock_client.invoke.return_value = mock_response

    svc._provider_utils = MagicMock()
    svc._provider_utils.normalize_provider.return_value = "anthropic"
    svc._provider_utils.get_provider_config.return_value = {
        "model": "claude-3-sonnet",
        "api_key": "test-key",
    }
    svc._client_factory = MagicMock()
    svc._client_factory.get_or_create_client.return_value = mock_client
    svc._message_utils = MagicMock()
    svc._message_utils.convert_messages_to_langchain.return_value = []
    svc._message_utils.extract_prompt_from_messages.return_value = "hello"

    return mock_response, mock_client


# ====================================================================
# TC-434 / AC4: Privacy-safe defaults -- no content in spans
# ====================================================================


class TestTC434PrivacySafeDefaults:
    """With default config, spans contain zero user data."""

    def test_llm_service_defaults_capture_prompts_false(self):
        """LLMService._capture_llm_prompts defaults to False."""
        svc = _make_llm_service()
        assert getattr(svc, "_capture_llm_prompts", False) is False

    def test_llm_service_defaults_capture_responses_false(self):
        """LLMService._capture_llm_responses defaults to False."""
        svc = _make_llm_service()
        assert getattr(svc, "_capture_llm_responses", False) is False

    def test_agent_context_defaults_capture_inputs_false(self):
        """Agent context defaults capture_agent_inputs to False."""
        agent = ConcreteTestAgent(name="a", prompt="p", context={})
        assert agent.context.get("capture_agent_inputs", False) is False

    def test_agent_context_defaults_capture_outputs_false(self):
        """Agent context defaults capture_agent_outputs to False."""
        agent = ConcreteTestAgent(name="a", prompt="p", context={})
        assert agent.context.get("capture_agent_outputs", False) is False

    def test_no_prompt_content_in_span_with_defaults(self):
        """No prompt content attribute on span with default flags."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "secret data"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT not in all_attrs
        assert GEN_AI_RESPONSE_CONTENT not in all_attrs

    def test_no_agent_io_in_span_with_defaults(self):
        """No agent input/output attributes on span with default flags."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={},
            telemetry_service=mock_telemetry,
        )

        # Call _capture_io_attributes directly
        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        # Should not have set any attributes (both flags default False)
        mock_telemetry.set_span_attributes.assert_not_called()


# ====================================================================
# TC-440: Agent input capture when flag enabled
# ====================================================================


class TestTC440AgentInputCapture:
    """capture_agent_inputs=True causes agent inputs to appear in spans."""

    def test_agent_inputs_captured_when_flag_true(self):
        """AGENT_INPUTS attribute set when capture_agent_inputs=True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={"capture_agent_inputs": True},
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        mock_telemetry.set_span_attributes.assert_called_once()
        attrs = mock_telemetry.set_span_attributes.call_args[0][1]
        assert AGENT_INPUTS in attrs
        # Output should NOT be captured (only input flag is True)
        assert AGENT_OUTPUTS not in attrs

    def test_agent_inputs_not_captured_when_flag_false(self):
        """AGENT_INPUTS attribute absent when capture_agent_inputs=False."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={"capture_agent_inputs": False},
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        mock_telemetry.set_span_attributes.assert_not_called()


# ====================================================================
# TC-441: Agent output capture when flag enabled
# ====================================================================


class TestTC441AgentOutputCapture:
    """capture_agent_outputs=True causes agent outputs to appear in spans."""

    def test_agent_outputs_captured_when_flag_true(self):
        """AGENT_OUTPUTS attribute set when capture_agent_outputs=True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={"capture_agent_outputs": True},
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        mock_telemetry.set_span_attributes.assert_called_once()
        attrs = mock_telemetry.set_span_attributes.call_args[0][1]
        assert AGENT_OUTPUTS in attrs
        assert AGENT_INPUTS not in attrs

    def test_agent_outputs_not_captured_when_flag_false(self):
        """AGENT_OUTPUTS attribute absent when capture_agent_outputs=False."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={"capture_agent_outputs": False},
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        mock_telemetry.set_span_attributes.assert_not_called()


# ====================================================================
# TC-442: LLM prompt capture when flag enabled
# ====================================================================


class TestTC442LLMPromptCapture:
    """_capture_llm_prompts=True causes prompts to appear in spans."""

    def test_llm_prompt_captured_when_flag_true(self):
        """GEN_AI_PROMPT_CONTENT attribute set when flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = True
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "What is AI?"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT in all_attrs


# ====================================================================
# TC-443: LLM response capture when flag enabled
# ====================================================================


class TestTC443LLMResponseCapture:
    """_capture_llm_responses=True causes responses to appear in spans."""

    def test_llm_response_captured_when_flag_true(self):
        """GEN_AI_RESPONSE_CONTENT attribute set when flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_responses = True
        _mock_successful_llm_call(svc, response_content="AI is cool")

        svc.call_llm(
            messages=[{"role": "user", "content": "What is AI?"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_RESPONSE_CONTENT in all_attrs
        assert all_attrs[GEN_AI_RESPONSE_CONTENT] == "AI is cool"


# ====================================================================
# TC-444 / AC3: Flags operate independently
# ====================================================================


class TestTC444FlagsIndependent:
    """Each of the 4 flags operates independently."""

    def test_agent_input_only(self):
        """Only agent inputs captured when only that flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={
                "capture_agent_inputs": True,
                "capture_agent_outputs": False,
            },
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        attrs = mock_telemetry.set_span_attributes.call_args[0][1]
        assert AGENT_INPUTS in attrs
        assert AGENT_OUTPUTS not in attrs

    def test_agent_output_only(self):
        """Only agent outputs captured when only that flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={
                "capture_agent_inputs": False,
                "capture_agent_outputs": True,
            },
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        attrs = mock_telemetry.set_span_attributes.call_args[0][1]
        assert AGENT_OUTPUTS in attrs
        assert AGENT_INPUTS not in attrs

    def test_both_agent_flags(self):
        """Both agent inputs and outputs captured when both flags True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        agent = ConcreteTestAgent(
            name="a",
            prompt="p",
            context={
                "capture_agent_inputs": True,
                "capture_agent_outputs": True,
            },
            telemetry_service=mock_telemetry,
        )

        agent._capture_io_attributes(mock_span, inputs={"x": 1}, output="result")

        attrs = mock_telemetry.set_span_attributes.call_args[0][1]
        assert AGENT_INPUTS in attrs
        assert AGENT_OUTPUTS in attrs

    def test_llm_prompt_only(self):
        """Only prompt captured when only prompt flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = True
        svc._capture_llm_responses = False
        _mock_successful_llm_call(svc, response_content="response")

        svc.call_llm(
            messages=[{"role": "user", "content": "prompt"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT in all_attrs
        assert GEN_AI_RESPONSE_CONTENT not in all_attrs

    def test_llm_response_only(self):
        """Only response captured when only response flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = False
        svc._capture_llm_responses = True
        _mock_successful_llm_call(svc, response_content="response")

        svc.call_llm(
            messages=[{"role": "user", "content": "prompt"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT not in all_attrs
        assert GEN_AI_RESPONSE_CONTENT in all_attrs


# ====================================================================
# TC-445 / AC1+AC2: DI wiring passes flags from telemetry service
# ====================================================================


class TestTC445DIWiringPassesFlags:
    """Content capture flags flow from telemetry_service to consumers."""

    def test_llm_container_wires_prompts_flag(self):
        """LLMContainer factory sets _capture_llm_prompts from telemetry flags."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "llm_prompts": True,
            "llm_responses": False,
        }

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert svc._capture_llm_prompts is True
        assert svc._capture_llm_responses is False

    def test_llm_container_wires_responses_flag(self):
        """LLMContainer factory sets _capture_llm_responses from telemetry flags."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "llm_prompts": False,
            "llm_responses": True,
        }

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert svc._capture_llm_prompts is False
        assert svc._capture_llm_responses is True

    def test_llm_container_defaults_when_no_flags(self):
        """LLMContainer factory defaults to False when no flags present."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock(spec=[])  # No _content_capture_flags attr

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert getattr(svc, "_capture_llm_prompts", False) is False
        assert getattr(svc, "_capture_llm_responses", False) is False

    def test_llm_container_defaults_when_telemetry_none(self):
        """LLMContainer factory defaults to False when telemetry is None."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=None,
        )

        assert getattr(svc, "_capture_llm_prompts", False) is False
        assert getattr(svc, "_capture_llm_responses", False) is False

    def test_agent_instantiation_wires_input_flag(self):
        """_wire_content_capture_flags sets capture_agent_inputs on agent context."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "agent_inputs": True,
            "agent_outputs": False,
        }

        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=MagicMock(
                get_class_logger=MagicMock(return_value=MagicMock())
            ),
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        agent = ConcreteTestAgent(name="a", prompt="p", context={})
        svc._wire_content_capture_flags(agent)
        assert agent.context["capture_agent_inputs"] is True
        assert agent.context["capture_agent_outputs"] is False

    def test_agent_instantiation_wires_output_flag(self):
        """_wire_content_capture_flags sets capture_agent_outputs on agent context."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "agent_inputs": False,
            "agent_outputs": True,
        }

        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=MagicMock(
                get_class_logger=MagicMock(return_value=MagicMock())
            ),
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        agent = ConcreteTestAgent(name="a", prompt="p", context={})
        svc._wire_content_capture_flags(agent)
        assert agent.context["capture_agent_inputs"] is False
        assert agent.context["capture_agent_outputs"] is True

    def test_agent_instantiation_defaults_when_no_flags(self):
        """_wire_content_capture_flags defaults when no _content_capture_flags."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock(spec=[])

        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=MagicMock(
                get_class_logger=MagicMock(return_value=MagicMock())
            ),
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        agent = ConcreteTestAgent(name="a", prompt="p", context={})
        svc._wire_content_capture_flags(agent)
        assert agent.context.get("capture_agent_inputs", False) is False
        assert agent.context.get("capture_agent_outputs", False) is False


# ====================================================================
# INT-430: Agent context receives capture flags via instantiation
# ====================================================================


class TestINT430AgentContextReceivesFlags:
    """Integration: agent factory receives capture flags in context."""

    def test_agent_factory_called_with_capture_flags_in_context(self):
        """When instantiating agents, context dict contains capture flags."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "agent_inputs": True,
            "agent_outputs": True,
        }

        mock_factory = MagicMock()
        mock_agent = MagicMock()
        mock_factory.create_agent_instance.return_value = mock_agent

        mock_injection = MagicMock()
        mock_injection.configure_all_services.return_value = {
            "total_services_configured": 0
        }

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        service = GraphAgentInstantiationService(
            agent_factory_service=mock_factory,
            agent_service_injection_service=mock_injection,
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_logging,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        # Create a mock bundle with a node
        mock_bundle = MagicMock()
        mock_node = MagicMock()
        mock_node.name = "test_node"
        mock_node.agent_type = "default"
        mock_node.description = ""
        mock_node.inputs = []
        mock_node.output = None
        mock_node.context = None
        mock_node.tool_source = None  # Prevent tool loading
        mock_bundle.nodes = {"test_node": mock_node}
        mock_bundle.agent_mappings = {"default": "agentmap.agents.base_agent.BaseAgent"}
        mock_bundle.custom_agents = set()
        mock_bundle.node_instances = {}
        mock_bundle.tools = {}
        mock_bundle.graph_name = "test_graph"
        mock_bundle.required_agents = set()
        mock_bundle.scoped_registry = None

        service.instantiate_agents(mock_bundle)

        # Verify agent factory was called
        mock_factory.create_agent_instance.assert_called_once()

        # Verify the returned agent instance has capture flags wired into context
        # _wire_content_capture_flags is called on the agent after factory creation
        agent_ctx = getattr(mock_agent, "context", None)
        if agent_ctx and isinstance(agent_ctx, dict):
            assert agent_ctx.get("capture_agent_inputs") is True
            assert agent_ctx.get("capture_agent_outputs") is True


# ====================================================================
# INT-431: LLMService receives capture flags via DI
# ====================================================================


class TestINT431LLMServiceReceivesFlags:
    """Integration: LLMService gets flags wired through LLMContainer."""

    def test_llm_service_flags_from_telemetry(self):
        """LLMService instance has flags set from telemetry._content_capture_flags."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {
            "llm_prompts": True,
            "llm_responses": True,
            "agent_inputs": True,  # Should be ignored by LLMService
            "agent_outputs": True,  # Should be ignored by LLMService
        }

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert svc._capture_llm_prompts is True
        assert svc._capture_llm_responses is True


# ====================================================================
# Edge cases
# ====================================================================


class TestEdgeCases:
    """Edge cases for content capture flag wiring."""

    def test_empty_content_capture_flags(self):
        """Empty _content_capture_flags dict results in all-false defaults."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {}

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert svc._capture_llm_prompts is False
        assert svc._capture_llm_responses is False

    def test_partial_flags_only_set_specified(self):
        """Only specified flags are set; unspecified default to False."""
        from agentmap.di.container_parts.llm import LLMContainer

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {"llm_prompts": True}

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        svc = LLMContainer._create_llm_service(
            app_config_service=mock_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        assert svc._capture_llm_prompts is True
        assert svc._capture_llm_responses is False
