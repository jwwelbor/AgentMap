"""
Unit tests for LLMService batch lifecycle methods.

Covers TC-AC1-01 through TC-AC8-02 from the E05-F03 test plan:
  AC-1: Submit returns LLMBatchHandle with amatch_ id; validates call_specs
  AC-2: Restore-after-restart handle supports poll and fetch
  AC-3: Normalized status mapping for all Anthropic processing_status values
  AC-4: Cancel active batch; cancel terminal raises LLMBatchCancelNotSupportedError
  AC-5: Results keyed by spec_id; mixed outcomes; usage/error shapes
  AC-6: Unsupported provider raises LLMBatchUnsupportedProviderError before network
  AC-7: Fetch before ended raises LLMBatchNotReadyError
  AC-8: Batch-incompatible params rejected before adapter call

Seam: tests patch AnthropicBatchAdapter methods and use a real BatchHandleRepository
pointed at a tmp_path directory.  LLMService.submit_batch etc. are called directly.
"""

import asyncio
import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchHandle,
    LLMBatchRequestCounts,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMBatchSubmitRequest,
    LLMCallSpec,
    LLMExecutionError,
    LLMUsage,
)
from agentmap.services.llm_batch_errors import (
    LLMBatchCancelNotSupportedError,
    LLMBatchExpiredError,
    LLMBatchNotReadyError,
    LLMBatchUnsupportedProviderError,
)
from agentmap.services.llm_batch_repository import BatchHandleRepository
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory

# Status map mirroring the adapter's _STATUS_MAP (used in test helpers only).
_ANTHROPIC_STATUS_MAP = {
    "in_progress": LLMBatchStatus.IN_PROGRESS,
    "canceling": LLMBatchStatus.CANCELING,
    "ended": LLMBatchStatus.ENDED,
    "expired": LLMBatchStatus.EXPIRED,
}


def _make_poll_result(
    processing_status: str,
    request_counts: dict = None,
    results_url: str = None,
    ended_at: str = None,
) -> BatchPollResult:
    """Build a BatchPollResult (as the adapter now returns) from test params."""
    counts = None
    if request_counts is not None:
        counts = LLMBatchRequestCounts(**request_counts)
    status = _ANTHROPIC_STATUS_MAP.get(processing_status, LLMBatchStatus.FAILED)
    return BatchPollResult(
        status=status,
        request_counts=counts,
        results_url=results_url,
        ended_at=ended_at,
    )


# ---------------------------------------------------------------------------
# Shared fixtures / factories
# ---------------------------------------------------------------------------


def _make_spec(spec_id: str, provider: str = None, **kwargs) -> LLMCallSpec:
    """Factory for minimal LLMCallSpec instances for batch tests.

    ``provider`` defaults to ``None`` — provider is a batch-level concern
    (REQ-F-008) and must not be set on individual specs unless testing the
    rejection path.
    """
    return LLMCallSpec(
        spec_id=spec_id,
        messages=[{"role": "user", "content": f"prompt for {spec_id}"}],
        provider=provider,
        **kwargs,
    )


def _make_batch_request(
    provider: str = "anthropic",
    specs=None,
    max_tokens: int = 1024,
    model: str = "claude-sonnet-4-6",
    **kwargs,
) -> LLMBatchSubmitRequest:
    """Convenience factory mirroring _make_spec() for batch submit requests."""
    if specs is None:
        specs = [_make_spec("s1")]
    return LLMBatchSubmitRequest(
        provider=provider,
        model=model,
        call_specs=specs,
        max_tokens=max_tokens,
        **kwargs,
    )


def _make_handle(
    status: LLMBatchStatus = LLMBatchStatus.IN_PROGRESS,
    spec_id_map: dict = None,
    **kwargs,
) -> LLMBatchHandle:
    """Convenience factory for constructing handles in known states."""
    defaults = dict(
        agentmap_batch_id="amatch_" + "a1b2c3d4" * 4,
        provider_batch_id="msgbatch_abc123",
        status=status,
        provider="anthropic",
        model="claude-sonnet-4-6",
        spec_id_map=spec_id_map or {"s1": "s1"},
        results_url=None,
        expires_at="2026-06-08T00:00:00Z",
        request_counts=None,
    )
    defaults.update(kwargs)
    return LLMBatchHandle(**defaults)


def _mock_jsonl_records(spec_id_map: dict, outcomes: dict) -> list:
    """
    Factory for LLMBatchResultRecord objects returned by adapter.fetch_results().

    ``outcomes`` maps spec_id -> outcome string: "succeeded", "errored",
    "canceled", "expired".  The adapter already converts JSONL to
    LLMBatchResultRecord objects, so this matches the real seam.
    """
    records = []
    for spec_id, outcome in outcomes.items():
        if outcome == "succeeded":
            records.append(
                LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="succeeded",
                    provider="anthropic",
                    model="claude-sonnet-4-6",
                    content=f"Response for {spec_id}",
                    usage=LLMUsage(
                        input_tokens=100,
                        output_tokens=50,
                        cache_creation_input_tokens=10,
                        cache_read_input_tokens=20,
                    ),
                )
            )
        elif outcome == "errored":
            records.append(
                LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="server_error",
                        message="internal error",
                        retryable=False,
                    ),
                )
            )
        elif outcome == "canceled":
            records.append(
                LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="canceled",
                )
            )
        elif outcome == "expired":
            records.append(
                LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="expired",
                )
            )
    return records


def _make_service(batch_dir: str = None) -> tuple:
    """
    Construct a minimal LLMService with mock dependencies.

    Returns (service, mock_adapter, repo) tuple.
    mock_adapter is the AnthropicBatchAdapter mock injected into the service.
    """
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_config = MockServiceFactory.create_mock_app_config_service()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 1,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
    }
    mock_config.get_llm_config.side_effect = lambda provider: {
        "model": f"{provider}-default-model",
        "api_key": "test-key",
    }
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()
    mock_routing = Mock()

    service = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
    )

    # Inject mock adapter — uses registry internally; keep _batch_adapter
    # attribute for backwards-compat with existing test helper assertions.
    mock_adapter = MagicMock()
    mock_adapter.provider_name = "anthropic"
    mock_adapter.supports_cancel = True
    service._batch_adapters = {"anthropic": mock_adapter}

    # Inject real (or mock) repository
    if batch_dir is not None:
        repo = BatchHandleRepository(batch_dir=batch_dir)
    else:
        repo = MagicMock()
    service._batch_repo = repo

    return service, mock_adapter, repo


