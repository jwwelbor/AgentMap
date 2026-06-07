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

import json
import os
from unittest.mock import MagicMock, Mock

import pytest

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import (
    LLMBatchHandle,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMBatchSubmitRequest,
    LLMCallSpec,
    LLMExecutionError,
    LLMUsage,
)
from agentmap.services.llm_batch_errors import (
    LLMBatchCancelNotSupportedError,
    LLMBatchNotReadyError,
    LLMBatchUnsupportedProviderError,
)
from agentmap.services.llm_batch_repository import BatchHandleRepository
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Shared fixtures / factories
# ---------------------------------------------------------------------------


def _make_spec(spec_id: str, provider: str = "anthropic", **kwargs) -> LLMCallSpec:
    """Factory for minimal LLMCallSpec instances for batch tests."""
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

    # Inject mock adapter
    mock_adapter = MagicMock()
    service._batch_adapter = mock_adapter

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
        mock_adapter.poll.return_value = {
            "processing_status": "in_progress",
            "request_counts": {
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            "results_url": None,
            "ended_at": None,
        }

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
        poll_result = {
            "processing_status": processing_status,
            "request_counts": request_counts
            or {
                "processing": 0,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            "results_url": None,
            "ended_at": None,
        }
        if extra:
            poll_result.update(extra)
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
        mock_adapter.poll.return_value = {
            "processing_status": "ended",
            "request_counts": {
                "processing": 0,
                "succeeded": 0,
                "errored": 2,
                "canceled": 1,
                "expired": 0,
            },
            "results_url": "https://api.anthropic.com/v1/messages/batches/msgbatch_abc/results",
            "ended_at": None,
        }
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
        mock_adapter.poll.return_value = {
            "processing_status": "ended",
            "request_counts": {
                "processing": 0,
                "succeeded": 1,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            "results_url": None,
            "ended_at": "2026-06-08T01:00:00Z",
        }
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
        mock_adapter.poll.return_value = {
            "processing_status": "canceling",
            "request_counts": {
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            "results_url": None,
            "ended_at": None,
        }

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
            {
                "processing_status": "canceling",
                "request_counts": {
                    "processing": 0,
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 1,
                    "expired": 0,
                },
                "results_url": None,
                "ended_at": None,
            },
            {
                "processing_status": "ended",
                "request_counts": {
                    "processing": 0,
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 1,
                    "expired": 0,
                },
                "results_url": None,
                "ended_at": "2026-06-08T01:00:00Z",
            },
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
        """TC-AC6-01: provider='openai' raises LLMBatchUnsupportedProviderError before adapter."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(
            provider="openai", specs=[_make_spec("s1", provider="openai")]
        )
        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.submit_batch(request)

        mock_adapter.submit.assert_not_called()

    def test_submit_gemini_raises_unsupported_provider(self, tmp_path):
        """TC-AC6-02: provider='gemini' raises LLMBatchUnsupportedProviderError."""
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))

        request = _make_batch_request(
            provider="gemini", specs=[_make_spec("s1", provider="gemini")]
        )
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

    def test_restore_with_non_anthropic_provider_raises(self):
        """F-HIGH-2: restore_batch must reject providers other than 'anthropic'.

        Previously only provider_batch_id presence was checked; any provider
        was accepted and later sent to the Anthropic adapter incorrectly.
        """
        service, mock_adapter, repo = _make_service()

        handle_data = {
            "agentmap_batch_id": "amatch_" + "a" * 32,
            "provider_batch_id": "batch_openai_abc",
            "provider": "openai",
            "model": "gpt-4",
            "status": "submitted",
            "spec_id_map": {},
        }
        with pytest.raises(LLMServiceError, match="openai"):
            service.restore_batch(handle_data)

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
