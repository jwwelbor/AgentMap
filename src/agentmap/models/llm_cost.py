"""
Data-only cost and budget models for LLM call receipts.

Introduced by E05-F06. These models are data-only — no business logic lives
here (constructed in ``services/llm/cost_calculator.py`` and the budget-guard
integration seam, never in ``models/``). All monetary fields use
``decimal.Decimal`` (NFR-F-005): rates and computed costs are built from YAML
config values via ``Decimal(str(value))``, and totals are quantized to 6
decimal places, so hosts summing thousands of receipts into durable ledgers
do not accumulate binary-float drift.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class LLMModelRates:
    """
    Configured per-million-token rates for one provider/model pair.

    Each rate is ``Optional[Decimal]``; a ``None`` rate means "not
    configured" for that token bucket, which is what drives REQ-F-002's rule
    that an incomplete catalog entry yields ``cost is None`` rather than a
    silently partial total whenever a positive-count bucket lacks a rate.
    """

    currency: str
    input_per_1m: Optional[Decimal] = None
    output_per_1m: Optional[Decimal] = None
    cache_write_per_1m: Optional[Decimal] = None
    cache_read_per_1m: Optional[Decimal] = None


@dataclass(frozen=True)
class LLMCostBreakdown:
    """
    Deterministic cost computed from ``LLMUsage`` token counts and configured
    rates — never estimated and never read from a provider response
    (REQ-F-001).

    Per-bucket subtotals (``input_cost``, ``output_cost``, ``cache_write_cost``,
    ``cache_read_cost``) are zero when the corresponding usage bucket was
    absent or zero, and each is ``Decimal`` so a host ledger can attribute
    spend per bucket. ``catalog_version`` travels with the number derived
    from that catalog so a receipt can be re-verified against the priced
    version later.
    """

    total_cost: Decimal
    currency: str
    catalog_version: Optional[str]
    input_cost: Decimal
    output_cost: Decimal
    cache_write_cost: Decimal
    cache_read_cost: Decimal


@dataclass(frozen=True)
class LLMBudgetCheck:
    """
    Pre-dispatch payload passed to a registered budget guard's
    ``check_before_dispatch()``.

    Carries only measured or configured values — no fabricated token
    estimates (REQ-F-003, REQ-F-009, Out of Scope 5).

    ``max_output_tokens`` / ``max_possible_output_cost`` fallback-tier
    limitation (accepted, v1): ``LLMFallbackHandler`` builds each fallback
    tier's config itself and dispatches through a callable that never
    carries the primary tier's resolved ``max_tokens``. So on fallback tiers
    — exactly where a cheaper primary may be replaced by a pricier model —
    both fields are ``None`` rather than a value borrowed from a different
    tier. A budget guard must branch on ``attempt_kind`` and price from
    ``rates`` when this bound is absent; it must not assume the bound is
    always populated. See spec.md Architecture Component Change 2 for the
    full rationale and the deferred alternative (widening the fallback
    callable's signature).
    """

    resolved_provider: str
    resolved_model: str
    rates: Optional[LLMModelRates]
    catalog_version: Optional[str]
    max_output_tokens: Optional[int]
    max_possible_output_cost: Optional[Decimal]
    message_count: int
    input_chars: int
    attempt_kind: str  # "primary" | "fallback"
