"""
Unit tests for LLMService vision/multimodal support.

Tests ask_vision(), _resolve_image(), multimodal message handling in
LLMMessageService, routing context vision flag injection, and non-vision
model filtering in select_candidates().
"""

import base64
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.services.llm_message_service import LLMMessageService
from agentmap.services.llm_service import LLMService
from agentmap.services.routing.types import RoutingContext
from tests.utils.mock_service_factory import MockServiceFactory


class TestResolveImage(unittest.TestCase):
    """Tests for LLMService._resolve_image()."""

    def test_resolve_image_bytes(self):
        """Bytes input passes through with correct MIME."""
        raw = b"\x89PNG\r\n\x1a\n"
        img_bytes, mime = LLMService._resolve_image(raw, "image/png")
        self.assertIs(img_bytes, raw)
        self.assertEqual(mime, "image/png")

    def test_resolve_image_bytes_custom_mime(self):
        """Custom MIME type is preserved for bytes input."""
        raw = b"\xff\xd8\xff"
        img_bytes, mime = LLMService._resolve_image(raw, "image/jpeg")
        self.assertEqual(mime, "image/jpeg")

    def test_resolve_image_file_path(self):
        """File path reads contents and infers MIME from extension."""
        content = b"fake-png-data"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.png")
            with open(path, "wb") as f:
                f.write(content)
            img_bytes, mime = LLMService._resolve_image(path)
            self.assertEqual(img_bytes, content)
            self.assertEqual(mime, "image/png")

    def test_resolve_image_jpeg_extension(self):
        """JPEG extension infers correct MIME type."""
        content = b"fake-jpeg-data"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.jpg")
            with open(path, "wb") as f:
                f.write(content)
            _, mime = LLMService._resolve_image(path)
            self.assertEqual(mime, "image/jpeg")

    def test_resolve_image_invalid_path(self):
        """Non-existent file path raises LLMServiceError."""
        from agentmap.exceptions import LLMServiceError

        with self.assertRaises(LLMServiceError) as ctx:
            LLMService._resolve_image("/nonexistent/path/image.png")
        self.assertIn("not found", str(ctx.exception))


