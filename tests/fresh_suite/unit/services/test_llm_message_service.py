"""
Unit tests for LLMMessageService — inject_cache_metadata() and rename verification.

Covers TC-001, TC-002, TC-003, TC-004, TC-007 from E05-F05 test plan.
Covers TC-015, TC-016, TC-017, TC-031, TC-031a from E05-F06 test plan
(T-E05-F06-007: tool-result round-trip in message conversion).
"""

import logging
import unittest
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# NOTE: These imports will fail until llm_message_service.py exists (RED phase).
from agentmap.exceptions import LLMServiceError
from agentmap.services.llm_message_service import LLMMessageService
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


class TestInjectCacheMetadataPlainString(unittest.TestCase):
    """TC-001: Plain string system message wrapped for Anthropic."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_plain_string_system_message_wrapped_with_cache_control(self):
        """
        TC-001: inject_cache_metadata converts plain string system content to
        structured list with cache_control for Anthropic.

        Counter-factual: a buggy impl returning messages unchanged would fail
        the assertion that content is a list with a cache_control key.
        """
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )

        # System message content must be a list
        system_content = result[0]["content"]
        self.assertIsInstance(system_content, list)

        # Must contain at least one block with type=text and cache_control
        text_blocks = [
            b for b in system_content if isinstance(b, dict) and b.get("type") == "text"
        ]
        self.assertGreater(len(text_blocks), 0, "No text blocks in transformed content")
        last_text_block = text_blocks[-1]
        self.assertIn("cache_control", last_text_block)
        self.assertEqual(last_text_block["cache_control"], {"type": "ephemeral"})
        # Original text preserved
        self.assertEqual(last_text_block["text"], "You are a helpful assistant.")

        # User message unchanged
        self.assertEqual(result[1], {"role": "user", "content": "Hello"})

    def test_original_messages_list_not_mutated(self):
        """TC-001: Defensive copy — original messages list is not mutated."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        original_content = messages[0]["content"]
        self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        # Original must still be a string
        self.assertIsInstance(messages[0]["content"], str)
        self.assertEqual(messages[0]["content"], original_content)

    def test_system_message_not_at_position_zero(self):
        """TC-001 edge case: system message after user message is correctly identified by role."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "You are a helpful assistant."},
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        system_result = next(m for m in result if m["role"] == "system")
        self.assertIsInstance(system_result["content"], list)
        self.assertIn("cache_control", system_result["content"][-1])


class TestInjectCacheMetadataNoSystemMessage(unittest.TestCase):
    """TC-002: No system message returns unchanged, no error."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_no_system_message_returns_unchanged(self):
        """
        TC-002: Messages without a system role entry are returned unchanged.

        Counter-factual: a buggy impl that crashes on missing system message
        would raise KeyError or AttributeError.
        """
        messages = [{"role": "user", "content": "Hello"}]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        self.assertEqual(result, [{"role": "user", "content": "Hello"}])

    def test_empty_messages_list_returns_empty(self):
        """TC-002 edge case: empty messages list returns empty without error."""
        result = self.service.inject_cache_metadata(
            [], provider="anthropic", cache_system_prompt=True
        )
        self.assertEqual(result, [])

    def test_only_assistant_messages_returns_unchanged(self):
        """TC-002 edge case: messages with only assistant roles returned unchanged."""
        messages = [{"role": "assistant", "content": "I'm here."}]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        self.assertEqual(result, [{"role": "assistant", "content": "I'm here."}])


