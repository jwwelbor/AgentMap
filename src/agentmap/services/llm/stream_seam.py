"""
Provider streaming seam for E06-F01.

Defines the per-provider stream seam classes and the ``stream_provider``
dispatch function.  Each seam class implements the ``StreamSeamProtocol``
interface (one async-generator method + ``provider_name``).

Architecture reference: spec.md §7.1, TD-1 (mirror batch-adapter pattern,
lighter — no submit/poll/cancel/fetch lifecycle).

Three implementations are provided: native Anthropic and OpenAI seams plus a
LangChain ``.astream()`` fallback for all other providers.

The native SDK imports (``anthropic``, ``openai``) are deferred to ``__init__``
and gated in ``try/except ImportError`` blocks that raise ``LLMDependencyError``
(REQ-F-014, mirroring ``anthropic_batch_adapter.py`` lines 53–60).

Credentials are NOT retained as module-level state and are never logged
(REQ-NF-011, Constraint C9).
"""

from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional

from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import LLMMessage, LLMStreamChunk, LLMUsage

# ---------------------------------------------------------------------------
# Message feature helpers (Constraint C4 / REQ-F-012, REQ-F-013 / TD-6)
# ---------------------------------------------------------------------------


def _messages_contain_cache_control(messages: List[LLMMessage]) -> bool:
    """Return True if any content block in *messages* carries a ``cache_control`` key.

    Checks both string-content messages (no blocks) and list-content messages
    (multimodal / structured content blocks).
    """
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "cache_control" in block:
                    return True
    return False


def _reject_unsupported_cache_control(seam_name: str, provider_name: str) -> None:
    """Raise ``LLMServiceError`` describing that ``cache_control`` is not supported.

    Called by seam implementations that cannot carry ``cache_control`` in
    streaming (REQ-F-013, TD-6, Constraint C4).  Raising here — before any
    ``yield`` — guarantees zero chunks are produced before the error.
    """
    raise LLMServiceError(
        f"The '{seam_name}' streaming seam (provider='{provider_name}') does not "
        "support 'cache_control' blocks in streaming mode.  Remove the "
        "'cache_control' block from your messages, or use the Anthropic native "
        "seam which carries 'cache_control' in streaming.  "
        "(spec.md REQ-F-013, Constraint C4)"
    )


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

                # message_stop, content_block_start, content_block_stop, ping,
                # and any other event types are intentionally ignored here.
                # The terminal chunk is emitted after the iterator is exhausted
                # (terminal-after-exhaust pattern) so that an empty or truncated
                # stream (no message_stop) still satisfies AC-5.

        # Emit the single terminal chunk after the event iterator is fully
        # exhausted.  This fires whether message_stop arrived, was absent (empty
        # stream), or the stream was truncated before message_stop — ensuring
        # exactly one is_final=True chunk is always emitted (AC-5).
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


# ---------------------------------------------------------------------------
# OpenAI native seam
# ---------------------------------------------------------------------------


