"""Data-only evidence for one physical, non-streaming provider attempt."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Optional

from agentmap.models.llm_cost import LLMModelRates
from agentmap.models.llm_execution import LLMUsage


@dataclass(frozen=True)
class LLMResponseEvidence:
    """Decoded entity bytes only; never include HTTP/client/request objects."""

    status: Literal["available", "unavailable", "partial"] = "unavailable"
    layer: Literal["http_entity_body"] = "http_entity_body"
    body: Optional[bytes] = field(default=None, repr=False)
    http_status: Optional[int] = None
    media_type: Optional[str] = None
    unavailable_reason: Optional[str] = "no_response"

    def __post_init__(self) -> None:
        reasons = {
            "no_response",
            "interrupted_read",
            "capture_not_supported",
            "capture_failed",
            "retention_disabled",
        }
        if self.layer != "http_entity_body" or self.status not in {
            "available",
            "unavailable",
            "partial",
        }:
            raise ValueError("invalid response evidence status/layer")
        if self.body is not None and not isinstance(self.body, bytes):
            raise TypeError("response evidence body must be bytes")
        if self.status == "available":
            valid = self.body is not None and self.unavailable_reason is None
        else:
            valid = self.unavailable_reason in reasons and (
                (self.body is None) == (self.status == "unavailable")
            )
        if not valid:
            raise ValueError("inconsistent response evidence")


@dataclass(frozen=True)
class LLMAttemptDescription:
    resolved_provider: str
    resolved_model: str
    attempt_kind: str
    retry_ordinal: int  # One-based within the resolved primary/fallback tier.
    rates: Optional[LLMModelRates]
    catalog_version: Optional[str]
    max_output_tokens: Optional[int]


@dataclass(frozen=True)
class LLMAttemptOutcome:
    """Unknown fields stay None; an error classification never implies no charge."""

    classification: str
    usage: Optional[LLMUsage] = None
    cost_usd: Optional[Decimal] = None
    provider_request_id: Optional[str] = None
    error_type: Optional[str] = None
    cleanup_failed: bool = False
    response_evidence: LLMResponseEvidence = field(default_factory=LLMResponseEvidence)
