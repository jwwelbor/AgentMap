"""
Async contract tests for LLM service protocols and test doubles.
"""

import unittest
from unittest.mock import AsyncMock, Mock, create_autospec, patch

from agentmap.exceptions import LLMConfigurationError, LLMTimeoutError
from agentmap.exceptions.service_exceptions import LLMResolvedCallError
from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols import LLMServiceProtocol
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

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
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
