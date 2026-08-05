"""
Async contract tests for LLM service protocols and test doubles.
"""

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, create_autospec, patch

from agentmap.exceptions import LLMConfigurationError, LLMServiceError, LLMTimeoutError
from agentmap.exceptions.service_exceptions import LLMResolvedCallError
from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols import LLMServiceProtocol
from agentmap.services.telemetry.constants import GEN_AI_USAGE_COST
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMServiceAsyncProtocol(unittest.TestCase):
    """Contract tests for additive async LLM service protocol changes."""

    def test_protocol_autospec_preserves_sync_members(self):
        """Sync members remain available after adding async siblings."""
        mock_service = create_autospec(LLMServiceProtocol, instance=True)

        self.assertTrue(hasattr(mock_service, "call_llm"))
        self.assertTrue(hasattr(mock_service, "ask_vision"))

    def test_protocol_autospec_exposes_async_siblings(self):
        """Async protocol methods are available as awaitable mocks."""
        mock_service = create_autospec(LLMServiceProtocol, instance=True)

        self.assertTrue(hasattr(mock_service, "call_llm_async"))
        self.assertTrue(hasattr(mock_service, "ask_async"))
        self.assertIsInstance(mock_service.call_llm_async, AsyncMock)
        self.assertIsInstance(mock_service.ask_async, AsyncMock)


class TestMockLLMServiceAsync(unittest.IsolatedAsyncioTestCase):
    """Tests for async-capable LLM service test doubles."""

    async def test_mock_service_exposes_async_siblings(self):
        """MockServiceFactory creates a test double with awaitable async methods."""
        mock_service = MockServiceFactory.create_mock_llm_service()

        response = await mock_service.call_llm_async(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        # call_llm_async returns LLMResponse; .text carries the response string.
        from agentmap.models.llm_execution import LLMResponse

        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.text, "Mock LLM response")
        self.assertTrue(hasattr(mock_service, "ask"))
        self.assertTrue(hasattr(mock_service, "call_llm_async"))
        self.assertTrue(hasattr(mock_service, "ask_async"))

    async def test_mock_service_async_ask_matches_sync_default_response(self):
        """Async ask helper returns the same basic test-double response."""
        mock_service = MockServiceFactory.create_mock_llm_service()

        response = await mock_service.ask_async("hello")

        self.assertEqual(response, "Mock LLM response")


