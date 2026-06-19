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

from typing import Any, AsyncIterator, Dict, List, Optional

from agentmap.exceptions import LLMDependencyError
from agentmap.models.llm_execution import LLMMessage, LLMStreamChunk

# ---------------------------------------------------------------------------
# Anthropic native seam
# ---------------------------------------------------------------------------


class AnthropicStreamSeam:
    """
    Provider streaming seam backed by the native ``anthropic.AsyncAnthropic``
    SDK.

    The ``anthropic`` import is deferred to ``__init__`` and gated so a missing
    optional dependency raises ``LLMDependencyError`` (REQ-F-014).

    The ``.stream()`` body is a stub; the full Anthropic event-to-chunk mapping
    (message_start → content_block_delta → message_delta → message_stop) is
    implemented by T-003.
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
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Yield normalized ``LLMStreamChunk`` objects from the Anthropic native
        streaming API.

        Stub — full implementation in T-003.  Credentials are consumed at call
        time; they are never logged (REQ-NF-011).
        """
        raise NotImplementedError(
            "AnthropicStreamSeam.stream() will be implemented by T-003."
        )
        # Needed to satisfy the async-generator type (unreachable but required).
        yield  # type: ignore[misc]


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