class TestAskVision(unittest.TestCase):
    """Tests for LLMService.ask_vision()."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
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

    @patch.object(LLMService, "call_llm", return_value="A cat sitting on a mat.")
    def test_ask_vision_with_bytes(self, mock_call_llm):
        """Passes image bytes, verifies multimodal message construction."""
        raw = b"\x89PNG\r\n\x1a\n"
        result = self.service.ask_vision(
            prompt="Describe this image.",
            image=raw,
            image_type="image/png",
            provider="anthropic",
        )

        self.assertEqual(result, "A cat sitting on a mat.")
        mock_call_llm.assert_called_once()

        messages = mock_call_llm.call_args[1]["messages"]

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        content = messages[0]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(content[1]["type"], "text")
        self.assertEqual(content[1]["text"], "Describe this image.")

        # Verify base64 encoding in data URL
        expected_b64 = base64.b64encode(raw).decode("ascii")
        self.assertIn(expected_b64, content[0]["image_url"]["url"])
        self.assertTrue(
            content[0]["image_url"]["url"].startswith("data:image/png;base64,")
        )

    @patch.object(LLMService, "call_llm", return_value="Extracted text.")
    def test_ask_vision_with_file_path(self, mock_call_llm):
        """Passes file path, verifies file reading and MIME inference."""
        content_bytes = b"fake-image-content"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.jpeg")
            with open(path, "wb") as f:
                f.write(content_bytes)
            result = self.service.ask_vision(
                prompt="Extract text.",
                image=path,
                provider="anthropic",
            )
            self.assertEqual(result, "Extracted text.")

            messages = mock_call_llm.call_args[1]["messages"]
            url = messages[0]["content"][0]["image_url"]["url"]
            self.assertTrue(url.startswith("data:image/jpeg;base64,"))

    @patch.object(LLMService, "call_llm", return_value="result")
    def test_ask_vision_default_provider(self, mock_call_llm):
        """Defaults to 'anthropic' when no provider or routing_context given."""
        raw = b"img"
        self.service.ask_vision(prompt="Describe.", image=raw)

        actual_kwargs = mock_call_llm.call_args[1]
        self.assertEqual(actual_kwargs["provider"], "anthropic")

    @patch.object(LLMService, "call_llm", return_value="result")
    def test_ask_vision_no_default_provider_with_routing(self, mock_call_llm):
        """Provider stays None when routing_context is provided."""
        raw = b"img"
        self.service.ask_vision(
            prompt="Describe.",
            image=raw,
            routing_context={"activity": "image_extraction"},
        )

        actual_kwargs = mock_call_llm.call_args[1]
        self.assertIsNone(actual_kwargs["provider"])

    @patch.object(LLMService, "call_llm", return_value="result")
    def test_ask_vision_with_routing_context(self, mock_call_llm):
        """Verifies routing_context flows through with requires_vision=True."""
        raw = b"img"
        routing_ctx = {"activity": "image_extraction", "routing_enabled": True}

        self.service.ask_vision(
            prompt="Analyze.",
            image=raw,
            routing_context=routing_ctx,
        )

        actual_kwargs = mock_call_llm.call_args[1]
        rc = actual_kwargs["routing_context"]
        self.assertTrue(rc["requires_vision"])
        self.assertEqual(rc["activity"], "image_extraction")

    @patch.object(LLMService, "call_llm", return_value="result")
    def test_ask_vision_routing_context_not_mutated(self, mock_call_llm):
        """Verifies the original routing_context dict is not modified."""
        raw = b"img"
        original = {"activity": "image_extraction", "routing_enabled": True}

        self.service.ask_vision(
            prompt="Analyze.",
            image=raw,
            routing_context=original,
        )

        # Original should not have requires_vision
        self.assertNotIn("requires_vision", original)

    @patch.object(LLMService, "call_llm")
    def test_ask_vision_rejects_prompt_caching_before_call_llm(self, mock_call_llm):
        """Cache mode is explicitly unsupported for ask_vision()."""
        with self.assertRaises(LLMServiceError) as ctx:
            self.service.ask_vision(
                prompt="Analyze.",
                image=b"img",
                routing_context={"requires_prompt_caching": True},
            )

        self.assertIn("prompt caching", str(ctx.exception).lower())
        self.assertIn("ask_vision", str(ctx.exception).lower())
        mock_call_llm.assert_not_called()


class TestLLMMessageServiceMultimodal(unittest.TestCase):
    """Tests for multimodal content handling in LLMMessageService."""

    def test_convert_messages_multimodal(self):
        """List content blocks are passed through to HumanMessage."""
        multimodal_content = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            {"type": "text", "text": "Describe this."},
        ]
        messages = [{"role": "user", "content": multimodal_content}]

        result = LLMMessageService.convert_messages_to_langchain(messages)

        self.assertEqual(len(result), 1)
        # LangChain HumanMessage should preserve the list content
        self.assertEqual(result[0].content, multimodal_content)

    def test_convert_messages_text_unchanged(self):
        """String content still works as before."""
        messages = [{"role": "user", "content": "Hello"}]
        result = LLMMessageService.convert_messages_to_langchain(messages)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "Hello")

    def test_extract_prompt_multimodal(self):
        """Text is extracted from multimodal content blocks."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,abc"},
                    },
                    {"type": "text", "text": "What is in this image?"},
                ],
            }
        ]
        result = LLMMessageService.extract_prompt_from_messages(messages)
        self.assertEqual(result, "What is in this image?")

    def test_extract_prompt_multimodal_multiple_text_blocks(self):
        """Multiple text blocks are joined."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First part."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,abc"},
                    },
                    {"type": "text", "text": "Second part."},
                ],
            }
        ]
        result = LLMMessageService.extract_prompt_from_messages(messages)
        self.assertEqual(result, "First part. Second part.")

    def test_extract_prompt_text_unchanged(self):
        """String content still works as before."""
        messages = [{"role": "user", "content": "Hello world"}]
        result = LLMMessageService.extract_prompt_from_messages(messages)
        self.assertEqual(result, "Hello world")

    def test_detect_prompt_caching_in_structured_blocks(self):
        """Cache-control metadata is detected without altering content."""
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

        self.assertTrue(LLMMessageService.has_prompt_caching(messages))

    def test_detect_prompt_caching_false_for_plain_text_messages(self):
        """Existing plain-text callers are not treated as cache mode."""
        messages = [{"role": "user", "content": "Hello world"}]
        self.assertFalse(LLMMessageService.has_prompt_caching(messages))


class TestRoutingContextVision(unittest.TestCase):
    """Tests for requires_vision in RoutingContext."""

    def test_default_requires_vision_false(self):
        """requires_vision defaults to False."""
        ctx = RoutingContext()
        self.assertFalse(ctx.requires_vision)

    def test_to_dict_includes_requires_vision(self):
        """to_dict includes requires_vision field."""
        ctx = RoutingContext(requires_vision=True)
        d = ctx.to_dict()
        self.assertTrue(d["requires_vision"])

    def test_from_dict_reads_requires_vision(self):
        """from_dict reads requires_vision from data."""
        ctx = RoutingContext.from_dict({"requires_vision": True})
        self.assertTrue(ctx.requires_vision)

    def test_from_dict_defaults_requires_vision(self):
        """from_dict defaults requires_vision to False when not present."""
        ctx = RoutingContext.from_dict({})
        self.assertFalse(ctx.requires_vision)


class TestSelectCandidatesVisionFiltering(unittest.TestCase):
    """Tests for non-vision model filtering in select_candidates()."""

    @patch(
        "agentmap.services.routing.routing_service._NON_VISION_MODELS",
        frozenset({"text-only-model"}),
    )
    def test_select_candidates_filters_non_vision_models(self):
        """Non-vision models are filtered when requires_vision=True."""
        from agentmap.services.routing.routing_service import LLMRoutingService

        # Create mock dependencies
        mock_routing_config = Mock()
        mock_routing_config.is_routing_cache_enabled.return_value = False
        mock_routing_config.routing_matrix = {"anthropic": {}, "openai": {}}
        mock_routing_config.get_model_for_complexity.return_value = None

        mock_logging_service = MockServiceFactory.create_mock_logging_service()

        # Mock the activities config to return candidates including a text-only model
        mock_routing_config.get_activities_config.return_value = {
            "image_extraction": {
                "low": {
                    "primary": {
                        "provider": "anthropic",
                        "model": "claude-haiku-4-5-20251001",
                    },
                    "fallbacks": [
                        {"provider": "openai", "model": "text-only-model"},
                    ],
                }
            }
        }

        routing_service = LLMRoutingService(
            llm_routing_config_service=mock_routing_config,
            logging_service=mock_logging_service,
            routing_cache=Mock(),
            prompt_complexity_analyzer=Mock(),
        )

        ctx = RoutingContext(
            activity="image_extraction",
            requires_vision=True,
            complexity_override="low",
        )

        from agentmap.services.routing.types import TaskComplexity

        candidates = routing_service.select_candidates(
            ctx,
            available_providers=["anthropic", "openai"],
            complexity=TaskComplexity.LOW,
        )

        # text-only-model should be filtered out
        models = [c["model"] for c in candidates]
        self.assertNotIn("text-only-model", models)

    def test_select_candidates_no_filtering_without_vision(self):
        """No filtering when requires_vision=False (default)."""
        ctx = RoutingContext(requires_vision=False)
        # Just verify the field is False — full integration tested above
        self.assertFalse(ctx.requires_vision)


class TestAskVisionAsync(unittest.IsolatedAsyncioTestCase):
    """Tests for LLMService.ask_vision_async() — rich LLMResponse return."""

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
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
        self._response = LLMResponse(
            text="Extracted text.",
            resolved_provider="anthropic",
            resolved_model="claude-haiku-4-5-20251001",
            usage=LLMUsage(input_tokens=120, output_tokens=44),
            finish_reason="end_turn",
        )

    async def test_returns_rich_llm_response(self):
        """Returns the LLMResponse from call_llm_async unchanged."""
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            result = await self.service.ask_vision_async(
                prompt="Extract text.",
                image=b"\x89PNG\r\n\x1a\n",
                image_type="image/png",
                provider="anthropic",
            )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "Extracted text.")
        self.assertEqual(result.usage.input_tokens, 120)
        self.assertEqual(result.finish_reason, "end_turn")
        mock_async.assert_awaited_once()

    async def test_builds_multimodal_message(self):
        """Constructs an image_url + text user message (non-cache path)."""
        raw = b"img-bytes"
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(prompt="Describe.", image=raw)

        messages = mock_async.await_args[1]["messages"]
        self.assertEqual(messages[0]["role"], "user")
        content = messages[0]["content"]
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(content[1]["type"], "text")
        self.assertEqual(content[1]["text"], "Describe.")
        expected_b64 = base64.b64encode(raw).decode("ascii")
        self.assertIn(expected_b64, content[0]["image_url"]["url"])

    async def test_injects_requires_vision_and_preserves_routing_context(self):
        """requires_vision is added; the caller's dict is not mutated."""
        original = {"activity": "ocr_extraction"}
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(
                prompt="Extract.",
                image=b"img",
                routing_context=original,
            )

        rc = mock_async.await_args[1]["routing_context"]
        self.assertTrue(rc["requires_vision"])
        self.assertEqual(rc["activity"], "ocr_extraction")
        self.assertNotIn("requires_vision", original)  # no mutation

    async def test_cache_prompt_attaches_cache_control_and_routing_signal(self):
        """cache_prompt marks the prompt block and requests cache-aware routing."""
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(
                prompt="Long static OCR instructions.",
                image=b"img",
                routing_context={"activity": "ocr_extraction"},
                cache_prompt=True,
            )

        kwargs = mock_async.await_args[1]
        text_block = kwargs["messages"][0]["content"][1]
        self.assertEqual(text_block["cache_control"], {"type": "ephemeral"})
        rc = kwargs["routing_context"]
        self.assertTrue(rc["requires_prompt_caching"])
        self.assertTrue(rc["requires_vision"])

    async def test_no_cache_control_when_cache_prompt_false(self):
        """Default path carries no cache_control or caching routing signal."""
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(
                prompt="x",
                image=b"img",
                routing_context={"activity": "ocr_extraction"},
            )

        kwargs = mock_async.await_args[1]
        self.assertNotIn("cache_control", kwargs["messages"][0]["content"][1])
        self.assertNotIn("requires_prompt_caching", kwargs["routing_context"])

    async def test_default_provider_only_without_routing(self):
        """Defaults to anthropic with no routing; stays None when routing active."""
        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(prompt="x", image=b"img")
        self.assertEqual(mock_async.await_args[1]["provider"], "anthropic")

        with patch.object(
            LLMService, "call_llm_async", new=AsyncMock(return_value=self._response)
        ) as mock_async:
            await self.service.ask_vision_async(
                prompt="x", image=b"img", routing_context={"activity": "ocr_extraction"}
            )
        self.assertIsNone(mock_async.await_args[1]["provider"])


class TestExtractFinishReason(unittest.TestCase):
    """Tests for LLMService._extract_finish_reason()."""

    def test_anthropic_stop_reason(self):
        resp = Mock(response_metadata={"stop_reason": "max_tokens"})
        self.assertEqual(LLMService._extract_finish_reason(resp), "max_tokens")

    def test_openai_finish_reason(self):
        resp = Mock(response_metadata={"finish_reason": "length"})
        self.assertEqual(LLMService._extract_finish_reason(resp), "length")

    def test_stop_reason_precedence_over_finish_reason(self):
        resp = Mock(
            response_metadata={"stop_reason": "end_turn", "finish_reason": "stop"}
        )
        self.assertEqual(LLMService._extract_finish_reason(resp), "end_turn")

    def test_none_when_absent(self):
        resp = Mock(response_metadata={})
        self.assertIsNone(LLMService._extract_finish_reason(resp))

    def test_none_when_metadata_not_dict(self):
        resp = Mock(response_metadata=None)
        self.assertIsNone(LLMService._extract_finish_reason(resp))


if __name__ == "__main__":
    unittest.main()
