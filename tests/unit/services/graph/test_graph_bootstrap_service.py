"""Graph bootstrap service dependency discovery tests."""

from unittest.mock import Mock, patch

from agentmap.di.containers import ApplicationContainer
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.agent_config_service import AgentConfigService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
from tests.utils.mock_service_factory import MockServiceFactory


def test_application_container_injects_dependency_checker():
    container = ApplicationContainer()

    bootstrap_service = container.graph_bootstrap_service()
    dependency_checker = container.dependency_checker_service()

    assert bootstrap_service.dependency_checker is dependency_checker


def test_llm_agent_registration_uses_injected_provider_discovery():
    dependency_checker = Mock(spec=DependencyCheckerService)
    dependency_checker.discover_and_validate_providers.return_value = {"openai": True}
    service = GraphBootstrapService(
        agent_registry_service=Mock(spec=AgentRegistryService),
        features_registry_service=Mock(spec=FeaturesRegistryService),
        app_config_service=Mock(spec=AppConfigService),
        logging_service=MockServiceFactory.create_mock_logging_service(),
        dependency_checker_service=dependency_checker,
    )
    service._register_agent = Mock(return_value=True)

    with (
        patch.object(
            AgentConfigService,
            "get_llm_agents",
            return_value={"openai": "agents.openai.OpenAIAgent"},
        ),
        patch.object(
            AgentConfigService,
            "get_llm_agent_to_provider",
            return_value={"openai": "openai"},
        ),
    ):
        service._register_required_llm_agents({"openai"}, None)

    dependency_checker.discover_and_validate_providers.assert_called_once_with("llm")
    service._register_agent.assert_called_once_with(
        "openai", "agents.openai.OpenAIAgent"
    )
    assert service._loaded_agents == {"openai"}
