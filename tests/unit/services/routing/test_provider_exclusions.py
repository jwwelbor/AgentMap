"""B006 regression coverage for routing and provider dispatch."""

from unittest.mock import Mock

import pytest

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMServiceError,
)
from agentmap.services.routing.types import RoutingContext, TaskComplexity


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
        ],
        ids=[
            "lower-complexity",
            "configured",
            "emergency",
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

    @pytest.mark.parametrize("model_override", ["claude-low", "missing-model"])
    def test_direct_model_override_uses_eligible_alternate(
        self, router, model_override
    ):
        decision = router.select_optimal_model(
            "general",
            TaskComplexity.MEDIUM,
            ["anthropic", "openai"],
            RoutingContext(
                excluded_providers=["Anthropic"], model_override=model_override
            ),
        )

        assert (decision.provider, decision.model) == ("openai", "gpt-low")
        assert decision.fallback_used

    def test_eligible_configured_routing_fallback_wins(self, router):
        decision = router.select_optimal_model(
            "general",
            TaskComplexity.MEDIUM,
            ["openai", "google", "anthropic"],
            RoutingContext(
                excluded_providers=["Anthropic"],
                fallback_provider="google",
                fallback_model="gemini-low",
                retry_with_lower_complexity=False,
            ),
        )

        assert (decision.provider, decision.model) == ("google", "gemini-low")
        assert "Configured fallback" in decision.reasoning

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

    @pytest.mark.parametrize(
        ("fallback_provider", "excluded"),
        [("gpt", "OPENAI"), ("missing", "OPENAI"), ("claude", "GOOGLE")],
    )
    async def test_router_failure_dispatches_eligible_provider(
        self, llm_service, mode, monkeypatch, fallback_provider, excluded
    ):
        service, clients = llm_service
        monkeypatch.setattr(
            service.routing_service,
            "route_request",
            Mock(side_effect=RuntimeError("router failed")),
        )

        text = await call_routed(
            service,
            mode,
            excluded_providers=[excluded],
            fallback_provider=fallback_provider,
        )

        assert text == "response from anthropic"
        assert [
            (call.args[0], call.args[1]["model"]) for call in clients.call_args_list
        ] == [("anthropic", "claude-low")]

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

    @pytest.mark.parametrize("configured_fallback", ["google", "openai"])
    async def test_retry_ignores_registry_providers_without_credentials(
        self, llm_service, mode, monkeypatch, configured_fallback
    ):
        service, clients = llm_service
        service.routing_config.fallback["default_provider"] = configured_fallback
        read_config = service.configuration.get_llm_config.side_effect
        service.configuration.get_llm_config.side_effect = lambda provider: read_config(
            provider
        ) | ({"api_key": ""} if provider == "google" else {})
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        resolve_config = Mock(wraps=service._provider_utils.get_provider_config)
        monkeypatch.setattr(
            service._provider_utils, "get_provider_config", resolve_config
        )

        with pytest.raises(LLMServiceError, match="primary"):
            await call_routed(
                service,
                mode,
                complexity_override="low",
                excluded_providers=["Anthropic"],
            )

        resolve_config.assert_called_once_with("openai")
        assert [call.args[0] for call in clients.call_args_list] == ["openai"]
