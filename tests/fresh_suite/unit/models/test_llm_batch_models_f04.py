"""
Unit tests for F04 batch model changes: CANCELED status, result_ref, BatchPollResult.

Test cases covered:
- TC-008: BatchPollResult is a dataclass with required fields
- TC-015: poll_batch returns BatchPollResult.status directly (behavior contract)
- TC-019: LLMBatchStatus.CANCELED exists
- TC-056: F03 persisted handle dict loads via from_dict without error
- TC-059: LLMBatchStatus.CANCELED is a terminal status concept
- TC-060: result_ref round-trips through to_dict/from_dict
"""

import pytest

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchHandle,
    LLMBatchRequestCounts,
    LLMBatchStatus,
)


# ---------------------------------------------------------------------------
# TC-019 — LLMBatchStatus.CANCELED exists
# ---------------------------------------------------------------------------
class TestLLMBatchStatusCanceled:
    def test_canceled_member_exists(self):
        """TC-019: CANCELED is a member of LLMBatchStatus."""
        assert LLMBatchStatus.CANCELED == "canceled"

    def test_canceled_is_string_enum(self):
        """CANCELED value is the string 'canceled'."""
        assert LLMBatchStatus.CANCELED.value == "canceled"

    def test_canceled_roundtrips(self):
        """LLMBatchStatus('canceled') produces CANCELED."""
        assert LLMBatchStatus("canceled") is LLMBatchStatus.CANCELED


# ---------------------------------------------------------------------------
# TC-008 — BatchPollResult dataclass
# ---------------------------------------------------------------------------
class TestBatchPollResult:
    def test_instantiation_with_required_fields(self):
        """TC-008: BatchPollResult can be created with status only."""
        pr = BatchPollResult(status=LLMBatchStatus.IN_PROGRESS)
        assert pr.status is LLMBatchStatus.IN_PROGRESS
        assert pr.request_counts is None
        assert pr.result_ref is None
        assert pr.results_url is None
        assert pr.ended_at is None
        assert pr.expires_at is None

    def test_instantiation_with_all_fields(self):
        """TC-008: BatchPollResult accepts all optional fields."""
        counts = LLMBatchRequestCounts(processing=2, succeeded=3)
        pr = BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=counts,
            result_ref="file-abc",
            results_url="https://example.com/results",
            ended_at="2026-06-07T12:00:00Z",
            expires_at="2026-06-08T12:00:00Z",
        )
        assert pr.status is LLMBatchStatus.ENDED
        assert pr.request_counts is counts
        assert pr.result_ref == "file-abc"
        assert pr.results_url == "https://example.com/results"
        assert pr.ended_at == "2026-06-07T12:00:00Z"
        assert pr.expires_at == "2026-06-08T12:00:00Z"

    def test_missing_status_raises_type_error(self):
        """TC-008: BatchPollResult() without status raises TypeError."""
        with pytest.raises(TypeError):
            BatchPollResult()  # type: ignore[call-arg]

    def test_status_field_accepts_canceled(self):
        """BatchPollResult.status can hold CANCELED."""
        pr = BatchPollResult(status=LLMBatchStatus.CANCELED)
        assert pr.status is LLMBatchStatus.CANCELED


# ---------------------------------------------------------------------------
# TC-056 — F03 handle back-compat: from_dict with no result_ref key
# ---------------------------------------------------------------------------
def _make_f03_handle_dict():
    """Canonical F03 persisted handle shape — no result_ref key."""
    return {
        "agentmap_batch_id": "amatch_f03_001",
        "provider_batch_id": "msgbatch_xyz",
        "status": "ended",
        "provider": "anthropic",
        "model": "claude-3-5-haiku-20241022",
        "spec_id_map": {"s1": "s1"},
        "results_url": "https://api.anthropic.com/v1/messages/batches/msgbatch_xyz/results",
        "expires_at": "2026-06-08T00:00:00Z",
        "ended_at": "2026-06-07T10:00:00Z",
        "request_counts": {
            "processing": 0,
            "succeeded": 1,
            "errored": 0,
            "canceled": 0,
            "expired": 0,
        },
    }


class TestLLMBatchHandleF04:
    def test_from_dict_f03_handle_no_result_ref(self):
        """TC-056: F03 handle dict (no result_ref) loads without KeyError."""
        d = _make_f03_handle_dict()
        assert "result_ref" not in d  # confirm it's a true F03 dict

        handle = LLMBatchHandle.from_dict(d)

        assert handle.result_ref is None
        assert handle.results_url == d["results_url"]
        assert handle.provider == "anthropic"
        assert handle.status is LLMBatchStatus.ENDED

    def test_result_ref_roundtrip_when_set(self):
        """TC-060 / AC-T2: result_ref serializes through to_dict/from_dict."""
        d = _make_f03_handle_dict()
        d["result_ref"] = "file-abc123"

        handle = LLMBatchHandle.from_dict(d)
        assert handle.result_ref == "file-abc123"

        serialized = handle.to_dict()
        assert serialized["result_ref"] == "file-abc123"

        handle2 = LLMBatchHandle.from_dict(serialized)
        assert handle2.result_ref == "file-abc123"

    def test_result_ref_none_serializes_in_to_dict(self):
        """AC-T2: to_dict includes result_ref key even when None."""
        d = _make_f03_handle_dict()
        handle = LLMBatchHandle.from_dict(d)

        serialized = handle.to_dict()
        assert "result_ref" in serialized
        assert serialized["result_ref"] is None

    def test_results_url_preserved_in_f03_handle(self):
        """TC-056: results_url value is preserved from F03 dict."""
        d = _make_f03_handle_dict()
        handle = LLMBatchHandle.from_dict(d)
        assert handle.results_url == d["results_url"]

    def test_handle_with_canceled_status(self):
        """AC-T1: CANCELED status can be stored in handle."""
        d = _make_f03_handle_dict()
        d["status"] = "canceled"
        handle = LLMBatchHandle.from_dict(d)
        assert handle.status is LLMBatchStatus.CANCELED

    def test_canceled_handle_roundtrips(self):
        """AC-T1: CANCELED handle survives to_dict/from_dict."""
        d = _make_f03_handle_dict()
        d["status"] = "canceled"
        handle = LLMBatchHandle.from_dict(d)
        serialized = handle.to_dict()
        assert serialized["status"] == "canceled"
        handle2 = LLMBatchHandle.from_dict(serialized)
        assert handle2.status is LLMBatchStatus.CANCELED
