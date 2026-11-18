"""Fixtures for B006 routing and provider dispatch regressions."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from agentmap.exceptions.service_exceptions import LLMProviderError
from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.llm_service import LLMService
from agentmap.services.routing.cache import RoutingCache
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import TaskComplexity
from tests.utils.mock_service_factory import MockServiceFactory


@pytest.fixture
def provider_configs():
    return {
        "anthropic": {"model": "claude-low", "api_key": "test-key"},
        "openai": {"model": "gpt-low", "api_key": "test-key"},
        "google": {"model": "gemini-low", "api_key": "test-key"},
    }


@pytest.fixture
def app_config(provider_configs):
    config = MockServiceFactory.create_mock_app_config_service()
    config.get_llm_resilience_config.return_value = {"retry": {"max_attempts": 1}}
    config.get_llm_config.side_effect = lambda provider: provider_configs.get(
        provider, {}
    ).copy()
    config.get_value.side_effect = lambda key, default=None: {
        f"llm.{provider}.model": entry.get("model")
        for provider, entry in provider_configs.items()
    }.get(key, default)
    config.get_routing_config.return_value = {
        "enabled": True,
        "performance": {"enable_routing_cache": True, "cache_ttl": 300},
        "cost_optimization": {"enabled": False},
        "task_types": {
            "general": {"provider_preference": ["anthropic", "openai", "google"]}
        },
        "fallback": {"default_provider": "anthropic"},
        "routing_matrix": {
            "anthropic": {"low": "claude-low"},
            "openai": {"low": "gpt-low"},
            "google": {"low": "gemini-low"},
        },
    }
    return config


@pytest.fixture
def router(app_config):
    logger = MockServiceFactory.create_mock_logging_service()
    config = LLMRoutingConfigService(
        app_config, logger, LLMModelsConfigService(app_config)
    )
    analyzer = Mock()
    analyzer.determine_overall_complexity.side_effect = (
        lambda prompt, task_type, context: TaskComplexity.from_string(
            context.complexity_override or "medium"
        )
    )
    return LLMRoutingService(config, logger, RoutingCache(logger), analyzer)


@pytest.fixture
def llm_service(router, app_config, provider_configs, monkeypatch):
    registry = Mock()
    registry.get_available_providers.return_value = list(provider_configs)
    registry.is_provider_available.side_effect = lambda service, provider: (
        provider in provider_configs
    )
    service = LLMService(
        configuration=app_config,
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