class TestLLMServiceAsync(unittest.IsolatedAsyncioTestCase):
    """Behavior tests for the async LLM service surface."""

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_app_config_service.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 3,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {
                "failure_threshold": 3,
                "reset_timeout": 60,
            },
        }
        self.mock_app_config_service.get_llm_config.side_effect = lambda provider: {
            "model": f"{provider}-default-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )
        self.mock_routing_service = Mock()
        self.mock_routing_config_service = Mock()
        self.mock_routing_config_service.supports_prompt_caching.return_value = False

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
            routing_config_service=self.mock_routing_config_service,
        )

    async def test_call_llm_async_uses_native_async_provider_surface(self):
        """Native async clients should be awaited instead of using sync invoke."""
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(return_value=Mock(content="async response"))
        mock_client.invoke = Mock()
        langchain_messages = [Mock()]

        with (
            patch.object(
                self.service._client_factory,
                "get_or_create_client",
                return_value=mock_client,
            ),
            patch.object(
                self.service._message_utils,
                "convert_messages_to_langchain",
                return_value=langchain_messages,
            ),
        ):
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai",
                model="gpt-4o-mini",
                temperature=0.2,
                max_tokens=77,
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "async response")
        self.assertEqual(result.resolved_provider, "openai")
        mock_client.ainvoke.assert_awaited_once_with(langchain_messages)
        mock_client.invoke.assert_not_called()

    async def test_call_llm_async_preserves_cache_marked_structured_blocks(self):
        """Async provider invocation preserves structured cache blocks unchanged."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "prefix",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "question"},
                ],
            }
        ]
        self.mock_routing_config_service.supports_prompt_caching.side_effect = (
            lambda provider: provider.lower() == "anthropic"
        )
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(return_value=Mock(content="async cached"))

        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
            return_value=mock_client,
        ):
            result = await self.service.call_llm_async(
                messages=messages,
                provider="anthropic",
            )

        self.assertEqual(result.text, "async cached")
        langchain_messages = mock_client.ainvoke.call_args.args[0]
        self.assertEqual(langchain_messages[0].content, messages[0]["content"])

    async def test_call_llm_async_rejects_prompt_caching_for_unsupported_provider(
        self,
    ):
        """Unsupported async providers fail before client creation."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "prefix",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]

        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
        ) as mock_get_client:
            with self.assertRaises(LLMServiceError) as ctx:
                await self.service.call_llm_async(
                    messages=messages,
                    provider="google",
                )

        self.assertIn("prompt caching", str(ctx.exception).lower())
        self.assertIn("google", str(ctx.exception).lower())
        mock_get_client.assert_not_called()

    async def test_call_llm_async_offloads_sync_only_client_to_worker_thread(self):
        """Sync-only clients should be invoked through the thread-offload seam."""
        mock_client = Mock()
        mock_client.ainvoke = None  # No async surface — forces the to_thread path.
        mock_client.invoke.return_value = Mock(content="compat response")
        langchain_messages = [Mock()]

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        with (
            patch.object(
                self.service._client_factory,
                "get_or_create_client",
                return_value=mock_client,
            ),
            patch.object(
                self.service._message_utils,
                "convert_messages_to_langchain",
                return_value=langchain_messages,
            ),
            patch(
                "agentmap.services.llm_service.asyncio.to_thread",
                new=AsyncMock(side_effect=fake_to_thread),
            ) as mock_to_thread,
        ):
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "compat response")
        mock_to_thread.assert_awaited_once()
        mock_client.invoke.assert_called_once_with(langchain_messages)

    async def test_call_llm_async_routing_ignores_explicit_provider_and_model(self):
        """Routing should own provider/model selection and log sync-parity warnings."""
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-3-7-sonnet-20250219"
        mock_decision.complexity = "medium"
        mock_decision.confidence = 0.91
        mock_decision.max_tokens = 64
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        self.mock_routing_service.route_request.return_value = mock_decision

        routed_response = LLMResponse(
            text="routed response",
            resolved_provider="anthropic",
            resolved_model="claude-3-7-sonnet-20250219",
        )
        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(return_value=routed_response),
        ) as mock_direct:
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "complex task"}],
                provider="openai",
                model="ignored",
                routing_context={
                    "routing_enabled": True,
                    "provider_preference": ["anthropic"],
                    "fallback_provider": "google",
                    "max_tokens": 64,
                },
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "routed response")
        mock_direct.assert_awaited_once_with(
            provider="anthropic",
            messages=[{"role": "user", "content": "complex task"}],
            model="claude-3-7-sonnet-20250219",
            temperature=None,
            routing_context={
                "routing_enabled": True,
                "provider_preference": ["anthropic"],
                "fallback_provider": "google",
                "max_tokens": 64,
            },
            cache_system_prompt=False,
            max_tokens=64,
        )
        self.assertEqual(self.service._logger.warning.call_count, 2)

    async def test_call_llm_async_routing_failure_uses_fallback_provider(self):
        """Routing failure should preserve fallback-provider async behavior."""
        self.mock_routing_service.route_request.side_effect = Exception(
            "routing failed"
        )

        fallback_response = LLMResponse(
            text="fallback response",
            resolved_provider="openai",
            resolved_model="openai-default-model",
        )
        with patch.object(
            self.service,
            "_call_llm_async_direct",
            new=AsyncMock(return_value=fallback_response),
        ) as mock_direct:
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "test"}],
                provider="anthropic",
                routing_context={
                    "routing_enabled": True,
                    "fallback_provider": "openai",
                    "max_tokens": 128,
                },
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "fallback response")
        mock_direct.assert_awaited_once_with(
            provider="openai",
            messages=[{"role": "user", "content": "test"}],
            model=None,
            temperature=None,
            routing_context={
                "routing_enabled": True,
                "fallback_provider": "openai",
                "max_tokens": 128,
            },
            cache_system_prompt=False,
            max_tokens=128,
        )

    async def test_ask_async_defaults_provider_and_shapes_messages_like_ask(self):
        """ask_async should mirror ask() default provider and message shaping."""
        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(
                return_value=LLMResponse(
                    text="default response",
                    resolved_provider="anthropic",
                    resolved_model="anthropic-default-model",
                )
            ),
        ) as mock_call_llm_async:
            result = await self.service.ask_async("Hello", temperature=0.8)

        self.assertEqual(result, "default response")
        mock_call_llm_async.assert_awaited_once_with(
            provider="anthropic",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.8,
        )

    async def test_call_llm_async_retries_with_async_sleep_and_records_success(self):
        """Retryable async failures should back off via asyncio.sleep and recover."""
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            side_effect=[
                RuntimeError("Connection timeout"),
                Mock(content="recovered"),
            ]
        )
        langchain_messages = [Mock()]

        with (
            patch.object(
                self.service._client_factory,
                "get_or_create_client",
                return_value=mock_client,
            ),
            patch.object(
                self.service._message_utils,
                "convert_messages_to_langchain",
                return_value=langchain_messages,
            ),
            patch(
                "agentmap.services.llm_service.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai",
                model="gpt-4o-mini",
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "recovered")
        self.assertEqual(mock_client.ainvoke.await_count, 2)
        mock_sleep.assert_awaited_once()
        self.assertEqual(self.service._circuit_breaker.failures, {})

    async def test_call_llm_async_non_retryable_failure_is_terminal(self):
        """Non-retryable async failures should preserve sync error classification."""
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(side_effect=RuntimeError("Invalid api_key"))

        with (
            patch.object(
                self.service._client_factory,
                "get_or_create_client",
                return_value=mock_client,
            ),
            patch.object(
                self.service._message_utils,
                "convert_messages_to_langchain",
                return_value=[Mock()],
            ),
            patch(
                "agentmap.services.llm_service.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            # Non-retryable errors are wrapped in LLMResolvedCallError so
            # callers get both the resolved identity and the underlying cause.
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await self.service.call_llm_async(
                    messages=[{"role": "user", "content": "hello"}],
                    provider="openai",
                    model="gpt-4o-mini",
                )
            self.assertIsInstance(ctx.exception.cause, LLMConfigurationError)
            self.assertRegex(str(ctx.exception.cause), "Invalid api_key|api_key")

        self.assertEqual(mock_client.ainvoke.await_count, 1)
        mock_sleep.assert_not_awaited()

    async def test_call_llm_async_uses_configured_fallback_handler(self):
        """Async direct-call failures should reuse configured tiered fallback logic."""
        mock_features_registry = Mock()
        mock_features_registry.is_provider_available.return_value = True
        mock_routing_config = Mock()
        mock_routing_config.fallback = {"default_provider": "anthropic"}
        mock_routing_config.routing_matrix = {"anthropic": {"low": "claude-haiku"}}

        service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
            features_registry_service=mock_features_registry,
            routing_config_service=mock_routing_config,
        )
        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            side_effect=lambda provider: {
                "model": f"{provider}-default-model",
                "api_key": "test-key",
            }
        )
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )

        failing_client = Mock()
        failing_client.ainvoke = AsyncMock(
            side_effect=RuntimeError("Connection timeout")
        )
        fallback_client = Mock()
        fallback_client.ainvoke = (
            None  # Sync-only fallback — forces the to_thread path.
        )
        fallback_client.invoke.return_value = Mock(content="fallback response")

        def fake_get_client(provider, config):
            return failing_client if provider == "openai" else fallback_client

        service._client_factory.get_or_create_client = Mock(side_effect=fake_get_client)

        result = await service.call_llm_async(
            messages=[{"role": "user", "content": "hello"}],
            provider="openai",
            model="gpt-4o-mini",
        )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "fallback response")

    async def test_call_llm_async_exhausted_retries_open_circuit(self):
        """Retry exhaustion should classify the error and open the circuit like sync."""
        self.service._resilience_config["retry"]["max_attempts"] = 3
        self.service._resilience_config["retry"]["jitter"] = False
        self.service._resilience_config["circuit_breaker"]["failure_threshold"] = 1
        self.service._circuit_breaker.threshold = 1

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(side_effect=RuntimeError("Connection timeout"))

        with (
            patch.object(
                self.service._client_factory,
                "get_or_create_client",
                return_value=mock_client,
            ),
            patch.object(
                self.service._message_utils,
                "convert_messages_to_langchain",
                return_value=[Mock()],
            ),
            patch(
                "agentmap.services.llm_service.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            # call_llm_async propagates LLMResolvedCallError (which is a
            # LLMServiceError subclass) carrying the resolved identity and the
            # underlying LLMTimeoutError as .cause.
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await self.service.call_llm_async(
                    messages=[{"role": "user", "content": "hello"}],
                    provider="openai",
                    model="gpt-4o-mini",
                )
            self.assertIsInstance(ctx.exception.cause, LLMTimeoutError)
            self.assertEqual(ctx.exception.resolved_provider, "openai")
            self.assertEqual(ctx.exception.resolved_model, "gpt-4o-mini")

        self.assertEqual(mock_client.ainvoke.await_count, 3)
        self.assertEqual(mock_sleep.await_count, 2)
        self.assertIn("openai:gpt-4o-mini", self.service._circuit_breaker.opened_at)


class TestLLMServiceCachePassthroughAsync(unittest.IsolatedAsyncioTestCase):
    """UAT-01 / UAT-02 (async): routing_context with requires_prompt_caching
    survives both the normal routed path and the routing-failure fallback path
    and triggers cache validation in _call_llm_async_direct."""

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_app_config_service.get_llm_resilience_config.return_value = {
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
        self.mock_app_config_service.get_llm_config.side_effect = lambda provider: {
            "model": f"{provider}-default-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )
        self.mock_routing_service = Mock()
        # routing_config that does NOT support caching for any provider
        self.mock_routing_config_service = Mock()
        self.mock_routing_config_service.supports_prompt_caching.return_value = False

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
            routing_config_service=self.mock_routing_config_service,
        )

    async def test_async_routed_path_propagates_requires_prompt_caching_flag(self):
        """UAT-01: _call_llm_async_with_routing passes routing_context to
        _call_llm_async_direct so requires_prompt_caching is validated even when
        messages contain no embedded cache_control blocks."""
        # Plain-text messages — no cache_control blocks embedded
        messages = [{"role": "user", "content": "plain text prompt"}]

        # Routing resolves a provider that does not support caching
        mock_decision = Mock()
        mock_decision.provider = "openai"
        mock_decision.model = "gpt-4o-mini"
        mock_decision.complexity = "low"
        mock_decision.confidence = 0.9
        mock_decision.max_tokens = None
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        self.mock_routing_service.route_request.return_value = mock_decision

        routing_context = {
            "routing_enabled": True,
            "requires_prompt_caching": True,
        }

        # _call_llm_async_direct should raise LLMServiceError because openai
        # does not support prompt caching (mock returns False for all providers).
        with self.assertRaises(LLMServiceError) as ctx:
            await self.service.call_llm_async(
                messages=messages,
                routing_context=routing_context,
            )

        self.assertIn("prompt caching", str(ctx.exception).lower())

    async def test_async_routing_fallback_propagates_requires_prompt_caching_flag(
        self,
    ):
        """UAT-02 (async): routing failure fallback passes routing_context to
        _call_llm_async_direct so requires_prompt_caching is validated even when
        messages contain no embedded cache_control blocks."""
        # Plain-text messages — no cache_control blocks embedded
        messages = [{"role": "user", "content": "plain text prompt"}]

        # Force routing to fail so the fallback path is exercised
        self.mock_routing_service.route_request.side_effect = RuntimeError(
            "routing unavailable"
        )

        routing_context = {
            "routing_enabled": True,
            "requires_prompt_caching": True,
            "fallback_provider": "openai",
        }

        # _call_llm_async_direct should raise LLMServiceError because openai
        # does not support prompt caching (mock returns False for all providers).
        with self.assertRaises(LLMServiceError) as ctx:
            await self.service.call_llm_async(
                messages=messages,
                routing_context=routing_context,
            )

        self.assertIn("prompt caching", str(ctx.exception).lower())


class TestCacheSystemPromptAsyncWiring(unittest.IsolatedAsyncioTestCase):
    """Async path tests for cache_system_prompt kwarg wiring.

    Covers TC-006 and TC-014 from E05-F05 test plan.
    """

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_app_config_service.get_llm_resilience_config.return_value = {
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
        self.mock_app_config_service.get_llm_config.side_effect = lambda provider: {
            "model": f"{provider}-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )
        self.mock_routing_service = None  # no routing for direct calls
        self.mock_routing_config_service = Mock()
        # Anthropic supports caching; google and openai do not
        self.mock_routing_config_service.supports_prompt_caching.side_effect = (
            lambda provider: provider == "anthropic"
        )

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
            routing_config_service=self.mock_routing_config_service,
        )

    async def test_tc006_call_llm_async_anthropic_injects_cache_control(self):
        """TC-006: call_llm_async with cache_system_prompt=True for Anthropic injects
        cache_control on the system message -- identical to TC-005 (sync parity).
        inject_cache_metadata is NOT mocked -- the real injection runs in async path.
        Counter-factual: an impl wiring injection only in sync would fail this test.
        """
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
        ]
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(return_value=Mock(content="4"))

        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
            return_value=mock_client,
        ):
            result = await self.service.call_llm_async(
                messages=messages,
                provider="anthropic",
                cache_system_prompt=True,
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "4")
        langchain_messages = mock_client.ainvoke.call_args.args[0]
        system_content = langchain_messages[0].content
        self.assertIsInstance(system_content, list)
        self.assertTrue(
            any(
                isinstance(block, dict) and "cache_control" in block
                for block in system_content
            ),
            f"Expected cache_control in system message content, got: {system_content}",
        )

    async def test_tc014_call_llm_async_unsupported_provider_raises_llmservice_error(
        self,
    ):
        """TC-014: call_llm_async with provider='google' and cache_system_prompt=True
        raises LLMServiceError -- same as sync path (TC-012), async parity.
        Counter-factual: an impl that only validates in sync would not raise here.
        """
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
        ) as mock_get_client:
            with self.assertRaises(LLMServiceError) as ctx:
                await self.service.call_llm_async(
                    messages=messages,
                    provider="google",
                    cache_system_prompt=True,
                )

        error_msg = str(ctx.exception).lower()
        self.assertIn("google", error_msg)
        # Error message contains "caching" (the feature name used in the error message)
        self.assertIn("cach", error_msg)
        mock_get_client.assert_not_called()


# ---------------------------------------------------------------------------
# T-E05-F06-004: cost wired onto the async receipt (TC-001/TC-002 rerun
# against the live LLMService path, not just LLMCostCalculator in isolation).
# ---------------------------------------------------------------------------


class TestLLMServiceCostReceiptWiring(unittest.IsolatedAsyncioTestCase):
    """TC-001 / TC-002 rerun against ``LLMService.call_llm_async`` -- proves the
    real ``LLMCostCalculator`` is wired into the async receipt-construction
    path, not merely unit-testable in isolation (that's T-E05-F06-003).

    Caller-Path Contract (test-plan.md TC-001/TC-002):
      - Entrypoint: ``LLMService.call_llm_async(messages, provider=..., model=...)``
      - Lowest allowed mock seam: ``_client_factory.get_or_create_client``
        returning a client whose ``ainvoke`` carries ``usage_metadata``.
      - Forbidden mocks: ``LLMCostCalculator.calculate`` and
        ``_invoke_with_resilience_async`` are never mocked here -- real cost
        computation must run from the real ``usage_metadata`` extraction path.
    """

    PRICING_CATALOG = {
        "catalog_version": "2026-08-01",
        "currency": "USD",
        "models": {
            "anthropic": {
                "claude-sonnet-4-5": {
                    "input_per_1m": "3.00",
                    "output_per_1m": "15.00",
                    "cache_write_per_1m": "3.75",
                    "cache_read_per_1m": "0.30",
                }
            }
        },
    }

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_app_config_service.get_llm_resilience_config.return_value = {
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
        self.mock_app_config_service.get_llm_config.side_effect = lambda provider: {
            "model": f"{provider}-default-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        self.mock_app_config_service.get_llm_pricing_config.return_value = (
            self.PRICING_CATALOG
        )
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )
        self.mock_routing_config_service = Mock()
        self.mock_routing_config_service.supports_prompt_caching.return_value = False

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=Mock(),
            llm_models_config_service=self.mock_llm_models_config_service,
            routing_config_service=self.mock_routing_config_service,
        )

    async def test_tc001_full_four_bucket_cost_computation_on_live_receipt(self):
        """TC-001: response.cost.total_cost sums all four buckets, quantized to
        6 decimal places, driven through the real async receipt path."""
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            return_value=Mock(
                content="ok",
                usage_metadata={
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 400,
                },
                response_metadata={},
            )
        )
        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
            return_value=mock_client,
        ):
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-sonnet-4-5",
            )

        # Expected total per REQ-F-001: sum of tokens/1e6*rate across all four
        # buckets, quantized to 6 places. Computed here (not hardcoded) so the
        # assertion is self-checking against the formula, independent of any
        # transcription error in a worked example:
        #   1000/1e6*3.00 + 500/1e6*15.00 + 200/1e6*3.75 + 400/1e6*0.30
        #   = 0.003 + 0.0075 + 0.00075 + 0.00012 = 0.01137
        expected_total = (
            (Decimal(1000) / Decimal(1_000_000) * Decimal("3.00"))
            + (Decimal(500) / Decimal(1_000_000) * Decimal("15.00"))
            + (Decimal(200) / Decimal(1_000_000) * Decimal("3.75"))
            + (Decimal(400) / Decimal(1_000_000) * Decimal("0.30"))
        ).quantize(Decimal("0.000001"))

        self.assertIsNotNone(result.cost)
        self.assertIsInstance(result.cost.total_cost, Decimal)
        self.assertEqual(result.cost.total_cost, expected_total)
        self.assertEqual(result.cost.currency, "USD")
        self.assertEqual(result.cost.catalog_version, "2026-08-01")

    async def test_tc002_two_bucket_usage_cache_buckets_absent(self):
        """TC-002: cache buckets absent (None) contribute zero, not skipped --
        cache_write_cost/cache_read_cost are Decimal("0"), total reflects only
        input/output."""
        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            return_value=Mock(
                content="ok",
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": None,
                    "cache_read_input_tokens": None,
                },
                response_metadata={},
            )
        )
        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
            return_value=mock_client,
        ):
            result = await self.service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-sonnet-4-5",
            )

        expected_total = (Decimal(100) / Decimal(1_000_000) * Decimal("3.00")) + (
            Decimal(50) / Decimal(1_000_000) * Decimal("15.00")
        )
        self.assertEqual(
            result.cost.total_cost, expected_total.quantize(Decimal("0.000001"))
        )
        self.assertEqual(result.cost.cache_write_cost, Decimal("0"))
        self.assertEqual(result.cost.cache_read_cost, Decimal("0"))


