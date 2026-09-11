"""
Tool-call extraction and receipt normalization for LLM async receipts (E05-F06).

Two pure, module-level helpers used at ``LLMResponse`` construction in
``LLMService._attempt_llm_call_async``:

- ``extract_tool_calls`` reads LangChain's already-normalized ``tool_calls``
  channel (populated for Anthropic ``tool_use`` blocks, OpenAI ``tool_calls``,
  and Google ``function_call`` parts alike) into ``LLMToolCall`` entries
  (REQ-F-005). AgentMap does not re-derive the three incompatible provider
  shapes itself -- the same reuse posture ``LLMService._extract_llm_usage``
  takes toward ``usage_metadata``.
- ``normalize_response_content`` derives that safe text projection and its
  provider-neutral receipt status. Its text projection is always a ``str``
  even when a provider's ``content`` is a block list (REQ-F-012), and a
  successful non-text block list is not indistinguishable from ordinary empty
  textual content (B005).

Both functions mirror ``_extract_llm_usage``'s per-field tolerance: a
malformed entry is skipped with a debug log rather than raising, so a single
bad field never converts a successful provider call into a failed one.

Not wired into ``LLMService`` here in the sense of ``tools=``/``bind_tools``
send-path support -- that is T-E05-F06-006. This module only supplies the
receive-side extraction and receipt normalization.
"""

import logging
from collections.abc import Mapping
from typing import Any, List, Optional, Tuple

from agentmap.models.llm_execution import ResponseTextStatus
from agentmap.models.llm_tool_call import LLMToolCall

logger = logging.getLogger(__name__)


def extract_tool_calls(response: Any) -> Optional[List[LLMToolCall]]:
    """Extract normalized ``LLMToolCall`` entries from a provider response.

    Reads ``response.tool_calls``, the list LangChain Core populates on
    ``AIMessage`` with entries shaped ``{"name", "args", "id", "type"}``.

    Returns ``None`` when the attribute is absent, not a list, or an empty
    list (REQ-F-005 -- never an empty list). The explicit ``isinstance(...,
    list)`` check (rather than a truthiness check on ``getattr(...)``) is
    required for test-double safety, not just provider-shape safety: an
    unspecced ``unittest.mock.Mock`` auto-creates a truthy child ``Mock`` for
    any unset attribute access, so a bare truthiness check would treat a
    Mock's un-configured ``.tool_calls`` as present and then fail trying to
    iterate over it. A real LangChain response always carries a real list.
    Entries with missing or non-string ``id``/``name`` fields, or carrying a
    non-dict ``args``, are skipped with a debug log rather than raising, so a
    malformed entry never converts a successful call into a failure; a
    well-formed entry elsewhere in the same list is still extracted.
    """
    raw_tool_calls = getattr(response, "tool_calls", None)
    if not isinstance(raw_tool_calls, list) or not raw_tool_calls:
        return None

    extracted: List[LLMToolCall] = []
    for entry in raw_tool_calls:
        if not isinstance(entry, dict):
            logger.debug("Skipping malformed tool call entry with non-mapping shape")
            continue

        call_id = entry.get("id")
        name = entry.get("name")
        if not isinstance(call_id, str) or not isinstance(name, str):
            logger.debug("Skipping tool call entry with non-string id/name field")
            continue
        if not call_id or not name:
            logger.debug("Skipping tool call entry missing required id/name field")
            continue

        arguments = entry.get("args")
        if not isinstance(arguments, dict):
            logger.debug("Skipping tool call entry with non-dict args field")
            continue

        extracted.append(LLMToolCall(id=call_id, name=name, arguments=arguments))

    return extracted or None


def normalize_response_content(response: Any) -> Tuple[str, ResponseTextStatus]:
    """Return the safe text projection and its provider-neutral receipt state.

    A non-empty block list with no text blocks is a successful, non-text
    response rather than an ordinary empty answer.  The raw blocks are not
    exposed: they can contain provider-specific tool arguments or reasoning.
    The same rule applies to non-list structured content; only provider text
    strings become ``LLMResponse.text``.
    """
    if not hasattr(response, "content"):
        return "", "empty"

    return normalize_response_content_value(response.content)


def normalize_response_content_value(content: Any) -> Tuple[str, ResponseTextStatus]:
    """Return the safe receipt projection for a raw provider content value."""

    if isinstance(content, str):
        return content, "empty" if not content else "text"

    if isinstance(content, list):
        parts: List[str] = []
        has_non_text_block = False
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                has_non_text_block = True
                continue
            text_value = block.get("text", "")
            if not isinstance(text_value, str):
                logger.debug("Skipping text block with non-string text value")
                has_non_text_block = True
                continue
            parts.append(text_value)
        text = "".join(parts)
        if text:
            return text, "text"
        return text, "non_text" if has_non_text_block else "empty"

    if isinstance(content, Mapping):
        return "", "empty" if not content else "non_text"

    if content is None:
        return "", "empty"

    return "", "non_text"
