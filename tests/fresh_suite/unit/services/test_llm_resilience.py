"""
Unit tests for LLM resilience — retry with backoff + circuit breaker.

Validates that _invoke_with_resilience() in LLMService correctly:
- retries on transient errors (timeout, rate limit)
- does NOT retry on auth/dependency errors
- applies exponential backoff with jitter
- respects circuit breaker open/half-open/closed states
- records success/failure to the circuit breaker
- fallback tiers use the resilience layer
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMTimeoutError,
)
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


def _make_service(**overrides) -> LLMService:
    """Create an LLMService with mocked dependencies for testing."""
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_config = MockServiceFactory.create_mock_app_config_service()

    # Provide resilience config defaults
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 3,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,  # deterministic for testing
        },
        "circuit_breaker": {
            "failure_threshold": 3,
            "reset_timeout": 60,
        },
    }
    # Provider config
    mock_config.get_llm_config.return_value = {
        "model": "test-model",
        "api_key": "test-key",
    }

    mock_routing = Mock()
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
        **overrides,
    )
    return svc


class TestInvokeWithResilience(unittest.TestCase):
    """Tests for LLMService._invoke_with_resilience()."""

    def setUp(self):
        self.svc = _make_service()
        self.mock_client = Mock()
        self.msgs = [Mock()]  # fake langchain messages

    # -- happy path -----------------------------------------------------------

    def test_success_on_first_attempt(self):
        self.mock_client.invoke.return_value = Mock(content="hello")

        result = self.svc._invoke_with_resilience(
            self.mock_client, self.msgs, "openai", "gpt-4"
        )

        self.assertEqual(result, "hello")
        self.mock_client.invoke.assert_called_once()

    def test_success_records_to_circuit_breaker(self):
        self.mock_client.invoke.return_value = Mock(content="ok")

        self.svc._invoke_with_resilience(self.mock_client, self.msgs, "openai", "gpt-4")

        # Circuit breaker should have no failures
        self.assertEqual(self.svc._circuit_breaker.failures, {})

    # -- retry on transient errors -------------------------------------------

    @patch("agentmap.services.llm_service.time.sleep")
    def test_retry_succeeds_after_transient_failure(self, mock_sleep):
        self.mock_client.invoke.side_effect = [
            RuntimeError("Connection timeout"),
            Mock(content="recovered"),
        ]

        result = self.svc._invoke_with_resilience(
            self.mock_client, self.msgs, "openai", "gpt-4"
        )

        self.assertEqual(result, "recovered")
        self.assertEqual(self.mock_client.invoke.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("agentmap.services.llm_service.time.sleep")
    def test_retries_exhaust_then_raises(self, mock_sleep):
        self.mock_client.invoke.side_effect = RuntimeError("Connection timeout")

        with self.assertRaises(LLMTimeoutError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        # 3 attempts = 3 invocations
        self.assertEqual(self.mock_client.invoke.call_count, 3)
        # 2 sleeps (between attempts 1→2 and 2→3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("agentmap.services.llm_service.time.sleep")
    def test_rate_limit_is_retried(self, mock_sleep):
        self.mock_client.invoke.side_effect = [
            RuntimeError("429 Too Many Requests"),
            Mock(content="ok"),
        ]

        result = self.svc._invoke_with_resilience(
            self.mock_client, self.msgs, "openai", "gpt-4"
        )

        self.assertEqual(result, "ok")
        self.assertEqual(self.mock_client.invoke.call_count, 2)

    # -- no retry on non-retryable errors ------------------------------------

    def test_auth_error_not_retried(self):
        self.mock_client.invoke.side_effect = RuntimeError("Invalid api_key")

        with self.assertRaises(LLMConfigurationError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        self.assertEqual(self.mock_client.invoke.call_count, 1)

    def test_dependency_error_not_retried(self):
        self.mock_client.invoke.side_effect = ImportError(
            "No module named 'langchain_openai'"
        )

        with self.assertRaises(LLMDependencyError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        self.assertEqual(self.mock_client.invoke.call_count, 1)

    # -- backoff timing ------------------------------------------------------

    @patch("agentmap.services.llm_service.time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep):
        self.mock_client.invoke.side_effect = RuntimeError("Connection timeout")

        with self.assertRaises(LLMTimeoutError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        # jitter=False, backoff_base=2.0: delays = 2^0=1.0, 2^1=2.0
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertAlmostEqual(delays[0], 1.0)
        self.assertAlmostEqual(delays[1], 2.0)

    @patch("agentmap.services.llm_service.time.sleep")
    @patch("agentmap.services.llm_service.random.random", return_value=0.5)
    def test_jitter_applied_when_enabled(self, mock_random, mock_sleep):
        # Enable jitter
        self.svc._resilience_config["retry"]["jitter"] = True
        self.mock_client.invoke.side_effect = [
            RuntimeError("Connection timeout"),
            Mock(content="ok"),
        ]

        self.svc._invoke_with_resilience(self.mock_client, self.msgs, "openai", "gpt-4")

        # With jitter: delay = base^0 * (0.5 + random()) = 1.0 * 1.0 = 1.0
        delay = mock_sleep.call_args[0][0]
        self.assertAlmostEqual(delay, 1.0)

    # -- circuit breaker -----------------------------------------------------

    def test_circuit_open_raises_immediately(self):
        cb = self.svc._circuit_breaker
        # Manually open the circuit
        cb.opened_at["openai:gpt-4"] = 999999999999.0  # far future

        with self.assertRaises(LLMProviderError) as ctx:
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        self.assertIn("Circuit breaker open", str(ctx.exception))
        self.mock_client.invoke.assert_not_called()

    @patch("agentmap.services.llm_service.time.sleep")
    def test_circuit_opens_after_threshold_failures(self, mock_sleep):
        self.mock_client.invoke.side_effect = RuntimeError("Connection timeout")

        # threshold=3, max_attempts=3 → one call exhausts 3 attempts
        with self.assertRaises(LLMTimeoutError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        cb = self.svc._circuit_breaker
        # After 1 _invoke_with_resilience call with all retries exhausted,
        # 1 failure is recorded. Need 2 more to open the circuit.
        self.assertEqual(cb.failures.get("openai:gpt-4", 0), 1)

        # Two more failed calls
        with self.assertRaises(LLMTimeoutError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )
        with self.assertRaises(LLMTimeoutError):
            self.svc._invoke_with_resilience(
                self.mock_client, self.msgs, "openai", "gpt-4"
            )

        # Now should be open
        self.assertIn("openai:gpt-4", cb.opened_at)

    def test_circuit_half_open_allows_retry_after_reset(self):
        cb = self.svc._circuit_breaker
        # Set opened_at far in the past so reset_timeout has elapsed
        cb.opened_at["openai:gpt-4"] = 0.0
        cb.failures["openai:gpt-4"] = 3

        self.mock_client.invoke.return_value = Mock(content="recovered")

        result = self.svc._invoke_with_resilience(
            self.mock_client, self.msgs, "openai", "gpt-4"
        )

        self.assertEqual(result, "recovered")
        # Circuit should be closed after success
        self.assertNotIn("openai:gpt-4", cb.opened_at)
        self.assertNotIn("openai:gpt-4", cb.failures)


class TestFallbackUsesResilience(unittest.TestCase):
    """Verify fallback tiers invoke through the resilience layer."""

    def test_fallback_handler_has_invoke_fn(self):
        svc = _make_service()
        self.assertIsNotNone(svc._fallback_handler._invoke_fn)
        self.assertEqual(svc._fallback_handler._invoke_fn, svc._invoke_with_resilience)


class TestRoutingStatsIncludesCircuitBreaker(unittest.TestCase):
    """Verify get_routing_stats() includes circuit breaker state."""

    def test_stats_contain_circuit_breaker_section(self):
        svc = _make_service()
        svc.routing_service.get_routing_stats.return_value = {"requests": 10}

        stats = svc.get_routing_stats()

        self.assertIn("circuit_breaker", stats)
        self.assertIn("open_circuits", stats["circuit_breaker"])
        self.assertIn("failure_counts", stats["circuit_breaker"])


if __name__ == "__main__":
    unittest.main()
