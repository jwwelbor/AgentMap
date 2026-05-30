"""
Regression tests for T-E05-F02-004: concurrency guards for shared provider config.

These tests verify the production entrypoints:
- LLMFallbackHandler.try_with_fallback_async
- LLMFallbackHandler.try_with_fallback

Core guarantee:
- Calls that share the same config dict returned by get_provider_config_fn must not
  mutate that shared dict's model value.
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
    """Construct a minimal LLMFallbackHandler with real tier-plan inputs."""
    mock_logging = MockServiceFactory.create_mock_logging_service()

    mock_routing_config = Mock()
    mock_routing_config.fallback = {"default_provider": tier2_provider}
    mock_routing_config.routing_matrix = {
        "openai": {"low": tier1_model},
        "anthropic": {"low": tier1_model},
    }

    providers = list(available_providers or [])
    if "openai" not in providers:
        providers.append("openai")
    if tier2_provider and tier2_provider not in providers:
        providers.append(tier2_provider)

    for provider in providers:
        if provider not in mock_routing_config.routing_matrix:
            mock_routing_config.routing_matrix[provider] = {"low": tier1_model}

    mock_features = Mock()
    mock_features.get_available_providers.return_value = providers
    mock_features.is_provider_available.side_effect = (
        lambda capability, provider: provider in providers
    )

    return LLMFallbackHandler(
        logging_service=mock_logging,
        routing_config=mock_routing_config,
        features_registry=mock_features,
    )


def _shared_config() -> dict:
    """A config dict shared between concurrent/sequential calls."""
    return {"model": "original-model", "api_key": "test-key"}


def _llm_response(text: str, model: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        resolved_provider="openai",
        resolved_model=model,
    )


# ---------------------------------------------------------------------------
# Async fallback paths: must not mutate shared config
# ---------------------------------------------------------------------------


class TestFallbackHandlerConfigIsolation(unittest.IsolatedAsyncioTestCase):
    async def test_tier1_async_concurrent_calls_do_not_cross_contaminate_config_model(
        self,
    ):
        shared_config = _shared_config()

        def fake_get_or_create_client_fn(provider, config):
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(
            tier1_model="tier1-fallback-model",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic"],
        )
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier1(original_model: str):
            return await handler.try_with_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create_client_fn,
                convert_messages_fn=lambda msgs: msgs,
            )

        result_a, result_b = await asyncio.gather(
            run_tier1("model-used-by-A"),
            run_tier1("model-used-by-B"),
        )

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(shared_config["model"], "original-model")

    async def test_tier1_async_each_coroutine_sees_own_fallback_model(self):
        shared_config = _shared_config()
        observed_configs: list[dict] = []

        def capturing_get_or_create(provider, config):
            observed_configs.append(dict(config))
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(
            tier1_model="tier1-fallback-model",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic"],
        )
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier1(original_model: str):
            return await handler.try_with_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=capturing_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        await asyncio.gather(run_tier1("model-A"), run_tier1("model-B"))

        self.assertEqual(len(observed_configs), 2)
        for captured in observed_configs:
            self.assertEqual(captured["model"], "tier1-fallback-model")
        self.assertEqual(shared_config["model"], "original-model")

    async def test_tier2_async_does_not_mutate_shared_config(self):
        shared_config = _shared_config()

        def fake_get_or_create(provider, config):
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            if provider == "openai":
                raise Exception("force tier1 failure")
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(
            tier1_model="tier2-fallback-model",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic"],
        )
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier2(original_model: str):
            return await handler.try_with_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        result_a, result_b = await asyncio.gather(
            run_tier2("model-A"),
            run_tier2("model-B"),
        )

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(shared_config["model"], "original-model")

    async def test_tier3_async_does_not_mutate_shared_config(self):
        shared_config = _shared_config()

        def fake_get_or_create(provider, config):
            return Mock()

        async def fake_invoke_async_fn(client, msgs, provider, model):
            await asyncio.sleep(0)
            if provider in {"openai", "anthropic"}:
                raise Exception(f"force {provider} failure")
            return _llm_response(f"response-{model}", model)

        handler = _make_fallback_handler(
            tier1_model="tier3-fallback-model",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic", "google"],
        )
        handler._invoke_async_fn = fake_invoke_async_fn

        def shared_get_provider_config_fn(provider):
            return shared_config

        async def run_tier3(original_model: str):
            return await handler.try_with_fallback_async(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=shared_get_provider_config_fn,
                get_or_create_client_fn=fake_get_or_create,
                convert_messages_fn=lambda msgs: msgs,
            )

        result_a, result_b = await asyncio.gather(
            run_tier3("model-A"),
            run_tier3("model-B"),
        )

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(shared_config["model"], "original-model")


# ---------------------------------------------------------------------------
# Sync fallback paths: must not mutate shared config
# ---------------------------------------------------------------------------


class TestFallbackHandlerSyncConfigIsolation(unittest.TestCase):
    def test_tier1_sync_does_not_mutate_shared_config(self):
        shared_config = _shared_config()

        handler = _make_fallback_handler(
            tier1_model="sync-tier1-fallback",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic"],
        )
        handler._invoke_fn = lambda client, msgs, provider, model: f"ok-{model}"

        for original_model in ["different-model-A", "different-model-B"]:
            result = handler.try_with_fallback(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=lambda provider: shared_config,
                get_or_create_client_fn=lambda provider, config: Mock(),
                convert_messages_fn=lambda msgs: msgs,
            )
            self.assertTrue(result.startswith("ok-"))

        self.assertEqual(shared_config["model"], "original-model")

    def test_tier2_sync_does_not_mutate_shared_config(self):
        shared_config = _shared_config()

        handler = _make_fallback_handler(
            tier1_model="sync-tier2-fallback",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic"],
        )

        def invoke_sync(client, msgs, provider, model):
            if provider == "openai":
                raise Exception("force tier1 failure")
            return f"ok-{provider}-{model}"

        handler._invoke_fn = invoke_sync

        for original_model in ["different-model-A", "different-model-B"]:
            result = handler.try_with_fallback(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=lambda provider: shared_config,
                get_or_create_client_fn=lambda provider, config: Mock(),
                convert_messages_fn=lambda msgs: msgs,
            )
            self.assertIn("anthropic", result)

        self.assertEqual(shared_config["model"], "original-model")

    def test_tier3_sync_does_not_mutate_shared_config(self):
        shared_config = _shared_config()

        handler = _make_fallback_handler(
            tier1_model="sync-tier3-fallback",
            tier2_provider="anthropic",
            available_providers=["openai", "anthropic", "google"],
        )

        def invoke_sync(client, msgs, provider, model):
            if provider in {"openai", "anthropic"}:
                raise Exception(f"force {provider} failure")
            return f"ok-{provider}-{model}"

        handler._invoke_fn = invoke_sync

        for original_model in ["different-model-A", "different-model-B"]:
            result = handler.try_with_fallback(
                original_provider="openai",
                original_model=original_model,
                messages=[{"role": "user", "content": "hi"}],
                error=Exception("test error"),
                get_provider_config_fn=lambda provider: shared_config,
                get_or_create_client_fn=lambda provider, config: Mock(),
                convert_messages_fn=lambda msgs: msgs,
            )
            self.assertIn("google", result)

        self.assertEqual(shared_config["model"], "original-model")


if __name__ == "__main__":
    unittest.main()
