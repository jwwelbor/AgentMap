"""
LLM Message Service for handling message conversion, extraction, and cache metadata injection.

Provides utilities for converting messages between different formats, extracting
content for analysis, and injecting provider-specific prompt-caching metadata.

Renamed from llm_message_utils.py (LLMMessageUtils) per E05-F05 Decision 3.
"""

import copy
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Cached LangChain message classes — resolved once to avoid retrying a
# failed langchain.schema import on every convert_messages_to_langchain call.
_langchain_message_classes = None


def _resolve_langchain_message_classes():
    global _langchain_message_classes
    if _langchain_message_classes is not None:
        return _langchain_message_classes
    try:
        from langchain.schema import AIMessage, HumanMessage, SystemMessage
    except ImportError:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            return None
    _langchain_message_classes = (AIMessage, HumanMessage, SystemMessage)
    return _langchain_message_classes


class LLMMessageService:
    """Service for handling LLM message transformation and cache metadata injection."""

    @staticmethod
    def has_prompt_caching(messages: List[Dict[str, Any]]) -> bool:
        """
        Detect provider-native prompt-caching metadata in structured messages.

        Args:
            messages: List of message dictionaries

        Returns:
            True when any structured content block includes cache metadata
        """
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")
            if not isinstance(content, list):
                continue

            for block in content:
                if isinstance(block, dict) and "cache_control" in block:
                    return True

        return False

    @staticmethod
    def strip_cache_control(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return a copy of *messages* with all ``cache_control`` blocks removed.

        ``cache_control`` is an Anthropic-specific content-block extension. When a
        request fails over to a non-Anthropic provider, reusing the original
        Anthropic-tagged messages can be rejected at that provider's API boundary.
        Fallback tiers are recovery calls where prompt-cache savings are moot, so
        the tier ladder strips the marker to guarantee cross-provider
        compatibility. Messages without any ``cache_control`` are returned as-is
        (no copy) — this is a no-op for the common case.

        Args:
            messages: List of message dictionaries (content may be a str or a
                list of structured content blocks).

        Returns:
            A new message list with ``cache_control`` stripped from every content
            block, or the original list when nothing needed stripping.
        """
        if not LLMMessageService.has_prompt_caching(messages):
            return messages

        sanitized: List[Dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
                sanitized.append(msg)
                continue
            new_content = []
            for block in msg["content"]:
                if isinstance(block, dict) and "cache_control" in block:
                    block = {k: v for k, v in block.items() if k != "cache_control"}
                new_content.append(block)
            sanitized.append({**msg, "content": new_content})
        return sanitized

    @staticmethod
    def extract_prompt_from_messages(messages: List[Dict[str, Any]]) -> str:
        """
        Extract the main prompt content from messages for complexity analysis.

        Args:
            messages: List of message dictionaries

        Returns:
            Combined prompt text
        """
        if not messages:
            return ""

        # Combine all user and system messages
        prompt_parts = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "system"] and content:
                if isinstance(content, list):
                    # Multimodal content blocks — extract text parts only
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                prompt_parts.append(text)
                elif isinstance(content, str):
                    prompt_parts.append(content)

        return " ".join(prompt_parts)

    @staticmethod
    def convert_messages_to_langchain(messages: List[Dict[str, Any]]) -> List[Any]:
        """
        Convert messages to LangChain message format.

        Supports both plain text content (str) and multimodal content blocks
        (list of dicts). When content is a list, it is passed directly to the
        LangChain message constructor — LangChain chat models handle multimodal
        content blocks natively.

        Args:
            messages: List of message dictionaries

        Returns:
            List of LangChain message objects
        """
        classes = _resolve_langchain_message_classes()
        if classes is None:
            return messages
        AIMessage, HumanMessage, SystemMessage = classes

        langchain_messages = []

        for msg in messages:
            if not isinstance(msg, dict):
                langchain_messages.append(msg)
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # default to user
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages

    @staticmethod
    def inject_cache_metadata(
        messages: List[Dict[str, Any]],
        provider: str,
        cache_system_prompt: bool,
    ) -> List[Dict[str, Any]]:
        """
        Inject provider-specific prompt-caching metadata into messages.

        When cache_system_prompt=False, returns messages unchanged (zero-cost path).
        When cache_system_prompt=True and provider is "anthropic":
          - Finds the system message(s) in the list.
          - If content is a plain string, converts it to a structured content block
            list with one text block carrying cache_control: {"type": "ephemeral"}.
          - If content is already a structured list, adds cache_control to the last
            text block that does not already have cache_control (idempotent for
            E05-F01 passthrough coexistence per NFR-F-005).
        When provider is "openai", returns messages unchanged (caching is automatic).
        When provider is any other value, returns messages unchanged.

        Args:
            messages: List of message dictionaries (not mutated — defensive copy made).
            provider: The resolved LLM provider name (e.g., "anthropic", "openai").
            cache_system_prompt: When True, inject cache metadata for supported providers.

        Returns:
            Transformed messages list (new list; original is not mutated).
        """
        if not cache_system_prompt:
            logger.debug(
                "inject_cache_metadata: provider=%s, injected=False, reason=cache_system_prompt_false",
                provider,
            )
            return list(messages)

        if provider != "anthropic":
            logger.debug(
                "inject_cache_metadata: provider=%s, injected=False, reason=no-op",
                provider,
            )
            return list(messages)

        # Anthropic path: make a defensive copy and inject into system messages
        result = copy.deepcopy(messages)
        injected = False

        for msg in result:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "system":
                continue

            content = msg.get("content", "")

            if isinstance(content, str):
                # Convert plain string to structured content block with cache_control
                msg["content"] = [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
                injected = True

            elif isinstance(content, list):
                # Find the last text block by position.  If it already has
                # cache_control, the system message is already cached — skip
                # injection entirely so we do not double-wrap an earlier block
                # (NFR-F-005 idempotency guard).
                last_text_idx = None
                for i, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "text":
                        last_text_idx = i

                if last_text_idx is not None:
                    last_text_block = content[last_text_idx]
                    if "cache_control" not in last_text_block:
                        last_text_block["cache_control"] = {"type": "ephemeral"}
                        injected = True

        logger.debug(
            "inject_cache_metadata: provider=%s, injected=%s, messages_count=%d",
            provider,
            injected,
            len(messages),
        )
        return result