# ---------------------------------------------------------------------------
# AC-1: submit_batch validation and handle creation
# ---------------------------------------------------------------------------


class TestSubmitBatch:
    """TC-AC1-01 through TC-AC1-04."""

    def test_submit_returns_llm_batch_handle_with_amatch_id(self, tmp_path):
        """TC-AC1-01: submit returns LLMBatchHandle with agentmap_batch_id starting 'amatch_'."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_abc123",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        assert isinstance(handle, LLMBatchHandle)
        assert handle.agentmap_batch_id.startswith("amatch_")
        assert handle.provider_batch_id == "msgbatch_abc123"
        assert handle.status == LLMBatchStatus.SUBMITTED
        assert handle.spec_id_map == {"s1": "s1"}

    def test_submit_persists_handle_to_disk(self, tmp_path):
        """TC-AC1-01: submitted handle is persisted to disk as a JSON file."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_abc123",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        expected_file = os.path.join(str(tmp_path), f"{handle.agentmap_batch_id}.json")
        assert os.path.exists(expected_file)
        with open(expected_file) as f:
            data = json.loads(f.read())
        assert data["agentmap_batch_id"] == handle.agentmap_batch_id
        assert data["provider_batch_id"] == "msgbatch_abc123"

    def test_submit_handle_contains_no_anthropic_sdk_types(self, tmp_path):
        """TC-AC1-03: returned handle is LLMBatchHandle, not any anthropic.* type."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_abc123",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        assert isinstance(handle, LLMBatchHandle)
        # to_dict must be a plain dict, json-serializable
        d = handle.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # Must not raise
        assert "api_key" not in d

    def test_submit_empty_call_specs_raises_before_adapter(self, tmp_path):
        """TC-AC1-02: empty call_specs raises LLMServiceError before adapter call."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(specs=[])
        with pytest.raises(LLMServiceError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_submit_duplicate_spec_ids_raises_before_adapter(self, tmp_path):
        """TC-AC1-04: duplicate spec_ids raises LLMServiceError before adapter call."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        specs = [_make_spec("dup"), _make_spec("dup")]
        request = _make_batch_request(specs=specs)
        with pytest.raises(LLMServiceError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()


# ---------------------------------------------------------------------------
# AC-2: restore_batch
# ---------------------------------------------------------------------------


class TestRestoreBatch:
    """TC-AC2-01, TC-AC2-02."""

    def test_restore_then_poll_uses_original_provider_batch_id(self, tmp_path):
        """TC-AC2-01: restored handle supports poll; adapter called with original provider_batch_id."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_abc123",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )
        mock_adapter.poll.return_value = _make_poll_result(
            "in_progress",
            request_counts={
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )

        # Submit, serialize, restore (simulating restart)
        request = _make_batch_request(specs=[_make_spec("s1")])
        handle = service.submit_batch(request)
        handle_dict = handle.to_dict()

        # New service instance (simulated restart)
        service2, mock_adapter2, _ = _make_service(batch_dir=str(tmp_path))
        mock_adapter2.poll.return_value = mock_adapter.poll.return_value

        restored = service2.restore_batch(handle_dict)
        assert restored.agentmap_batch_id == handle.agentmap_batch_id
        assert restored.provider_batch_id == "msgbatch_abc123"
        assert restored.spec_id_map == {"s1": "s1"}

        # Poll should delegate with correct provider_batch_id
        updated = service2.poll_batch(restored)
        mock_adapter2.poll.assert_called_once_with("msgbatch_abc123")
        assert updated.status == LLMBatchStatus.IN_PROGRESS

    def test_restore_missing_provider_batch_id_raises(self):
        """TC-AC2-02: restore with dict missing provider_batch_id raises LLMServiceError."""
        service, mock_adapter, repo = _make_service()

        incomplete = {
            "agentmap_batch_id": "amatch_xyz",
            "provider": "anthropic",
        }
        with pytest.raises((LLMServiceError, ValueError)):
            service.restore_batch(incomplete)

        mock_adapter.poll.assert_not_called()


# ---------------------------------------------------------------------------
# AC-3: Status mapping
# ---------------------------------------------------------------------------


class TestPollBatchStatusMapping:
    """TC-AC3-01 through TC-AC3-06: Anthropic processing_status -> normalized status."""

    def _poll_with_status(self, processing_status, request_counts=None, extra=None):
        """Helper: poll a handle with mocked adapter returning given processing_status."""
        service, mock_adapter, repo = _make_service()
        poll_result = _make_poll_result(
            processing_status=processing_status,
            request_counts=request_counts
            or {
                "processing": 0,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )
        mock_adapter.poll.return_value = poll_result

        handle = _make_handle(status=LLMBatchStatus.SUBMITTED)
        return service.poll_batch(handle)

    def test_in_progress_maps_to_in_progress(self):
        """TC-AC3-01: Anthropic 'in_progress' -> normalized 'in_progress'."""
        result = self._poll_with_status(
            "in_progress",
            request_counts={
                "processing": 5,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )
        assert result.status == LLMBatchStatus.IN_PROGRESS
        assert result.request_counts.processing == 5

    def test_canceling_maps_to_canceling(self):
        """TC-AC3-02: Anthropic 'canceling' -> normalized 'canceling'."""
        result = self._poll_with_status(
            "canceling",
            request_counts={
                "processing": 2,
                "succeeded": 1,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )
        assert result.status == LLMBatchStatus.CANCELING
        assert result.request_counts.processing == 2
        assert result.request_counts.succeeded == 1

    def test_ended_maps_to_ended(self):
        """TC-AC3-03: Anthropic 'ended' -> normalized 'ended'."""
        result = self._poll_with_status(
            "ended",
            request_counts={
                "processing": 0,
                "succeeded": 3,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )
        assert result.status == LLMBatchStatus.ENDED
        assert result.request_counts.succeeded == 3

    def test_ended_with_results_url_populated(self):
        """TC-AC3-04: 'ended' with results_url -> results_url populated on handle."""
        service, mock_adapter, repo = _make_service()
        mock_adapter.poll.return_value = _make_poll_result(
            "ended",
            request_counts={
                "processing": 0,
                "succeeded": 0,
                "errored": 2,
                "canceled": 1,
                "expired": 0,
            },
            results_url="https://api.anthropic.com/v1/messages/batches/msgbatch_abc/results",
        )
        handle = _make_handle(status=LLMBatchStatus.IN_PROGRESS)
        result = service.poll_batch(handle)
        assert result.status == LLMBatchStatus.ENDED
        assert result.results_url is not None

    def test_unknown_status_maps_to_failed_deterministically(self):
        """TC-AC3-05: Unknown Anthropic status maps to 'failed' (documented behavior)."""
        result = self._poll_with_status("queued")
        # Unknown status -> "failed" (per developer decision documented in spec)
        assert result.status == LLMBatchStatus.FAILED

    def test_ended_with_ended_at_populated(self):
        """TC-AC3-06: 'ended' with ended_at -> handle.ended_at populated."""
        service, mock_adapter, repo = _make_service()
        mock_adapter.poll.return_value = _make_poll_result(
            "ended",
            request_counts={
                "processing": 0,
                "succeeded": 1,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            ended_at="2026-06-08T01:00:00Z",
        )
        handle = _make_handle(status=LLMBatchStatus.IN_PROGRESS)
        result = service.poll_batch(handle)
        assert result.status == LLMBatchStatus.ENDED
        assert result.ended_at == "2026-06-08T01:00:00Z"


# ---------------------------------------------------------------------------
# AC-4: cancel_batch
# ---------------------------------------------------------------------------


class TestCancelBatch:
    """TC-AC4-01 through TC-AC4-04."""

    def test_cancel_active_batch_calls_adapter_and_updates_handle(self, tmp_path):
        """TC-AC4-01: cancel active batch calls adapter.cancel() and returns updated handle."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.cancel.return_value = None
        mock_adapter.poll.return_value = _make_poll_result(
            "canceling",
            request_counts={
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )

        handle = _make_handle(status=LLMBatchStatus.IN_PROGRESS)
        result = service.cancel_batch(handle)

        mock_adapter.cancel.assert_called_once_with("msgbatch_abc123")
        assert result.status in {LLMBatchStatus.CANCELING, LLMBatchStatus.ENDED}

    def test_cancel_active_then_poll_shows_transition(self, tmp_path):
        """TC-AC4-02: cancel then poll shows transition toward ended."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.cancel.return_value = None
        # First poll after cancel returns canceling
        mock_adapter.poll.side_effect = [
            _make_poll_result(
                "canceling",
                request_counts={
                    "processing": 0,
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 1,
                    "expired": 0,
                },
            ),
            _make_poll_result(
                "ended",
                request_counts={
                    "processing": 0,
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 1,
                    "expired": 0,
                },
                ended_at="2026-06-08T01:00:00Z",
            ),
        ]

        handle = _make_handle(status=LLMBatchStatus.IN_PROGRESS)
        cancelled_handle = service.cancel_batch(handle)
        final_handle = service.poll_batch(cancelled_handle)
        assert final_handle.status == LLMBatchStatus.ENDED

    def test_cancel_ended_batch_raises_cancel_not_supported(self):
        """TC-AC4-03: cancel on 'ended' handle raises LLMBatchCancelNotSupportedError."""
        service, mock_adapter, repo = _make_service()

        handle = _make_handle(status=LLMBatchStatus.ENDED)
        with pytest.raises(LLMBatchCancelNotSupportedError):
            service.cancel_batch(handle)

        mock_adapter.cancel.assert_not_called()

    def test_cancel_expired_batch_raises_cancel_not_supported(self):
        """TC-AC4-04: cancel on 'expired' handle raises LLMBatchCancelNotSupportedError."""
        service, mock_adapter, repo = _make_service()

        handle = _make_handle(status=LLMBatchStatus.EXPIRED)
        with pytest.raises(LLMBatchCancelNotSupportedError):
            service.cancel_batch(handle)

        mock_adapter.cancel.assert_not_called()


# ---------------------------------------------------------------------------
# AC-5: fetch_batch_results
# ---------------------------------------------------------------------------


class TestFetchBatchResults:
    """TC-AC5-01, TC-AC5-02, TC-AC5-04."""

    def test_fetch_returns_records_keyed_by_spec_id_in_any_order(self):
        """TC-AC5-01: fetch returns records for each spec_id regardless of JSONL order."""
        service, mock_adapter, repo = _make_service()
        spec_id_map = {"alpha": "alpha", "beta": "beta", "gamma": "gamma"}
        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map=spec_id_map,
            results_url="https://api.anthropic.com/v1/batches/batch_01/results",
        )
        # adapter returns in shuffled order: gamma, alpha, beta
        mock_adapter.fetch_results.return_value = _mock_jsonl_records(
            spec_id_map,
            {"gamma": "succeeded", "alpha": "succeeded", "beta": "succeeded"},
        )

        results = service.fetch_batch_results(handle)

        assert len(results) == 3
        spec_ids = {r.spec_id for r in results}
        assert spec_ids == {"alpha", "beta", "gamma"}
        assert all(r.status == "succeeded" for r in results)
        assert all(isinstance(r.usage, LLMUsage) for r in results)

    def test_fetch_mixed_outcomes_all_records_returned(self):
        """TC-AC5-02: mixed outcomes (succeeded/errored/canceled/expired) all returned."""
        service, mock_adapter, repo = _make_service()
        spec_id_map = {"s1": "s1", "s2": "s2", "s3": "s3", "s4": "s4"}
        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map=spec_id_map,
            results_url="https://api.anthropic.com/v1/batches/batch_01/results",
        )
        mock_adapter.fetch_results.return_value = _mock_jsonl_records(
            spec_id_map,
            {"s1": "succeeded", "s2": "errored", "s3": "canceled", "s4": "expired"},
        )

        results = service.fetch_batch_results(handle)

        assert len(results) == 4
        by_id = {r.spec_id: r for r in results}
        assert by_id["s1"].status == "succeeded"
        assert isinstance(by_id["s1"].usage, LLMUsage)
        assert by_id["s2"].status == "errored"
        assert isinstance(by_id["s2"].error, LLMExecutionError)
        assert by_id["s2"].usage is None
        assert by_id["s3"].status == "canceled"
        assert by_id["s3"].content is None
        assert by_id["s4"].status == "expired"
        assert by_id["s4"].content is None

    def test_fetch_errored_record_has_error_and_no_usage(self):
        """TC-AC5-04: errored record has LLMExecutionError; usage is None."""
        service, mock_adapter, repo = _make_service()
        spec_id_map = {"s1": "s1"}
        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map=spec_id_map,
            results_url="https://api.anthropic.com/v1/batches/batch_01/results",
        )
        mock_adapter.fetch_results.return_value = _mock_jsonl_records(
            spec_id_map,
            {"s1": "errored"},
        )

        results = service.fetch_batch_results(handle)

        assert len(results) == 1
        record = results[0]
        assert record.status == "errored"
        assert record.error is not None
        assert record.error.error_type == "server_error"
        assert record.error.message == "internal error"
        assert record.usage is None
        assert record.content is None


# ---------------------------------------------------------------------------
# AC-6: Unsupported provider
# ---------------------------------------------------------------------------


class TestUnsupportedProvider:
    """TC-AC6-01, TC-AC6-02."""

    def test_submit_openai_raises_unsupported_provider_before_network(self, tmp_path):
        """TC-AC6-01: provider='openai' (unregistered) raises LLMBatchUnsupportedProviderError before adapter."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        # _make_service only registers "anthropic"; "openai" is unregistered here.
        request = _make_batch_request(provider="openai", specs=[_make_spec("s1")])
        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_submit_gemini_raises_unsupported_provider(self, tmp_path):
        """TC-AC6-02: provider='gemini' (unregistered) raises LLMBatchUnsupportedProviderError."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(provider="gemini", specs=[_make_spec("s1")])
        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()


# ---------------------------------------------------------------------------
# AC-7: Premature fetch
# ---------------------------------------------------------------------------


class TestPrematureFetch:
    """TC-AC7-01: fetch before ended raises LLMBatchNotReadyError."""

    def test_fetch_in_progress_raises_not_ready(self):
        """fetch_batch_results on in_progress handle raises LLMBatchNotReadyError."""
        service, mock_adapter, repo = _make_service()

        handle = _make_handle(status=LLMBatchStatus.IN_PROGRESS)
        with pytest.raises(LLMBatchNotReadyError):
            service.fetch_batch_results(handle)

        mock_adapter.fetch_results.assert_not_called()

    def test_fetch_submitted_raises_not_ready(self):
        """fetch_batch_results on submitted handle raises LLMBatchNotReadyError."""
        service, mock_adapter, repo = _make_service()

        handle = _make_handle(status=LLMBatchStatus.SUBMITTED)
        with pytest.raises(LLMBatchNotReadyError):
            service.fetch_batch_results(handle)

        mock_adapter.fetch_results.assert_not_called()

    def test_fetch_canceling_raises_not_ready(self):
        """fetch_batch_results on canceling handle raises LLMBatchNotReadyError."""
        service, mock_adapter, repo = _make_service()

        handle = _make_handle(status=LLMBatchStatus.CANCELING)
        with pytest.raises(LLMBatchNotReadyError):
            service.fetch_batch_results(handle)

        mock_adapter.fetch_results.assert_not_called()

    def test_fetch_ended_proceeds_without_error(self):
        """fetch_batch_results on ended handle calls adapter (no guard error)."""
        service, mock_adapter, repo = _make_service()
        spec_id_map = {"s1": "s1"}
        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map=spec_id_map,
            results_url="https://api.anthropic.com/v1/batches/batch_01/results",
        )
        mock_adapter.fetch_results.return_value = _mock_jsonl_records(
            spec_id_map, {"s1": "succeeded"}
        )

        results = service.fetch_batch_results(handle)
        mock_adapter.fetch_results.assert_called_once()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# AC-8: Batch-incompatible param validation
# ---------------------------------------------------------------------------


class TestBatchIncompatibleParams:
    """TC-AC8-01, TC-AC8-02."""

    def test_submit_with_stream_true_raises_before_adapter(self, tmp_path):
        """TC-AC8-01: call_specs containing stream=True raises LLMServiceError before adapter."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        spec = _make_spec("s1", request_options={"stream": True})
        request = _make_batch_request(specs=[spec])
        with pytest.raises(LLMServiceError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_submit_with_max_tokens_zero_raises_before_adapter(self, tmp_path):
        """TC-AC8-02: max_tokens=0 raises LLMServiceError before adapter call."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(specs=[_make_spec("s1")], max_tokens=0)
        with pytest.raises(LLMServiceError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Regression tests for UAT-rejected defects (F-CRIT-1, F-MED-1, F-HIGH-2, F-MED-3)
# ---------------------------------------------------------------------------


class TestBatchLevelRequestOptionsValidation:
    """Regression tests for F-CRIT-1 and F-MED-1.

    Batch-level request.request_options must be subject to the same
    incompatible-param validation as per-spec request_options.
    """

    def test_batch_level_stream_true_raises_before_adapter(self, tmp_path):
        """F-CRIT-1: request.request_options={'stream': True} must raise LLMServiceError.

        Previously only per-spec request_options were checked; batch-level options
        were forwarded to the adapter unchecked.
        """
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(
            specs=[_make_spec("s1")],
            request_options={"stream": True},
        )
        with pytest.raises(LLMServiceError, match="stream"):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_batch_level_max_tokens_zero_raises_before_adapter(self, tmp_path):
        """F-MED-1: request.request_options={'max_tokens': 0} must raise LLMServiceError.

        max_tokens=0 as a request_options key bypassed the request.max_tokens check.
        """
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(
            specs=[_make_spec("s1")],
            request_options={"max_tokens": 0},
        )
        with pytest.raises(LLMServiceError, match="max_tokens"):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_per_spec_max_tokens_zero_in_request_options_raises_before_adapter(
        self, tmp_path
    ):
        """F-MED-1: per-spec request_options={'max_tokens': 0} must also raise.

        The per-spec loop checked for incompatible *keys* (stream) but not
        for max_tokens=0 value in per-spec request_options.
        """
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        spec = _make_spec("s1", request_options={"max_tokens": 0})
        request = _make_batch_request(specs=[spec])
        with pytest.raises(LLMServiceError, match="max_tokens"):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()


class TestRestoreBatchValidation:
    """Regression tests for F-HIGH-2 (provider + id validation in restore_batch)."""

    def test_restore_with_any_provider_accepted(self):
        """F04 update: restore_batch now accepts any provider (multi-provider registry).

        F03 rejected non-anthropic providers; F04 removes that guard since the
        registry supports openai/google as well. restore_batch is now provider-agnostic.
        """
        service, mock_adapter, repo = _make_service()

        valid_id = "amatch_" + "a" * 32
        handle_data = {
            "agentmap_batch_id": valid_id,
            "provider_batch_id": "batch_openai_abc",
            "provider": "openai",
            "model": "gpt-4",
            "status": "submitted",
            "spec_id_map": {},
        }
        # Should not raise in F04 — any provider can be restored.
        handle = service.restore_batch(handle_data)
        assert handle.provider == "openai"

    def test_restore_with_path_traversal_id_raises(self):
        """F-HIGH-2: restore_batch must reject agentmap_batch_id containing path separators.

        '../../etc/pwn' was previously accepted and later used in the file path,
        enabling writes outside the batch directory.
        """
        service, mock_adapter, repo = _make_service()

        handle_data = {
            "agentmap_batch_id": "../../etc/pwn",
            "provider_batch_id": "batch_01abc",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "status": "submitted",
            "spec_id_map": {},
        }
        with pytest.raises(LLMServiceError, match="agentmap_batch_id"):
            service.restore_batch(handle_data)

    def test_restore_with_invalid_id_format_raises(self):
        """F-HIGH-2: agentmap_batch_id must match ^amatch_[a-f0-9]{32}$."""
        service, mock_adapter, repo = _make_service()

        handle_data = {
            "agentmap_batch_id": "not_valid",
            "provider_batch_id": "batch_01abc",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "status": "submitted",
            "spec_id_map": {},
        }
        with pytest.raises(LLMServiceError, match="agentmap_batch_id"):
            service.restore_batch(handle_data)

    def test_restore_with_valid_data_succeeds(self):
        """F-HIGH-2: well-formed handle with provider=anthropic and valid id still works."""
        service, mock_adapter, repo = _make_service()

        valid_id = "amatch_" + "a" * 32
        handle_data = {
            "agentmap_batch_id": valid_id,
            "provider_batch_id": "batch_01abc",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "status": "submitted",
            "spec_id_map": {},
        }
        handle = service.restore_batch(handle_data)
        assert handle.agentmap_batch_id == valid_id


class TestFetchBatchResultsEndedNoResultsUrl:
    """Regression tests for F-MED-3 (ended + results_url=None handling)."""

    def test_fetch_ended_with_results_url_none_raises(self, tmp_path):
        """F-MED-3: fetch_batch_results on ended handle with results_url=None must raise.

        Previously the status gate passed and the adapter was called without a
        results_url, leaving results_url durability (REQ-NF-002) unverified.
        """
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map={"s1": "s1"},
            results_url=None,
        )
        with pytest.raises(LLMServiceError, match="results_url"):
            service.fetch_batch_results(handle)

        mock_adapter.fetch_results.assert_not_called()

    def test_fetch_ended_with_results_url_set_proceeds(self, tmp_path):
        """F-MED-3 counterpart: ended handle with results_url set proceeds normally."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        spec_id_map = {"s1": "s1"}
        handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            spec_id_map=spec_id_map,
            results_url="https://api.anthropic.com/v1/batches/batch_01/results",
        )
        mock_adapter.fetch_results.return_value = _mock_jsonl_records(
            spec_id_map, {"s1": "succeeded"}
        )

        results = service.fetch_batch_results(handle)
        mock_adapter.fetch_results.assert_called_once()
        assert len(results) == 1


# ===========================================================================
# F04 tests: TC-009..TC-086 (registry dispatch, async wrappers, CX helpers)
# ===========================================================================


def _make_mock_adapter(provider_name: str, supports_cancel: bool = True) -> MagicMock:
    """Build a mock BatchAdapterProtocol adapter with the given attributes."""
    adapter = MagicMock()
    adapter.provider_name = provider_name
    adapter.supports_cancel = supports_cancel
    return adapter


def _make_registry_service(
    batch_dir: str = None,
    providers: dict = None,
) -> tuple:
    """
    Construct LLMService with a provider→adapter registry (Dict[str, adapter]).

    Returns (service, adapters_dict, repo) tuple.
    adapters_dict maps provider name → mock adapter.
    """
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_config = MockServiceFactory.create_mock_app_config_service()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 1,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
    }
    mock_config.get_llm_config.side_effect = lambda p: {
        "model": f"{p}-default-model",
        "api_key": "test-key",
    }
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()
    mock_routing = Mock()

    service = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
    )

    if providers is None:
        providers = {
            "anthropic": _make_mock_adapter("anthropic", supports_cancel=True),
            "openai": _make_mock_adapter("openai", supports_cancel=True),
            "google": _make_mock_adapter("google", supports_cancel=False),
        }

    service._batch_adapters = providers

    if batch_dir is not None:
        repo = BatchHandleRepository(batch_dir=batch_dir)
    else:
        repo = MagicMock()
    service._batch_repo = repo

    return service, providers, repo


def _make_ended_handle(provider: str = "anthropic", **kwargs) -> LLMBatchHandle:
    """Build an ENDED handle with results_url set (so fetch proceeds)."""
    defaults = dict(
        agentmap_batch_id="amatch_" + "a1b2c3d4" * 4,
        provider_batch_id="batch_abc123",
        status=LLMBatchStatus.ENDED,
        provider=provider,
        model="test-model",
        spec_id_map={"s1": "s1"},
        results_url="https://example.com/results",
        expires_at="2026-06-08T00:00:00Z",
        request_counts=None,
    )
    defaults.update(kwargs)
    return LLMBatchHandle(**defaults)


def _make_expired_handle(provider: str = "anthropic") -> LLMBatchHandle:
    return LLMBatchHandle(
        agentmap_batch_id="amatch_" + "a1b2c3d4" * 4,
        provider_batch_id="batch_abc123",
        status=LLMBatchStatus.EXPIRED,
        provider=provider,
        model="test-model",
        spec_id_map={"s1": "s1"},
        results_url=None,
        expires_at="2024-01-01T00:00:00Z",
        request_counts=None,
    )


# ---------------------------------------------------------------------------
# AC-2 (TC-009..014): Registry dispatch
# ---------------------------------------------------------------------------


class TestRegistryDispatch:
    """TC-009..014: submit_batch and poll_batch dispatch via provider registry."""

    def test_submit_routes_to_openai_adapter(self, tmp_path):
        """TC-009: submit_batch(provider="openai") calls openai adapter, not anthropic."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["openai"].submit.return_value = (
            "batch_openai_001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(provider="openai", specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        adapters["openai"].submit.assert_called_once()
        adapters["anthropic"].submit.assert_not_called()
        assert handle.provider == "openai"

    def test_submit_routes_to_anthropic_adapter(self, tmp_path):
        """TC-009 counterpart: anthropic still routes to anthropic adapter."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_anthro001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(provider="anthropic", specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        adapters["anthropic"].submit.assert_called_once()
        adapters["openai"].submit.assert_not_called()
        assert handle.provider == "anthropic"

    def test_submit_routes_to_google_adapter(self, tmp_path):
        """TC-009: submit_batch(provider="google") calls google adapter."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["google"].submit.return_value = (
            "job_gemini_001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        request = _make_batch_request(provider="google", specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        adapters["google"].submit.assert_called_once()
        adapters["anthropic"].submit.assert_not_called()
        assert handle.provider == "google"

    def test_poll_dispatches_on_handle_provider(self):
        """TC-010: poll_batch routes to adapter matching handle.provider."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="openai", status=LLMBatchStatus.IN_PROGRESS)
        adapters["openai"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            results_url="https://example.com/r",
            ended_at=None,
        )

        updated = service.poll_batch(handle)

        adapters["openai"].poll.assert_called_once()
        adapters["anthropic"].poll.assert_not_called()
        assert updated.status == LLMBatchStatus.ENDED

    def test_cancel_dispatches_on_handle_provider(self):
        """TC-011: cancel_batch routes to adapter matching handle.provider."""
        service, adapters, repo = _make_registry_service()
        # provider openai, supports_cancel=True
        handle = _make_handle(provider="openai", status=LLMBatchStatus.IN_PROGRESS)
        adapters["openai"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.CANCELING,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )

        service.cancel_batch(handle)

        adapters["openai"].cancel.assert_called_once()
        adapters["anthropic"].cancel.assert_not_called()

    def test_fetch_dispatches_on_handle_provider(self):
        """TC-012: fetch_batch_results routes to adapter matching handle.provider."""
        service, adapters, repo = _make_registry_service()
        handle = _make_ended_handle(provider="openai")
        adapters["openai"].fetch_results.return_value = []

        service.fetch_batch_results(handle)

        adapters["openai"].fetch_results.assert_called_once()
        adapters["anthropic"].fetch_results.assert_not_called()

    def test_submit_unregistered_provider_raises_before_adapter_call(self):
        """TC-013: submitting with unregistered provider raises LLMBatchUnsupportedProviderError."""
        service, adapters, repo = _make_registry_service()

        request = _make_batch_request(provider="mistral", specs=[_make_spec("s1")])
        with pytest.raises(LLMBatchUnsupportedProviderError) as exc_info:
            service.submit_batch(request)

        # No adapter should be called
        for adapter in adapters.values():
            adapter.submit.assert_not_called()
        # Error message names registered providers (TC-073)
        error_msg = str(exc_info.value)
        assert "mistral" in error_msg

    def test_unregistered_provider_error_names_registered_providers(self):
        """TC-073: error message for unregistered provider contains known provider names."""
        service, adapters, repo = _make_registry_service()

        request = _make_batch_request(provider="mistral", specs=[_make_spec("s1")])
        with pytest.raises(LLMBatchUnsupportedProviderError) as exc_info:
            service.submit_batch(request)

        error_msg = str(exc_info.value)
        # At least one registered provider should be mentioned
        assert any(p in error_msg for p in ["anthropic", "openai", "google"])

    def test_poll_unregistered_provider_raises(self):
        """TC-070: poll_batch for handle with provider not in registry raises LLMBatchUnsupportedProviderError."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="mistral", status=LLMBatchStatus.IN_PROGRESS)

        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.poll_batch(handle)


# ---------------------------------------------------------------------------
# AC-3 (TC-015..028): Status passthrough (no service-level status map)
# ---------------------------------------------------------------------------


class TestStatusPassthrough:
    """TC-015..028: poll_batch passes adapter-returned status through unchanged."""

    def test_poll_returns_in_progress_status_unchanged(self):
        """TC-015: poll_batch passes BatchPollResult.status directly to updated handle."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic", status=LLMBatchStatus.SUBMITTED)
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
            request_counts=LLMBatchRequestCounts(
                processing=5, succeeded=0, errored=0, canceled=0, expired=0
            ),
            results_url=None,
            ended_at=None,
        )

        updated = service.poll_batch(handle)

        assert updated.status == LLMBatchStatus.IN_PROGRESS
        # Verify service does NOT have _ANTHROPIC_STATUS_MAP
        assert not hasattr(service, "_ANTHROPIC_STATUS_MAP")

    def test_poll_returns_ended_status(self):
        """TC-017: ENDED status passed through unchanged."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic")
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            results_url="https://example.com/r",
            ended_at="2026-06-08T01:00:00Z",
        )

        updated = service.poll_batch(handle)

        assert updated.status == LLMBatchStatus.ENDED

    def test_poll_returns_failed_status(self):
        """TC-018: FAILED status passed through unchanged."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic")
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.FAILED,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )

        updated = service.poll_batch(handle)
        assert updated.status == LLMBatchStatus.FAILED

    def test_anthropic_status_map_absent_from_service(self):
        """TC-015 structural: _ANTHROPIC_STATUS_MAP must not exist on LLMService."""
        service, adapters, repo = _make_registry_service()
        assert not hasattr(service, "_ANTHROPIC_STATUS_MAP")


# ---------------------------------------------------------------------------
# AC-4 (TC-029..040): Sync + async surfaces; wait_for_batch
# ---------------------------------------------------------------------------


class TestSyncAndAsyncSurfaces:
    """TC-029..040: sync/async method pairs; wait_for_batch and submit_and_wait."""

    def test_submit_batch_sync(self, tmp_path):
        """TC-030: submit_batch (sync) returns handle; adapter.submit called."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_sync001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        handle = service.submit_batch(
            _make_batch_request(provider="anthropic", specs=[_make_spec("s1")])
        )

        adapters["anthropic"].submit.assert_called_once()
        assert handle.provider == "anthropic"

    def test_poll_batch_sync(self):
        """TC-032: poll_batch (sync) returns updated handle; adapter.poll called."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic")
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )

        updated = service.poll_batch(handle)

        adapters["anthropic"].poll.assert_called_once()
        assert updated.status == LLMBatchStatus.IN_PROGRESS

    def test_asubmit_batch_uses_to_thread(self, tmp_path):
        """TC-031: asubmit_batch runs adapter.submit inside asyncio.to_thread."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_async001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        to_thread_calls = []

        async def fake_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return func(*args, **kwargs)

        async def run():
            with patch("asyncio.to_thread", side_effect=fake_to_thread):
                handle = await service.asubmit_batch(
                    _make_batch_request(provider="anthropic", specs=[_make_spec("s1")])
                )
            return handle

        handle = asyncio.run(run())
        assert len(to_thread_calls) == 1
        assert handle.provider == "anthropic"

    def test_apoll_batch_uses_to_thread(self):
        """TC-033: apoll_batch runs adapter.poll inside asyncio.to_thread."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic")
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )

        to_thread_calls = []

        async def fake_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return func(*args, **kwargs)

        async def run():
            with patch("asyncio.to_thread", side_effect=fake_to_thread):
                return await service.apoll_batch(handle)

        asyncio.run(run())
        assert len(to_thread_calls) == 1

    def test_wait_for_batch_returns_when_terminal(self):
        """TC-035: wait_for_batch returns handle when terminal status reached."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic", status=LLMBatchStatus.IN_PROGRESS)

        call_count = [0]
        ended_handle = _make_handle(
            provider="anthropic",
            status=LLMBatchStatus.ENDED,
            results_url="https://example.com/r",
        )

        async def fake_apoll(h, *args, **kwargs):
            call_count[0] += 1
            return ended_handle

        async def run():
            with patch.object(service, "apoll_batch", side_effect=fake_apoll):
                return await service.wait_for_batch(
                    handle, poll_interval=0.01, timeout=5.0
                )

        result = asyncio.run(run())
        assert result.status == LLMBatchStatus.ENDED
        assert call_count[0] >= 1

    def test_wait_for_batch_raises_timeout_error(self):
        """TC-036: wait_for_batch raises TimeoutError when timeout exceeded."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="anthropic", status=LLMBatchStatus.IN_PROGRESS)

        in_progress_result = _make_handle(
            provider="anthropic", status=LLMBatchStatus.IN_PROGRESS
        )

        async def fake_apoll(h, *args, **kwargs):
            return in_progress_result

        async def run():
            with patch.object(service, "apoll_batch", side_effect=fake_apoll):
                await service.wait_for_batch(handle, poll_interval=0.01, timeout=0.05)

        with pytest.raises(TimeoutError):
            asyncio.run(run())

    def test_submit_and_wait_convenience(self, tmp_path):
        """TC-037: submit_and_wait wraps submit_batch + wait_for_batch."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_wait001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )

        ended_handle = _make_ended_handle(provider="anthropic")

        async def fake_wait(h, *args, **kwargs):
            return ended_handle

        with patch.object(service, "wait_for_batch", side_effect=fake_wait):
            result = service.submit_and_wait(
                _make_batch_request(provider="anthropic", specs=[_make_spec("s1")]),
                poll_interval=0.01,
                timeout=5.0,
            )

        assert result.status == LLMBatchStatus.ENDED


