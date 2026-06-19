"""
Unit tests for the LLMStreamChunk data model (E06-F01, T-E06-F01-001).

Test cases covered:
- TC-F01-MODEL-1: Construction with required fields; terminal-only fields default to None
- TC-F01-MODEL-2: Non-final chunk field types are correct; terminal fields are None
- TC-F01-MODEL-3: Terminal chunk exposes all LLMResponse-compatible field names populated
- TC-F01-MODEL-4: Terminal chunk text_delta is empty string (not None); concat never raises TypeError
- TC-F01-MODEL-5: Field-name and Optional[LLMUsage] type parity with LLMResponse
- TC-F01-MODEL-6: usage field accepts an LLMUsage instance
- TC-F01-MODEL-7: LLMStreamChunk is non-frozen; post-construction field assignment succeeds
"""

import dataclasses
import unittest

from agentmap.models.llm_execution import LLMResponse, LLMStreamChunk, LLMUsage


class TestLLMStreamChunkConstruction(unittest.TestCase):
    """TC-F01-MODEL-1: Construction with required fields; terminal-only defaults to None."""

    def test_construction_with_required_fields_succeeds(self):
        """TC-F01-MODEL-1: LLMStreamChunk constructs with text_delta, chunk_index, is_final."""
        chunk = LLMStreamChunk(text_delta="hi", chunk_index=0, is_final=False)
        self.assertEqual(chunk.text_delta, "hi")
        self.assertEqual(chunk.chunk_index, 0)
        self.assertFalse(chunk.is_final)

    def test_terminal_only_fields_default_to_none(self):
        """TC-F01-MODEL-1: usage, finish_reason, resolved_provider, resolved_model default None."""
        chunk = LLMStreamChunk(text_delta="hi", chunk_index=0, is_final=False)
        self.assertIsNone(chunk.usage)
        self.assertIsNone(chunk.finish_reason)
        self.assertIsNone(chunk.resolved_provider)
        self.assertIsNone(chunk.resolved_model)

    def test_construction_missing_required_field_raises_type_error(self):
        """TC-F01-MODEL-1: Missing required fields raise TypeError."""
        with self.assertRaises(TypeError):
            LLMStreamChunk()  # type: ignore[call-arg]


class TestLLMStreamChunkNonFinalFields(unittest.TestCase):
    """TC-F01-MODEL-2: Non-final chunk fields are correct types; terminal fields are None."""

    def setUp(self):
        self.chunk = LLMStreamChunk(text_delta="hello", chunk_index=3, is_final=False)

    def test_text_delta_is_str(self):
        """TC-F01-MODEL-2: text_delta is a str."""
        self.assertIsInstance(self.chunk.text_delta, str)

    def test_chunk_index_is_int(self):
        """TC-F01-MODEL-2: chunk_index is an int."""
        self.assertIsInstance(self.chunk.chunk_index, int)

    def test_is_final_is_bool(self):
        """TC-F01-MODEL-2: is_final is a bool."""
        self.assertIsInstance(self.chunk.is_final, bool)

    def test_usage_is_none_on_non_final(self):
        """TC-F01-MODEL-2: usage is None on non-final chunk."""
        self.assertIsNone(self.chunk.usage)

    def test_finish_reason_is_none_on_non_final(self):
        """TC-F01-MODEL-2: finish_reason is None on non-final chunk."""
        self.assertIsNone(self.chunk.finish_reason)

    def test_resolved_provider_is_none_on_non_final(self):
        """TC-F01-MODEL-2: resolved_provider is None on non-final chunk."""
        self.assertIsNone(self.chunk.resolved_provider)

    def test_resolved_model_is_none_on_non_final(self):
        """TC-F01-MODEL-2: resolved_model is None on non-final chunk."""
        self.assertIsNone(self.chunk.resolved_model)


