"""
Deterministic cost calculator for LLM async receipts (E05-F06).

``LLMCostCalculator`` turns an ``LLMUsage`` plus a resolved provider/model
into a deterministic ``LLMCostBreakdown`` -- or an explicit ``None``, never a
fabricated or partial total (REQ-F-001, REQ-F-002, Decision 7).

Placed in ``services/llm/`` alongside ``stream_seam.py`` rather than as more
methods on ``llm_service.py``, per claude.md's file-size limits
(NFR-F-006, Decision 10).

Not wired into ``LLMService`` here -- that integration is T-E05-F06-004.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from agentmap.exceptions import LLMConfigurationError
from agentmap.models.llm_cost import LLMCostBreakdown, LLMModelRates
from agentmap.models.llm_execution import LLMUsage

_QUANTUM = Decimal("0.000001")


class LLMCostCalculator:
    """
    Computes deterministic per-call cost from a configured price catalog.

    Constructed from the ``llm.pricing`` config dict (see
    ``LLMConfigManager.get_pricing_config()`` /
    ``AppConfigService.get_llm_pricing_config()``) and a logging service.
    """

    def __init__(self, pricing_config: Dict[str, Any], logging_service):
        """
        Args:
            pricing_config: The ``llm.pricing`` dict, shaped
                ``{"catalog_version": ..., "currency": ..., "models": {...}}``
                (an empty/absent catalog is ``{"catalog_version": None,
                "currency": "USD", "models": {}}``).
            logging_service: Service exposing ``get_class_logger(self)``.
        """
        self._logger: logging.Logger = logging_service.get_class_logger(self)
        self._catalog_version: Optional[str] = pricing_config.get("catalog_version")
        self._currency: str = pricing_config.get("currency") or "USD"

        raw_models: Dict[str, Any] = pricing_config.get("models") or {}
        self._raw_rate_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for provider, models in raw_models.items():
            for model, raw_rates in (models or {}).items():
                self._raw_rate_index[(provider.lower(), model.lower())] = (
                    raw_rates or {}
                )

    @property
    def catalog_version(self) -> Optional[str]:
        """The configured catalog version, or ``None`` when unconfigured."""
        return self._catalog_version

    def get_rates(self, provider: str, model: str) -> Optional[LLMModelRates]:
        """
        Look up configured rates for a resolved provider/model pair.

        Case-insensitive exact match only -- no prefix or fuzzy matching
        (YAGNI, spec.md Component Change 5). Returns ``None`` when the
        catalog has no entry for this pair.

        Raises:
            LLMConfigurationError: If a configured rate value cannot be
                parsed as a ``Decimal`` -- a malformed catalog entry must be
                loud, never silently indistinguishable from "unpriced"
                (Decision 7, TC-001a).
        """
        raw_rates = self._raw_rate_index.get((provider.lower(), model.lower()))
        if raw_rates is None:
            return None

        return LLMModelRates(
            currency=self._currency,
            input_per_1m=self._to_decimal(raw_rates.get("input_per_1m")),
            output_per_1m=self._to_decimal(raw_rates.get("output_per_1m")),
            cache_write_per_1m=self._to_decimal(raw_rates.get("cache_write_per_1m")),
            cache_read_per_1m=self._to_decimal(raw_rates.get("cache_read_per_1m")),
        )

    def calculate(
        self, usage: Optional[LLMUsage], provider: str, model: str
    ) -> Optional[LLMCostBreakdown]:
        """
        Compute a deterministic cost breakdown, or ``None`` when the total
        cannot be trusted.

        Returns ``None`` in every REQ-F-002 case: ``usage is None``, no
        catalog entry for the resolved pair, or any token bucket present in
        ``usage`` with a value greater than zero has no configured rate. A
        bucket whose value is ``None`` or ``0`` contributes nothing and does
        not require a configured rate.
        """
        if usage is None:
            return None

        rates = self.get_rates(provider, model)
        if rates is None:
            return None

        buckets = (
            (usage.input_tokens, rates.input_per_1m),
            (usage.output_tokens, rates.output_per_1m),
            (usage.cache_creation_input_tokens, rates.cache_write_per_1m),
            (usage.cache_read_input_tokens, rates.cache_read_per_1m),
        )
        if any(tokens and rate is None for tokens, rate in buckets):
            return None

        input_cost = self._bucket_cost(usage.input_tokens, rates.input_per_1m)
        output_cost = self._bucket_cost(usage.output_tokens, rates.output_per_1m)
        cache_write_cost = self._bucket_cost(
            usage.cache_creation_input_tokens, rates.cache_write_per_1m
        )
        cache_read_cost = self._bucket_cost(
            usage.cache_read_input_tokens, rates.cache_read_per_1m
        )
        total_cost = self._quantize(
            input_cost + output_cost + cache_write_cost + cache_read_cost
        )

        return LLMCostBreakdown(
            total_cost=total_cost,
            currency=rates.currency,
            catalog_version=self._catalog_version,
            input_cost=self._quantize(input_cost),
            output_cost=self._quantize(output_cost),
            cache_write_cost=self._quantize(cache_write_cost),
            cache_read_cost=self._quantize(cache_read_cost),
        )

    @staticmethod
    def _bucket_cost(tokens: Optional[int], rate: Optional[Decimal]) -> Decimal:
        """One bucket's cost: ``tokens / 1_000_000 * rate``, or zero when the
        bucket is absent/zero (rate need not be configured in that case)."""
        if not tokens or rate is None:
            return Decimal("0")
        return (Decimal(tokens) / Decimal(1_000_000)) * rate

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        """Quantize to 6 decimal places, ROUND_HALF_UP (NFR-F-005)."""
        return value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        """Parse a YAML-sourced rate value via ``Decimal(str(value))``, never
        ``Decimal(float)`` (NFR-F-005 -- avoids binary-float precision loss).

        Raises:
            LLMConfigurationError: If ``value`` is not ``None`` and cannot be
                parsed as a ``Decimal``, or parses to a non-finite (NaN,
                ±Infinity) or negative value -- a config-authoring bug must
                be loud, not silently treated as "not configured" or allowed
                to corrupt a downstream total_cost (Decision 7, TD-045).
        """
        if value is None:
            return None
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise LLMConfigurationError(
                f"Invalid llm.pricing rate value {value!r}: not a valid "
                "decimal number. Fix the catalog entry rather than leaving "
                "it -- a malformed rate must not be silently treated as "
                "unpriced."
            ) from exc

        if not dec.is_finite():
            raise LLMConfigurationError(
                f"Invalid llm.pricing rate value {value!r}: must be a "
                "finite number (not NaN or ±Infinity). Fix the catalog "
                "entry rather than leaving it -- a malformed rate must not "
                "be silently treated as unpriced."
            )
        if dec < 0:
            raise LLMConfigurationError(
                f"Invalid llm.pricing rate value {value!r}: must be "
                "non-negative. Fix the catalog entry rather than leaving "
                "it -- a malformed rate must not be silently treated as "
                "unpriced."
            )

        return dec
