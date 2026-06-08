"""
Data-only execution models for fan-out and batch LLM call contracts.

These models define the shared request and result envelope for multi-call
execution modes introduced by E05-F02. They are intentionally data-only —
no business logic lives here.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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
    """

    text: str
    resolved_provider: str
    resolved_model: str
    usage: Optional["LLMUsage"] = None


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


# ---------------------------------------------------------------------------
# Batch execution models (E05-F03)
# ---------------------------------------------------------------------------


class LLMBatchStatus(str, Enum):
    """
    Normalized batch lifecycle status.

    AgentMap-owned superset of Anthropic's processing_status values.
    ``submitted`` and ``failed`` are AgentMap-side derivations;
    ``in_progress``, ``canceling``, ``ended``, and ``expired`` map 1:1
    from the provider.
    """

    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    CANCELING = "canceling"
    ENDED = "ended"
    EXPIRED = "expired"
    CANCELED = "canceled"
    FAILED = "failed"


@dataclass
class LLMBatchRequestCounts:
    """
    Normalized snapshot of per-item outcome counts for a batch poll result.

    Fields are optional because counts may not be available for all providers
    or at all lifecycle stages.
    """

    processing: Optional[int] = None
    succeeded: Optional[int] = None
    errored: Optional[int] = None
    canceled: Optional[int] = None
    expired: Optional[int] = None


@dataclass
class LLMBatchSubmitRequest:
    """
    Caller-owned submission descriptor for a provider-native batch call.

    ``requests`` must be non-empty and contain unique ``request_id`` values.
    ``provider`` must be one of ``"anthropic"``, ``"openai"``, or ``"google"``.
    No ``api_key`` field — credentials are injected at adapter level.
    """

    provider: str
    model: str
    requests: List[LLMRequest]
    max_tokens: Optional[int] = None
    request_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMBatchHandle:
    """
    Opaque, serializable reference to a submitted provider-native batch.

    Contains only AgentMap-owned types — no ``anthropic.*`` SDK objects.
    Provides ``to_dict()`` / ``from_dict()`` for file-backed persistence
    without carrying credentials.

    ``agentmap_batch_id`` is generated by AgentMap (``amatch_<uuid>``).
    ``provider_batch_id`` is the provider-assigned identifier.
    ``request_id_map`` maps caller ``request_id`` values to the ``custom_id``
    sent to the provider (sanitized for provider constraints).
    """

    agentmap_batch_id: str
    provider_batch_id: str
    status: LLMBatchStatus
    provider: str
    model: str
    request_id_map: Dict[str, str]
    results_url: Optional[str] = None
    result_ref: Optional[str] = None
    expires_at: Optional[str] = None
    ended_at: Optional[str] = None
    request_counts: Optional[LLMBatchRequestCounts] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a plain serializable dict suitable for json.dumps().

        No ``api_key`` is included. ``status`` is serialized as its string
        value so the dict round-trips through JSON without enum awareness.
        """
        counts: Optional[Dict[str, Any]] = None
        if self.request_counts is not None:
            counts = {
                "processing": self.request_counts.processing,
                "succeeded": self.request_counts.succeeded,
                "errored": self.request_counts.errored,
                "canceled": self.request_counts.canceled,
                "expired": self.request_counts.expired,
            }
        return {
            "agentmap_batch_id": self.agentmap_batch_id,
            "provider_batch_id": self.provider_batch_id,
            "status": (
                self.status.value
                if isinstance(self.status, LLMBatchStatus)
                else self.status
            ),
            "provider": self.provider,
            "model": self.model,
            "request_id_map": dict(self.request_id_map),
            "results_url": self.results_url,
            "result_ref": self.result_ref,
            "expires_at": self.expires_at,
            "ended_at": self.ended_at,
            "request_counts": counts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMBatchHandle":
        """
        Reconstruct an ``LLMBatchHandle`` from a serialized dict.

        Inverse of ``to_dict()``. Restores ``status`` as ``LLMBatchStatus``.
        """
        counts: Optional[LLMBatchRequestCounts] = None
        raw_counts = data.get("request_counts")
        if raw_counts is not None:
            counts = LLMBatchRequestCounts(
                processing=raw_counts.get("processing"),
                succeeded=raw_counts.get("succeeded"),
                errored=raw_counts.get("errored"),
                canceled=raw_counts.get("canceled"),
                expired=raw_counts.get("expired"),
            )
        return cls(
            agentmap_batch_id=data["agentmap_batch_id"],
            provider_batch_id=data["provider_batch_id"],
            status=LLMBatchStatus(data["status"]),
            provider=data["provider"],
            model=data["model"],
            request_id_map=dict(data["request_id_map"]),
            results_url=data.get("results_url"),
            result_ref=data.get("result_ref"),
            expires_at=data.get("expires_at"),
            ended_at=data.get("ended_at"),
            request_counts=counts,
        )


@dataclass
class LLMBatchResult:
    """
    Per-item result from a completed provider-native batch.

    ``request_id`` is the caller-provided identifier from ``LLMRequest``.
    ``status`` is one of: ``"succeeded"``, ``"errored"``, ``"canceled"``,
    ``"expired"``.  ``text`` and ``usage`` are populated on success;
    ``error`` is populated on failure.

    Field names mirror ``LLMResponse``. ``resolved_model`` stays optional —
    the Gemini batch adapter legitimately omits it.
    """

    request_id: str
    status: str  # "succeeded" | "errored" | "canceled" | "expired"
    resolved_provider: Optional[str] = None
    resolved_model: Optional[str] = None
    text: Optional[str] = None
    usage: Optional[LLMUsage] = None
    error: Optional[LLMExecutionError] = None


@dataclass
class BatchPollResult:
    """
    Normalized poll result returned by all adapter ``poll()`` implementations.

    All adapters return this dataclass so ``LLMService.poll_batch`` can read
    ``status`` directly without performing its own provider-specific mapping.
    ``result_ref`` carries the provider file/object reference used to fetch
    results (e.g. OpenAI output_file_id); it is ``None`` for providers that
    use URL-based or inline result delivery.
    """

    status: LLMBatchStatus
    request_counts: Optional[LLMBatchRequestCounts] = None
    result_ref: Optional[str] = None
    results_url: Optional[str] = None
    ended_at: Optional[str] = None
    expires_at: Optional[str] = None
