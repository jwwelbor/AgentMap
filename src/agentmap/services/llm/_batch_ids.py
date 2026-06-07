"""
Shared spec_id sanitization and collision-detection for batch adapters.

All three adapters (Anthropic, OpenAI, Gemini) share the same canonical
id-sanitization path (REQ-F-008; spec §1.9; feedback_one_path_no_duplicate_config).

Usage::

    from agentmap.services.llm._batch_ids import build_spec_id_map, CUSTOM_ID_RE

    spec_id_map = build_spec_id_map(specs, regex=CUSTOM_ID_RE)
"""

import hashlib
import re
from typing import Dict, List, Pattern

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import LLMCallSpec

# Default regex for Anthropic and OpenAI custom_id values.
CUSTOM_ID_RE: Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Regex for Gemini job key values.
GEMINI_KEY_RE: Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _sanitize_spec_id(spec_id: str, regex: Pattern[str] = CUSTOM_ID_RE) -> str:
    """
    Return a provider-safe id for ``spec_id`` using the given ``regex`` constraint.

    If ``spec_id`` already matches ``regex``, return it unchanged.
    Otherwise derive a deterministic SHA-1 hex string truncated to fit within
    the regex's max-length constraint (extracted from ``{1,N}`` quantifier),
    falling back to 64 characters if the quantifier is absent.

    Args:
        spec_id: The raw caller-supplied spec identifier.
        regex: A compiled regex pattern whose ``{1,N}`` quantifier determines
            the maximum safe length.  Defaults to ``CUSTOM_ID_RE`` (Anthropic /
            OpenAI constraint ``^[a-zA-Z0-9_-]{1,64}$``).

    Returns:
        A sanitized string that satisfies ``regex``.
    """
    if regex.match(spec_id):
        return spec_id
    # Extract max length from quantifier like {1,64} or {1,128}; fall back to 64.
    max_len = 64
    m = re.search(r"\{1,(\d+)\}", regex.pattern)
    if m:
        max_len = int(m.group(1))
    return hashlib.sha1(spec_id.encode()).hexdigest()[:max_len]


def build_spec_id_map(
    specs: List[LLMCallSpec],
    regex: Pattern[str] = CUSTOM_ID_RE,
) -> Dict[str, str]:
    """
    Build a ``spec_id -> provider_id`` mapping for a list of call specs.

    Each ``spec.spec_id`` is sanitized via ``_sanitize_spec_id(spec_id, regex)``
    and then checked for collisions.  If two distinct spec_ids produce the same
    provider-safe id, ``LLMServiceError`` is raised immediately so callers never
    send an ambiguous batch to a provider.

    Args:
        specs: Ordered list of ``LLMCallSpec`` objects from the caller.
        regex: Provider regex constraint passed through to ``_sanitize_spec_id``.

    Returns:
        ``Dict[str, str]`` mapping each ``spec_id`` to its provider-safe id.

    Raises:
        LLMServiceError: When two spec_ids sanitize to the same provider-safe id.
    """
    spec_id_map: Dict[str, str] = {}
    seen: Dict[str, str] = {}  # provider_id -> first spec_id

    for spec in specs:
        provider_id = _sanitize_spec_id(spec.spec_id, regex)
        if provider_id in seen:
            raise LLMServiceError(
                f"custom_id collision: spec_id {spec.spec_id!r} and "
                f"{seen[provider_id]!r} both sanitize to {provider_id!r}. "
                "Rename one spec_id to avoid ambiguous demux."
            )
        seen[provider_id] = spec.spec_id
        spec_id_map[spec.spec_id] = provider_id

    return spec_id_map
