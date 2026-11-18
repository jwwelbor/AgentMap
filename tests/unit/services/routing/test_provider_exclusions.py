"""B006 regression coverage for routing and provider dispatch."""

import pytest

from agentmap.exceptions.service_exceptions import LLMConfigurationError
from agentmap.services.config.llm_routing_matrix import load_routing_matrix
from agentmap.services.routing.types import RoutingContext, TaskComplexity


class TestRoutingProviderExclusions:
    @pytest.mark.parametrize("entrypoint", ["route_request", "select_optimal_model"])
    @pytest.mark.parametrize(
        ("provider", "excluded"),
        [
            ("anthropic", "Anthropic"),
            ("anthropic", "Claude"),
            ("openai", "GpT"),
            ("google", "gemini"),
        ],
    )
    def test_refuses_when_every_available_provider_is_excluded(
        self, router, entrypoint, provider, excluded
    ):
        context = RoutingContext(excluded_providers=[excluded])

        with pytest.raises(LLMConfigurationError, match="No eligible providers"):
            if entrypoint == "route_request":
                router.route_request("test", "general", [provider], context)
            else:
                router.select_optimal_model(
                    "general", TaskComplexity.MEDIUM, [provider], context
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
        revised_exclusion = [] if initial_exclusion else ["Claude"]

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

    def test_candidates_match_aliases_and_preserve_available_spelling(self, router):
        candidates = router.select_candidates(
            RoutingContext(excluded_providers=["CLAUDE", "google"]),
            complexity=TaskComplexity.LOW,
            available_providers=["GPT", "anthropic", "GeMiNi"],
        )

        assert candidates == [{"provider": "GPT", "model": "gpt-low"}]

    def test_duplicate_provider_alias_keeps_first_preference_position(self, router):
        candidates = router.select_candidates(
            RoutingContext(provider_preference=["openai", "anthropic", "gpt"]),
            complexity=TaskComplexity.LOW,
            available_providers=["anthropic", "openai", "google"],
        )

        assert [candidate["provider"] for candidate in candidates] == [
            "openai",
            "anthropic",
            "google",
        ]

    def test_emergency_fallback_refuses_provider_without_own_model(self, router):
        with pytest.raises(LLMConfigurationError, match="no-model-provider"):
            router.create_emergency_fallback(["no-model-provider"], "matrix exhausted")

    def test_alias_keyed_matrix_rows_are_available_to_candidate_selection(self, router):
        router.routing_config.config_dict["routing_matrix"] = {
            "gpt": {"low": "alias-openai-low"}
        }
        router.routing_config.routing_matrix = load_routing_matrix(
            router.routing_config.config_dict, router._logger
        )

        implicit = router.select_candidates(
            RoutingContext(), complexity=TaskComplexity.LOW
        )
        explicit = router.select_candidates(
            RoutingContext(),
            complexity=TaskComplexity.LOW,
            available_providers=["gpt"],
        )

        assert router.routing_config.routing_matrix == {
            "openai": {"low": "alias-openai-low"}
        }
        assert router.routing_config.get_model_for_complexity("gpt", "low") == (
            "alias-openai-low"
        )
        assert router.routing_config.is_provider_available("GPT")
        assert implicit == [{"provider": "openai", "model": "alias-openai-low"}]
        assert explicit == [{"provider": "gpt", "model": "alias-openai-low"}]

    def test_alias_keyed_capabilities_match_canonical_provider_candidates(self, router):
        router.routing_config.config_dict["routing_matrix"] = {
            "gpt": {"low": "alias-openai-low"}
        }
        router.routing_config.routing_matrix = load_routing_matrix(
            router.routing_config.config_dict, router._logger
        )
        router.routing_config.config_dict["provider_capabilities"] = {
            "gpt": {"prompt_caching": True}
        }
        router.routing_config.provider_capabilities = (
            router.routing_config._load_provider_capabilities()
        )

        assert router.routing_config.provider_capabilities == {
            "openai": {"prompt_caching": True}
        }
        candidates = router.select_candidates(
            RoutingContext(requires_prompt_caching=True),
            complexity=TaskComplexity.LOW,
            available_providers=["gpt"],
        )

        assert candidates == [{"provider": "gpt", "model": "alias-openai-low"}]

    @pytest.mark.parametrize(
        "matrix",
        [
            {
                "openai": {"low": "canonical-low"},
                "gpt": {"low": "alias-low", "medium": "alias-medium"},
            },
            {
                "gpt": {"low": "alias-low", "medium": "alias-medium"},
                "openai": {"low": "canonical-low"},
            },
        ],
        ids=["canonical-row-first", "alias-row-first"],
    )
    def test_canonical_matrix_row_wins_alias_collision_independent_of_order(
        self, router, matrix
    ):
        router.routing_config.config_dict["routing_matrix"] = matrix
        router.routing_config.routing_matrix = load_routing_matrix(
            router.routing_config.config_dict, router._logger
        )

        assert router.routing_config.routing_matrix == {
            "openai": {"low": "canonical-low", "medium": "alias-medium"}
        }

    @pytest.mark.parametrize(
        "capabilities",
        [
            {
                "openai": {"prompt_caching": False},
                "gpt": {"prompt_caching": True},
            },
            {
                "gpt": {"prompt_caching": True},
                "openai": {"prompt_caching": False},
            },
        ],
        ids=["canonical-capability-first", "alias-capability-first"],
    )
    def test_canonical_capabilities_win_alias_collision_independent_of_order(
        self, router, capabilities
    ):
        router.routing_config.config_dict["provider_capabilities"] = capabilities
        router.routing_config.provider_capabilities = (
            router.routing_config._load_provider_capabilities()
        )

        assert not router.routing_config.supports_prompt_caching("gpt")

    @pytest.mark.asyncio
    async def test_alias_keyed_matrix_is_async_available(self, router):
        router.routing_config.config_dict["routing_matrix"] = {
            "gpt": {"low": "alias-openai-low"}
        }
        router.routing_config.routing_matrix = load_routing_matrix(
            router.routing_config.config_dict, router._logger
        )

        assert await router.routing_config.is_provider_available_async("gpt")

    def test_emergency_fallback_skips_model_less_provider_for_later_eligible_model(
        self, router
    ):
        decision = router.create_emergency_fallback(
            ["no-model-provider", "google"], "matrix exhausted"
        )

        assert (decision.provider, decision.model) == ("google", "gemini-low")

    def test_configured_fallback_without_model_continues_to_later_eligible_provider(
        self, router
    ):
        decision = router.recover_route(
            ["no-model-provider", "google"],
            RoutingContext(fallback_provider="no-model-provider"),
            "matrix exhausted",
        )

        assert (decision.provider, decision.model) == ("google", "gemini-low")

    def test_route_request_emergency_uses_later_eligible_provider_with_model(
        self, router
    ):
        decision = router.route_request(
            "test",
            "general",
            ["anthropic", "no-model-provider", "google"],
            RoutingContext(
                excluded_providers=["anthropic"],
                retry_with_lower_complexity=False,
            ),
        )

        assert (decision.provider, decision.model) == ("google", "gemini-low")