class TestLLMStreamChunkTerminalFields(unittest.TestCase):
    """TC-F01-MODEL-3: Terminal chunk exposes populated LLMResponse-compatible fields."""

    def setUp(self):
        self.usage = LLMUsage(input_tokens=10, output_tokens=20)
        self.terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=5,
            is_final=True,
            usage=self.usage,
            finish_reason="stop",
            resolved_provider="anthropic",
            resolved_model="claude-3-5-haiku-20241022",
        )

    def test_terminal_chunk_is_final_true(self):
        """TC-F01-MODEL-3: is_final is True on the terminal chunk."""
        self.assertTrue(self.terminal.is_final)

    def test_terminal_chunk_text_delta_empty_string(self):
        """TC-F01-MODEL-3: text_delta is empty string on terminal chunk."""
        self.assertEqual(self.terminal.text_delta, "")

    def test_terminal_chunk_usage_populated(self):
        """TC-F01-MODEL-3: usage is populated on terminal chunk."""
        self.assertIsNotNone(self.terminal.usage)
        self.assertEqual(self.terminal.usage.input_tokens, 10)
        self.assertEqual(self.terminal.usage.output_tokens, 20)

    def test_terminal_chunk_finish_reason_populated(self):
        """TC-F01-MODEL-3: finish_reason is populated on terminal chunk."""
        self.assertEqual(self.terminal.finish_reason, "stop")

    def test_terminal_chunk_resolved_provider_populated(self):
        """TC-F01-MODEL-3: resolved_provider is populated on terminal chunk."""
        self.assertEqual(self.terminal.resolved_provider, "anthropic")

    def test_terminal_chunk_resolved_model_populated(self):
        """TC-F01-MODEL-3: resolved_model is populated on terminal chunk."""
        self.assertEqual(self.terminal.resolved_model, "claude-3-5-haiku-20241022")

    def test_terminal_chunk_fields_can_construct_llm_response(self):
        """TC-F01-MODEL-3: Terminal chunk's fields can reconstruct an LLMResponse."""
        # This is the F03 reconstruction pattern — it must work without KeyError or AttributeError
        response = LLMResponse(
            text="accumulated text",
            resolved_provider=self.terminal.resolved_provider,
            resolved_model=self.terminal.resolved_model,
            usage=self.terminal.usage,
            finish_reason=self.terminal.finish_reason,
        )
        self.assertEqual(response.resolved_provider, "anthropic")
        self.assertEqual(response.resolved_model, "claude-3-5-haiku-20241022")
        self.assertEqual(response.usage, self.usage)
        self.assertEqual(response.finish_reason, "stop")


class TestLLMStreamChunkTextDeltaConcatenation(unittest.TestCase):
    """TC-F01-MODEL-4: Terminal chunk text_delta is ""; concatenation never raises TypeError."""

    def test_terminal_text_delta_is_empty_string_not_none(self):
        """TC-F01-MODEL-4: Terminal chunk text_delta is '' not None."""
        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=2,
            is_final=True,
            finish_reason="stop",
            resolved_provider="openai",
            resolved_model="gpt-4o",
        )
        self.assertEqual(terminal.text_delta, "")
        self.assertIsNotNone(terminal.text_delta)

    def test_concatenation_across_stream_never_raises_type_error(self):
        """TC-F01-MODEL-4: Concatenating text_delta across non-final+terminal chunks works."""
        chunks = [
            LLMStreamChunk(text_delta="Hello", chunk_index=0, is_final=False),
            LLMStreamChunk(text_delta=" world", chunk_index=1, is_final=False),
            LLMStreamChunk(
                text_delta="",
                chunk_index=2,
                is_final=True,
                finish_reason="stop",
                resolved_provider="anthropic",
                resolved_model="claude-3-5-haiku-20241022",
            ),
        ]
        # This must not raise TypeError regardless of chunk ordering
        full_text = "".join(c.text_delta for c in chunks)
        self.assertEqual(full_text, "Hello world")


class TestLLMStreamChunkFieldNameParity(unittest.TestCase):
    """TC-F01-MODEL-5: Field-name and Optional[LLMUsage] type parity with LLMResponse."""

    def test_terminal_field_names_match_llm_response(self):
        """TC-F01-MODEL-5: LLMStreamChunk has the same terminal field names as LLMResponse."""
        response_fields = {f.name for f in dataclasses.fields(LLMResponse)}
        chunk_fields = {f.name for f in dataclasses.fields(LLMStreamChunk)}

        # The four terminal-only fields must be present in both
        terminal_fields = {
            "usage",
            "finish_reason",
            "resolved_provider",
            "resolved_model",
        }
        self.assertTrue(
            terminal_fields.issubset(response_fields),
            f"LLMResponse missing expected fields: {terminal_fields - response_fields}",
        )
        self.assertTrue(
            terminal_fields.issubset(chunk_fields),
            f"LLMStreamChunk missing expected fields: {terminal_fields - chunk_fields}",
        )

    def test_usage_field_type_hint_is_optional_llm_usage(self):
        """TC-F01-MODEL-5: LLMStreamChunk.usage is typed Optional[LLMUsage] same as LLMResponse."""
        chunk_fields = {f.name: f for f in dataclasses.fields(LLMStreamChunk)}
        response_fields = {f.name: f for f in dataclasses.fields(LLMResponse)}

        self.assertIn("usage", chunk_fields)
        self.assertIn("usage", response_fields)

        chunk_usage_type = chunk_fields["usage"].type
        response_usage_type = response_fields["usage"].type

        # Both must carry the same type annotation (Optional[LLMUsage] or equivalent string form)
        # We verify by checking the annotation on the class itself
        chunk_hints = LLMStreamChunk.__dataclass_fields__["usage"]
        response_hints = LLMResponse.__dataclass_fields__["usage"]

        # The default value on both must be None (Optional signature)
        self.assertIsNone(chunk_hints.default)
        self.assertIsNone(response_hints.default)

        # Both type strings reference LLMUsage
        self.assertIn("LLMUsage", str(chunk_usage_type))
        self.assertIn("LLMUsage", str(response_usage_type))


