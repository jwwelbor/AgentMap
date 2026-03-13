"""
Tests for DI wiring of telemetry_service through the agent construction chain.

Covers task T-E02-F02-003: DI Wiring for Telemetry Service Injection.
Test cases: TC-142, TC-143, INT-130.

Tests verify:
- GraphAgentContainer declares telemetry_service dependency
- ApplicationContainer wires telemetry into graph_agent
- GraphAgentInstantiationService accepts and forwards telemetry
- AgentFactoryService forwards telemetry to constructor builder
- AgentConstructorBuilder conditionally injects telemetry
- Backward compatibility when telemetry_service is None
"""

import inspect
from unittest.mock import MagicMock, Mock, create_autospec, patch

import pytest

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.agent.agent_constructor_builder import AgentConstructorBuilder
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.logging_service import LoggingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ConcreteAgent(BaseAgent):
    """Agent with telemetry_service in __init__ (inherits from BaseAgent)."""

    def process(self, inputs):
        return "ok"


class _LegacyAgent:
    """Agent whose __init__ does NOT accept telemetry_service."""

    def __init__(self, name, prompt, context, logger=None):
        self.name = name
        self.prompt = prompt
        self.context = context

    def run(self, state):
        return state


def _mock_logging_service():
    mock_ls = create_autospec(LoggingService, instance=True)
    mock_logger = MagicMock()
    for method in ["debug", "info", "warning", "error", "trace"]:
        setattr(mock_logger, method, MagicMock())
    mock_ls.get_class_logger.return_value = mock_logger
    return mock_ls


# ===========================================================================
# AC1: GraphAgentContainer declares telemetry dependency
# ===========================================================================


class TestGraphAgentContainerTelemetryDependency:
    """AC1: GraphAgentContainer has telemetry_service Dependency provider."""

    def test_container_has_telemetry_service_dependency(self):
        """GraphAgentContainer declares telemetry_service as a Dependency provider."""
        from dependency_injector import providers

        from agentmap.di.container_parts.graph_agent import GraphAgentContainer

        assert hasattr(GraphAgentContainer, "telemetry_service")
        # It should be a Dependency provider
        assert isinstance(GraphAgentContainer.telemetry_service, providers.Dependency)

    def test_create_graph_agent_instantiation_service_accepts_telemetry(self):
        """_create_graph_agent_instantiation_service accepts telemetry_service param."""
        from agentmap.di.container_parts.graph_agent import GraphAgentContainer

        sig = inspect.signature(
            GraphAgentContainer._create_graph_agent_instantiation_service
        )
        param_names = list(sig.parameters.keys())
        assert "telemetry_service" in param_names


# ===========================================================================
# AC2: ApplicationContainer wires telemetry into graph_agent
# ===========================================================================


class TestApplicationContainerTelemetryWiring:
    """AC2: ApplicationContainer passes telemetry_service to _graph_agent."""

    def test_graph_agent_container_receives_telemetry_kwarg(self):
        """The _graph_agent Container provider includes telemetry_service."""
        import inspect as _inspect

        from agentmap.di import containers as containers_module

        # Verify the source code of containers.py includes the telemetry wiring
        # in the _graph_agent Container provider definition.
        source = _inspect.getsource(containers_module)
        # Look for telemetry_service=_expose(_telemetry, "telemetry_service")
        # in the _graph_agent provider block
        assert 'telemetry_service=_expose(_telemetry, "telemetry_service")' in source, (
            "telemetry_service wiring not found in _graph_agent Container provider "
            "in containers.py"
        )


# ===========================================================================
# AC3: GraphAgentInstantiationService accepts and forwards telemetry
# ===========================================================================


class TestGraphAgentInstantiationServiceTelemetry:
    """AC3: GraphAgentInstantiationService stores and forwards telemetry_service."""

    def test_init_accepts_telemetry_service(self):
        """__init__ accepts telemetry_service parameter."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        sig = inspect.signature(GraphAgentInstantiationService.__init__)
        param_names = list(sig.parameters.keys())
        assert "telemetry_service" in param_names

    def test_init_stores_telemetry_service(self):
        """telemetry_service is stored as self.telemetry_service."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock(name="telemetry_service")
        mock_ls = _mock_logging_service()

        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_ls,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            declaration_registry_service=None,
            telemetry_service=mock_telemetry,
        )

        assert svc.telemetry_service is mock_telemetry

    def test_init_defaults_telemetry_to_none(self):
        """telemetry_service defaults to None for backward compatibility."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_ls = _mock_logging_service()

        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_ls,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
        )

        assert svc.telemetry_service is None

    def test_instantiate_single_agent_forwards_telemetry(self):
        """_instantiate_single_agent passes telemetry_service to create_agent_instance."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_telemetry = MagicMock(name="telemetry_service")
        mock_factory = MagicMock()
        mock_factory.create_agent_instance.return_value = MagicMock()
        mock_ls = _mock_logging_service()
        mock_injection = MagicMock()
        mock_injection.configure_all_services.return_value = {
            "total_services_configured": 0
        }

        svc = GraphAgentInstantiationService(
            agent_factory_service=mock_factory,
            agent_service_injection_service=mock_injection,
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_ls,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )

        # Create mock node and bundle
        mock_node = MagicMock()
        mock_node.name = "test_node"
        mock_node.agent_type = "default"
        mock_bundle = MagicMock()
        mock_bundle.agent_mappings = {"default": "path.to.DefaultAgent"}
        mock_bundle.custom_agents = set()
        mock_bundle.tools = {}
        mock_bundle.node_instances = {}

        svc._instantiate_single_agent(
            bundle=mock_bundle,
            node_name="test_node",
            node=mock_node,
            graph_name="test_graph",
            node_definitions_registry={},
            execution_tracker=None,
        )

        # Verify telemetry_service was forwarded
        call_kwargs = mock_factory.create_agent_instance.call_args
        assert call_kwargs.kwargs.get("telemetry_service") is mock_telemetry or (
            "telemetry_service" in str(call_kwargs)
        )


