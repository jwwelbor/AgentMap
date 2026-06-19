"""
Tests for LLMClientFactory cache key and streaming dimension.

Original: Regression tests for T-E05-F02-009: temperature-sensitive client caching.
Extended: T-E06-F02-001: streaming dimension in cache key + regression coverage.
"""

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
        """Same provider/model/api_key/max_tokens/temperature should hit the cache.

        TC-F02-REG-1: updated assertion per T-E06-F02-001 CRITICAL note.
        After adding streaming param to _create_langchain_client, internal call
        becomes ("openai", config, False) — not ("openai", config).
        """
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
        mock_create.assert_called_once_with("openai", config, False)

    def test_different_temperature_creates_distinct_cached_clients(self):
        """Different temperatures must not collide in the client cache key.

        TC-F02-REG-2: no assertion change needed (only call_count checked).
        """
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


class TestLLMClientFactoryStreamingCacheKey(unittest.TestCase):
    """
    T-E06-F02-001: streaming dimension in cache key.

    Covers: AC-1, AC-3, AC-9 (KEY tests) and REQ-NF-001/REQ-NF-003 (REG/BND).
    Mocking layer 1: patch._create_langchain_client on the instance.
    """

    def setUp(self):
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.factory = LLMClientFactory(self.logging_service)
        self._base_config = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "max_tokens": 256,
        }

    def test_streaming_and_non_streaming_produce_two_distinct_clients(self):
        """TC-F02-KEY-1: same (provider, config), streaming=False then streaming=True.

        Construction must be called twice; returned objects must not be the same.
        AC-1, AC-3.
        """
        ns_client = Mock(name="ns_client")
        s_client = Mock(name="s_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[ns_client, s_client],
        ) as mock_create:
            got_ns = self.factory.get_or_create_client(
                "openai", self._base_config, streaming=False
            )
            got_s = self.factory.get_or_create_client(
                "openai", self._base_config, streaming=True
            )

        self.assertEqual(
            mock_create.call_count, 2, "Must construct once per streaming value"
        )
        self.assertIs(got_ns, ns_client)
        self.assertIs(got_s, s_client)
        self.assertIsNot(
            got_ns, got_s, "Streaming and non-streaming must be distinct objects"
        )

    def test_repeated_calls_hit_cache_and_return_own_client(self):
        """TC-F02-KEY-2: after KEY-1, repeat each call — no new constructions.

        Each repeated call returns its own cached client, never the other.
        AC-3.
        """
        ns_client = Mock(name="ns_client")
        s_client = Mock(name="s_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[ns_client, s_client],
        ) as mock_create:
            # First calls — establish cache
            self.factory.get_or_create_client(
                "openai", self._base_config, streaming=False
            )
            self.factory.get_or_create_client(
                "openai", self._base_config, streaming=True
            )
            # Repeat each call — should hit cache, not construct again
            repeated_ns = self.factory.get_or_create_client(
                "openai", self._base_config, streaming=False
            )
            repeated_s = self.factory.get_or_create_client(
                "openai", self._base_config, streaming=True
            )

        self.assertEqual(
            mock_create.call_count, 2, "No new constructions after cache warm-up"
        )
        self.assertIs(
            repeated_ns,
            ns_client,
            "Repeated non-streaming must return its own cached client",
        )
        self.assertIs(
            repeated_s, s_client, "Repeated streaming must return its own cached client"
        )
        self.assertIsNot(
            repeated_ns, repeated_s, "Must never return the other streaming variant"
        )

    def test_cache_keys_end_with_correct_streaming_suffix(self):
        """TC-F02-KEY-3: inspect _clients keys directly.

        One key ends '_False', other ends '_True'; they share a common prefix.
        AC-1.
        """
        ns_client = Mock(name="ns_client")
        s_client = Mock(name="s_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[ns_client, s_client],
        ):
            self.factory.get_or_create_client(
                "openai", self._base_config, streaming=False
            )
            self.factory.get_or_create_client(
                "openai", self._base_config, streaming=True
            )

        keys = list(self.factory._clients.keys())
        self.assertEqual(len(keys), 2)

        false_keys = [k for k in keys if k.endswith("_False")]
        true_keys = [k for k in keys if k.endswith("_True")]
        self.assertEqual(len(false_keys), 1, "Exactly one key should end with '_False'")
        self.assertEqual(len(true_keys), 1, "Exactly one key should end with '_True'")

        # Shared prefix — everything before the last '_'-separated segment
        ns_key = false_keys[0]
        s_key = true_keys[0]
        self.assertEqual(
            ns_key.rsplit("_", 1)[0],
            s_key.rsplit("_", 1)[0],
            "Streaming and non-streaming keys must share the same prefix",
        )

    def test_pre_fix_collision_guard(self):
        """TC-F02-KEY-4: pre-fix collision guard — the "fails pre-fix" test.

        Old-style key (no streaming segment) is identical for both inputs,
        demonstrating the collision the fix removes. The new implementation
        produces 2 distinct clients (collision fixed).
        AC-9, AC-1, AC-3.
        """
        config = dict(self._base_config)

        # Demonstrate that the old key (without streaming segment) collides
        def old_style_key(provider, cfg):
            max_tok = cfg.get("max_tokens")
            temperature = cfg.get("temperature", 0.7)
            return (
                f"{provider}_{cfg.get('model')}_{cfg.get('api_key', '')[:8]}_"
                f"{max_tok}_{temperature!r}"
            )

        old_key_ns = old_style_key("openai", config)
        old_key_s = old_style_key("openai", config)
        self.assertEqual(
            old_key_ns,
            old_key_s,
            "Old-style keys (no streaming segment) must collide — this is the pre-fix bug",
        )

        # Under the fixed implementation, same inputs produce 2 distinct clients
        ns_client = Mock(name="ns_client")
        s_client = Mock(name="s_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[ns_client, s_client],
        ) as mock_create:
            got_ns = self.factory.get_or_create_client(
                "openai", config, streaming=False
            )
            got_s = self.factory.get_or_create_client("openai", config, streaming=True)

        self.assertEqual(
            mock_create.call_count, 2, "Fixed impl must construct two clients, not one"
        )
        self.assertIsNot(
            got_ns, got_s, "Fixed impl must not collide streaming and non-streaming"
        )

    def test_exact_cache_key_shape_and_segment_order(self):
        """TC-F02-KEY-5: exact key string pin.

        For a fixed config, asserts the full key strings match exactly,
        proving streaming is appended last and no other segment is reordered.
        REQ-NF-001, AC-1, REQ-F-001.
        """
        config = {
            "api_key": "testkey1",
            "model": "gpt-4",
            "temperature": 0.4,
            "max_tokens": 256,
        }

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[Mock(), Mock()],
        ):
            self.factory.get_or_create_client("openai", config, streaming=False)
            self.factory.get_or_create_client("openai", config, streaming=True)

        keys = list(self.factory._clients.keys())
        false_key = next(k for k in keys if k.endswith("_False"))
        true_key = next(k for k in keys if k.endswith("_True"))

        self.assertEqual(
            false_key,
            "openai_gpt-4_testkey1_256_0.4_False",
            "Non-streaming key must match exact shape: provider_model_apikey8_max_tokens_temp!r_False",
        )
        self.assertEqual(
            true_key,
            "openai_gpt-4_testkey1_256_0.4_True",
            "Streaming key must match exact shape: provider_model_apikey8_max_tokens_temp!r_True",
        )

    def test_api_key_truncation_equality_preservation(self):
        """TC-F02-KEY-6: api_key[:8] equality-preservation / truncation pin.

        Two keys sharing the same first 8 chars but differing afterward produce
        one construction (cache hit). A key differing in first 8 chars is a miss.
        REQ-NF-001, REQ-NF-003, AC-2.
        """
        # Two api_keys with same first 8 chars — should produce a cache hit
        config1 = dict(self._base_config)
        config1["api_key"] = "abcdefgh_LONGER1"
        config2 = dict(self._base_config)
        config2["api_key"] = "abcdefgh_LONGER2"

        # An api_key that differs in the first 8 chars — should be a cache miss
        config3 = dict(self._base_config)
        config3["api_key"] = "XXXXXXXX_anything"

        first_client = Mock(name="first_client")
        second_client = Mock(name="second_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=[first_client, second_client],
        ) as mock_create:
            # Same first 8 chars — second call should hit cache
            got1 = self.factory.get_or_create_client("openai", config1, streaming=False)
            got2 = self.factory.get_or_create_client("openai", config2, streaming=False)
            # Different first 8 chars — should be a cache miss
            got3 = self.factory.get_or_create_client("openai", config3, streaming=False)

        self.assertIs(got1, first_client)
        self.assertIs(
            got2,
            first_client,
            "Keys sharing same api_key[:8] must be a cache hit — extra material must NOT be in key",
        )
        self.assertIs(
            got3, second_client, "Keys with different api_key[:8] must be a cache miss"
        )
        self.assertEqual(
            mock_create.call_count,
            2,
            "Exactly 2 constructions: one for same-first-8 pair, one for distinct-prefix key",
        )

    def test_default_streaming_arg_behaves_as_non_streaming(self):
        """TC-F02-REG-3: calling with no streaming arg behaves as non-streaming.

        Key ends '_False'; second identical call hits cache.
        AC-8.
        """
        config = dict(self._base_config)
        client = Mock(name="default_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            return_value=client,
        ) as mock_create:
            # Call with NO streaming argument (default)
            got1 = self.factory.get_or_create_client("openai", config)
            got2 = self.factory.get_or_create_client("openai", config)

        self.assertEqual(mock_create.call_count, 1, "Second call must hit cache")
        self.assertIs(got1, client)
        self.assertIs(got2, client)

        # Key must end with _False
        keys = list(self.factory._clients.keys())
        self.assertEqual(len(keys), 1)
        self.assertTrue(
            keys[0].endswith("_False"),
            f"Default (no streaming arg) key must end '_False', got: {keys[0]}",
        )

    def test_non_streaming_distinct_dims_still_distinct(self):
        """TC-F02-REG-4: non-streaming calls differing in model/max_tokens/api_key.

        Each differing dimension still produces distinct clients — appending
        streaming segment must not collapse any existing dimension.
        AC-2, REQ-NF-001.
        """
        base = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "max_tokens": 256,
        }
        # Different model
        config_diff_model = dict(base)
        config_diff_model["model"] = "gpt-3.5-turbo"
        # Different max_tokens
        config_diff_tokens = dict(base)
        config_diff_tokens["max_tokens"] = 512
        # Different api_key prefix
        config_diff_key = dict(base)
        config_diff_key["api_key"] = "other_key_1234"

        clients = [Mock(name=f"client_{i}") for i in range(4)]

        with patch.object(
            self.factory,
            "_create_langchain_client",
            side_effect=clients,
        ) as mock_create:
            self.factory.get_or_create_client("openai", base)
            self.factory.get_or_create_client("openai", config_diff_model)
            self.factory.get_or_create_client("openai", config_diff_tokens)
            self.factory.get_or_create_client("openai", config_diff_key)

        self.assertEqual(
            mock_create.call_count, 4, "Each differing dimension must be a cache miss"
        )

    def test_optional_fields_default_rendering_in_key(self):
        """TC-F02-REG-5: max_tokens absent -> '_None_'; temperature absent -> '_0.7_'.

        Pins the exact rendering of optional-field defaults in the cache key.
        REQ-NF-001, AC-1.
        """
        # Config with max_tokens absent (omitted)
        config_no_max = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
        }
        # Config with temperature absent (should default to 0.7)
        config_no_temp = {
            "api_key": "test_key_123456",
            "model": "gpt-4o-mini",
            "max_tokens": 256,
        }

        factory_no_max = LLMClientFactory(self.logging_service)
        factory_no_temp = LLMClientFactory(self.logging_service)

        with patch.object(
            factory_no_max,
            "_create_langchain_client",
            return_value=Mock(),
        ):
            factory_no_max.get_or_create_client(
                "openai", config_no_max, streaming=False
            )

        with patch.object(
            factory_no_temp,
            "_create_langchain_client",
            return_value=Mock(),
        ):
            factory_no_temp.get_or_create_client(
                "openai", config_no_temp, streaming=False
            )

        key_no_max = list(factory_no_max._clients.keys())[0]
        key_no_temp = list(factory_no_temp._clients.keys())[0]

        self.assertIn(
            "_None_",
            key_no_max,
            f"Key for absent max_tokens must contain '_None_', got: {key_no_max}",
        )
        self.assertIn(
            "_0.7_",
            key_no_temp,
            f"Key for absent temperature must contain '_0.7_', got: {key_no_temp}",
        )

    def test_cache_is_plain_dict_with_no_lock(self):
        """TC-F02-BND-2: cache is a plain dict; no lock attribute on factory.

        AC-12, REQ-NF-002.
        """
        self.assertIsInstance(
            self.factory._clients,
            dict,
            "_clients must be a plain dict (no OrderedDict, no custom cache)",
        )
        self.assertNotIsInstance(
            self.factory._clients,
            type(None),
        )
        # No asyncio.Lock or threading.Lock attribute
        import asyncio
        import threading

        for attr_name in vars(self.factory):
            attr = getattr(self.factory, attr_name)
            self.assertNotIsInstance(
                attr,
                asyncio.Lock,
                f"Factory must not have an asyncio.Lock attribute (found at {attr_name!r})",
            )
            self.assertNotIsInstance(
                attr,
                type(threading.Lock()),
                f"Factory must not have a threading.Lock attribute (found at {attr_name!r})",
            )

    def test_two_first_use_streaming_calls_same_triple_one_construction(self):
        """TC-F02-BND-3: two sequential first-use streaming calls for same triple.

        Second call hits cache; construction count stays 1 for that triple.
        AC-3, REQ-NF-002.
        """
        config = dict(self._base_config)
        s_client = Mock(name="s_client")

        with patch.object(
            self.factory,
            "_create_langchain_client",
            return_value=s_client,
        ) as mock_create:
            got1 = self.factory.get_or_create_client("openai", config, streaming=True)
            got2 = self.factory.get_or_create_client("openai", config, streaming=True)

        self.assertEqual(
            mock_create.call_count,
            1,
            "Two calls for same (provider, config, streaming=True) triple must construct only once",
        )
        self.assertIs(got1, s_client)
        self.assertIs(got2, s_client)


if __name__ == "__main__":
    unittest.main()