class OpenAIStreamSeam:
    """
    Provider streaming seam backed by the native ``openai.AsyncOpenAI`` SDK.

    The ``openai`` import is deferred to ``__init__`` and gated so a missing
    optional dependency raises ``LLMDependencyError`` (REQ-F-014).

    Event-to-chunk mapping (spec.md §7.2):
      - ``chunk.choices[0].delta.content`` (non-None): emit a non-final
        ``LLMStreamChunk`` carrying the text delta; ``None`` content →
        ``text_delta=""`` (no crash, no ``None`` propagation).
      - ``chunk.choices[0].finish_reason`` (non-null): capture as accumulating
        ``finish_reason``; no chunk emitted at this step.
      - Final usage chunk (``choices == []``, ``chunk.usage`` set): capture
        ``usage`` into terminal fields.
      - End of iterator: emit the single terminal ``LLMStreamChunk``
        (``is_final=True``, ``text_delta=""``) carrying accumulated ``LLMUsage``
        (or ``None`` if no usage chunk arrived), ``finish_reason``,
        ``resolved_provider="openai"``, and ``resolved_model`` (REQ-F-008).

    ``stream_options={"include_usage": True}`` is passed unconditionally to the
    SDK call so the final usage-bearing chunk is emitted (REQ-F-009, TD-5).

    Credentials are consumed at call time and never logged (REQ-NF-011).
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
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """
        Yield normalized ``LLMStreamChunk`` objects from the OpenAI native
        streaming API.

        Passes ``stream_options={"include_usage": True}`` unconditionally so
        the final usage-bearing chunk is emitted by OpenAI (REQ-F-009).
        Credentials are consumed at call time and never logged (REQ-NF-011).
        Completion content (``text_delta``) is never logged (REQ-NF-010).

        Args:
            messages: Normalized message list (role + content dicts).
            params: Resolved call parameters; must include ``"model"``.
            client: Optional pre-constructed ``openai.AsyncOpenAI`` client.
                    If ``None``, a fresh client is constructed from
                    ``credentials``.
            credentials: Optional dict with ``"api_key"`` and related fields.
                         Values are never logged.

        Yields:
            Non-final ``LLMStreamChunk`` objects for each text delta, then a
            single terminal chunk (``is_final=True``) with accumulated usage
            and metadata.
        """
        import openai  # noqa: PLC0415

        # Build or reuse the client — credentials consumed here, never logged.
        if client is None:
            api_key = (credentials or {}).get("api_key")
            if api_key is not None:
                sdk_client = openai.AsyncOpenAI(api_key=api_key)
            else:
                sdk_client = openai.AsyncOpenAI()
        else:
            sdk_client = client

        model: str = params.get("model", "")
        call_params = {k: v for k, v in params.items() if k != "model"}

        # Accumulate finish_reason and usage across chunks.
        finish_reason: Optional[str] = None
        usage: Optional[LLMUsage] = None

        chunk_index: int = 0

        # REQ-F-009: stream_options={"include_usage": True} is set unconditionally
        # at this native call-site so OpenAI emits a final usage-bearing chunk.
        async for oai_chunk in await sdk_client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            stream_options={"include_usage": True},
            **call_params,
        ):
            choices = getattr(oai_chunk, "choices", None) or []

            # Final usage chunk: choices == [], chunk.usage set (spec.md §7.2).
            if not choices:
                raw_usage = getattr(oai_chunk, "usage", None)
                if raw_usage is not None:
                    usage = LLMUsage(
                        input_tokens=getattr(raw_usage, "prompt_tokens", None),
                        output_tokens=getattr(raw_usage, "completion_tokens", None),
                    )
                # No chunk emitted for the usage-only event.
                continue

            # Regular chunk with choices: extract content and finish_reason.
            choice = choices[0]
            delta = getattr(choice, "delta", None)

            raw_content = getattr(delta, "content", None) if delta is not None else None
            # Treat None content as "" (REQ-F-008 / TC-F01-OAI-2).
            text = raw_content if raw_content is not None else ""

            raw_finish = getattr(choice, "finish_reason", None)
            if raw_finish is not None:
                # Capture finish_reason; it does not force an immediate chunk yield.
                finish_reason = raw_finish

            # Emit a non-final chunk only when there is actual text content or
            # when content was explicitly present (even as "").  A chunk that
            # carries only a finish_reason and no content (content=None) does
            # not produce a text-delta emission per spec §7.2 mapping table.
            if raw_content is not None:
                yield LLMStreamChunk(
                    text_delta=text,
                    chunk_index=chunk_index,
                    is_final=False,
                )
                chunk_index += 1

        # Emit the single terminal chunk after the iterator is exhausted.
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=chunk_index,
            is_final=True,
            usage=usage,
            finish_reason=finish_reason,
            resolved_provider=self.provider_name,
            resolved_model=model,
        )


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

    The ``.stream()`` body maps the LangChain ``.astream()`` output
    (``AIMessageChunk`` → ``LLMStreamChunk``).
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
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """
        Yield normalized ``LLMStreamChunk`` objects via a LangChain client's
        ``.astream(messages)`` async iterator.

        Maps ``AIMessageChunk`` objects (spec.md §7.2 LangChain fallback table):
          - Each chunk's ``.content`` → a non-final ``LLMStreamChunk`` with
            ``text_delta=content`` and incrementing ``chunk_index``.
          - After the iterator is exhausted, emit the single terminal
            ``LLMStreamChunk`` (``is_final=True``, ``text_delta=""``) carrying:
            - ``finish_reason`` from the last chunk's ``response_metadata``
              (key ``"finish_reason"``), if present.
            - ``usage`` from the last chunk's ``usage_metadata`` when present;
              ``None`` when ``usage_metadata`` is absent (REQ-F-010, TC-F01-LC-3).
            - ``resolved_provider`` = ``self.provider_name``.
            - ``resolved_model`` from ``params["model"]``.

        Credentials are consumed at call time and never logged (REQ-NF-011).
        Completion content (``text_delta``) is never logged (REQ-NF-010).

        Args:
            messages: Normalized message list (role + content dicts).
            params: Resolved call parameters; ``"model"`` is used for the
                    terminal chunk's ``resolved_model``.
            client: Pre-constructed LangChain chat model (must expose
                    ``.astream(messages)`` returning an async iterator of
                    ``AIMessageChunk``-like objects).
            credentials: Optional credentials dict (not used by this seam —
                         LangChain manages its own provider credentials inside
                         the client; included for interface uniformity).

        Yields:
            Non-final ``LLMStreamChunk`` objects for each content chunk, then
            a single terminal chunk (``is_final=True``) with usage and metadata.
        """
        model: str = params.get("model", "")

        # credentials is accepted for interface uniformity with the native seams
        # (StreamSeamProtocol symmetry) but LangChain manages its own provider
        # credentials inside the client object — there is nothing to extract here.
        # The parameter is intentionally unused in this seam implementation.
        del credentials  # suppress "unused variable" linters (REQ-NF-011)

        # The LangChain fallback seam requires a pre-constructed client — there is
        # no provider-SDK construction path here (client construction is F02's scope,
        # per spec.md §9 ADR-3).  A missing client is a caller error.
        if client is None:
            raise ValueError(
                "LangChainFallbackStreamSeam.stream() requires a pre-constructed "
                "LangChain client (client=...).  Client construction is handled by F02."
            )

        # REQ-F-013 / Constraint C4 (TD-6): The LangChain fallback seam does NOT
        # carry ``cache_control`` blocks — LangChain's .astream() interface has no
        # native support for Anthropic prompt-caching control keys in streaming.
        # Reject explicitly before yielding any chunk so callers learn immediately
        # rather than silently losing the cache_control semantics.
        if _messages_contain_cache_control(messages):
            _reject_unsupported_cache_control(
                "LangChainFallbackStreamSeam", self.provider_name
            )

        # Accumulate terminal fields as we consume the iterator.
        finish_reason: Optional[str] = None
        usage: Optional[LLMUsage] = None
        chunk_index: int = 0

        # FIX (BLOCKER-1): astream() is an async-generator function, NOT a
        # coroutine.  inspect.isasyncgenfunction(BaseChatModel.astream) == True.
        # ``await client.astream(...)`` raises TypeError at runtime.
        # Iterate directly without await.
        async for lc_chunk in client.astream(messages):
            content: str = getattr(lc_chunk, "content", "") or ""

            # Capture the latest response_metadata and usage_metadata so the
            # terminal chunk can read them from the last chunk in the stream.
            response_metadata = getattr(lc_chunk, "response_metadata", None) or {}
            raw_usage_metadata = getattr(lc_chunk, "usage_metadata", None)

            # Update finish_reason from this chunk; the last update wins.
            # FIX (MEDIUM): check "finish_reason" first (OpenAI-via-LangChain),
            # then fall back to "stop_reason" (Anthropic-via-LangChain), so
            # finish_reason is populated across all underlying providers.
            raw_finish = response_metadata.get("finish_reason")
            if raw_finish is None:
                raw_finish = response_metadata.get("stop_reason")
            if raw_finish is not None:
                finish_reason = raw_finish

            # FIX (BLOCKER-2): AIMessageChunk.usage_metadata is a dict at
            # runtime (UsageMetadata is a TypedDict).  getattr(a_dict, key,
            # None) always returns None — use dict.get() instead.
            # Defensive: handle both dict (real runtime shape) and object
            # (hypothetical subclass / other LangChain integrations), mirroring
            # the pattern in llm_service.py:2465-2468.
            if raw_usage_metadata is not None:
                if isinstance(raw_usage_metadata, dict):
                    in_tok = raw_usage_metadata.get("input_tokens")
                    out_tok = raw_usage_metadata.get("output_tokens")
                else:
                    in_tok = getattr(raw_usage_metadata, "input_tokens", None)
                    out_tok = getattr(raw_usage_metadata, "output_tokens", None)
                usage = LLMUsage(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                )

            yield LLMStreamChunk(
                text_delta=content,
                chunk_index=chunk_index,
                is_final=False,
            )
            chunk_index += 1

        # Emit the single terminal chunk after the iterator is exhausted.
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=chunk_index,
            is_final=True,
            usage=usage,
            finish_reason=finish_reason,
            resolved_provider=self.provider_name,
            resolved_model=model,
        )


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
