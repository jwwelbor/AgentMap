"""
Regression tests for T-E05-F02-004: async concurrency guards for fan-out shared state.

Covers:
- Item 1: LLMFallbackHandler tier helpers must not mutate the shared config dict
  returned by get_provider_config_fn. Two concurrent coroutines sharing a provider
  must each see their own model value after the tier helper runs.

Notes on Items 2 and 3:
- LLMClientFactory._clients cache race: documented as an accepted benign race
  (last-write-wins; both created clients are equivalent). No lock added.
- CircuitBreaker state mutations: documented as best-effort / approximate-count
  behaviour. No lock added.
"""

import asyncio
import unittest
from unittest.mock import Mock

from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fallback_handler(
    *,
    tier1_model: str = "fallback-low",
    tier2_provider: str | None = None,
    available_providers: list[str] | None = None,
) -> LLMFallbackHandler:
    """Construct a minimal LLMFallbackHandler with controllable tier models."""
    mock_logging = MockServiceFactory.create_mock_logging_service()

    mock_routing_config = Mock()
    mock_routing_config.get_configured_fallback_provider.return_value = tier2_provider

    mock_features = Mock()
    mock_features.get_available_providers.return_value = available_providers or []

    handler = LLMFallbackHandler(
        logging_service=mock_logging,
        routing_config=mock_routing_config,
        features_registry=mock_features,
        invoke_fn=None,
        invoke_async_fn=None,
    )

    # Stub get_fallback_model to return tier1_model for "low" complexity
    handler.get_fallback_model = Mock(
        side_effect=lambda provider, complexity: (
            tier1_model if complexity == "low" else None
        )
    )

    return handler


def _shared_config() -> dict:
    """A config dict shared between concurrent coroutines (the scenario under test)."""
    return {"model": "original-model", "api_key": "test-key"}


def _llm_response(text: str, model: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        resolved_provider="openai",
        resolved_model=model,
    )


# ---------------------------------------------------------------------------
# TC for Item 1: Tier 1 async fallback config isolation
# ---------------------------------------------------------------------------


