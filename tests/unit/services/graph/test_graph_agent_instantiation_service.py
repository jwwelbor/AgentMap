"""Unit tests for GraphAgentInstantiationService service-name filtering."""

import unittest
from typing import Any
from unittest.mock import MagicMock, Mock

from agentmap.models.declaration_models import AgentDeclaration
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.agent.agent_service_injection_service import (
    AgentServiceInjectionService,
)
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.graph.graph_agent_instantiation_service import (
    GraphAgentInstantiationService,
)
from agentmap.services.protocols import LLMCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class MockLLMAgent(LLMCapableAgent):
    """Minimal agent used to verify LLM service injection."""

    def __init__(self, name: str = "llm_agent"):
        self.name = name
        self.llm_service = None

    def configure_llm_service(self, llm_service: Any) -> None:
        self.llm_service = llm_service


class TestGraphAgentInstantiationService(unittest.TestCase):
    """Tests for service requirement normalization in agent instantiation."""

    def setUp(self) -> None:
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_logger = self.mock_logging.get_class_logger.return_value
        self.parser = DeclarationParser(self.mock_logging)

        self.llm_service = Mock(name="llm_service")
        self.storage_service_manager = Mock(name="storage_service_manager")
        self.prompt_manager_service = Mock(name="prompt_manager_service")
        self.graph_bundle_service = Mock(name="graph_bundle_service")
        self.execution_tracking_service = Mock(name="execution_tracking_service")
        self.state_adapter_service = Mock(name="state_adapter_service")

        self.agent_injection = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.mock_logging,
            prompt_manager_service=self.prompt_manager_service,
        )

        self.agent_factory = Mock(spec=AgentFactoryService)
        self.agent = MockLLMAgent()
        self.agent_factory.create_agent_instance.return_value = self.agent

        self.instantiation_service = GraphAgentInstantiationService(
            agent_factory_service=self.agent_factory,
            agent_service_injection_service=self.agent_injection,
            execution_tracking_service=self.execution_tracking_service,
            state_adapter_service=self.state_adapter_service,
            logging_service=self.mock_logging,
            prompt_manager_service=self.prompt_manager_service,
            graph_bundle_service=self.graph_bundle_service,
        )

    def test_alias_normalization_reaches_llm_injection(self) -> None:
        """Custom agent aliases should normalize before required_services filtering."""
        declaration = self.parser.parse_agent(
            "llm_vision",
            {
                "class_path": "app.agents.llm_vision.LlmVisionAgent",
                "services": ["LLMService"],
                "protocols": ["LLMCapableAgent"],
            },
            "yaml:/tmp/custom_agents.yaml",
        )

        bundle = GraphBundle(
            graph_name="test_graph",
            nodes={
                "llm_node": Node(name="llm_node", agent_type="llm_vision"),
            },
            required_agents={"llm_vision"},
            agent_mappings={
                "llm_vision": "app.agents.llm_vision.LlmVisionAgent",
            },
            custom_agents={"llm_vision"},
        )
        bundle.scoped_registry = MagicMock()
        bundle.scoped_registry.get_agent_declaration.return_value = declaration

        self.assertEqual(
            self.instantiation_service._get_required_services_for_agent(
                "llm_vision", bundle
            ),
            {"llm_service"},
        )

        result = self.instantiation_service.instantiate_agents(bundle)

        self.assertIs(result.node_instances["llm_node"], self.agent)
        self.assertIs(self.agent.llm_service, self.llm_service)


if __name__ == "__main__":
    unittest.main()