class TestInjectCacheMetadataStructuredContentList(unittest.TestCase):
    """TC-003: Structured content list gets cache_control on last text block."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_structured_content_list_cache_control_on_last_text_block(self):
        """
        TC-003: When system content is already a list, cache_control is added to
        the last text block that does not already have cache_control.

        Counter-factual: an impl that only handles string content would leave
        structured content unmodified; cache_control assertion would fail.
        """
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are a helpful assistant."},
                    {"type": "text", "text": "Focus on brevity."},
                ],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )

        content = result[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 2, "Block count must not change")

        # First block: no cache_control
        self.assertNotIn("cache_control", content[0])
        # Last block: has cache_control
        self.assertIn("cache_control", content[1])
        self.assertEqual(content[1]["cache_control"], {"type": "ephemeral"})

    def test_single_text_block_in_list_gets_cache_control(self):
        """TC-003 edge case: single text block in list gets cache_control."""
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are helpful."}],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        content = result[0]["content"]
        self.assertIn("cache_control", content[0])

    def test_non_text_blocks_do_not_get_cache_control(self):
        """TC-003 negative: non-text blocks (e.g., image_url type) do NOT get cache_control."""
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are helpful."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "http://example.com/img.png"},
                    },
                ],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        content = result[0]["content"]
        # The image block must not have cache_control
        image_block = content[1]
        self.assertNotIn("cache_control", image_block)
        # The text block (last text block) gets cache_control
        text_block = content[0]
        self.assertIn("cache_control", text_block)


class TestInjectCacheMetadataOpenAINoOp(unittest.TestCase):
    """TC-004: OpenAI provider returns messages unchanged."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_openai_provider_messages_returned_unchanged(self):
        """
        TC-004: inject_cache_metadata with provider=openai returns messages unchanged.

        Counter-factual: a buggy impl that injects Anthropic cache_control blocks
        for OpenAI would mutate messages; this assertion catches it.
        """
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="openai", cache_system_prompt=True
        )
        # Content must remain a plain string, not a list
        self.assertIsInstance(result[0]["content"], str)
        self.assertEqual(result[0]["content"], "You are helpful.")
        self.assertNotIn("cache_control", result[0])

    def test_openai_no_cache_control_anywhere_in_result(self):
        """TC-004 negative: no cache_control key anywhere in returned messages for OpenAI."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="openai", cache_system_prompt=True
        )
        for msg in result:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    self.assertNotIn("cache_control", block)
            else:
                self.assertNotIn("cache_control", msg)

    def test_openai_structured_content_returned_unchanged(self):
        """TC-004 edge case: provider=openai with structured content still returned unchanged."""
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are helpful."}],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="openai", cache_system_prompt=True
        )
        content = result[0]["content"]
        # Should be returned as-is without cache_control added
        self.assertNotIn("cache_control", content[0])


class TestInjectCacheMetadataIdempotency(unittest.TestCase):
    """TC-007: Idempotency — already-cached block not double-wrapped."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_already_cached_block_not_double_wrapped(self):
        """
        TC-007: inject_cache_metadata with already-cached structured content does
        not double-wrap or add a second cache_control.

        Counter-factual: an impl that unconditionally injects would add a second
        cache_control or create a second wrapped block; Anthropic API would reject it.
        """
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are helpful.",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )

        content = result[0]["content"]
        # Exactly one text block — no new block added
        self.assertEqual(len(content), 1)
        # Existing cache_control is present and unchanged
        self.assertEqual(content[0]["cache_control"], {"type": "ephemeral"})
        # No duplicate or nested cache_control
        self.assertEqual(
            list(k for k in content[0] if k == "cache_control"), ["cache_control"]
        )

    def test_multiple_blocks_last_already_cached_unchanged(self):
        """TC-007 edge case: multiple blocks where last has cache_control; last block unchanged."""
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "First block."},
                    {
                        "type": "text",
                        "text": "Second block.",
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            }
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=True
        )
        content = result[0]["content"]
        self.assertEqual(len(content), 2)
        # First block: still no cache_control
        self.assertNotIn("cache_control", content[0])
        # Last block: cache_control unchanged (not double-wrapped)
        self.assertEqual(content[1]["cache_control"], {"type": "ephemeral"})


class TestInjectCacheMetadataCacheSystemPromptFalse(unittest.TestCase):
    """cache_system_prompt=False is a zero-cost no-op."""

    def setUp(self):
        self.service = LLMMessageService()

    def test_cache_system_prompt_false_returns_unchanged(self):
        """When cache_system_prompt=False, messages are returned unchanged regardless of provider."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        result = self.service.inject_cache_metadata(
            messages, provider="anthropic", cache_system_prompt=False
        )
        self.assertIsInstance(result[0]["content"], str)
        self.assertEqual(result[0]["content"], "You are a helpful assistant.")


class TestInjectCacheMetadataObservability(unittest.TestCase):
    """Observability: inject_cache_metadata emits required DEBUG log lines."""

    def setUp(self):
        self.service = LLMMessageService()
        # Re-enable the logger in case a prior test (e.g., DI container test
        # calling logging.config.dictConfig with disable_existing_loggers=True)
        # has set logger.disabled = True on our target logger.
        self._target_logger = logging.getLogger("agentmap.services.llm_message_service")
        self._orig_disabled = self._target_logger.disabled
        self._target_logger.disabled = False

    def tearDown(self):
        self._target_logger.disabled = self._orig_disabled

    def test_anthropic_injection_emits_debug_log_injected_true(self):
        """TC-001 observability: DEBUG log line includes provider=anthropic, injected=True."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
        ]
        with self.assertLogs(
            "agentmap.services.llm_message_service", level="DEBUG"
        ) as log_ctx:
            self.service.inject_cache_metadata(
                messages, provider="anthropic", cache_system_prompt=True
            )
        combined = " ".join(log_ctx.output)
        self.assertIn("provider=anthropic", combined)
        self.assertIn("injected=True", combined)

    def test_openai_no_op_emits_debug_log_injected_false(self):
        """TC-004 observability: DEBUG log line includes provider=openai, injected=False."""
        messages = [
            {"role": "system", "content": "You are helpful."},
        ]
        with self.assertLogs(
            "agentmap.services.llm_message_service", level="DEBUG"
        ) as log_ctx:
            self.service.inject_cache_metadata(
                messages, provider="openai", cache_system_prompt=True
            )
        combined = " ".join(log_ctx.output)
        self.assertIn("provider=openai", combined)
        self.assertIn("injected=False", combined)