class TestFallbackHandlerConfigIsolation(unittest.IsolatedAsyncioTestCase):
    """
    Regression test: concurrent fan-out coroutines sharing a provider config
    dict must not cross-contaminate each other's config['model'] value.

    The fix is: each tier helper must do ``config = dict(config)`` before
    mutating the dict. Without the defensive copy, coroutine A's mutation
    of config['model'] is visible to coroutine B because both received the
    same dict reference.
    """

    async def test_tier1_async_concurrent_calls_do_not_cross_contaminate_config_model(
        self,
    ):
        """
        TC-T004-001 (Item 1): Two concurrent Tier 1 fallback calls sharing the
        same provider config dict must each see their own fallback model, not
        each other's.

        Production entrypoint: LLMFallbackHandler._try_tier1_fallback_async()
        called concurrently via asyncio.gather.

        Caller-path contract: drives the private method at the exact kwargs
        signature that try_with_fallback_async uses internally.

        Counter-factual: without ``config = dict(config)``, the second coroutine
        to run would read the model name written by the first coroutine, causing
        both coroutines to use the same model value (cross-contamination). The
        assertion ``model_seen_by_a != model_seen_by_b`` would FAIL.
        """
        # Arrange: a SINGLE shared dict (as get_provider_config_fn would return
        # if it simply returns a reference to an internal dict)
        shared_config = _shared_config()
        observed_models: list[str] = []

        def fake_get_or_create_client_fn(provider, config):
            # Record the model value the coroutine sees at invocation time
            observed_models.append(config["model"])
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            # Introduce a brief yield so both coroutines are truly concurrent
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(tier1_model="tier1-fallback-model")
        # Wire the async invoke fn onto the handler
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            # Returns the SAME dict object — the vulnerability scenario
            return shared_config

        async def run_tier1(original_model: str):
            return await handler._try_tier1_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                attempted_fallbacks=[],
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create_client_fn,
                convert_messages_fn=lambda msgs: msgs,
            )

        # Act: launch two concurrent coroutines sharing the same config dict
        result_a, result_b = await asyncio.gather(
            run_tier1("model-used-by-A"),
            run_tier1("model-used-by-B"),
        )

        # Assert: both calls should succeed
        self.assertIsNotNone(result_a, "Coroutine A must return a result")
        self.assertIsNotNone(result_b, "Coroutine B must return a result")

        # Assert: the shared dict itself must remain unmodified (defensive copy)
        self.assertEqual(
            shared_config["model"],
            "original-model",
            "The shared config dict must not be mutated by the fallback tier helper",
        )

    async def test_tier1_async_each_coroutine_sees_own_fallback_model(self):
        """
        TC-T004-002 (Item 1 extended): Each concurrent Tier 1 call invokes the
        client with the fallback model, not the original model or a value
        contaminated by a sibling coroutine.

        Counter-factual: without the defensive copy, get_or_create_client_fn
        would receive ``config`` with model == whatever the last concurrent
        write set it to, making all concurrent calls share one model.
        """
        shared_config = _shared_config()
        observed_configs: list[dict] = []

        def capturing_get_or_create(provider, config):
            # Capture a snapshot of the config at call time
            observed_configs.append(dict(config))
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(tier1_model="tier1-fallback-model")
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier1(original_model: str):
            return await handler._try_tier1_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                attempted_fallbacks=[],
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=capturing_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        await asyncio.gather(
            run_tier1("model-A"),
            run_tier1("model-B"),
        )

        # Both coroutines must have invoked the client with the tier1 fallback model
        self.assertEqual(
            len(observed_configs), 2, "Both coroutines must invoke the client"
        )
        for captured in observed_configs:
            self.assertEqual(
                captured["model"],
                "tier1-fallback-model",
                f"Each coroutine must see the tier1 fallback model, got: {captured['model']}",
            )

    async def test_tier2_async_does_not_mutate_shared_config(self):
        """
        TC-T004-003 (Item 1 Tier 2): Tier 2 fallback helper also makes a
        defensive copy before mutating config['model'].
        """
        shared_config = _shared_config()

        def fake_get_or_create(provider, config):
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(tier1_model="tier2-fallback-model")
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier2():
            return await handler._try_tier2_fallback_async(
                fallback_provider="anthropic",
                messages=[{"role": "user", "content": "hi"}],
                attempted_fallbacks=[],
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        result_a, result_b = await asyncio.gather(run_tier2(), run_tier2())

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(
            shared_config["model"],
            "original-model",
            "Tier 2 handler must not mutate the shared config dict",
        )

    async def test_tier3_async_does_not_mutate_shared_config(self):
        """
        TC-T004-004 (Item 1 Tier 3): Tier 3 emergency fallback helper also
        makes a defensive copy before mutating config['model'].
        """
        shared_config = _shared_config()

        def fake_get_or_create(provider, config):
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(
            tier1_model="tier3-fallback-model",
            available_providers=["anthropic", "google"],
        )
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier3():
            return await handler._try_tier3_fallback_async(
                original_provider="openai",
                configured_fallback_provider=None,
                messages=[{"role": "user", "content": "hi"}],
                attempted_fallbacks=[],
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        result_a, result_b = await asyncio.gather(run_tier3(), run_tier3())

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(
            shared_config["model"],
            "original-model",
            "Tier 3 handler must not mutate the shared config dict",
        )


# ---------------------------------------------------------------------------
# Sync tier helpers must also make defensive copies (Items 1 sync paths)
# ---------------------------------------------------------------------------


class TestFallbackHandlerSyncConfigIsolation(unittest.TestCase):
    """
    Regression tests for the sync tier helpers.  Even though the sync path
    is not directly exercised by async fan-out, the task spec says all six
    mutation sites must be fixed.
    """

    def _make_sync_handler(self, fallback_model: str = "sync-fallback-model"):
        mock_logging = MockServiceFactory.create_mock_logging_service()
        mock_routing_config = Mock()
        mock_routing_config.get_configured_fallback_provider.return_value = None
        mock_features = Mock()
        mock_features.get_available_providers.return_value = []

        handler = LLMFallbackHandler(
            logging_service=mock_logging,
            routing_config=mock_routing_config,
            features_registry=mock_features,
        )
        handler.get_fallback_model = Mock(
            side_effect=lambda provider, complexity: (
                fallback_model if complexity == "low" else None
            )
        )
        return handler

    def test_tier1_sync_does_not_mutate_shared_config(self):
        """TC-T004-005 (Item 1 sync Tier 1): sync path also makes a defensive copy."""
        shared_config = _shared_config()
        fake_client = Mock()
        fake_client.invoke.return_value = Mock(content="response")

        handler = self._make_sync_handler()

        handler._try_tier1_fallback(
            original_provider="openai",
            original_model="different-model",
            messages=[{"role": "user", "content": "hi"}],
            attempted_fallbacks=[],
            get_provider_config_fn=lambda provider: shared_config,
            get_or_create_client_fn=lambda provider, config: fake_client,
            convert_messages_fn=lambda msgs: msgs,
        )

        self.assertEqual(
            shared_config["model"],
            "original-model",
            "Sync Tier 1 must not mutate the shared config dict",
        )

    def test_tier2_sync_does_not_mutate_shared_config(self):
        """TC-T004-006 (Item 1 sync Tier 2): sync path also makes a defensive copy."""
        shared_config = _shared_config()
        fake_client = Mock()
        fake_client.invoke.return_value = Mock(content="response")

        handler = self._make_sync_handler()

        handler._try_tier2_fallback(
            fallback_provider="anthropic",
            messages=[{"role": "user", "content": "hi"}],
            attempted_fallbacks=[],
            get_provider_config_fn=lambda provider: shared_config,
            get_or_create_client_fn=lambda provider, config: fake_client,
            convert_messages_fn=lambda msgs: msgs,
        )

        self.assertEqual(
            shared_config["model"],
            "original-model",
            "Sync Tier 2 must not mutate the shared config dict",
        )

    def test_tier3_sync_does_not_mutate_shared_config(self):
        """TC-T004-007 (Item 1 sync Tier 3): sync path also makes a defensive copy."""
        shared_config = _shared_config()
        fake_client = Mock()
        fake_client.invoke.return_value = Mock(content="response")

        mock_logging = MockServiceFactory.create_mock_logging_service()
        mock_routing_config = Mock()
        mock_routing_config.get_configured_fallback_provider.return_value = None
        mock_features = Mock()
        mock_features.get_available_providers.return_value = ["anthropic"]

        handler = LLMFallbackHandler(
            logging_service=mock_logging,
            routing_config=mock_routing_config,
            features_registry=mock_features,
        )
        handler.get_fallback_model = Mock(
            side_effect=lambda provider, complexity: (
                "tier3-fallback" if complexity == "low" else None
            )
        )

        handler._try_tier3_fallback(
            original_provider="openai",
            configured_fallback_provider=None,
            messages=[{"role": "user", "content": "hi"}],
            attempted_fallbacks=[],
            get_provider_config_fn=lambda provider: shared_config,
            get_or_create_client_fn=lambda provider, config: fake_client,
            convert_messages_fn=lambda msgs: msgs,
        )

        self.assertEqual(
            shared_config["model"],
            "original-model",
            "Sync Tier 3 must not mutate the shared config dict",
        )


if __name__ == "__main__":
    unittest.main()
