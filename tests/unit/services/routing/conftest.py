"""Fixtures for B006 routing and provider dispatch regressions."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from agentmap.exceptions.service_exceptions import LLMProviderError
from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.llm_service import LLMService
from agentmap.services.routing.cache import RoutingCache
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import TaskComplexity
from tests.utils.mock_service_factory import MockServiceFactory


@pytest.fixture
def router():
    config = Mock()
    config.is_routing_cache_enabled.return_value = True
    config.performance = {}
    config.get_cache_ttl.return_value = 300
    config.get_provider_preference.return_value = ["anthropic", "openai", "google"]
    config.is_cost_optimization_enabled.return_value = False
    config.get_fallback_provider.return_value = "anthropic"
    config.get_fallback_model.return_value = "claude-low"
    config.fallback = {"default_provider": "anthropic"}
    config.routing_matrix = {
        "anthropic": {"low": "claude-low"},
        "openai": {"low": "gpt-low"},
        "google": {"low": "gemini-low"},
    }
    config.get_model_for_complexity.side_effect = (
        lambda provider, complexity: config.routing_matrix.get(provider, {}).get(
            complexity
        )
    )
    logger = MockServiceFactory.create_mock_logging_service()
    analyzer = Mock()
    analyzer.determine_overall_complexity.side_effect = (
        lambda prompt, task_type, context: TaskComplexity.from_string(
            context.complexity_override or "medium"
        )
    )
    return LLMRoutingService(config, logger, RoutingCache(logger), analyzer)


@pytest.fixture
def llm_service(router, monkeypatch):
    config = MockServiceFactory.create_mock_app_config_service()
    config.get_llm_resilience_config.return_value = {"retry": {"max_attempts": 1}}
    config.get_llm_config.side_effect = lambda provider: {
        "model": router.routing_config.routing_matrix[provider]["low"],
        "api_key": "test-key",
    }
    registry = Mock()
    registry.get_available_providers.return_value = list(
        router.routing_config.routing_matrix
    )
    registry.is_provider_available.side_effect = (
        lambda service, provider: provider in router.routing_config.routing_matrix
    )
    service = LLMService(
        configuration=config,
        logging_service=MockServiceFactory.create_mock_logging_service(),
        routing_service=router,
        llm_models_config_service=MockServiceFactory.create_mock_llm_models_config_service(),
        features_registry_service=registry,
        routing_config_service=router.routing_config,
    )

    def make_client(provider, config, **kwargs):
        if provider == "openai":
            error = LLMProviderError("primary call failed")
            return Mock(
                invoke=Mock(side_effect=error), ainvoke=AsyncMock(side_effect=error)
            )
        response = AIMessage(content=f"response from {provider}")
        return Mock(
            invoke=Mock(return_value=response), ainvoke=AsyncMock(return_value=response)
        )

    client_factory = Mock(side_effect=make_client)
    monkeypatch.setattr(service._client_factory, "get_or_create_client", client_factory)

    async def stream_response(messages, params, provider, model, client, credentials):
        if provider == "openai":
            raise LLMProviderError("primary stream failed")
        yield LLMStreamChunk(
            text_delta=f"response from {provider}", chunk_index=0, is_final=False
        )

    monkeypatch.setattr(
        service, "_invoke_with_resilience_stream_async", stream_response
    )
    return service, client_factory
