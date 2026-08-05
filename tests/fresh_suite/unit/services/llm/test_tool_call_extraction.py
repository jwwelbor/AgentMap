"""
Unit tests for ``extract_tool_calls`` / ``normalize_response_text``
(T-E05-F06-005).

Covers TC-013a, TC-013b (REQ-F-005 / AC-7 -- field-level extraction cases)
and TC-026, TC-027, TC-028, TC-028a (REQ-F-012 / AC-17 -- text-shape
normalization) from
docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F06-llm-cost-receipts-and-structured-tool-results/test-plan.md.

Scope-boundary note: TC-013's own Caller-Path Contract declares
``LLMService.call_llm_async(..., tools=[...])`` as its entrypoint and
additionally asserts a ``bind_tools`` call -- that assertion belongs to
T-E05-F06-006 (tool-definition send path), which this task's Scope Boundary
explicitly excludes ("Do NOT implement tools=/bind_tools here"). This task
implements the receive-side half only: ``extract_tool_calls()`` reading
whatever ``response.tool_calls`` a (possibly future tool-bound) client
returns. TC-013's extraction-into-``LLMResponse`` assertion is covered at
the service level in ``test_llm_service_async.py`` (mocking ``ainvoke`` to
return a response carrying ``.tool_calls`` directly, without exercising
``bind_tools``); this file covers the field-level TC-013a/TC-013b cases
against the declared internal-only entrypoint, ``extract_tool_calls()``
itself -- there is no lower seam to mock (spec.md Component Change 8:
``_invoke_with_resilience_async`` calls it directly with the raw provider
response object).

Data-integrity note for TC-028a's third sub-case (non-string ``text``
value): spec.md does not pin coerce-vs-skip. This implementation coerces via
``str(...)`` (see ``normalize_response_text`` docstring) so a non-string
text payload is never silently dropped; this test file's assertion matches
that choice explicitly rather than assuming it silently.
"""

import unittest

from agentmap.models.llm_tool_call import LLMToolCall
from agentmap.services.llm.tool_call_extraction import (
    extract_tool_calls,
    normalize_response_text,
)


class _Resp:
    """Minimal stand-in for a LangChain ``AIMessage``-like response."""

    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


class TestExtractToolCallsAbsentOrEmpty(unittest.TestCase):
    """TC-013a: absent/empty tool-call channel -> None (never [])."""

    def test_tc013a_no_tool_calls_attribute_returns_none(self):
        response = _Resp(content="hello")
        self.assertIsNone(extract_tool_calls(response))

    def test_tc013a_empty_tool_calls_list_returns_none(self):
        response = _Resp(content="hello", tool_calls=[])
        self.assertIsNone(extract_tool_calls(response))


class TestExtractToolCallsMalformedEntries(unittest.TestCase):
    """TC-013b: malformed entries are skipped with a debug log, not raised."""

    def test_tc013b_entry_missing_id_is_skipped_with_debug_log(self):
        response = _Resp(
            tool_calls=[{"name": "get_weather", "args": {}}],
        )
        with self.assertLogs(
            "agentmap.services.llm.tool_call_extraction", level="DEBUG"
        ) as ctx:
            result = extract_tool_calls(response)

        self.assertIsNone(result)
        self.assertTrue(any("id" in msg or "name" in msg for msg in ctx.output))

    def test_tc013b_entry_missing_name_is_skipped_with_debug_log(self):
        response = _Resp(
            tool_calls=[{"id": "toolu_1", "args": {}}],
        )
        with self.assertLogs(
            "agentmap.services.llm.tool_call_extraction", level="DEBUG"
        ):
            result = extract_tool_calls(response)

        self.assertIsNone(result)

    def test_tc013b_mixed_list_keeps_the_well_formed_entry(self):
        """A single bad entry must not convert a successful call into a
        failure -- the well-formed sibling entry is still extracted."""
        response = _Resp(
            tool_calls=[
                {"name": "get_weather", "args": {}},  # missing id -- skipped
                {
                    "id": "toolu_1",
                    "name": "get_weather",
                    "args": {"city": "Oslo"},
                    "type": "tool_call",
                },
            ],
        )
        with self.assertLogs(
            "agentmap.services.llm.tool_call_extraction", level="DEBUG"
        ):
            result = extract_tool_calls(response)

        self.assertEqual(
            result,
            [LLMToolCall(id="toolu_1", name="get_weather", arguments={"city": "Oslo"})],
        )


class TestExtractToolCallsWellFormed(unittest.TestCase):
    """Contract surface: normalized shape mapping (args -> arguments)."""

    def test_single_well_formed_entry_maps_args_to_arguments(self):
        response = _Resp(
            tool_calls=[
                {
                    "id": "toolu_1",
                    "name": "get_weather",
                    "args": {"city": "Oslo"},
                    "type": "tool_call",
                }
            ]
        )
        result = extract_tool_calls(response)
        self.assertEqual(
            result,
            [LLMToolCall(id="toolu_1", name="get_weather", arguments={"city": "Oslo"})],
        )


class TestNormalizeResponseTextBlockList(unittest.TestCase):
    """TC-026: block-list content with a text block -> concatenated string."""

    def test_tc026_text_block_and_tool_use_block_concatenates_text_only(self):
        response = _Resp(
            content=[
                {"type": "text", "text": "Let me check."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {},
                },
            ]
        )
        result = normalize_response_text(response)
        self.assertEqual(result, "Let me check.")
        self.assertIsInstance(result, str)


class TestNormalizeResponseTextNoTextBlock(unittest.TestCase):
    """TC-027: block-list content with no text block -> ""."""

    def test_tc027_tool_use_only_yields_empty_string(self):
        response = _Resp(
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {},
                }
            ]
        )
        result = normalize_response_text(response)
        self.assertEqual(result, "")
        self.assertIsInstance(result, str)


class TestNormalizeResponseTextPlainString(unittest.TestCase):
    """TC-028: plain string content -> unchanged (regression)."""

    def test_tc028_plain_string_content_used_verbatim(self):
        response = _Resp(content="hello")
        self.assertEqual(normalize_response_text(response), "hello")


class TestNormalizeResponseTextMalformedBlocks(unittest.TestCase):
    """TC-028a: malformed block-list content -- closed input-model enumeration."""

    def test_tc028a_non_dict_list_entry_is_skipped(self):
        response = _Resp(content=["plain string entry", {"type": "text", "text": "b"}])
        self.assertEqual(normalize_response_text(response), "b")

    def test_tc028a_text_block_missing_text_key_contributes_empty_string(self):
        response = _Resp(content=[{"type": "text"}])
        self.assertEqual(normalize_response_text(response), "")

    def test_tc028a_text_block_with_non_string_text_value_is_coerced(self):
        """Spec.md does not pin coerce-vs-skip for this sub-case; this
        implementation coerces via str(...) -- see module docstring."""
        response = _Resp(content=[{"type": "text", "text": 123}])
        self.assertEqual(normalize_response_text(response), "123")

    def test_tc028a_empty_list_yields_empty_string(self):
        response = _Resp(content=[])
        self.assertEqual(normalize_response_text(response), "")


class TestNormalizeResponseTextNoContentAttribute(unittest.TestCase):
    """Fallback parity with the pre-existing catch-all this helper replaces."""

    def test_response_without_content_attribute_falls_back_to_str(self):
        response = object()
        self.assertEqual(normalize_response_text(response), str(response))