# ---------------------------------------------------------------------------
# AC-7 (TC-062..075): Typed error outcomes
# ---------------------------------------------------------------------------


class TestTypedErrors:
    """TC-062..075: Expired handles, cancel disambiguation, LLMBatchExpiredError."""

    def test_poll_expired_handle_raises_llm_batch_expired_error(self):
        """TC-062: poll_batch on expired handle raises LLMBatchExpiredError."""
        service, adapters, repo = _make_registry_service()
        handle = _make_expired_handle(provider="anthropic")

        with pytest.raises(LLMBatchExpiredError) as exc_info:
            service.poll_batch(handle)

        # No adapter method called
        adapters["anthropic"].poll.assert_not_called()
        # Error message contains handle id
        assert handle.agentmap_batch_id in str(exc_info.value)

    def test_fetch_expired_handle_raises_llm_batch_expired_error(self):
        """TC-062: fetch_batch_results on expired handle raises LLMBatchExpiredError."""
        service, adapters, repo = _make_registry_service()
        handle = _make_expired_handle(provider="anthropic")

        with pytest.raises(LLMBatchExpiredError):
            service.fetch_batch_results(handle)

        adapters["anthropic"].fetch_results.assert_not_called()

    def test_cancel_on_provider_not_supports_cancel_raises_with_provider_message(self):
        """TC-063: cancel on adapter.supports_cancel=False raises with 'does not support cancel' message."""
        service, adapters, repo = _make_registry_service()
        # google adapter has supports_cancel=False
        handle = _make_handle(provider="google", status=LLMBatchStatus.IN_PROGRESS)

        with pytest.raises(LLMBatchCancelNotSupportedError) as exc_info:
            service.cancel_batch(handle)

        error_msg = str(exc_info.value)
        assert "does not support cancel" in error_msg
        adapters["google"].cancel.assert_not_called()

    def test_cancel_on_terminal_handle_raises_with_terminal_message(self):
        """TC-063: cancel on terminal handle raises with 'terminal' message (distinct from not-supports-cancel)."""
        service, adapters, repo = _make_registry_service()
        # openai has supports_cancel=True, but batch is ENDED
        handle = _make_handle(provider="openai", status=LLMBatchStatus.ENDED)

        with pytest.raises(LLMBatchCancelNotSupportedError) as exc_info:
            service.cancel_batch(handle)

        error_msg = str(exc_info.value)
        # Should contain terminal-related text, NOT "does not support cancel"
        assert "terminal" in error_msg
        adapters["openai"].cancel.assert_not_called()

    def test_cancel_supported_and_active_proceeds(self):
        """TC-063: cancel on supports_cancel=True, non-terminal handle calls adapter.cancel."""
        service, adapters, repo = _make_registry_service()
        handle = _make_handle(provider="openai", status=LLMBatchStatus.IN_PROGRESS)
        adapters["openai"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.CANCELING,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )

        service.cancel_batch(handle)

        adapters["openai"].cancel.assert_called_once()

    def test_wait_for_batch_raises_expired_error_on_expired_handle(self):
        """TC-074: wait_for_batch raises LLMBatchExpiredError (not infinite loop) for expired handle."""
        service, adapters, repo = _make_registry_service()
        handle = _make_expired_handle(provider="anthropic")

        async def run():
            await service.wait_for_batch(handle, poll_interval=0.01, timeout=5.0)

        with pytest.raises(LLMBatchExpiredError):
            asyncio.run(run())

    def test_spec_provider_set_with_request_provider_raises(self):
        """TC-068/TC-080: LLMCallSpec.provider set alongside request.provider raises LLMServiceError."""
        service, adapters, repo = _make_registry_service()
        spec = _make_spec("s1", provider="openai")
        request = _make_batch_request(provider="anthropic", specs=[spec])

        with pytest.raises(LLMServiceError) as exc_info:
            service.submit_batch(request)

        error_msg = str(exc_info.value)
        assert "batch-level" in error_msg.lower() or "provider" in error_msg.lower()
        adapters["anthropic"].submit.assert_not_called()

    def test_conflicting_model_in_spec_and_envelope_raises(self):
        """TC-084: spec.model conflicts with request.model raises LLMServiceError."""
        service, adapters, repo = _make_registry_service()
        spec = _make_spec("s1", model="gpt-3.5-turbo")
        request = _make_batch_request(
            provider="anthropic", specs=[spec], model="gpt-4o"
        )

        with pytest.raises(LLMServiceError) as exc_info:
            service.submit_batch(request)

        error_msg = str(exc_info.value).lower()
        assert "model" in error_msg
        adapters["anthropic"].submit.assert_not_called()


