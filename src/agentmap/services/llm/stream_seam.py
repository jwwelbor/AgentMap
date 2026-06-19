"""
Provider streaming seam for E06-F01.

Defines the per-provider stream seam classes and the ``stream_provider``
dispatch function.  Each seam class implements the ``StreamSeamProtocol``
interface (one async-generator method + ``provider_name``).

Architecture reference: spec.md §7.1, TD-1 (mirror batch-adapter pattern,
lighter — no submit/poll/cancel/fetch lifecycle).

Three implementations are provided as class stubs; their ``.stream()`` bodies
will be filled in by T-003 (Anthropic), T-004 (OpenAI), and T-005 (LangChain).

The native SDK imports (``anthropic``, ``openai``) are deferred to ``__init__``
and gated in ``try/except ImportError`` blocks that raise ``LLMDependencyError``
(REQ-F-014, mirroring ``anthropic_batch_adapter.py`` lines 53–60).

Credentials are NOT retained as module-level state and are never logged
(REQ-NF-011, Constraint C9).
"""

from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional

from agentmap.exceptions import LLMDependencyError
from agentmap.models.llm_execution import LLMMessage, LLMStreamChunk, LLMUsage

# ---------------------------------------------------------------------------
# Anthropic native seam
# ---------------------------------------------------------------------------


