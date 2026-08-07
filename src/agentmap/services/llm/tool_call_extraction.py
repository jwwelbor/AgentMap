"""
Tool-call extraction and text normalization for LLM async receipts (E05-F06).

Two pure, module-level helpers used at ``LLMResponse`` construction in
``LLMService._invoke_with_resilience_async``:

- ``extract_tool_calls`` reads LangChain's already-normalized ``tool_calls``
  channel (populated for Anthropic ``tool_use`` blocks, OpenAI ``tool_calls``,
  and Google ``function_call`` parts alike) into ``LLMToolCall`` entries
  (REQ-F-005). AgentMap does not re-derive the three incompatible provider
  shapes itself -- the same reuse posture ``LLMService._extract_llm_usage``
  takes toward ``usage_metadata``.
- ``normalize_response_text`` guarantees ``LLMResponse.text`` is always a
  ``str`` even when a provider's ``content`` is a block list (REQ-F-012),
  which is the mechanism that keeps REQ-F-005/REQ-F-006's text guarantees
  true once tool-bound calls exist.

Both functions mirror ``_extract_llm_usage``'s per-field tolerance: a
malformed entry is skipped with a debug log rather than raising, so a single
bad field never converts a successful provider call into a failed one.

Not wired into ``LLMService`` here in the sense of ``tools=``/``bind_tools``
send-path support -- that is T-E05-F06-006. This module only supplies the
receive-side extraction and the text-shape guard.
"""

import logging
from typing import Any, List, Optional

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
    Entries missing ``id`` or ``name``, or carrying a non-dict ``args``, are
    skipped with a debug log rather than raising, so a malformed entry never
    converts a successful call into a failure; a well-formed entry elsewhere
    in the same list is still extracted.
    """
    raw_tool_calls = getattr(response, "tool_calls", None)
    if not isinstance(raw_tool_calls, list) or not raw_tool_calls:
        return None

    extracted: List[LLMToolCall] = []
    for entry in raw_tool_calls:
        if not isinstance(entry, dict):
            logger.debug("Skipping malformed tool call entry (not a dict): %r", entry)
            continue

        call_id = entry.get("id")
        name = entry.get("name")
        if not call_id or not name:
            logger.debug(
                "Skipping tool call entry missing required id/name field: %r", entry
            )
            continue

        arguments = entry.get("args")
        if not isinstance(arguments, dict):
            logger.debug("Skipping tool call entry with non-dict args field: %r", entry)
            continue

        extracted.append(LLMToolCall(id=call_id, name=name, arguments=arguments))

    return extracted or None


def normalize_response_text(response: Any) -> str:
    """Normalize a provider response into ``LLMResponse.text`` -- always a ``str``.

    Provider-agnostic, shape-keyed rule (REQ-F-012):
    - No ``content`` attribute at all: fall back to ``str(response)``
      (matches the pre-existing catch-all this helper replaces).
    - ``content`` is a ``str``: used verbatim (the common path -- must not
      change behavior).
    - ``content`` is a ``list``: concatenate the ``text`` value of every
      block whose ``type == "text"``, yielding ``""`` when there are none.
      Non-dict entries are skipped rather than raising. A ``text`` key that
      is missing contributes ``""`` for that block. A ``text`` value that is
      present but not a ``str`` is coerced via ``str(...)`` -- spec.md does
      not pin this sub-case; coercion (over skipping) was chosen so a
      non-string text payload is never silently dropped.
    - Anything else (non-str, non-list ``content``): fall back to
      ``str(content)``.
    """
    if not hasattr(response, "content"):
        return str(response)

    content = response.content
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text_value = block.get("text", "")
            if not isinstance(text_value, str):
                text_value = str(text_value)
            parts.append(text_value)
        return "".join(parts)

    return str(content)