class TestLLMMessageServiceRenameVerification(unittest.TestCase):
    """Verify the rename from LLMMessageUtils to LLMMessageService is correct."""

    def test_class_name_is_llm_message_service(self):
        """The class must be importable as LLMMessageService from llm_message_service."""
        self.assertEqual(LLMMessageService.__name__, "LLMMessageService")

    def test_existing_methods_still_present(self):
        """All three existing methods move unchanged: has_prompt_caching,
        extract_prompt_from_messages, convert_messages_to_langchain."""
        svc = LLMMessageService()
        self.assertTrue(hasattr(svc, "has_prompt_caching"))
        self.assertTrue(hasattr(svc, "extract_prompt_from_messages"))
        self.assertTrue(hasattr(svc, "convert_messages_to_langchain"))

    def test_inject_cache_metadata_is_present(self):
        """inject_cache_metadata() method must be present."""
        svc = LLMMessageService()
        self.assertTrue(hasattr(svc, "inject_cache_metadata"))
        self.assertTrue(callable(svc.inject_cache_metadata))


class TestStripCacheControl(unittest.TestCase):
    """strip_cache_control removes Anthropic-only cache_control for failover."""

    def test_strips_cache_control_from_structured_block(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                    {
                        "type": "text",
                        "text": "extract",
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            }
        ]
        out = LLMMessageService.strip_cache_control(messages)
        self.assertFalse(LLMMessageService.has_prompt_caching(out))
        # Original is not mutated.
        self.assertTrue(LLMMessageService.has_prompt_caching(messages))
        # Non-cache fields preserved.
        text_block = out[0]["content"][1]
        self.assertEqual(text_block["text"], "extract")
        self.assertEqual(text_block["type"], "text")

    def test_no_cache_control_returns_same_object(self):
        messages = [{"role": "user", "content": "plain"}]
        self.assertIs(LLMMessageService.strip_cache_control(messages), messages)

    def test_handles_plain_string_content(self):
        messages = [
            {"role": "system", "content": "sys"},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "hi",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
        ]
        out = LLMMessageService.strip_cache_control(messages)
        self.assertFalse(LLMMessageService.has_prompt_caching(out))
        self.assertEqual(out[0]["content"], "sys")