class TestLLMServiceCostTelemetry(unittest.IsolatedAsyncioTestCase):
    """TC-022 / TC-023 / TC-024: cost span attribute, error-isolated (REQ-F-010).

    Caller-Path Contract (test-plan.md TC-022):
      - Entrypoint: ``LLMService(..., telemetry_service=telemetry).call_llm_async(...)``
        with ``telemetry_service`` passed at construction -- matching the
        established pattern at ``test_llm_service_streaming.py:63,72``
        (``_make_llm_service(telemetry_service=...)``).
      - Lowest allowed mock seam: ``_client_factory.get_or_create_client`` for
        the provider client; ``telemetry.set_span_attributes`` is asserted via
        call-argument inspection.
      - Forbidden mocks: ``_set_current_span_attributes`` is NOT mocked into a
        no-op -- it internally calls the real ``opentelemetry.trace.get_current_span``,
        so that OTel API is patched to return a recording fake span (the
        established pattern in ``tests/unit/services/test_llm_service_telemetry.py::TestTokenCountExtraction``),
        and assertions run against the mocked ``telemetry.set_span_attributes``
        call arguments.
      - Counter-factual: an impl that computes ``response.cost`` correctly but
        never calls the span-attribute helper (or uses the wrong key) would
        still pass a test that only checked ``response.cost`` -- asserting on
        the telemetry mock's call arguments catches that.
    """

    PRICING_CATALOG = {
        "catalog_version": "2026-08-01",
        "currency": "USD",
        "models": {
            "anthropic": {
                "claude-sonnet-4-5": {
                    "input_per_1m": "3.00",
                    "output_per_1m": "15.00",
                },
            },
        },
    }
    EMPTY_CATALOG = {"catalog_version": None, "currency": "USD", "models": {}}

    def _make_service(self, pricing_config, telemetry_service):
        mock_logging_service = MockServiceFactory.create_mock_logging_service()
        mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        mock_app_config_service.get_llm_resilience_config.return_value = {
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
        mock_app_config_service.get_llm_config.side_effect = lambda provider: {
            "model": f"{provider}-default-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        mock_app_config_service.get_llm_pricing_config.return_value = pricing_config
        mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )
        mock_routing_config_service = Mock()
        mock_routing_config_service.supports_prompt_caching.return_value = False

        return LLMService(
            configuration=mock_app_config_service,
            logging_service=mock_logging_service,
            routing_service=Mock(),
            llm_models_config_service=mock_llm_models_config_service,
            routing_config_service=mock_routing_config_service,
            telemetry_service=telemetry_service,
        )

    @staticmethod
    def _mock_recording_span():
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        return mock_span

    @staticmethod
    def _collect_span_attributes(telemetry):
        all_attrs = {}
        for call in telemetry.set_span_attributes.call_args_list:
            call_args = call[0]
            if len(call_args) > 1:
                all_attrs.update(call_args[1])
        return all_attrs

    @patch("opentelemetry.trace.get_current_span")
    async def test_tc022_priced_call_records_cost_span_attribute(self, mock_get_span):
        """TC-022: priced call + enabled telemetry -> set_span_attributes is
        called with a cost attribute equal to float(response.cost.total_cost)."""
        mock_get_span.return_value = self._mock_recording_span()
        telemetry = MagicMock(name="telemetry_service")
        service = self._make_service(self.PRICING_CATALOG, telemetry)

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            return_value=Mock(
                content="ok",
                usage_metadata={
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": None,
                    "cache_read_input_tokens": None,
                },
                response_metadata={},
            )
        )
        with patch.object(
            service._client_factory, "get_or_create_client", return_value=mock_client
        ):
            result = await service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-sonnet-4-5",
            )

        self.assertIsNotNone(result.cost)
        all_attrs = self._collect_span_attributes(telemetry)
        self.assertIn(GEN_AI_USAGE_COST, all_attrs)
        self.assertEqual(all_attrs[GEN_AI_USAGE_COST], float(result.cost.total_cost))

    @patch("opentelemetry.trace.get_current_span")
    async def test_tc023_unpriced_call_does_not_set_cost_attribute(self, mock_get_span):
        """TC-023: no pricing catalog configured -> cost is None -> no cost
        attribute is set (absence is meaningful; zero is not), even though
        other attributes (e.g. token counts) are legitimately recorded on the
        same span."""
        mock_get_span.return_value = self._mock_recording_span()
        telemetry = MagicMock(name="telemetry_service")
        service = self._make_service(self.EMPTY_CATALOG, telemetry)

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            return_value=Mock(
                content="ok",
                usage_metadata={
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": None,
                    "cache_read_input_tokens": None,
                },
                response_metadata={},
            )
        )
        with patch.object(
            service._client_factory, "get_or_create_client", return_value=mock_client
        ):
            result = await service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-sonnet-4-5",
            )

        self.assertIsNone(result.cost)
        all_attrs = self._collect_span_attributes(telemetry)
        self.assertNotIn(GEN_AI_USAGE_COST, all_attrs)

    @patch("opentelemetry.trace.get_current_span")
    async def test_tc024_telemetry_failure_does_not_fail_the_call(self, mock_get_span):
        """TC-024: telemetry.set_span_attributes raises -> call_llm_async still
        returns the real successful LLMResponse (error-isolation swallows the
        telemetry failure), not an exception and not a degraded response."""
        mock_get_span.return_value = self._mock_recording_span()
        telemetry = MagicMock(name="telemetry_service")
        telemetry.set_span_attributes.side_effect = RuntimeError("otel exporter down")
        service = self._make_service(self.PRICING_CATALOG, telemetry)

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(
            return_value=Mock(
                content="ok",
                usage_metadata={
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": None,
                    "cache_read_input_tokens": None,
                },
                response_metadata={},
            )
        )
        with patch.object(
            service._client_factory, "get_or_create_client", return_value=mock_client
        ):
            result = await service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-sonnet-4-5",
            )

        self.assertEqual(result.text, "ok")
        self.assertIsNotNone(result.cost)

    @patch("opentelemetry.trace.get_current_span")
    async def test_tc024_provider_failure_not_masked_by_telemetry_failure(
        self, mock_get_span
    ):
        """TC-024 (negative cross-check): when BOTH the provider call and
        telemetry fail, the exception surfaced is the provider's failure --
        never the telemetry RuntimeError -- proving telemetry failure never
        masquerades as or replaces the real outcome."""
        mock_get_span.return_value = self._mock_recording_span()
        telemetry = MagicMock(name="telemetry_service")
        telemetry.set_span_attributes.side_effect = RuntimeError("otel exporter down")
        service = self._make_service(self.PRICING_CATALOG, telemetry)

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(side_effect=RuntimeError("Invalid api_key"))

        with patch.object(
            service._client_factory, "get_or_create_client", return_value=mock_client
        ):
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await service.call_llm_async(
                    messages=[{"role": "user", "content": "hi"}],
                    provider="anthropic",
                    model="claude-sonnet-4-5",
                )

        self.assertIsInstance(ctx.exception.cause, LLMConfigurationError)
        self.assertNotIn("otel exporter down", str(ctx.exception))
