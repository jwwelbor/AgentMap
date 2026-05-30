"""
Tests for T-E05-F02-005: narrow routing try/except + dedupe sync/async fallback tier ladders.

Part A: Verify that errors from the actual LLM invocation (_call_llm_direct,
_call_llm_async_direct) are NOT caught and relabeled as routing failures. Only
errors from route_request() and its supporting setup should trigger the
fallback_provider path.

Part B: Verify that LLMFallbackHandler._build_tier_plan() produces the same
tier sequence used by both try_with_fallback (sync) and try_with_fallback_async.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMResolvedCallError,
    LLMTimeoutError,
)
from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


def _make_service(**overrides) -> LLMService:
    """Create an LLMService with mocked dependencies for testing."""
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_config = MockServiceFactory.create_mock_app_config_service()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 1,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {
            "failure_threshold": 3,
            "reset_timeout": 60,
        },
    }
    mock_config.get_llm_config.side_effect = lambda provider: {
        "model": f"{provider}-default-model",
        "api_key": "test-key",
        "temperature": 0.7,
    }
    mock_routing = Mock()
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()
    return LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
        **overrides,
    )


def _make_fallback_handler(
    routing_matrix=None, fallback_default=None, available_providers=None
) -> LLMFallbackHandler:
    """Construct a minimal LLMFallbackHandler for tier-plan tests."""
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_routing_config = Mock()
    mock_routing_config.routing_matrix = routing_matrix or {
        "openai": {"low": "gpt-3.5-turbo"},
        "anthropic": {"low": "claude-instant-1"},
        "google": {"low": "gemini-pro"},
    }
    mock_routing_config.fallback = {"default_provider": fallback_default or "openai"}

    mock_features = Mock()
    mock_features.is_provider_available.side_effect = lambda svc, p: (
        p in (available_providers or ["openai", "anthropic"])
    )
    mock_features.get_available_providers.return_value = available_providers or [
        "openai",
        "anthropic",
    ]

    return LLMFallbackHandler(
        logging_service=mock_logging,
        routing_config=mock_routing_config,
        features_registry=mock_features,
    )


# ---------------------------------------------------------------------------
# Part A — sync routing try/except scope
# ---------------------------------------------------------------------------


class TestSyncRoutingTryExceptScope(unittest.TestCase):
    """Errors from the LLM invocation must NOT be caught by the routing except block.

    Production entrypoint: LLMService._call_llm_with_routing()
    Caller-path contract: _call_llm_with_routing calls route_request() for routing
    decision, then delegates to _call_llm_direct(). Only route_request() errors
    should fall back to fallback_provider; _call_llm_direct() errors must propagate.
    """

    def setUp(self):
        self.service = _make_service()
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-3-haiku"
        mock_decision.complexity = "low"
        mock_decision.confidence = 0.9
        mock_decision.max_tokens = None
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        self.service.routing_service.route_request.return_value = mock_decision
        self.routing_context = {
            "routing_enabled": True,
            "fallback_provider": "openai",
        }
        self.messages = [{"role": "user", "content": "test"}]

    def test_llm_config_error_from_direct_call_propagates_without_routing_fallback(
        self,
    ):
        """LLMConfigurationError from _call_llm_direct must NOT trigger routing fallback.

        Counter-factual: with the original wide try/except, LLMConfigurationError from
        _call_llm_direct would be caught at the outer except, logged as "Routing failed",
        and _call_llm_direct would be called again with fallback_provider — masking the
        real error origin. After narrowing, the error propagates as-is.
        """
        config_error = LLMConfigurationError("Invalid API key")

        with patch.object(
            self.service, "_call_llm_direct", side_effect=config_error
        ) as mock_direct:
            with self.assertRaises(LLMConfigurationError) as ctx:
                self.service._call_llm_with_routing(self.messages, self.routing_context)

        self.assertIs(ctx.exception, config_error)
        # _call_llm_direct called once with routed provider — NOT called again with fallback
        self.assertEqual(mock_direct.call_count, 1)
        self.assertEqual(
            mock_direct.call_args.kwargs.get("provider")
            or mock_direct.call_args[1].get("provider"),
            "anthropic",
        )

    def test_llm_dependency_error_from_direct_call_propagates_without_routing_fallback(
        self,
    ):
        """LLMDependencyError from _call_llm_direct must NOT trigger routing fallback."""
        dep_error = LLMDependencyError("Missing dependency")

        with patch.object(
            self.service, "_call_llm_direct", side_effect=dep_error
        ) as mock_direct:
            with self.assertRaises(LLMDependencyError) as ctx:
                self.service._call_llm_with_routing(self.messages, self.routing_context)

        self.assertIs(ctx.exception, dep_error)
        self.assertEqual(mock_direct.call_count, 1)

    def test_routing_failure_still_uses_fallback_provider(self):
        """Actual route_request() failure should still trigger fallback_provider path."""
        self.service.routing_service.route_request.side_effect = Exception(
            "routing service unavailable"
        )
        fallback_response = "fallback text"

        with patch.object(
            self.service, "_call_llm_direct", return_value=fallback_response
        ) as mock_direct:
            result = self.service._call_llm_with_routing(
                self.messages, self.routing_context
            )

        self.assertEqual(result, fallback_response)
        # _call_llm_direct must be called with the fallback_provider
        called_provider = mock_direct.call_args.kwargs.get(
            "provider"
        ) or mock_direct.call_args[1].get("provider")
        self.assertEqual(called_provider, "openai")


# ---------------------------------------------------------------------------
# Part A — async routing try/except scope
# ---------------------------------------------------------------------------


class TestAsyncRoutingTryExceptScope(unittest.IsolatedAsyncioTestCase):
    """Errors from the async LLM invocation must NOT be caught by the routing except block.

    Production entrypoint: LLMService._call_llm_async_with_routing()
    """

    def setUp(self):
        self.service = _make_service()
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-3-haiku"
        mock_decision.complexity = "low"
        mock_decision.confidence = 0.9
        mock_decision.max_tokens = None
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        self.service.routing_service.route_request.return_value = mock_decision
        self.routing_context = {
            "routing_enabled": True,
            "fallback_provider": "openai",
        }
        self.messages = [{"role": "user", "content": "test"}]

    async def test_llm_config_error_from_async_direct_call_propagates_without_routing_fallback(
        self,
    ):
        """LLMConfigurationError from _call_llm_async_direct must NOT trigger routing fallback.

        Counter-factual: with the original wide try/except, the async routing handler
        would catch this error at 'except Exception as e:', log "Routing failed", and
        call _call_llm_async_direct again with fallback_provider, hiding that the error
        came from the invocation layer, not the routing layer.
        """
        config_error = LLMConfigurationError("Invalid API key")

        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(side_effect=config_error),
        ) as mock_direct:
            with self.assertRaises(LLMConfigurationError) as ctx:
                await self.service._call_llm_async_with_routing(
                    self.messages, self.routing_context
                )

        self.assertIs(ctx.exception, config_error)
        # _call_llm_async_direct called once with routed provider — NOT again with fallback
        self.assertEqual(mock_direct.await_count, 1)
        called_provider = mock_direct.call_args.kwargs.get(
            "provider"
        ) or mock_direct.call_args[1].get("provider")
        self.assertEqual(called_provider, "anthropic")

    async def test_llm_provider_error_from_async_direct_call_propagates_without_routing_fallback(
        self,
    ):
        """LLMProviderError from _call_llm_async_direct must NOT trigger routing fallback."""
        provider_error = LLMProviderError("Provider API error")

        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(side_effect=provider_error),
        ) as mock_direct:
            with self.assertRaises(LLMProviderError) as ctx:
                await self.service._call_llm_async_with_routing(
                    self.messages, self.routing_context
                )

        self.assertIs(ctx.exception, provider_error)
        self.assertEqual(mock_direct.await_count, 1)

    async def test_resolved_call_error_propagates_without_routing_fallback(self):
        """LLMResolvedCallError from _call_llm_async_direct must propagate as-is.

        LLMResolvedCallError carries resolved provider/model identity from a
        post-selection failure. It must never be swapped to fallback_provider.
        """
        resolved_error = LLMResolvedCallError(
            resolved_provider="anthropic",
            resolved_model="claude-3-haiku",
            cause=LLMTimeoutError("timed out"),
        )

        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(side_effect=resolved_error),
        ) as mock_direct:
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await self.service._call_llm_async_with_routing(
                    self.messages, self.routing_context
                )

        self.assertIs(ctx.exception, resolved_error)
        self.assertEqual(mock_direct.await_count, 1)

    async def test_async_routing_failure_still_uses_fallback_provider(self):
        """Actual route_request() failure should still trigger fallback_provider path."""
        self.service.routing_service.route_request.side_effect = Exception(
            "routing service unavailable"
        )
        fallback_response = LLMResponse(
            text="fallback text",
            resolved_provider="openai",
            resolved_model="openai-default-model",
        )

        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(return_value=fallback_response),
        ) as mock_direct:
            result = await self.service._call_llm_async_with_routing(
                self.messages, self.routing_context
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "fallback text")
        called_provider = mock_direct.call_args.kwargs.get(
            "provider"
        ) or mock_direct.call_args[1].get("provider")
        self.assertEqual(called_provider, "openai")


# ---------------------------------------------------------------------------
# Part B — _build_tier_plan deduplication
# ---------------------------------------------------------------------------


class TestBuildTierPlan(unittest.TestCase):
    """_build_tier_plan() must exist on LLMFallbackHandler and return the
    shared tier sequence used by both sync and async try_with_fallback paths.

    Production entrypoint: LLMFallbackHandler._build_tier_plan()
    """

    def test_build_tier_plan_exists_on_fallback_handler(self):
        """_build_tier_plan must be a method on LLMFallbackHandler.

        Counter-factual: without extracting _build_tier_plan, calling it would
        raise AttributeError, failing this test.
        """
        handler = _make_fallback_handler()
        self.assertTrue(
            hasattr(handler, "_build_tier_plan"),
            "_build_tier_plan method not found on LLMFallbackHandler",
        )
        self.assertTrue(callable(handler._build_tier_plan))

    def test_build_tier_plan_returns_list_of_provider_model_tuples(self):
        """_build_tier_plan returns a list of (provider, model) tuples.

        Counter-factual: if each sync and async tier ladder computed tiers
        independently (the old approach), changing the tier order in one place
        would not update the other. A shared _build_tier_plan ensures one source.
        """
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
                "anthropic": {"low": "claude-instant-1"},
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        plan = handler._build_tier_plan(
            original_provider="openai",
            original_model="gpt-4",
        )

        self.assertIsInstance(plan, list)
        for entry in plan:
            self.assertIsInstance(entry, tuple)
            self.assertEqual(len(entry), 2)

    def test_build_tier_plan_includes_tier1_same_provider_lower_model(self):
        """Tier 1 (same provider, lower model) appears first in the plan when available.

        Counter-factual: if tier ordering was wrong, the fallback would skip the
        same-provider low-complexity model and jump to a different provider.
        """
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
                "anthropic": {"low": "claude-instant-1"},
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        plan = handler._build_tier_plan(
            original_provider="openai",
            original_model="gpt-4",
        )

        providers_in_plan = [p for p, _ in plan]
        models_in_plan = [m for _, m in plan]
        # Tier 1: same provider (openai) with lower model
        self.assertIn("openai", providers_in_plan)
        self.assertIn("gpt-3.5-turbo", models_in_plan)
        # Tier 1 must be first
        self.assertEqual(plan[0], ("openai", "gpt-3.5-turbo"))

    def test_build_tier_plan_excludes_already_tried_model_for_tier1(self):
        """Tier 1 is skipped when the fallback model equals the original model."""
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-4"},  # same as original
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        plan = handler._build_tier_plan(
            original_provider="openai",
            original_model="gpt-4",
        )

        # Tier 1 entry (openai, gpt-4) should be excluded since it's the same model
        self.assertNotIn(("openai", "gpt-4"), plan)

    def test_build_tier_plan_includes_configured_fallback_provider_as_tier2(self):
        """Tier 2 (configured fallback provider) appears after Tier 1."""
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
                "anthropic": {"low": "claude-instant-1"},
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        plan = handler._build_tier_plan(
            original_provider="openai",
            original_model="gpt-4",
        )

        providers = [p for p, _ in plan]
        # Tier 2: anthropic (the configured fallback)
        self.assertIn("anthropic", providers)
        # anthropic must come after openai in the plan
        openai_idx = next(i for i, (p, _) in enumerate(plan) if p == "openai")
        anthropic_idx = next(i for i, (p, _) in enumerate(plan) if p == "anthropic")
        self.assertLess(openai_idx, anthropic_idx)

    def test_build_tier_plan_does_not_include_original_provider_as_tier2(self):
        """Tier 2 is skipped when fallback_provider equals original_provider."""
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
            },
            fallback_default="openai",  # same as original
            available_providers=["openai"],
        )

        plan = handler._build_tier_plan(
            original_provider="openai",
            original_model="gpt-4",
        )

        # Should only include tier1 entry (openai, gpt-3.5-turbo), NOT a second openai entry
        openai_entries = [(p, m) for p, m in plan if p == "openai"]
        self.assertLessEqual(len(openai_entries), 1)

    def test_build_tier_plan_sync_and_async_use_same_plan(self):
        """try_with_fallback and try_with_fallback_async must use _build_tier_plan.

        Counter-factual: if the sync path still used inline tier logic instead
        of calling _build_tier_plan, modifying _build_tier_plan would not change
        sync fallback behavior — i.e., the ladder would differ between sync/async.
        This test verifies _build_tier_plan is called in both paths.
        """
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
                "anthropic": {"low": "claude-instant-1"},
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        messages = [{"role": "user", "content": "test"}]
        error = LLMProviderError("provider error")

        def fake_get_config(provider):
            return {"model": f"{provider}-model", "api_key": "key"}

        def fake_get_client(provider, config):
            mock_client = Mock()
            mock_client.invoke.return_value = Mock(content="response")
            return mock_client

        def fake_convert(messages):
            return messages

        # Patch _build_tier_plan and verify it's called from the sync path
        original_build = handler._build_tier_plan
        build_calls = []

        def tracking_build(*args, **kwargs):
            result = original_build(*args, **kwargs)
            build_calls.append(result)
            return result

        handler._build_tier_plan = tracking_build

        try:
            handler.try_with_fallback(
                original_provider="openai",
                original_model="gpt-4",
                messages=messages,
                error=error,
                get_provider_config_fn=fake_get_config,
                get_or_create_client_fn=fake_get_client,
                convert_messages_fn=fake_convert,
            )
        except Exception:
            pass  # exhaustion is fine; we're testing that _build_tier_plan was called

        self.assertGreater(
            len(build_calls),
            0,
            "_build_tier_plan was not called by try_with_fallback (sync path)",
        )


class TestBuildTierPlanAsyncPath(unittest.IsolatedAsyncioTestCase):
    """Verify _build_tier_plan is called from the async fallback path."""

    async def test_async_try_with_fallback_uses_build_tier_plan(self):
        """try_with_fallback_async must call _build_tier_plan.

        Counter-factual: if async path used its own inline tier logic instead,
        _build_tier_plan call count would stay 0, failing this assertion.
        """
        handler = _make_fallback_handler(
            routing_matrix={
                "openai": {"low": "gpt-3.5-turbo"},
                "anthropic": {"low": "claude-instant-1"},
            },
            fallback_default="anthropic",
            available_providers=["openai", "anthropic"],
        )

        messages = [{"role": "user", "content": "test"}]
        error = LLMProviderError("provider error")

        async def fake_invoke_async(client, lc_msgs, provider, model):
            return LLMResponse(
                text="async response",
                resolved_provider=provider,
                resolved_model=model,
            )

        handler._invoke_async_fn = fake_invoke_async

        def fake_get_config(provider):
            return {"model": f"{provider}-model", "api_key": "key"}

        def fake_get_client(provider, config):
            return Mock()

        def fake_convert(messages):
            return messages

        original_build = handler._build_tier_plan
        build_calls = []

        def tracking_build(*args, **kwargs):
            result = original_build(*args, **kwargs)
            build_calls.append(result)
            return result

        handler._build_tier_plan = tracking_build

        try:
            await handler.try_with_fallback_async(
                original_provider="openai",
                original_model="gpt-4",
                messages=messages,
                error=error,
                get_provider_config_fn=fake_get_config,
                get_or_create_client_fn=fake_get_client,
                convert_messages_fn=fake_convert,
            )
        except Exception:
            pass  # exhaustion is fine

        self.assertGreater(
            len(build_calls),
            0,
            "_build_tier_plan was not called by try_with_fallback_async (async path)",
        )


if __name__ == "__main__":
    unittest.main()
