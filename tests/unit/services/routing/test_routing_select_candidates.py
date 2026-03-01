from unittest.mock import Mock, create_autospec

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import TaskComplexity

ROUTING_MATRIX = {
    "anthropic": {"low": "claude-haiku-4-5", "medium": "claude-sonnet-4-6"},
    "openai": {"low": "gpt-4o-mini", "medium": "gpt-4o"},
    "google": {"low": "gemini-2.5-flash", "medium": "gemini-2.5-pro"},
}

ACTIVITIES = {
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


def make_router():
    """Build an LLMRoutingService with autospec'd dependencies."""
    mock_config = create_autospec(LLMRoutingConfigService, instance=True)
    mock_config.routing_matrix = ROUTING_MATRIX
    mock_config.performance = {"max_cache_size": 1000}
    mock_config.is_routing_cache_enabled.return_value = False
    mock_config.get_cache_ttl.return_value = 300
    mock_config.get_fallback_provider.return_value = "anthropic"
    mock_config.get_fallback_model.return_value = "claude-sonnet-4-6"
    mock_config.get_provider_preference.return_value = ["anthropic", "openai"]
    mock_config.get_activities_config.return_value = ACTIVITIES
    mock_config.get_model_for_complexity.side_effect = (
        lambda provider, tier: ROUTING_MATRIX.get(provider, {}).get(tier)
    )

    mock_analyzer = create_autospec(PromptComplexityAnalyzer, instance=True)
    mock_analyzer.analyze_prompt_complexity.return_value = TaskComplexity.MEDIUM

    mock_logger = create_autospec(LoggingService, instance=True)
    mock_logger.get_class_logger.return_value = Mock()

    # Construct service without __init__ to isolate select_candidates
    router = LLMRoutingService.__new__(LLMRoutingService)
    router.routing_config = mock_config
    router._logger = mock_logger.get_class_logger(router)
    router.complexity_analyzer = mock_analyzer
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