class TestConvertMessagesToolResultRoundTrip(unittest.TestCase):
    """TC-015 / TC-016 / TC-017 (T-E05-F06-007): convert_messages_to_langchain()
    supports the two message shapes a caller-owned tool loop sends back,
    closing the silent-degradation path where an unrecognized role became a
    HumanMessage (REQ-F-007, spec.md AC-9/AC-10).

    Caller-Path Contract (all three cases):
      - Entrypoint: ``LLMMessageService.convert_messages_to_langchain(messages)``.
      - Lowest allowed mock seam: none -- pure static-method transform, the
        same entrypoint production callers (llm_service.py) use directly.
    """

    def test_tc015_tool_role_with_tool_call_id_becomes_tool_message(self):
        """TC-015: role='tool' + tool_call_id -> ToolMessage with matching
        tool_call_id and content.

        Counter-factual: today's silent-degradation bug coerces this to a
        HumanMessage -- a buggy fix that keeps the `else` branch as the
        catch-all would still produce a HumanMessage and this
        isinstance(result[0], ToolMessage) assertion would fail.
        """
        messages = [{"role": "tool", "tool_call_id": "toolu_1", "content": "18C"}]

        result = LLMMessageService.convert_messages_to_langchain(messages)

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], ToolMessage)
        self.assertEqual(result[0].tool_call_id, "toolu_1")
        self.assertEqual(result[0].content, "18C")

    def test_tc016_tool_role_without_tool_call_id_raises_llm_service_error(self):
        """TC-016: role='tool' with no tool_call_id raises LLMServiceError
        naming the missing field -- no silent coercion to HumanMessage."""
        messages = [{"role": "tool", "content": "18C"}]

        with self.assertRaises(LLMServiceError) as ctx:
            LLMMessageService.convert_messages_to_langchain(messages)

        self.assertIn("tool_call_id", str(ctx.exception))

    def test_tc017_assistant_tool_calls_become_ai_message_preserving_them(self):
        """TC-017: assistant message carrying tool_calls -> AIMessage whose
        tool_calls preserve id/name/args from the input.

        Note: LangChain's AIMessage.tool_calls validator normalizes each
        entry by adding a 'type': 'tool_call' key when absent, so the
        resulting list is not byte-for-byte identical to the input dict --
        the id/name/args fields (what a caller-owned tool loop actually
        needs) are asserted individually instead of a brittle full-list
        equality that would break on any LangChain-internal normalization
        detail unrelated to this feature.
        """
        input_tool_calls = [
            {"id": "toolu_1", "name": "get_weather", "args": {}},
        ]
        messages = [
            {"role": "assistant", "content": "", "tool_calls": input_tool_calls}
        ]

        result = LLMMessageService.convert_messages_to_langchain(messages)

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], AIMessage)
        self.assertEqual(len(result[0].tool_calls), 1)
        preserved = result[0].tool_calls[0]
        self.assertEqual(preserved["id"], "toolu_1")
        self.assertEqual(preserved["name"], "get_weather")
        self.assertEqual(preserved["args"], {})

    def test_tc017_regression_assistant_without_tool_calls_unchanged(self):
        """TC-017 regression: assistant message with no tool_calls key still
        produces a plain AIMessage (existing behavior unchanged)."""
        messages = [{"role": "assistant", "content": "Hello there."}]

        result = LLMMessageService.convert_messages_to_langchain(messages)

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], AIMessage)
        self.assertEqual(result[0].content, "Hello there.")
        self.assertFalse(result[0].tool_calls)

    def test_tc020_regression_system_and_user_conversion_unchanged(self):
        """AC-9/AC-10 regression gate (TC-020): existing system/user
        conversions are unaffected by the new tool/assistant-tool_calls
        branches."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]

        result = LLMMessageService.convert_messages_to_langchain(messages)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].content, "You are helpful.")
        self.assertIsInstance(result[1], HumanMessage)
        self.assertEqual(result[1].content, "Hi")


class TestToolResultRoundTripStripCacheControlChain(unittest.TestCase):
    """TC-031a (T-E05-F06-007): strip_cache_control() -> convert_messages_to_langchain()
    unit-level chain -- supplementary, explicitly internal-only.

    This supplements TC-031 (below); it does not replace it. TC-031 is the
    production-path evidence (drives the real LLMService.call_llm_async()
    fallback dispatch). This case exists only to isolate a failure to the
    message-service layer specifically when TC-031 fails -- a legitimate
    debugging aid, not primary AC evidence (spec.md AC-20, Codex finding).
    """

    def test_tc031a_field_survival_through_strip_then_convert_chain(self):
        """tool_call_id and tool_calls survive strip_cache_control() ->
        convert_messages_to_langchain() chained directly at the
        message-service boundary."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What's the weather?",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "name": "get_weather",
                        "args": {"location": "NYC"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "toolu_1", "content": "18C"},
        ]

        stripped = LLMMessageService.strip_cache_control(messages)
        result = LLMMessageService.convert_messages_to_langchain(stripped)

        self.assertEqual(len(result), 3)

        human_message = result[0]
        self.assertIsInstance(human_message, HumanMessage)
        for block in human_message.content:
            self.assertNotIn("cache_control", block)

        ai_message = result[1]
        self.assertIsInstance(ai_message, AIMessage)
        self.assertEqual(len(ai_message.tool_calls), 1)
        self.assertEqual(ai_message.tool_calls[0]["id"], "toolu_1")
        self.assertEqual(ai_message.tool_calls[0]["name"], "get_weather")
        self.assertEqual(ai_message.tool_calls[0]["args"], {"location": "NYC"})

        tool_message = result[2]
        self.assertIsInstance(tool_message, ToolMessage)
        self.assertEqual(tool_message.tool_call_id, "toolu_1")
        self.assertEqual(tool_message.content, "18C")