class AnthropicStreamSeam:
    """
    Provider streaming seam backed by the native ``anthropic.AsyncAnthropic``
    SDK.

    The ``anthropic`` import is deferred to ``__init__`` and gated so a missing
    optional dependency raises ``LLMDependencyError`` (REQ-F-014).

    Event-to-chunk mapping (spec.md §7.2):
      - ``message_start``: capture input_tokens + cache token fields from
        ``message.usage``; no chunk emitted.
      - ``content_block_delta`` with ``delta.type == "text_delta"``: emit a
        non-final ``LLMStreamChunk`` carrying ``delta.text`` and incrementing
        ``chunk_index``.
      - ``content_block_delta`` with any other ``delta.type`` (e.g. tool_use
        ``input_json_delta``): ignored — no chunk emitted (spec.md TD-4).
      - ``message_delta``: capture ``usage.output_tokens`` and
        ``delta.stop_reason``; no chunk emitted.
      - ``message_stop``: emit the terminal ``LLMStreamChunk`` (``is_final=True``,
        ``text_delta=""``) carrying accumulated ``LLMUsage``, ``finish_reason``,
        ``resolved_provider``, and ``resolved_model`` (spec.md REQ-F-006).
      - All other event types (``content_block_start``, ``content_block_stop``,
        ``ping``, etc.) are ignored.

    Credentials are consumed at call time and never logged (REQ-NF-011).
    """

    provider_name: str = "anthropic"

    def __init__(self) -> None:
        try:
            import anthropic  # noqa: PLC0415, F401
        except ImportError:
            raise LLMDependencyError(
                "The 'anthropic' package is required for native Anthropic streaming. "
                "Install it with: pip install anthropic"
            )

    async def stream(
        self,
        messages: List[LLMMessage],
        params: Dict[str, Any],
        *,
        client: Optional[Any] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """
        Yield normalized ``LLMStreamChunk`` objects from the Anthropic native
        streaming API.

        Credentials are consumed at call time and never logged (REQ-NF-011).
        Completion content (``text_delta``) is never logged (REQ-NF-010).

        Args:
            messages: Normalized message list (role + content dicts).
            params: Resolved call parameters; must include ``"model"``.
            client: Optional pre-constructed ``anthropic.AsyncAnthropic`` client.
                    If ``None``, a fresh client is constructed from ``credentials``.
            credentials: Optional dict with ``"api_key"`` and related fields.
                         Values are never logged.

        Yields:
            Non-final ``LLMStreamChunk`` objects for each text delta, then a
            single terminal chunk (``is_final=True``) with accumulated usage and
            metadata.
        """
        import anthropic  # noqa: PLC0415

        # Build or reuse the client — credentials consumed here, never logged.
        if client is None:
            api_key = (credentials or {}).get("api_key")
            if api_key is not None:
                sdk_client = anthropic.AsyncAnthropic(api_key=api_key)
            else:
                sdk_client = anthropic.AsyncAnthropic()
        else:
            sdk_client = client

        model: str = params.get("model", "")
        call_params = {k: v for k, v in params.items() if k != "model"}

        # Accumulate token counts across message_start and message_delta events.
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        cache_creation_tokens: Optional[int] = None
        cache_read_tokens: Optional[int] = None
        stop_reason: Optional[str] = None

        chunk_index: int = 0

        async with sdk_client.messages.stream(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            **call_params,
        ) as stream:
            async for event in stream:
                event_type = getattr(event, "type", None)

                if event_type == "message_start":
                    # Capture input usage from message.usage (spec.md §7.2).
                    msg_usage = getattr(getattr(event, "message", None), "usage", None)
                    if msg_usage is not None:
                        input_tokens = getattr(msg_usage, "input_tokens", None)
                        raw_creation = getattr(
                            msg_usage, "cache_creation_input_tokens", None
                        )
                        raw_read = getattr(msg_usage, "cache_read_input_tokens", None)
                        # Only carry cache fields when they are non-zero; the
                        # SDK may return 0 for non-cached requests.
                        cache_creation_tokens = raw_creation if raw_creation else None
                        cache_read_tokens = raw_read if raw_read else None

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if (
                        delta is not None
                        and getattr(delta, "type", None) == "text_delta"
                    ):
                        text = getattr(delta, "text", "") or ""
                        yield LLMStreamChunk(
                            text_delta=text,
                            chunk_index=chunk_index,
                            is_final=False,
                        )
                        chunk_index += 1
                    # Non-text deltas (input_json_delta, etc.) are silently ignored
                    # per spec.md TD-4 (non-text block filtering rationale).

                elif event_type == "message_delta":
                    # Capture output tokens and stop_reason (spec.md §7.2).
                    delta_usage = getattr(event, "usage", None)
                    if delta_usage is not None:
                        output_tokens = getattr(delta_usage, "output_tokens", None)
                    delta_obj = getattr(event, "delta", None)
                    if delta_obj is not None:
                        stop_reason = getattr(delta_obj, "stop_reason", None)

                elif event_type == "message_stop":
                    # Emit the terminal chunk with accumulated usage and metadata.
                    usage = LLMUsage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_creation_input_tokens=cache_creation_tokens,
                        cache_read_input_tokens=cache_read_tokens,
                    )
                    yield LLMStreamChunk(
                        text_delta="",
                        chunk_index=chunk_index,
                        is_final=True,
                        usage=usage,
                        finish_reason=stop_reason,
                        resolved_provider=self.provider_name,
                        resolved_model=model,
                    )
                    # Terminal chunk emitted; stop iterating.
                    return

                # content_block_start, content_block_stop, ping, and any other
                # event types are intentionally ignored.


# ---------------------------------------------------------------------------
# OpenAI native seam
# ---------------------------------------------------------------------------


