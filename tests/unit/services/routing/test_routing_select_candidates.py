from agentmap.services.routing.routing_service import (
    LLMRoutingService,
)
from agentmap.services.routing.types import TaskComplexity


class DummyCfg:
    routing_matrix = {
        "anthropic": {"low": "claude-haiku-4-5", "medium": "claude-sonnet-4-6"},
        "openai": {"low": "gpt-4o-mini", "medium": "gpt-4o"},
        "google": {"low": "gemini-2.5-flash", "medium": "gemini-2.5-pro"},
    }
    performance = {"max_cache_size": 1000}

    def is_routing_cache_enabled(self):
        return False

    def get_cache_ttl(self):
        return 300

    def get_model_for_complexity(self, provider, tier):
        return self.routing_matrix.get(provider, {}).get(tier)

    def get_fallback_provider(self):
        return "anthropic"

    def get_fallback_model(self):
        return "claude-sonnet-4-6"

    def get_provider_preference(self):
        return ["anthropic", "openai"]

    def get_config(self):
        return {
            "routing": {
                "activities": {
                    "narrative": {
                        "medium": {
                            "primary": {
                                "provider": "anthropic",
                                "model": "claude-sonnet-4-6",
                            },
                            "fallbacks": [
                                {"provider": "openai", "model": "gpt-4o"},
                                {"provider": "google", "model": "gemini-2.5-pro"},
                            ],
                        }
                    }
                }
            }
        }


class DummyLogger:
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def make_router():
    # minimal construction—inject dummies for collaborators used in this test
    router = LLMRoutingService.__new__(LLMRoutingService)
    router.routing_config = DummyCfg()
    router._logger = DummyLogger()

    # fake analyzer
    class An:
        def analyze_prompt_complexity(self, *_a, **_k):
            return TaskComplexity.MEDIUM

    router.complexity_analyzer = An()
    return router


def test_activity_first_candidates():
    router = make_router()
    ctx = {
        "routing_enabled": True,
        "activity": "narrative",
        "input_context": {"user_input": "tell me a story"},
        "provider_preference": ["anthropic", "openai"],
    }
    cands = LLMRoutingService.select_candidates(router, ctx)
    assert cands[0] == {"provider": "anthropic", "model": "claude-sonnet-4-6"}
    # matrix peers should still appear (but after explicit fallbacks)
    assert {"provider": "google", "model": "gemini-2.5-pro"} in cands


def test_matrix_backstop_when_no_activity():
    router = make_router()
    ctx = {
        "routing_enabled": True,
        "input_context": {"user_input": "classify this"},
        "provider_preference": ["openai", "anthropic"],
    }
    cands = LLMRoutingService.select_candidates(router, ctx)
    # first is per preference + medium tier matrix model
    assert cands[0]["provider"] in ("openai", "anthropic")
