"""B006 regression coverage for routing and provider dispatch."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMProviderError,
)
from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.llm_service import LLMService
from agentmap.services.routing.cache import RoutingCache
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import RoutingContext, TaskComplexity
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


class TestRoutingProviderExclusions:
    @pytest.mark.parametrize("entrypoint", ["route_request", "select_optimal_model"])
    def test_refuses_when_every_available_provider_is_excluded(
        self, router, entrypoint
    ):
        context = RoutingContext(excluded_providers=["Anthropic"])

        with pytest.raises(LLMConfigurationError, match="No eligible providers"):
            if entrypoint == "route_request":
                router.route_request("test", "general", ["anthropic"], context)
            else:
                router.select_optimal_model(
                    "general", TaskComplexity.MEDIUM, ["anthropic"], context
                )

    @pytest.mark.parametrize(
        ("options", "reason"),
        [
            ({}, "Fallback: lowered complexity"),
            (
                {"retry_with_lower_complexity": False},
                "Emergency fallback",
            ),
            (
                {"retry_with_lower_complexity": False, "fallback_provider": "GOOGLE"},
                "Emergency fallback",
            ),
            ({"model_override": "claude-low"}, "Emergency fallback"),
            ({"model_override": "missing-model"}, "Emergency fallback"),
        ],
        ids=[
            "lower-complexity",
            "configured",
            "emergency",
            "known-model",
            "unknown-model",
        ],
    )
    def test_fallback_selects_an_eligible_provider(self, router, options, reason):
        context = RoutingContext(excluded_providers=["Anthropic"], **options)

        decision = router.route_request(
            "test", "general", ["anthropic", "openai"], context
        )

        assert (decision.provider, decision.model) == ("openai", "gpt-low")
        assert decision.fallback_used
        assert reason in decision.reasoning

    def test_exception_recovery_selects_an_eligible_provider(self, router):
        router.complexity_analyzer.determine_overall_complexity.side_effect = (
            RuntimeError("Analysis failed")
        )

        decision = router.route_request(
            "test",
            "general",
            ["anthropic", "openai"],
            RoutingContext(excluded_providers=["ANTHROPIC"]),
        )

        assert (decision.provider, decision.model) == ("openai", "gpt-low")
        assert decision.fallback_used
        assert "Analysis failed" in decision.reasoning

    @pytest.mark.parametrize("initial_exclusion", [[], ["Anthropic"]])
    def test_cache_tracks_changed_and_relaxed_exclusions(
        self, router, initial_exclusion
    ):
        providers = ["anthropic", "openai"]
        initial = "openai" if initial_exclusion else "anthropic"
        revised = "anthropic" if initial_exclusion else "openai"
        revised_exclusion = [] if initial_exclusion else ["Anthropic"]

        def route(excluded):
            return router.route_request(
                "test",
                "general",
                providers,
                RoutingContext(complexity_override="low", excluded_providers=excluded),
            )

        assert route(initial_exclusion).provider == initial
        assert route(revised_exclusion).provider == revised
        cached = route(revised_exclusion)
        assert cached.provider == revised
        assert cached.cache_hit
        with pytest.raises(LLMConfigurationError, match="No eligible providers"):
            route(providers)

    def test_cache_preserves_eligible_provider_order(self, router):
        context = RoutingContext(
            complexity_override="low", excluded_providers=["Google"]
        )
        first = router.route_request(
            "test", "general", ["anthropic", "openai", "google"], context
        )
        reordered = router.route_request(
            "test", "general", ["openai", "anthropic", "google"], context
        )

        assert first.provider == "anthropic"
        assert reordered.provider == "openai"

    def test_explicitly_empty_candidate_availability(self, router):
        context = RoutingContext()

        assert (
            router.select_candidates(
                context, complexity=TaskComplexity.LOW, available_providers=[]
            )
            == []
        )
        assert [
            candidate["provider"]
            for candidate in router.select_candidates(
                context, complexity=TaskComplexity.LOW
            )
        ] == ["anthropic", "openai", "google"]


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
        yield LLMStreamChunk(text_delta=f"response from {provider}", chunk_index=0)

    monkeypatch.setattr(
        service, "_invoke_with_resilience_stream_async", stream_response
    )
    return service, client_factory


async def call_routed(service, mode, **routing_context):
    messages = [{"role": "user", "content": "test"}]
    if mode == "sync":
        return service.call_llm(messages, routing_context=routing_context)
    if mode == "async":
        response = await service.call_llm_async(
            messages, routing_context=routing_context
        )
        return response.text
    return "".join(
        [
            chunk.text_delta
            async for chunk in service.call_llm_stream_async(
                messages, routing_context=routing_context
            )
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
class TestRoutedDispatchProviderExclusions:
    async def test_all_excluded_refuses_before_client_acquisition(
        self, llm_service, mode
    ):
        service, clients = llm_service

        with pytest.raises(LLMConfigurationError, match="No eligible providers"):
            await call_routed(
                service, mode, excluded_providers=["Anthropic", "OpenAI", "Google"]
            )

        clients.assert_not_called()

    async def test_router_failure_cannot_dispatch_excluded_fallback(
        self, llm_service, mode, monkeypatch
    ):
        service, clients = llm_service
        monkeypatch.setattr(
            service.routing_service,
            "route_request",
            Mock(side_effect=RuntimeError("router failed")),
        )

        with pytest.raises(LLMConfigurationError, match="eligible"):
            await call_routed(
                service,
                mode,
                excluded_providers=["ANTHROPIC"],
                fallback_provider="claude",
            )

        clients.assert_not_called()

    @pytest.mark.parametrize("configured_fallback", ["anthropic", "openai"])
    async def test_provider_failure_retries_only_eligible_providers(
        self, llm_service, mode, configured_fallback
    ):
        service, clients = llm_service
        service.routing_config.fallback["default_provider"] = configured_fallback

        text = await call_routed(
            service,
            mode,
            complexity_override="low",
            provider_preference=["openai"],
            excluded_providers=["Anthropic"],
        )

        assert [call.args[0] for call in clients.call_args_list] == ["openai", "google"]
        assert text == "response from google"