# ===========================================================================
# AC4: AgentFactoryService forwards telemetry to constructor builder
# ===========================================================================


class TestAgentFactoryServiceTelemetryForwarding:
    """AC4: create_agent_instance accepts and forwards telemetry_service."""

    def test_create_agent_instance_accepts_telemetry_service(self):
        """create_agent_instance has telemetry_service parameter."""
        sig = inspect.signature(AgentFactoryService.create_agent_instance)
        param_names = list(sig.parameters.keys())
        assert "telemetry_service" in param_names

    def test_create_agent_instance_telemetry_defaults_to_none(self):
        """telemetry_service parameter defaults to None."""
        sig = inspect.signature(AgentFactoryService.create_agent_instance)
        param = sig.parameters["telemetry_service"]
        assert param.default is None

    def test_create_agent_instance_forwards_telemetry_to_builder(self):
        """telemetry_service is passed through to _builder.build_constructor_args."""
        mock_ls = _mock_logging_service()
        factory = AgentFactoryService(
            features_registry_service=MagicMock(),
            logging_service=mock_ls,
            custom_agent_loader=MagicMock(),
        )

        mock_telemetry = MagicMock(name="telemetry_service")
        mock_builder = MagicMock()
        mock_builder.build_constructor_args.return_value = {
            "name": "test",
            "prompt": "",
            "context": {},
        }
        factory._builder = mock_builder

        # Mock resolve_agent_class to return a simple class
        mock_agent_class = MagicMock()
        mock_agent_class.__name__ = "TestAgent"
        mock_instance = MagicMock()
        mock_instance.name = "test"
        mock_agent_class.return_value = mock_instance

        with patch.object(
            factory, "resolve_agent_class", return_value=mock_agent_class
        ):
            mock_node = MagicMock()
            mock_node.name = "test"
            mock_node.agent_type = "default"
            mock_node.context = {}

            factory.create_agent_instance(
                node=mock_node,
                graph_name="test_graph",
                agent_mappings={"default": "path.TestAgent"},
                telemetry_service=mock_telemetry,
            )

        # Verify builder received telemetry_service
        builder_call = mock_builder.build_constructor_args.call_args
        assert builder_call.kwargs.get("telemetry_service") is mock_telemetry


# ===========================================================================
# AC5: AgentConstructorBuilder conditionally injects telemetry
# ===========================================================================


class TestAgentConstructorBuilderTelemetryInjection:
    """AC5: build_constructor_args conditionally adds telemetry_service."""

    def setup_method(self):
        self.mock_ls = _mock_logging_service()
        self.builder = AgentConstructorBuilder(self.mock_ls)

    def _make_node(self, name="test_node"):
        node = MagicMock()
        node.name = name
        node.prompt = "test prompt"
        return node

    def test_build_constructor_args_accepts_telemetry_service(self):
        """build_constructor_args has telemetry_service parameter."""
        sig = inspect.signature(AgentConstructorBuilder.build_constructor_args)
        param_names = list(sig.parameters.keys())
        assert "telemetry_service" in param_names

    def test_telemetry_injected_when_agent_supports_it(self):
        """telemetry_service added to constructor_args when agent __init__ accepts it."""
        mock_telemetry = MagicMock(name="telemetry_service")

        args = self.builder.build_constructor_args(
            agent_class=_ConcreteAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=mock_telemetry,
        )

        assert "telemetry_service" in args
        assert args["telemetry_service"] is mock_telemetry

    def test_telemetry_not_injected_when_agent_lacks_param(self):
        """telemetry_service NOT added when agent __init__ does not accept it."""
        mock_telemetry = MagicMock(name="telemetry_service")

        args = self.builder.build_constructor_args(
            agent_class=_LegacyAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=mock_telemetry,
        )

        assert "telemetry_service" not in args

    def test_telemetry_not_injected_when_none(self):
        """telemetry_service NOT added when it is None (even if agent accepts it)."""
        args = self.builder.build_constructor_args(
            agent_class=_ConcreteAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=None,
        )

        assert "telemetry_service" not in args

    def test_telemetry_defaults_to_none_when_omitted(self):
        """Omitting telemetry_service does not break existing callers."""
        # This tests backward compatibility -- existing callers don't pass it
        args = self.builder.build_constructor_args(
            agent_class=_ConcreteAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
        )

        assert "telemetry_service" not in args


