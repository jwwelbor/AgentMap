"""
Integration test suite for E05-F03: Provider-Native Batch LLM Contract.

Covers the five integration scenarios from the test plan:
  INT-01: submit_batch -> persist -> restore -> poll (full lifecycle)
  INT-02: submit_batch -> fetch_batch_results with sanitized request_ids (demux)
  INT-03: BatchHandleRepository mirrors bundle_storage pattern (atomic write,
          keyed by agentmap_batch_id, JSON-valid, no api_key)
  INT-04: No change to existing LLMService single-call and fan-out methods
          (confirmed by importing existing test modules without modification)
  INT-05: DI container wires BatchHandleRepository and AnthropicBatchAdapter
          as singletons; LLMService resolves with batch deps intact

All tests mock the AnthropicBatchAdapter at its submit/poll/cancel/fetch_results
seam.  No live Anthropic API calls are made.  The BatchHandleRepository uses a
real tmp_path directory so file-I/O is exercised end-to-end.

Seam convention matches test_llm_batch_service.py: adapter methods are replaced
with unittest.mock.MagicMock; repository is a real instance pointing to tmp_path.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchHandle,
    LLMBatchRequestCounts,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMBatchSubmitRequest,
    LLMExecutionError,
    LLMRequest,
    LLMUsage,
)
from agentmap.services.llm_batch_repository import BatchHandleRepository
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory

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
# Shared helpers
# ---------------------------------------------------------------------------


def _make_spec(request_id: str, provider: str = None, **kwargs) -> LLMRequest:
    # provider defaults to None — it is a batch-level concern (REQ-F-008/F04).
    return LLMRequest(
        request_id=request_id,
        messages=[{"role": "user", "content": f"hello from {request_id}"}],
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
    if specs is None:
        specs = [_make_spec("s1")]
    return LLMBatchSubmitRequest(
        provider=provider,
        model=model,
        requests=specs,
        max_tokens=max_tokens,
        **kwargs,
    )


def _make_handle(
    status: LLMBatchStatus = LLMBatchStatus.IN_PROGRESS,
    request_id_map: dict = None,
    **kwargs,
) -> LLMBatchHandle:
    # agentmap_batch_id must match ^amatch_[a-f0-9]{32}$ (path-safety constraint
    # added during rework code review; see llm_batch_repository._require_safe_batch_id).
    # Default results_url is set so ended-status handles are valid for fetch_batch_results
    # (F-MED-3 fix requires results_url when status==ended).
    defaults = dict(
        agentmap_batch_id="amatch_" + "a" * 32,
        provider_batch_id="msgbatch_intabc123",
        status=status,
        provider="anthropic",
        model="claude-sonnet-4-6",
        request_id_map=request_id_map or {"s1": "s1"},
        results_url="https://api.anthropic.com/v1/messages/batches/msgbatch_intabc123/results",
        expires_at="2026-06-08T00:00:00Z",
        request_counts=None,
    )
    defaults.update(kwargs)
    return LLMBatchHandle(**defaults)


def _make_service(batch_dir: str = None) -> tuple:
    """
    Build a minimal LLMService wired with a mock adapter and a real (or mock)
    BatchHandleRepository.  Returns (service, mock_adapter, repo).
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
    mock_routing = MagicMock()

    service = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
    )

    mock_adapter = MagicMock()
    mock_adapter.provider_name = "anthropic"
    mock_adapter.supports_cancel = True
    service._batch_adapters = {"anthropic": mock_adapter}

    if batch_dir is not None:
        repo = BatchHandleRepository(batch_dir=batch_dir)
    else:
        repo = MagicMock()
    service._batch_repo = repo

    return service, mock_adapter, repo


def _make_succeeded_record(request_id: str) -> LLMBatchResultRecord:
    return LLMBatchResultRecord(
        request_id=request_id,
        status="succeeded",
        provider="anthropic",
        model="claude-sonnet-4-6",
        content=f"result for {request_id}",
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=20,
        ),
    )


def _make_errored_record(request_id: str) -> LLMBatchResultRecord:
    return LLMBatchResultRecord(
        request_id=request_id,
        status="errored",
        error=LLMExecutionError(
            error_type="server_error",
            message="internal error",
            retryable=False,
        ),
    )


# ---------------------------------------------------------------------------
# INT-01: submit_batch -> persist -> restore -> poll (full lifecycle)
# ---------------------------------------------------------------------------