# ---------------------------------------------------------------------------
# AC-8 (TC-076..086): batch_capabilities and canonical param path
# ---------------------------------------------------------------------------


class TestBatchCapabilities:
    """TC-076..086: batch_capabilities introspection and param canonical path."""

    def test_capabilities_anthropic(self):
        """TC-076: batch_capabilities("anthropic") returns dict with supported=True and adapter's supports_cancel."""
        service, adapters, repo = _make_registry_service()

        caps = service.batch_capabilities("anthropic")

        assert caps["supported"] is True
        assert "cancelable" in caps
        assert caps["cancelable"] == adapters["anthropic"].supports_cancel
        assert caps["provider"] == "anthropic"

    def test_capabilities_openai(self):
        """TC-077: batch_capabilities("openai") returns correct dict."""
        service, adapters, repo = _make_registry_service()

        caps = service.batch_capabilities("openai")

        assert caps["supported"] is True
        assert caps["cancelable"] == adapters["openai"].supports_cancel
        assert caps["provider"] == "openai"

    def test_capabilities_google(self):
        """TC-078: batch_capabilities("google") returns correct dict with supports_cancel=False."""
        service, adapters, repo = _make_registry_service()

        caps = service.batch_capabilities("google")

        assert caps["supported"] is True
        assert caps["cancelable"] is False  # google mock has supports_cancel=False
        assert caps["provider"] == "google"

    def test_capabilities_unregistered_provider_raises(self):
        """TC-079: batch_capabilities("mistral") raises LLMBatchUnsupportedProviderError."""
        service, adapters, repo = _make_registry_service()

        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.batch_capabilities("mistral")

    def test_results_by_spec_id(self):
        """TC-008/CX: results_by_spec_id returns dict keyed by spec_id."""
        service, adapters, repo = _make_registry_service()
        records = [
            LLMBatchResultRecord(
                spec_id="s1",
                status="succeeded",
                content="resp1",
                provider="anthropic",
                model="claude-3",
            ),
            LLMBatchResultRecord(
                spec_id="s2",
                status="succeeded",
                content="resp2",
                provider="anthropic",
                model="claude-3",
            ),
        ]

        result = service.results_by_spec_id(records)

        assert "s1" in result
        assert "s2" in result
        assert result["s1"].content == "resp1"
        assert result["s2"].content == "resp2"

    def test_model_only_at_batch_level_accepted(self, tmp_path):
        """TC-082: model set only at request level (no per-spec conflict) is accepted."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "batch_001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )
        # Spec has no model override
        spec = LLMCallSpec(
            spec_id="s1",
            messages=[{"role": "user", "content": "hello"}],
        )
        request = _make_batch_request(
            provider="anthropic", specs=[spec], model="claude-sonnet-4-6"
        )

        # Should not raise
        handle = service.submit_batch(request)
        assert handle is not None

    def test_temperature_only_at_batch_level_accepted(self, tmp_path):
        """TC-085: temperature set only at request level is accepted."""
        service, adapters, repo = _make_registry_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "batch_001",
            {"s1": "s1"},
            "2026-06-08T00:00:00Z",
        )
        spec = LLMCallSpec(
            spec_id="s1",
            messages=[{"role": "user", "content": "hello"}],
        )
        request = _make_batch_request(
            provider="anthropic",
            specs=[spec],
            model="claude-sonnet-4-6",
            request_options={"temperature": 0.7},
        )

        handle = service.submit_batch(request)
        assert handle is not None


class TestNoProviderGuardLiterals:
    """AC-T1 structural: no provider=='anthropic' guard literals in batch code paths."""

    def test_grep_no_anthropic_guard_in_batch_methods(self):
        """AC-T1: grep confirms no provider=='anthropic' guards remain in batch methods.

        Scopes check to the batch section of llm_service.py (from _get_adapter
        through the async wrappers). The realtime path may legitimately reference
        'anthropic' for telemetry extraction (non-batch).
        """
        # Read the file and extract the batch section.
        with open(
            "/home/jwwel/projects/agentmap/src/agentmap/services/llm_service.py"
        ) as f:
            content = f.read()

        # Find the batch section (from _get_adapter to _extract_llm_usage).
        start_marker = "def _get_adapter("
        end_marker = "def _extract_llm_usage("
        start = content.find(start_marker)
        end = content.find(end_marker)
        assert start >= 0, "_get_adapter method not found"
        assert end >= 0, "_extract_llm_usage method not found"

        batch_section = content[start:end]
        assert (
            'provider == "anthropic"' not in batch_section
        ), 'Found provider=="anthropic" guard literal in batch section'
        assert (
            'provider != "anthropic"' not in batch_section
        ), 'Found provider!="anthropic" guard literal in batch section'
