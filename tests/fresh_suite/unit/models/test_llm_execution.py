"""
Unit tests for T-E05-F06-002: cost/tool-call models and LLMResponse extension.

Test cases covered (per test-plan.md's
``tests/fresh_suite/unit/models/test_llm_execution.py (extend)`` entry):
- New ``LLMResponse.cost`` / ``LLMResponse.tool_calls`` fields default to
  ``None``.
- ``LLMResponse`` stays a frozen dataclass (NFR-F-004).
- Batch models remain importable from ``llm_batch.py`` (regression on
  T-E05-F06-001's module split).
- ``LLMToolCall`` / ``LLMModelRates`` / ``LLMCostBreakdown`` / ``LLMBudgetCheck``
  shapes per spec.md Architecture Component Changes 2 and 3.
"""

import dataclasses
from decimal import Decimal

import pytest

from agentmap.models.llm_cost import LLMBudgetCheck, LLMCostBreakdown, LLMModelRates
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.models.llm_tool_call import LLMToolCall


# ---------------------------------------------------------------------------
# LLMResponse extension — new fields default to None, still frozen
# ---------------------------------------------------------------------------
class TestLLMResponseExtension:
    def test_cost_defaults_to_none(self):
        """LLMResponse.cost defaults to None when not supplied (NFR-F-004)."""
        response = LLMResponse(
            text="hello", resolved_provider="anthropic", resolved_model="claude"
        )
        assert response.cost is None

    def test_tool_calls_defaults_to_none(self):
        """LLMResponse.tool_calls defaults to None when not supplied (NFR-F-004)."""
        response = LLMResponse(
            text="hello", resolved_provider="anthropic", resolved_model="claude"
        )
        assert response.tool_calls is None

    def test_response_still_frozen(self):
        """LLMResponse remains frozen=True; mutation raises FrozenInstanceError."""
        response = LLMResponse(
            text="hello", resolved_provider="anthropic", resolved_model="claude"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            response.cost = None  # type: ignore[misc]

    def test_cost_and_tool_calls_constructible_with_values(self):
        """Both new fields accept keyword-constructed values (additive-only)."""
        cost = LLMCostBreakdown(
            total_cost=Decimal("0.001"),
            currency="USD",
            catalog_version="2026-08-01",
            input_cost=Decimal("0.001"),
            output_cost=Decimal("0"),
            cache_write_cost=Decimal("0"),
            cache_read_cost=Decimal("0"),
        )
        tool_calls = [
            LLMToolCall(id="toolu_1", name="get_weather", arguments={"city": "Oslo"})
        ]
        response = LLMResponse(
            text="hello",
            resolved_provider="anthropic",
            resolved_model="claude",
            cost=cost,
            tool_calls=tool_calls,
        )
        assert response.cost is cost
        assert response.tool_calls == tool_calls

    def test_existing_fields_unaffected_by_extension(self):
        """Pre-existing fields (text/usage/finish_reason) remain unchanged (regression)."""
        usage = LLMUsage(input_tokens=10, output_tokens=5)
        response = LLMResponse(
            text="hi",
            resolved_provider="openai",
            resolved_model="gpt",
            usage=usage,
            finish_reason="stop",
        )
        assert response.text == "hi"
        assert response.usage is usage
        assert response.finish_reason == "stop"
        assert response.cost is None
        assert response.tool_calls is None


# ---------------------------------------------------------------------------
# Batch models remain importable from llm_batch.py (T-E05-F06-001 regression)
# ---------------------------------------------------------------------------
class TestBatchModelsImportableFromLlmBatch:
    def test_batch_models_import_from_llm_batch_module(self):
        """Batch models still live in llm_batch.py, not llm_execution.py."""
        from agentmap.models.llm_batch import (
            BatchPollResult,
            LLMBatchHandle,
            LLMBatchRequestCounts,
            LLMBatchStatus,
            LLMBatchSubmitRequest,
        )

        assert LLMBatchStatus.SUBMITTED == "submitted"
        assert BatchPollResult is not None
        assert LLMBatchHandle is not None
        assert LLMBatchRequestCounts is not None
        assert LLMBatchSubmitRequest is not None

    def test_llm_batch_result_importable(self):
        """LLMBatchResult (moved model) is importable from llm_batch.py."""
        from agentmap.models.llm_batch import LLMBatchResult

        assert LLMBatchResult is not None

    def test_batch_models_not_reexported_from_llm_execution(self):
        """No re-export shim: batch model names are absent from llm_execution's module namespace."""
        import agentmap.models.llm_execution as llm_execution_module

        assert not hasattr(llm_execution_module, "LLMBatchStatus")
        assert not hasattr(llm_execution_module, "LLMBatchResult")


# ---------------------------------------------------------------------------
# LLMToolCall — data-only shape (spec.md Component Change 2)
# ---------------------------------------------------------------------------
class TestLLMToolCall:
    def test_construction_with_required_fields(self):
        tool_call = LLMToolCall(
            id="toolu_1", name="get_weather", arguments={"city": "Oslo"}
        )
        assert tool_call.id == "toolu_1"
        assert tool_call.name == "get_weather"
        assert tool_call.arguments == {"city": "Oslo"}

    def test_is_frozen(self):
        tool_call = LLMToolCall(id="toolu_1", name="get_weather", arguments={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            tool_call.name = "other"  # type: ignore[misc]

    def test_equality_by_value(self):
        a = LLMToolCall(id="toolu_1", name="get_weather", arguments={"city": "Oslo"})
        b = LLMToolCall(id="toolu_1", name="get_weather", arguments={"city": "Oslo"})
        assert a == b


# ---------------------------------------------------------------------------
# LLMModelRates / LLMCostBreakdown / LLMBudgetCheck (spec.md Component Change 2)
# ---------------------------------------------------------------------------
class TestLLMModelRates:
    def test_all_rate_fields_optional_default_none(self):
        rates = LLMModelRates(currency="USD")
        assert rates.input_per_1m is None
        assert rates.output_per_1m is None
        assert rates.cache_write_per_1m is None
        assert rates.cache_read_per_1m is None
        assert rates.currency == "USD"

    def test_construction_with_decimal_rates(self):
        rates = LLMModelRates(
            input_per_1m=Decimal("3.00"),
            output_per_1m=Decimal("15.00"),
            cache_write_per_1m=Decimal("3.75"),
            cache_read_per_1m=Decimal("0.30"),
            currency="USD",
        )
        assert rates.input_per_1m == Decimal("3.00")
        assert rates.output_per_1m == Decimal("15.00")
        assert rates.cache_write_per_1m == Decimal("3.75")
        assert rates.cache_read_per_1m == Decimal("0.30")

    def test_is_frozen(self):
        rates = LLMModelRates(currency="USD")
        with pytest.raises(dataclasses.FrozenInstanceError):
            rates.currency = "EUR"  # type: ignore[misc]


class TestLLMCostBreakdown:
    def test_construction_with_required_and_bucket_fields(self):
        breakdown = LLMCostBreakdown(
            total_cost=Decimal("0.000123"),
            currency="USD",
            catalog_version="2026-08-01",
            input_cost=Decimal("0.00003"),
            output_cost=Decimal("0.000075"),
            cache_write_cost=Decimal("0"),
            cache_read_cost=Decimal("0.000018"),
        )
        assert breakdown.total_cost == Decimal("0.000123")
        assert breakdown.currency == "USD"
        assert breakdown.catalog_version == "2026-08-01"
        assert breakdown.input_cost == Decimal("0.00003")
        assert breakdown.output_cost == Decimal("0.000075")
        assert breakdown.cache_write_cost == Decimal("0")
        assert breakdown.cache_read_cost == Decimal("0.000018")

    def test_catalog_version_optional(self):
        breakdown = LLMCostBreakdown(
            total_cost=Decimal("0"),
            currency="USD",
            catalog_version=None,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            cache_write_cost=Decimal("0"),
            cache_read_cost=Decimal("0"),
        )
        assert breakdown.catalog_version is None

    def test_is_frozen(self):
        breakdown = LLMCostBreakdown(
            total_cost=Decimal("0"),
            currency="USD",
            catalog_version=None,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            cache_write_cost=Decimal("0"),
            cache_read_cost=Decimal("0"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            breakdown.total_cost = Decimal("1")  # type: ignore[misc]


class TestLLMBudgetCheck:
    def test_construction_primary_tier(self):
        rates = LLMModelRates(
            input_per_1m=Decimal("3.00"), output_per_1m=Decimal("15.00"), currency="USD"
        )
        check = LLMBudgetCheck(
            resolved_provider="anthropic",
            resolved_model="claude-sonnet-4-5",
            rates=rates,
            catalog_version="2026-08-01",
            max_output_tokens=4096,
            max_possible_output_cost=Decimal("0.06144"),
            message_count=3,
            input_chars=512,
            attempt_kind="primary",
        )
        assert check.resolved_provider == "anthropic"
        assert check.resolved_model == "claude-sonnet-4-5"
        assert check.rates is rates
        assert check.catalog_version == "2026-08-01"
        assert check.max_output_tokens == 4096
        assert check.max_possible_output_cost == Decimal("0.06144")
        assert check.message_count == 3
        assert check.input_chars == 512
        assert check.attempt_kind == "primary"

    def test_fallback_tier_allows_none_output_bound_fields(self):
        """Fallback-tier limitation (spec.md Component Change 2): max_output_tokens
        and max_possible_output_cost are None on fallback tiers, not fabricated."""
        check = LLMBudgetCheck(
            resolved_provider="openai",
            resolved_model="gpt-4o-mini",
            rates=None,
            catalog_version=None,
            max_output_tokens=None,
            max_possible_output_cost=None,
            message_count=3,
            input_chars=512,
            attempt_kind="fallback",
        )
        assert check.attempt_kind == "fallback"
        assert check.max_output_tokens is None
        assert check.max_possible_output_cost is None

    def test_is_frozen(self):
        check = LLMBudgetCheck(
            resolved_provider="anthropic",
            resolved_model="claude",
            rates=None,
            catalog_version=None,
            max_output_tokens=None,
            max_possible_output_cost=None,
            message_count=1,
            input_chars=1,
            attempt_kind="primary",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            check.attempt_kind = "fallback"  # type: ignore[misc]