class TestInt01FullLifecycle:
    """
    INT-01: Full submit -> persist -> restore -> poll lifecycle.

    Components: LLMService + AnthropicBatchAdapter (mock) + BatchHandleRepository (real)
    UAT coverage: 3.7 (serializable handle), 3.8 (restore), 3.9 (polling)
    """

    def test_submit_persist_restore_poll_lifecycle(self, tmp_path):
        """
        Full lifecycle: submit returns handle, file is persisted, restored handle
        supports poll with the original provider_batch_id.
        """
        # ---- Phase 1: submit ----
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_lifecycle001",
            {"s1": "s1"},
            "2026-06-09T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec("s1")])
        handle = service.submit_batch(request)

        # Handle identity
        assert isinstance(handle, LLMBatchHandle)
        assert handle.agentmap_batch_id.startswith("amatch_")
        assert handle.provider_batch_id == "msgbatch_lifecycle001"
        assert handle.status == LLMBatchStatus.SUBMITTED
        assert handle.request_id_map == {"s1": "s1"}

        # File persisted
        json_file = os.path.join(str(tmp_path), f"{handle.agentmap_batch_id}.json")
        assert os.path.exists(json_file), "handle JSON file must exist after submit"
        with open(json_file) as f:
            on_disk = json.load(f)
        assert on_disk["agentmap_batch_id"] == handle.agentmap_batch_id
        assert on_disk["provider_batch_id"] == "msgbatch_lifecycle001"

        # ---- Phase 2: serialize (simulate external storage / process restart) ----
        handle_dict = handle.to_dict()

        # ---- Phase 3: restore with new service instance ----
        service2, mock_adapter2, _ = _make_service(batch_dir=str(tmp_path))
        mock_adapter2.poll.return_value = _make_poll_result(
            "in_progress",
            request_counts={
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        )

        restored = service2.restore_batch(handle_dict)
        assert restored.agentmap_batch_id == handle.agentmap_batch_id
        assert restored.provider_batch_id == "msgbatch_lifecycle001"
        assert restored.request_id_map == {"s1": "s1"}

        # ---- Phase 4: poll ----
        updated = service2.poll_batch(restored)
        mock_adapter2.poll.assert_called_once_with("msgbatch_lifecycle001")
        assert updated.status == LLMBatchStatus.IN_PROGRESS

    def test_handle_serialization_roundtrip_preserves_all_fields(self, tmp_path):
        """
        to_dict() -> restore_batch() must preserve all handle fields end-to-end.
        This catches bugs where status or request_id_map serialization loses data.
        """
        service, mock_adapter, repo = _make_service(batch_dir=str(tmp_path))
        mock_adapter.submit.return_value = (
            "msgbatch_round001",
            {"alpha": "alpha", "beta-spec": "beta-spec"},
            "2026-06-09T00:00:00Z",
        )

        specs = [_make_spec("alpha"), _make_spec("beta-spec")]
        request = _make_batch_request(specs=specs)
        handle = service.submit_batch(request)

        handle_dict = handle.to_dict()
        assert isinstance(handle_dict, dict)
        json.dumps(handle_dict)  # must not raise
        assert "api_key" not in handle_dict

        service2, mock_adapter2, _ = _make_service(batch_dir=str(tmp_path))
        mock_adapter2.poll.return_value = _make_poll_result(
            "ended",
            request_counts={
                "processing": 0,
                "succeeded": 2,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            results_url="https://api.anthropic.com/v1/messages/batches/msgbatch_round001/results",
            ended_at="2026-06-09T01:00:00Z",
        )

        restored = service2.restore_batch(handle_dict)
        final = service2.poll_batch(restored)
        assert final.status == LLMBatchStatus.ENDED
        assert final.results_url is not None
        assert final.ended_at == "2026-06-09T01:00:00Z"


# ---------------------------------------------------------------------------
# INT-02: submit_batch -> fetch_batch_results with sanitized request_ids
# ---------------------------------------------------------------------------


class TestInt02SanitizedSpecIdDemux:
    """
    INT-02: End-to-end request_id sanitization + demux.

    Components: LLMService + AnthropicBatchAdapter (sanitization) + demux logic
    UAT coverage: 3.10 (results mapped to request_id)
    """

    def test_sanitized_request_id_demux_end_to_end(self):
        """
        When request_id requires sanitization, the custom_id stored in request_id_map
        must be used during fetch_results to produce a record with the original request_id.
        """
        service, mock_adapter, repo = _make_service()

        dirty_request_id = "my spec/id"
        # Compute the sanitized id the adapter would produce
        import hashlib

        sanitized = hashlib.sha1(dirty_request_id.encode()).hexdigest()[:64]

        # Adapter returns request_id_map with sanitized custom_id
        mock_adapter.submit.return_value = (
            "msgbatch_sanitized",
            {dirty_request_id: sanitized},
            "2026-06-09T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec(dirty_request_id)])
        handle = service.submit_batch(request)

        # Verify request_id_map maps dirty -> sanitized
        assert dirty_request_id in handle.request_id_map
        assert handle.request_id_map[dirty_request_id] == sanitized

        # Now fetch results: adapter returns record keyed by sanitized custom_id
        # The service must reverse-map back to the original request_id
        result_record = LLMBatchResultRecord(
            request_id=dirty_request_id,  # service demux restores original request_id
            status="succeeded",
            provider="anthropic",
            model="claude-sonnet-4-6",
            content="hello",
            usage=LLMUsage(input_tokens=10, output_tokens=5),
        )
        mock_adapter.fetch_results.return_value = [result_record]

        ended_handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            request_id_map={dirty_request_id: sanitized},
            agentmap_batch_id=handle.agentmap_batch_id,
            provider_batch_id=handle.provider_batch_id,
        )
        results = service.fetch_batch_results(ended_handle)

        assert len(results) == 1
        assert results[0].request_id == dirty_request_id

    def test_clean_request_id_used_verbatim_in_demux(self):
        """Clean request_ids (valid regex) must appear unchanged in result records."""
        service, mock_adapter, repo = _make_service()

        clean_id = "my-clean-spec"
        mock_adapter.submit.return_value = (
            "msgbatch_clean",
            {clean_id: clean_id},
            "2026-06-09T00:00:00Z",
        )

        request = _make_batch_request(specs=[_make_spec(clean_id)])
        handle = service.submit_batch(request)
        assert handle.request_id_map[clean_id] == clean_id

        mock_adapter.fetch_results.return_value = [_make_succeeded_record(clean_id)]
        ended_handle = _make_handle(
            status=LLMBatchStatus.ENDED,
            request_id_map={clean_id: clean_id},
            agentmap_batch_id=handle.agentmap_batch_id,
            provider_batch_id=handle.provider_batch_id,
        )
        results = service.fetch_batch_results(ended_handle)
        assert results[0].request_id == clean_id


# ---------------------------------------------------------------------------
# INT-03: BatchHandleRepository mirrors bundle_storage.py pattern
# ---------------------------------------------------------------------------


class TestInt03RepositoryPersistencePattern:
    """
    INT-03: BatchHandleRepository atomic write, keyed by agentmap_batch_id,
    JSON-valid, no api_key.

    Components: BatchHandleRepository + filesystem
    UAT coverage: 3.8, 4.4 (composes with existing persistence patterns)
    """

    def test_save_is_keyed_by_agentmap_batch_id(self):
        """File name must be {agentmap_batch_id}.json (mirrors bundle storage key)."""
        # ID must match ^amatch_[a-f0-9]{32}$ per path-safety constraint.
        safe_id = "amatch_" + "b" * 32
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = BatchHandleRepository(batch_dir=tmp_dir)
            handle = _make_handle(agentmap_batch_id=safe_id)
            repo.save(handle)
            expected = os.path.join(tmp_dir, f"{safe_id}.json")
            assert os.path.exists(expected)

    def test_saved_json_is_valid_and_parseable(self):
        """JSON file must be parseable by json.loads() without error."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = BatchHandleRepository(batch_dir=tmp_dir)
            handle = _make_handle()
            repo.save(handle)
            path = os.path.join(tmp_dir, f"{handle.agentmap_batch_id}.json")
            with open(path) as f:
                data = json.loads(f.read())
            assert isinstance(data, dict)

    def test_saved_json_excludes_api_key(self):
        """api_key must NEVER appear in persisted JSON (security requirement)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = BatchHandleRepository(batch_dir=tmp_dir)
            handle = _make_handle()
            repo.save(handle)
            path = os.path.join(tmp_dir, f"{handle.agentmap_batch_id}.json")
            with open(path) as f:
                data = json.loads(f.read())
            assert "api_key" not in data

    def test_saved_json_preserves_request_id_map(self):
        """request_id_map must survive write/read cycle intact."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = BatchHandleRepository(batch_dir=tmp_dir)
            request_id_map = {"clean": "clean", "dirty/key": "hash123abc"}
            handle = _make_handle(request_id_map=request_id_map)
            repo.save(handle)
            path = os.path.join(tmp_dir, f"{handle.agentmap_batch_id}.json")
            with open(path) as f:
                data = json.loads(f.read())
            assert data["request_id_map"] == request_id_map

    def test_load_from_dict_restores_handle_with_request_id_map(self):
        """load_from_dict must reconstruct handle preserving request_id_map."""
        request_id_map = {"my-spec": "my-spec", "needs/sanitize": "a3f9c2"}
        handle = _make_handle(request_id_map=request_id_map)
        data = handle.to_dict()
        restored = BatchHandleRepository.load_from_dict(data)
        assert restored.request_id_map == request_id_map
        assert restored.agentmap_batch_id == handle.agentmap_batch_id
        assert restored.provider_batch_id == handle.provider_batch_id
        assert isinstance(restored.status, LLMBatchStatus)

    def test_overwrite_is_idempotent(self):
        """Saving the same handle twice must overwrite cleanly (no corruption)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = BatchHandleRepository(batch_dir=tmp_dir)
            handle = _make_handle()
            repo.save(handle)
            repo.save(handle)  # Second save must not raise
            path = os.path.join(tmp_dir, f"{handle.agentmap_batch_id}.json")
            with open(path) as f:
                data = json.loads(f.read())
            assert data["agentmap_batch_id"] == handle.agentmap_batch_id


# ---------------------------------------------------------------------------
# INT-04: No change to existing LLMService single-call and fan-out methods
# ---------------------------------------------------------------------------


class TestInt04ExistingMethodsUnchanged:
    """
    INT-04: Adding batch methods must not break existing single-call and fan-out
    behavior.

    The definitive check is running test_llm_service.py and test_llm_service_fanout.py
    unmodified.  This class provides a lightweight smoke-test that the LLMService
    public API surface (call_llm, call_llm_async, call_llm_many_async) is still
    importable and callable-shaped without requiring live LLM calls.

    Full regression confirmation: pytest tests/fresh_suite/unit/services/test_llm_service.py
    and tests/fresh_suite/unit/services/test_llm_service_fanout.py must pass.
    """

    def test_llm_service_exposes_existing_call_llm_method(self):
        """call_llm must still be present and callable on LLMService."""
        assert callable(getattr(LLMService, "call_llm", None))

    def test_llm_service_exposes_call_llm_async_method(self):
        """call_llm_async must still be present on LLMService."""
        import inspect

        assert callable(getattr(LLMService, "call_llm_async", None))
        assert inspect.iscoroutinefunction(LLMService.call_llm_async)

    def test_llm_service_exposes_call_llm_many_async_method(self):
        """call_llm_many_async must still be present on LLMService."""
        import inspect

        assert callable(getattr(LLMService, "call_llm_many_async", None))
        assert inspect.iscoroutinefunction(LLMService.call_llm_many_async)

    def test_llm_service_batch_methods_coexist_with_single_call(self):
        """
        LLMService instance with batch deps wired must still expose all five
        batch methods alongside the legacy single-call methods.
        """
        service, mock_adapter, repo = _make_service()
        batch_methods = [
            "submit_batch",
            "restore_batch",
            "poll_batch",
            "cancel_batch",
            "fetch_batch_results",
        ]
        legacy_methods = ["call_llm", "call_llm_async", "call_llm_many_async"]
        for name in batch_methods + legacy_methods:
            assert callable(
                getattr(service, name, None)
            ), f"method {name} missing from LLMService"

    def test_import_existing_test_modules_succeeds(self):
        """
        The existing test modules must be importable without error.  This catches
        any breaking import-time change to LLMService or its dependencies.
        """
        import importlib

        importlib.import_module("tests.fresh_suite.unit.services.test_llm_service")
        importlib.import_module(
            "tests.fresh_suite.unit.services.test_llm_service_fanout"
        )


# ---------------------------------------------------------------------------
# INT-05: DI container wires batch deps as singletons
# ---------------------------------------------------------------------------


class TestInt05DIContainerWiring:
    """
    INT-05: DI container resolves LLMService with batch dependencies wired.

    Components: LLMContainer + ApplicationContainer
    UAT coverage: 4.4 (runtime persistence patterns)

    Note: The container attempts to construct AnthropicBatchAdapter which
    calls anthropic.Anthropic(api_key=...).  We patch the anthropic module
    at sys.modules level so no real SDK or network call is made.
    """

    def test_di_container_wires_batch_adapter_and_repo_as_singletons(self, tmp_path):
        """
        Container resolves LLMService; _batch_adapter and _batch_repo attributes
        are non-None singletons.
        """
        import sys
        from unittest.mock import MagicMock, patch

        from agentmap.di import initialize_di_for_testing

        # Patch anthropic SDK at module level so adapter init does not fail
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = MagicMock()

        config_overrides = {
            "llm": {
                "anthropic": {"api_key": "test-key", "model": "claude-sonnet-4-6"},
                "batch_dir": str(tmp_path),
            }
        }

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            container = initialize_di_for_testing(config_overrides=config_overrides)
            llm_service = container.llm_service()

        assert llm_service is not None
        assert isinstance(llm_service, LLMService)
        # Batch adapter must be wired (F04: stored in _batch_adapters registry).
        assert (
            llm_service._batch_adapters.get("anthropic") is not None
        ), "_batch_adapters['anthropic'] must be wired by DI container"
        # Batch repo must be wired
        assert (
            llm_service._batch_repo is not None
        ), "_batch_repo must be wired by DI container"

    def test_di_container_batch_adapter_is_singleton(self, tmp_path):
        """
        Resolving LLMService twice must yield the same _batch_adapter instance
        (singleton scope wired through LLMContainer).
        """
        import sys
        from unittest.mock import patch

        from agentmap.di import initialize_di_for_testing

        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = MagicMock()

        config_overrides = {
            "llm": {
                "anthropic": {"api_key": "test-key", "model": "claude-sonnet-4-6"},
                "batch_dir": str(tmp_path),
            }
        }

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            container = initialize_di_for_testing(config_overrides=config_overrides)
            svc1 = container.llm_service()
            svc2 = container.llm_service()

        # Both calls must return the same singleton service
        assert svc1 is svc2, "llm_service must be a singleton"
        # And the adapter on both references must be the same object (singleton).
        assert svc1._batch_adapters.get("anthropic") is svc2._batch_adapters.get(
            "anthropic"
        ), "anthropic_batch_adapter must be a singleton"

    def test_di_container_batch_repo_is_singleton(self, tmp_path):
        """
        Resolving LLMService twice must yield the same _batch_repo instance
        (singleton scope wired through LLMContainer).
        """
        import sys
        from unittest.mock import patch

        from agentmap.di import initialize_di_for_testing

        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = MagicMock()

        config_overrides = {
            "llm": {
                "anthropic": {"api_key": "test-key", "model": "claude-sonnet-4-6"},
                "batch_dir": str(tmp_path),
            }
        }

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            container = initialize_di_for_testing(config_overrides=config_overrides)
            svc1 = container.llm_service()
            svc2 = container.llm_service()

        assert (
            svc1._batch_repo is svc2._batch_repo
        ), "batch_handle_repository must be a singleton"


# ---------------------------------------------------------------------------
# TC-AC9-03: pyproject.toml contains no new third-party dependency
# ---------------------------------------------------------------------------


class TestAc9PyprojectNoDeps:
    """
    TC-AC9-03: Static check — pyproject.toml must not contain 'anthropic' as a
    new direct dependency.  The feature uses anthropic as a transitive dep via
    langchain-anthropic; listing it explicitly would be a regression.
    """

    def test_anthropic_not_in_direct_dependencies(self):
        """'anthropic' must not appear as a standalone direct dependency."""
        import tomllib
        from pathlib import Path

        pyproject_path = Path(__file__).parents[4] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        direct_deps = data.get("project", {}).get("dependencies", [])
        for dep in direct_deps:
            dep_name = dep.split("[")[0].split(">=")[0].split("==")[0].strip().lower()
            assert (
                dep_name != "anthropic"
            ), f"'anthropic' must not be a direct dependency; found: {dep!r}"
