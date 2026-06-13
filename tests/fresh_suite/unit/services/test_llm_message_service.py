"""
Unit tests for LLMMessageService — inject_cache_metadata() and rename verification.

Covers TC-001, TC-002, TC-003, TC-004, TC-007 from E05-F05 test plan.
"""

import logging
import unittest

# NOTE: These imports will fail until llm_message_service.py exists (RED phase).
from agentmap.services.llm_message_service import LLMMessageService


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


if __name__ == "__main__":
    unittest.main()
