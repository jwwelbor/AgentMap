"""Regression tests for T-E05-F02-009: temperature-sensitive client caching."""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.llm_client_factory import LLMClientFactory
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMClientFactoryCacheKey(unittest.TestCase):
    """Verify client caching distinguishes configs that differ by temperature."""

    def setUp(self):
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.factory = LLMClientFactory(self.logging_service)

    def test_same_config_reuses_cached_client(self):
        """Same provider/model/api_key/max_tokens/temperature should hit the cache."""
        config = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "max_tokens": 256,
        }
        first_client = Mock(name="first_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            return_value=first_client,
        ) as mock_create:
            client_a = self.factory.get_or_create_client("openai", config)
            client_b = self.factory.get_or_create_client("openai", dict(config))

        self.assertIs(client_a, client_b)
        mock_create.assert_called_once_with("openai", config)

    def test_different_temperature_creates_distinct_cached_clients(self):
        """Different temperatures must not collide in the client cache key."""
        cooler_config = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 256,
        }
        hotter_config = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.9,
            "max_tokens": 256,
        }
        cool_client = Mock(name="cool_client")
        hot_client = Mock(name="hot_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[cool_client, hot_client],
        ) as mock_create:
            first = self.factory.get_or_create_client("openai", cooler_config)
            second = self.factory.get_or_create_client("openai", hotter_config)

        self.assertIs(first, cool_client)
        self.assertIs(second, hot_client)
        self.assertIsNot(first, second)
        self.assertEqual(
            mock_create.call_count,
            2,
            "temperature must participate in the cache key, otherwise the "
            "second config reuses the first client",
        )


if __name__ == "__main__":
    unittest.main()