class OpenAIStreamSeam:
    """
    Provider streaming seam backed by the native ``openai.AsyncOpenAI`` SDK.

    The ``openai`` import is deferred to ``__init__`` and gated so a missing
    optional dependency raises ``LLMDependencyError`` (REQ-F-014).

    The ``.stream()`` body is a stub; the full OpenAI chunk-to-stream mapping
    (including ``stream_options={"include_usage": True}``, REQ-F-009) is
    implemented by T-004.
    """

    provider_name: str = "openai"

    def __init__(self) -> None:
        try:
            import openai  # noqa: PLC0415, F401
        except ImportError:
            raise LLMDependencyError(
                "The 'openai' package is required for native OpenAI streaming. "
                "Install it with: pip install openai"
            )

    async def stream(
        self,
        messages: List[LLMMessage],
        params: Dict[str, Any],
        *,
        client: Optional[Any] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Yield normalized ``LLMStreamChunk`` objects from the OpenAI native
        streaming API.

        Stub — full implementation in T-004 (including unconditional
        ``stream_options={"include_usage": True}``, REQ-F-009).  Credentials
        are consumed at call time; they are never logged (REQ-NF-011).
        """
        raise NotImplementedError(
            "OpenAIStreamSeam.stream() will be implemented by T-004."
        )
        yield  # type: ignore[misc]


# ---------------------------------------------------------------------------
# LangChain fallback seam
# ---------------------------------------------------------------------------


class LangChainFallbackStreamSeam:
    """
    Provider streaming seam backed by a LangChain chat client's ``.astream()``
    method (yielding ``AIMessageChunk``).

    This is the fallback substrate for any provider key not handled by the
    native Anthropic or OpenAI seams (ADR-2, REQ-F-010).  The
    ``provider_name`` reflects the provider whose LangChain client is supplied
    at call time.

    No native SDK gating is needed here — LangChain itself handles the
    provider SDK dependency.

    The ``.stream()`` body is a stub; the full LangChain chunk-to-stream
    mapping (``AIMessageChunk`` → ``LLMStreamChunk``) is implemented by T-005.
    """

    # Default provider_name for the fallback seam.  The actual runtime provider
    # identity comes from the resolved model string on the terminal chunk
    # (populated by T-005 from the LangChain client's response metadata).
    provider_name: str = "langchain"

    def __init__(self) -> None:
        pass  # No SDK gating needed; LangChain manages its own dependencies.

    async def stream(
        self,
        messages: List[LLMMessage],
        params: Dict[str, Any],
        *,
        client: Optional[Any] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Yield normalized ``LLMStreamChunk`` objects via a LangChain client's
        ``.astream(messages)`` async iterator.

        Stub — full implementation in T-005.  ``client`` is the pre-constructed
        LangChain chat model; credentials are consumed at call time and never
        logged (REQ-NF-011).
        """
        raise NotImplementedError(
            "LangChainFallbackStreamSeam.stream() will be implemented by T-005."
        )
        yield  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Per-provider dispatch
# ---------------------------------------------------------------------------

# Map from canonical provider key to seam class.
# Anthropic and OpenAI use native SDK seams; all other providers fall back to
# the LangChain substrate.  Mirrors the duck-typed selection pattern in
# LLMService._get_adapter / di/container_parts/llm.py (TD-1, REQ-F-011).
_NATIVE_SEAM_CLASSES: Dict[str, type] = {
    "anthropic": AnthropicStreamSeam,
    "openai": OpenAIStreamSeam,
}


async def stream_provider(
    provider: str,
    messages: List[LLMMessage],
    params: Dict[str, Any],
    *,
    client: Optional[Any] = None,
    credentials: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[LLMStreamChunk]:
    """
    Dispatch to the per-provider streaming seam by provider key (REQ-F-011).

    ``"anthropic"`` routes to :class:`AnthropicStreamSeam`;
    ``"openai"`` routes to :class:`OpenAIStreamSeam`;
    any other key falls back to :class:`LangChainFallbackStreamSeam`.

    Credentials are passed at call time and are never logged (REQ-NF-011).

    Args:
        provider: Canonical provider key (e.g. ``"anthropic"``, ``"openai"``).
        messages: Normalized message list (role + content dicts).
        params: Resolved call parameters (model, max_tokens, temperature, …).
        client: Optional pre-constructed provider client.
        credentials: Optional dict of provider credentials (api_key, etc.).

    Yields:
        :class:`~agentmap.models.llm_execution.LLMStreamChunk` objects.
        The last chunk has ``is_final=True``.
    """
    seam_cls = _NATIVE_SEAM_CLASSES.get(provider)
    if seam_cls is not None:
        seam = seam_cls()
    else:
        seam = LangChainFallbackStreamSeam()

    async for chunk in seam.stream(
        messages,
        params,
        client=client,
        credentials=credentials,
    ):
        yield chunk