class TestLLMStreamChunkUsageField(unittest.TestCase):
    """TC-F01-MODEL-6: usage field accepts an LLMUsage instance."""

    def test_usage_accepts_llm_usage_instance(self):
        """TC-F01-MODEL-6: LLMStreamChunk.usage accepts LLMUsage directly."""
        usage = LLMUsage(input_tokens=100, output_tokens=50)
        chunk = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            usage=usage,
        )
        self.assertIsInstance(chunk.usage, LLMUsage)
        self.assertEqual(chunk.usage.input_tokens, 100)
        self.assertEqual(chunk.usage.output_tokens, 50)

    def test_usage_with_cache_tokens_accepted(self):
        """TC-F01-MODEL-6: LLMUsage with cache token fields is accepted by usage."""
        usage = LLMUsage(
            input_tokens=200,
            output_tokens=80,
            cache_creation_input_tokens=50,
            cache_read_input_tokens=30,
        )
        chunk = LLMStreamChunk(
            text_delta="",
            chunk_index=1,
            is_final=True,
            usage=usage,
        )
        self.assertEqual(chunk.usage.cache_creation_input_tokens, 50)
        self.assertEqual(chunk.usage.cache_read_input_tokens, 30)


class TestLLMStreamChunkNonFrozen(unittest.TestCase):
    """TC-F01-MODEL-7: LLMStreamChunk is non-frozen; post-construction mutation succeeds."""

    def test_non_frozen_finish_reason_mutation_succeeds(self):
        """TC-F01-MODEL-7: Assigning finish_reason post-construction does not raise."""
        chunk = LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)
        # Must NOT raise FrozenInstanceError — deliberate deviation from LLMResponse (frozen=True)
        chunk.finish_reason = "stop"
        self.assertEqual(chunk.finish_reason, "stop")

    def test_non_frozen_usage_mutation_succeeds(self):
        """TC-F01-MODEL-7: Assigning usage post-construction does not raise."""
        chunk = LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)
        usage = LLMUsage(input_tokens=10, output_tokens=5)
        chunk.usage = usage
        self.assertEqual(chunk.usage.input_tokens, 10)

    def test_non_frozen_resolved_provider_mutation_succeeds(self):
        """TC-F01-MODEL-7: Assigning resolved_provider post-construction does not raise."""
        chunk = LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)
        chunk.resolved_provider = "anthropic"
        self.assertEqual(chunk.resolved_provider, "anthropic")

    def test_non_frozen_resolved_model_mutation_succeeds(self):
        """TC-F01-MODEL-7: Assigning resolved_model post-construction does not raise."""
        chunk = LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)
        chunk.resolved_model = "claude-3-5-haiku-20241022"
        self.assertEqual(chunk.resolved_model, "claude-3-5-haiku-20241022")

    def test_llm_response_is_frozen_contrast(self):
        """TC-F01-MODEL-7: LLMResponse IS frozen — verify the contrast is meaningful."""
        from dataclasses import FrozenInstanceError

        response = LLMResponse(
            text="hello",
            resolved_provider="anthropic",
            resolved_model="claude-3-5-haiku-20241022",
        )
        with self.assertRaises(FrozenInstanceError):
            response.finish_reason = "stop"  # type: ignore[misc]

    def test_llm_stream_chunk_is_not_decorated_frozen(self):
        """TC-F01-MODEL-7: LLMStreamChunk dataclass params do not include frozen=True."""
        params = LLMStreamChunk.__dataclass_params__
        self.assertFalse(params.frozen)


if __name__ == "__main__":
    unittest.main()