# ===========================================================================
# AC7: Backward compatibility preserved
# ===========================================================================


class TestBackwardCompatibility:
    """AC7: All new parameters default to None; existing callers unaffected."""

    def test_existing_factory_callers_work_without_telemetry(self):
        """Existing callers of create_agent_instance without telemetry still work."""
        mock_ls = _mock_logging_service()
        factory = AgentFactoryService(
            features_registry_service=MagicMock(),
            logging_service=mock_ls,
            custom_agent_loader=MagicMock(),
        )

        mock_node = MagicMock()
        mock_node.name = "test"
        mock_node.agent_type = "default"
        mock_node.prompt = "test"
        mock_node.inputs = []
        mock_node.output = "result"
        mock_node.description = ""
        mock_node.context = {}

        mock_agent_class = MagicMock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_instance = MagicMock()
        mock_instance.name = "test"
        mock_agent_class.return_value = mock_instance

        with patch.object(
            factory, "resolve_agent_class", return_value=mock_agent_class
        ):
            # Call WITHOUT telemetry_service -- should not raise
            result = factory.create_agent_instance(
                node=mock_node,
                graph_name="test_graph",
                agent_mappings={"default": "path.DefaultAgent"},
            )

        assert result.name == "test"

    def test_existing_builder_callers_work_without_telemetry(self):
        """Existing callers of build_constructor_args without telemetry still work."""
        mock_ls = _mock_logging_service()
        builder = AgentConstructorBuilder(mock_ls)

        node = MagicMock()
        node.name = "test"
        node.prompt = "test"

        # Call without telemetry_service
        args = builder.build_constructor_args(
            agent_class=_LegacyAgent,
            node=node,
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
        )

        assert "name" in args
        assert args["name"] == "test"

    def test_existing_instantiation_service_callers_work_without_telemetry(self):
        """Existing callers constructing GraphAgentInstantiationService without
        telemetry_service still work (defaults to None)."""
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        mock_ls = _mock_logging_service()

        # Construct without telemetry_service -- must not raise
        svc = GraphAgentInstantiationService(
            agent_factory_service=MagicMock(),
            agent_service_injection_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            logging_service=mock_ls,
            prompt_manager_service=MagicMock(),
            graph_bundle_service=MagicMock(),
        )

        assert svc.telemetry_service is None


# ===========================================================================
# AC8 (T-E02-F02-004): Constructor builder **kwargs agent receives telemetry
# ===========================================================================


class TestConstructorBuilderKwargsAgent:
    """AC8: Agent with **kwargs in __init__ receives telemetry_service.

    The AgentConstructorBuilder should detect ``**kwargs`` in an agent's
    ``__init__`` and inject ``telemetry_service`` through it.
    """

    def setup_method(self):
        self.mock_ls = _mock_logging_service()
        self.builder = AgentConstructorBuilder(self.mock_ls)

    def _make_node(self, name="test_node"):
        node = MagicMock()
        node.name = name
        node.prompt = "test prompt"
        return node

    def test_kwargs_agent_receives_telemetry_service(self):
        """Agent with **kwargs in __init__ receives telemetry_service through kwargs."""

        class KwargsAgent(BaseAgent):
            """Agent that accepts **kwargs in __init__."""

            def __init__(self, name, prompt, context=None, **kwargs):
                super().__init__(name=name, prompt=prompt, context=context, **kwargs)

            def process(self, inputs):
                return "ok"

        mock_telemetry = MagicMock(name="telemetry_service")

        args = self.builder.build_constructor_args(
            agent_class=KwargsAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=mock_telemetry,
        )

        assert (
            "telemetry_service" in args
        ), "Agent with **kwargs should receive telemetry_service"
        assert args["telemetry_service"] is mock_telemetry

    def test_kwargs_agent_without_telemetry_omits_it(self):
        """Agent with **kwargs but telemetry_service=None omits the key."""

        class KwargsAgent(BaseAgent):
            def __init__(self, name, prompt, context=None, **kwargs):
                super().__init__(name=name, prompt=prompt, context=context, **kwargs)

            def process(self, inputs):
                return "ok"

        args = self.builder.build_constructor_args(
            agent_class=KwargsAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=None,
        )

        assert "telemetry_service" not in args

    def test_kwargs_agent_actually_receives_telemetry_at_runtime(self):
        """End-to-end: KwargsAgent constructed with builder args receives telemetry."""

        class KwargsAgent(BaseAgent):
            def __init__(self, name, prompt, context=None, **kwargs):
                super().__init__(name=name, prompt=prompt, context=context, **kwargs)

            def process(self, inputs):
                return "ok"

        mock_telemetry = MagicMock(name="telemetry_service")

        args = self.builder.build_constructor_args(
            agent_class=KwargsAgent,
            node=self._make_node(),
            context={},
            execution_tracking_service=None,
            state_adapter_service=None,
            prompt_manager_service=None,
            telemetry_service=mock_telemetry,
        )

        agent = KwargsAgent(**args)
        assert agent._telemetry_service is mock_telemetry