class TestToolResultRoundTripRealFallbackDispatch(unittest.IsolatedAsyncioTestCase):
    """TC-031 (T-E05-F06-007): tool-result round-trip field survival proven
    at the real LLMService.call_llm_async() fallback dispatch path -- not an
    isolated message-service unit test (Codex BLOCKER fix, spec.md AC-20).

    Caller-Path Contract:
      - Entrypoint: ``LLMService.call_llm_async(messages, provider="anthropic")``
        -- no ``tools=`` argument, so REQ-F-008's fallback suppression does
        not apply and the fallback ladder is genuinely live.
      - Lowest allowed mock seam: ``_client_factory.get_or_create_client``
        returning tier-specific mock clients (mirrors the TC-018/TC-019
        fallback harness in test_llm_service_async.py).
      - Forbidden mocks: ``LLMMessageService.strip_cache_control()``,
        ``convert_messages_to_langchain()``, and ``LLMFallbackHandler`` are
        never mocked -- all three run for real, which is the production seam
        Codex's red-team review required.
      - Counter-factual: a buggy ``strip_cache_control()`` that rebuilds
        message dicts via a partial ``{**msg, "content": ...}`` merge that
        drops non-content keys would silently lose ``tool_call_id`` before it
        ever reaches the fallback client's ``ainvoke()`` call -- this test
        inspects the actual LangChain messages the fallback client received.
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
            "model": f"{provider}-default-model",
            "api_key": "test-key",
            "temperature": 0.7,
        }
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )

        self.mock_features_registry = Mock()
        self.mock_features_registry.is_provider_available.return_value = True

        self.mock_routing_config_service = Mock()
        # Tier 1 (same provider, low-complexity model) is deliberately absent
        # from the routing matrix so the single live fallback tier is tier 2
        # (the configured default_provider) -- keeps the primary/fallback
        # client dispatch unambiguous in fake_get_client below.
        self.mock_routing_config_service.fallback = {"default_provider": "openai"}
        self.mock_routing_config_service.routing_matrix = {
            "openai": {"low": "gpt-4o-mini"}
        }
        # Messages carry an embedded cache_control block (Anthropic passthrough,
        # E05-F01); the primary provider must support it or
        # _validate_prompt_caching_support raises before any client is built.
        self.mock_routing_config_service.supports_prompt_caching.return_value = True

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=Mock(),
            llm_models_config_service=self.mock_llm_models_config_service,
            features_registry_service=self.mock_features_registry,
            routing_config_service=self.mock_routing_config_service,
        )

    async def test_tc031_real_fallback_dispatch_preserves_tool_fields(self):
        """TC-031: the fallback tier's ainvoke() call receives LangChain
        messages where the ToolMessage's tool_call_id and the AIMessage's
        tool_calls are unchanged from the original input, and the
        cache_control block was stripped -- proven at the actual
        provider-invocation boundary."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What's the weather?",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "name": "get_weather",
                        "args": {"location": "NYC"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "toolu_1", "content": "18C"},
        ]

        failing_client = Mock()
        failing_client.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        fallback_client = Mock()
        fallback_client.ainvoke = AsyncMock(
            return_value=Mock(content="It's 18C in NYC.")
        )

        def fake_get_client(provider, config):
            return failing_client if provider == "anthropic" else fallback_client

        with patch.object(
            self.service._client_factory,
            "get_or_create_client",
            side_effect=fake_get_client,
        ):
            result = await self.service.call_llm_async(
                messages=messages,
                provider="anthropic",
            )

        self.assertEqual(result.text, "It's 18C in NYC.")
        self.assertEqual(result.resolved_provider, "openai")

        fallback_client.ainvoke.assert_awaited_once()
        sent_messages = fallback_client.ainvoke.call_args.args[0]

        tool_messages = [m for m in sent_messages if isinstance(m, ToolMessage)]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(tool_messages[0].tool_call_id, "toolu_1")
        self.assertEqual(tool_messages[0].content, "18C")

        ai_messages = [m for m in sent_messages if isinstance(m, AIMessage)]
        self.assertEqual(len(ai_messages), 1)
        self.assertEqual(len(ai_messages[0].tool_calls), 1)
        self.assertEqual(ai_messages[0].tool_calls[0]["id"], "toolu_1")
        self.assertEqual(ai_messages[0].tool_calls[0]["name"], "get_weather")
        self.assertEqual(ai_messages[0].tool_calls[0]["args"], {"location": "NYC"})

        # AC-20 regression: the cache_control block was stripped before the
        # fallback client ever saw the message (strip_cache_control() ran
        # for real on this path).
        human_messages = [m for m in sent_messages if isinstance(m, HumanMessage)]
        self.assertEqual(len(human_messages), 1)
        for block in human_messages[0].content:
            self.assertNotIn("cache_control", block)


if __name__ == "__main__":
    unittest.main()
