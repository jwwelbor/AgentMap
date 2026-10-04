"""Data-only evidence for one physical, non-streaming provider attempt."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from agentmap.models.llm_cost import LLMModelRates
from agentmap.models.llm_execution import LLMUsage


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
