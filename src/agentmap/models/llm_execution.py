"""
Data-only execution models for fan-out and batch LLM call contracts.

These models define the shared request and result envelope for multi-call
execution modes introduced by E05-F02. They are intentionally data-only —
no business logic lives here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_tool_call import LLMToolCall

# Structured message block for LLM calls.  Content values may be plain strings
# (text-only messages) or structured dicts/lists (vision, cache-control blocks,
# multi-modal content).  Using Any instead of str matches LangChain and the
# OpenAI / Anthropic SDKs, both of which accept heterogeneous content types.
LLMMessage = Dict[str, Any]
DEFAULT_TOKEN_LIMIT = 10000


@dataclass(frozen=True)
class LLMResponse:
    """
    Internal seam result carrying the resolved provider identity and usage.

    Returned by ``call_llm_async`` and every private async method below it
    (``_call_llm_async_core``, ``_call_llm_async_direct``,
    ``_call_llm_async_with_routing``, ``_invoke_with_resilience_async``).
    The high-level ``ask_async()`` extracts ``.text`` and returns a plain
    ``str`` to preserve its public contract.

    ``resolved_provider`` and ``resolved_model`` reflect the provider and model
    that **actually handled** the request — after routing rewrites or fallback
    tier selection — not the values the caller specified.

    ``usage`` is ``None`` only when the underlying provider did not return
    ``usage_metadata`` on the response.

    ``finish_reason`` is the provider's normalized stop reason when available
    (e.g. Anthropic ``stop_reason`` / OpenAI/Google ``finish_reason``), read
    from the response metadata. It is ``None`` when the provider did not report
    one. Callers use it to detect truncation (``"max_tokens"`` / ``"length"``).

    ``cost`` is the deterministic receipt derived from ``usage`` and the
    configured price catalog (E05-F06). It is ``None`` whenever pricing is
    unconfigured, no catalog entry matches the resolved provider/model, or any
    positive-count usage bucket lacks a configured rate — never a fabricated
    or partial total (REQ-F-001/REQ-F-002).

    ``tool_calls`` is the normalized tool-call list extracted from the
    provider response (E05-F06). It is ``None`` when the response carried no
    tool calls; it is never an empty list (REQ-F-005).
    """

    text: str
    resolved_provider: str
    resolved_model: str
    usage: Optional["LLMUsage"] = None
    finish_reason: Optional[str] = None
    cost: Optional["LLMCostBreakdown"] = None
    tool_calls: Optional[List["LLMToolCall"]] = None


@dataclass
class LLMStreamChunk:
    """
    Normalized chunk from a provider streaming response.

    Emitted by the provider streaming seam as an async iterator. Most chunks
    carry only ``text_delta`` (an incremental text fragment). The terminal
    chunk (``is_final=True``) additionally carries ``usage``, ``finish_reason``,
    ``resolved_provider``, and ``resolved_model`` — the same fields
    ``LLMResponse`` carries — so the streaming path (E06-F03) can reconstruct
    the existing non-streaming result contract.

    ``chunk_index`` is a zero-based, monotonically increasing counter assigned
    by the seam. It is NOT the provider's sequence number.

    Deliberately mirrors ``LLMResponse``'s terminal fields but does **not**
    gain ``cost`` or ``tool_calls`` (E05-F06). That is intentional, not an
    oversight: E06 owns the streaming seam and ``stream_seam.py`` filters
    tool-call events by design, so a streaming chunk never carries a
    tool-call channel to normalize, and cost is out of scope for the
    streaming path (E05-F06 spec.md Out of Scope 3).

    Non-frozen by design (deviation from ``LLMResponse``): the seam accumulates
    the terminal chunk's fields progressively as native events arrive (input
    tokens at message_start, output tokens + stop_reason at message_delta).
    A frozen dataclass would force reconstruction at each accumulation step.
    ``LLMUsage``, ``LLMRequest``, and the batch models are likewise non-frozen.
    """

    text_delta: str  # incremental text fragment; "" on the terminal chunk
    chunk_index: int  # 0-based ordering counter, seam-assigned
    is_final: bool  # True on exactly one chunk (the last)

    # Terminal-only fields (None on non-final chunks)
    usage: Optional["LLMUsage"] = None
    finish_reason: Optional[str] = None
    resolved_provider: Optional[str] = None
    resolved_model: Optional[str] = None


@dataclass
class LLMRequest:
    """
    Caller-owned specification for a single LLM call within a fan-out submission.

    ``request_id`` must be unique within one submission. The fan-out method uses it
    to preserve input order and map results back to the originating spec.
    """

    request_id: str
    messages: List[Dict[str, Any]]
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    routing_context: Optional[Dict[str, Any]] = None
    request_options: Dict[str, Any] = field(default_factory=dict)
    cache_system_prompt: bool = False


@dataclass
class LLMUsage:
    """
    Normalized per-item usage envelope.

    Fields reflect what the realtime path can report. Absent fields remain
    ``None`` rather than carrying fabricated defaults.
    """

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


@dataclass
class LLMExecutionError:
    """
    Structured error payload for a failed fan-out item.

    Replaces raw uncaught exceptions so callers can inspect failure details
    without catching submission-level exceptions.
    """

    error_type: str
    message: str
    retryable: bool


@dataclass
class LLMFanoutResult:
    """
    Terminal per-item result for a fan-out submission.

    ``status`` is a closed terminal set: ``"succeeded"`` or ``"failed"``.
    Successful results carry ``text`` and ``usage``; failed results carry
    ``error``. ``resolved_provider`` and ``resolved_model`` may be ``None``
    when the failure occurs before provider resolution.

    Field names mirror ``LLMResponse`` so the realtime and fan-out result
    envelopes read as one family.
    """

    request_id: str
    status: str  # "succeeded" | "failed"
    resolved_provider: Optional[str] = None
    resolved_model: Optional[str] = None
    text: Optional[str] = None
    usage: Optional[LLMUsage] = None
    error: Optional[LLMExecutionError] = None
