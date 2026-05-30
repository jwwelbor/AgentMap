"""
Data-only execution models for fan-out and batch LLM call contracts.

These models define the shared request and result envelope for multi-call
execution modes introduced by E05-F02. They are intentionally data-only —
no business logic lives here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Structured message block for LLM calls.  Content values may be plain strings
# (text-only messages) or structured dicts/lists (vision, cache-control blocks,
# multi-modal content).  Using Any instead of str matches LangChain and the
# OpenAI / Anthropic SDKs, both of which accept heterogeneous content types.
LLMMessage = Dict[str, Any]


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
    """

    text: str
    resolved_provider: str
    resolved_model: str
    usage: Optional["LLMUsage"] = None


@dataclass
class LLMCallSpec:
    """
    Caller-owned specification for a single LLM call within a fan-out submission.

    ``spec_id`` must be unique within one submission. The fan-out method uses it
    to preserve input order and map results back to the originating spec.
    """

    spec_id: str
    messages: List[Dict[str, Any]]
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    routing_context: Optional[Dict[str, Any]] = None
    request_options: Dict[str, Any] = field(default_factory=dict)


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
class LLMCallResult:
    """
    Terminal per-item result for a fan-out submission.

    ``status`` is a closed terminal set: ``"succeeded"`` or ``"failed"``.
    Successful results carry ``content`` and ``usage``; failed results carry
    ``error``. ``provider`` and ``model`` may be ``None`` when the failure
    occurs before provider resolution.
    """

    spec_id: str
    status: str  # "succeeded" | "failed"
    provider: Optional[str] = None
    model: Optional[str] = None
    content: Optional[str] = None
    usage: Optional[LLMUsage] = None
    error: Optional[LLMExecutionError] = None
