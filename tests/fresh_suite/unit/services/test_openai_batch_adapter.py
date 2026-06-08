"""
Unit tests for OpenAIBatchAdapter.

Covers:
- TC-041: submit builds JSONL and stages file before batches.create
- TC-042: fetch_results downloads output_file_id and demuxes by custom_id
- TC-043: OpenAI usage normalization from completion_tokens/prompt_tokens shape
- TC-044: item-level error (failed request) produces LLMBatchResult with error field
- TC-087: LLMDependencyError raised when openai package not importable
- TC-089: With SDK installed (mocked), adapter instantiates successfully
- TC-005: provider_name and supports_cancel class attributes
- poll: OpenAI status → LLMBatchStatus mapping
"""

import builtins
import importlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from agentmap.exceptions import LLMDependencyError
from agentmap.models.llm_execution import (
    LLMBatchStatus,
    LLMRequest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(request_id: str, messages=None) -> LLMRequest:
    """Build a minimal LLMRequest for testing."""
    if messages is None:
        messages = [{"role": "user", "content": f"hello from {request_id}"}]
    return LLMRequest(request_id=request_id, messages=messages)


def _make_mock_openai_module():
    """Build a minimal fake openai module for patching sys.modules."""
    mock_sdk = MagicMock()
    client_instance = MagicMock()
    mock_sdk.OpenAI.return_value = client_instance
    return mock_sdk, client_instance


def _make_resolved(specs, model="gpt-4o", max_tokens=1024, request_options=None):
    """Build a resolved_params list from old-style args (test helper only)."""
    rp = {"model": model, "max_tokens": max_tokens}
    if request_options:
        rp.update(request_options)
    return [dict(rp) for _ in specs]


def _make_adapter(client_instance=None):
    """Create an OpenAIBatchAdapter with the openai SDK mocked out."""
    mock_sdk, ci = _make_mock_openai_module()
    if client_instance is not None:
        mock_sdk.OpenAI.return_value = client_instance
        ci = client_instance

    adapter_key = "agentmap.services.llm.openai_batch_adapter"
    # Remove and reload so the import gate fires against our mock
    sys.modules.pop(adapter_key, None)
    with patch.dict("sys.modules", {"openai": mock_sdk}):
        mod = importlib.import_module(adapter_key)
        adapter = mod.OpenAIBatchAdapter(api_key="sk-test", logger=MagicMock())
    # Re-register module under the real key so teardown is clean
    sys.modules[adapter_key] = mod
    return adapter, ci


# ---------------------------------------------------------------------------
# TC-005 / AC-T5: class-level attributes
# ---------------------------------------------------------------------------


class TestClassAttributes:
    """TC-005, AC-T5: provider_name and supports_cancel."""

    def test_provider_name_is_openai(self):
        """provider_name class attribute must be 'openai'."""
        mock_sdk, ci = _make_mock_openai_module()
        adapter_key = "agentmap.services.llm.openai_batch_adapter"
        sys.modules.pop(adapter_key, None)
        with patch.dict("sys.modules", {"openai": mock_sdk}):
            mod = importlib.import_module(adapter_key)
            assert mod.OpenAIBatchAdapter.provider_name == "openai"
        sys.modules.pop(adapter_key, None)

    def test_supports_cancel_is_true(self):
        """supports_cancel class attribute must be True."""
        mock_sdk, ci = _make_mock_openai_module()
        adapter_key = "agentmap.services.llm.openai_batch_adapter"
        sys.modules.pop(adapter_key, None)
        with patch.dict("sys.modules", {"openai": mock_sdk}):
            mod = importlib.import_module(adapter_key)
            assert mod.OpenAIBatchAdapter.supports_cancel is True
        sys.modules.pop(adapter_key, None)


# ---------------------------------------------------------------------------
# TC-087/TC-089: Import gating
# ---------------------------------------------------------------------------


class TestImportGating:
    """TC-087: LLMDependencyError when openai not installed; TC-089: OK when installed."""

    def test_raises_llm_dependency_error_when_openai_missing(self):
        """
        OpenAIBatchAdapter.__init__ must raise LLMDependencyError (not bare
        ImportError) when the openai package cannot be imported.
        """
        original_import = builtins.__import__

        def import_that_fails_for_openai(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return original_import(name, *args, **kwargs)

        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "openai" or key.startswith("openai."):
                saved_modules[key] = sys.modules.pop(key)

        adapter_key = "agentmap.services.llm.openai_batch_adapter"
        saved_adapter = sys.modules.pop(adapter_key, None)

        try:
            with patch("builtins.__import__", side_effect=import_that_fails_for_openai):
                if adapter_key in sys.modules:
                    del sys.modules[adapter_key]

                mod = importlib.import_module(adapter_key)
                OpenAIBatchAdapter = mod.OpenAIBatchAdapter

                with pytest.raises(LLMDependencyError) as exc_info:
                    OpenAIBatchAdapter(api_key="sk-test", logger=MagicMock())

                assert "openai" in str(exc_info.value).lower()
        finally:
            sys.modules.update(saved_modules)
            if saved_adapter is not None:
                sys.modules[adapter_key] = saved_adapter
            else:
                sys.modules.pop(adapter_key, None)

    def test_instantiates_successfully_when_openai_installed(self):
        """TC-089: Import gate does not block instantiation when SDK is present."""
        adapter, ci = _make_adapter()
        assert adapter is not None


# ---------------------------------------------------------------------------
# TC-041: submit builds JSONL and stages file before batches.create
# ---------------------------------------------------------------------------


class TestSubmit:
    """TC-041: JSONL staging hidden inside submit."""

    def test_submit_calls_files_create_then_batches_create(self):
        """
        submit must call files.create(purpose='batch') with JSONL bytes
        then batches.create(input_file_id, endpoint, completion_window).
        """
        ci = MagicMock()
        # files.create returns a file object with .id
        mock_file = MagicMock()
        mock_file.id = "file-123"
        ci.files.create.return_value = mock_file

        # batches.create returns a batch with .id and .expires_at
        mock_batch = MagicMock()
        mock_batch.id = "batch-abc"
        mock_batch.expires_at = "2025-01-01T00:00:00Z"
        ci.batches.create.return_value = mock_batch

        adapter, _ = _make_adapter(client_instance=ci)

        specs = [_make_spec("s1"), _make_spec("s2")]
        batch_id, request_id_map, expires_at = adapter.submit(
            specs,
            resolved_params=_make_resolved(specs, model="gpt-4o", max_tokens=1024),
        )

        # files.create must be called once
        assert ci.files.create.call_count == 1
        call_kwargs = ci.files.create.call_args

        # purpose must be 'batch'
        assert call_kwargs.kwargs.get("purpose") == "batch" or (
            len(call_kwargs.args) >= 1 and call_kwargs.kwargs.get("purpose") == "batch"
        )

        # The file data must be JSONL with exactly 2 lines
        file_arg = call_kwargs.kwargs.get("file") or (
            call_kwargs.args[0] if call_kwargs.args else None
        )
        assert file_arg is not None
        # file_arg may be a tuple (name, bytes) or bytes-like
        if isinstance(file_arg, tuple):
            raw_bytes = file_arg[1]
        else:
            raw_bytes = file_arg
        lines = [ln for ln in raw_bytes.split(b"\n") if ln.strip()]
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert "custom_id" in record
            assert record.get("method") == "POST"
            assert record.get("url") == "/v1/chat/completions"
            assert "body" in record

        # batches.create must be called once with correct args
        assert ci.batches.create.call_count == 1
        batch_kwargs = ci.batches.create.call_args.kwargs
        assert batch_kwargs.get("input_file_id") == "file-123"
        assert batch_kwargs.get("endpoint") == "/v1/chat/completions"
        assert batch_kwargs.get("completion_window") == "24h"

        # Return tuple must be (batch_id, request_id_map, expires_at) — 3 elements
        assert batch_id == "batch-abc"
        assert set(request_id_map.keys()) == {"s1", "s2"}
        assert expires_at == "2025-01-01T00:00:00Z"

    def test_submit_file_id_does_not_leak_to_caller(self):
        """
        The return value must be a 3-tuple; file_id must not be a 4th element.
        Counter-factual: if it leaks, tuple unpack to 3 raises ValueError.
        """
        ci = MagicMock()
        mock_file = MagicMock()
        mock_file.id = "file-999"
        ci.files.create.return_value = mock_file
        mock_batch = MagicMock()
        mock_batch.id = "batch-xyz"
        mock_batch.expires_at = None
        ci.batches.create.return_value = mock_batch

        adapter, _ = _make_adapter(client_instance=ci)
        s = [_make_spec("s1")]
        result = adapter.submit(
            s, resolved_params=_make_resolved(s, model="gpt-4o", max_tokens=512)
        )

        # Must unpack to exactly 3 without ValueError
        batch_id, request_id_map, expires_at = result

    def test_submit_per_spec_model_override(self):
        """Spec with model override uses spec.model in the body."""
        ci = MagicMock()
        mock_file = MagicMock()
        mock_file.id = "file-11"
        ci.files.create.return_value = mock_file
        mock_batch = MagicMock()
        mock_batch.id = "b-1"
        mock_batch.expires_at = None
        ci.batches.create.return_value = mock_batch

        adapter, _ = _make_adapter(client_instance=ci)
        spec_override = LLMRequest(
            request_id="s1",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-3.5-turbo",
        )
        # resolved_params carries the already-resolved model (spec.model wins after
        # central resolution when only spec.model is set)
        adapter.submit(
            [spec_override],
            resolved_params=[{"model": "gpt-3.5-turbo", "max_tokens": 256}],
        )

        file_arg = (
            ci.files.create.call_args.kwargs.get("file")
            or ci.files.create.call_args.args[0]
        )
        if isinstance(file_arg, tuple):
            raw_bytes = file_arg[1]
        else:
            raw_bytes = file_arg
        record = json.loads(raw_bytes.split(b"\n")[0])
        assert record["body"]["model"] == "gpt-3.5-turbo"


# ---------------------------------------------------------------------------
# TC-042: fetch_results demuxes by custom_id (not position)
# ---------------------------------------------------------------------------


def _jsonl_bytes(records):
    """Encode a list of dicts as JSONL bytes."""
    return b"\n".join(json.dumps(r).encode() for r in records)


class TestFetchResults:
    """TC-042, TC-043, TC-044: fetch_results behaviour."""

    def _setup_files_content(self, ci, jsonl_records):
        """Wire ci.files.content to return mock JSONL."""
        mock_resp = MagicMock()
        mock_resp.content = _jsonl_bytes(jsonl_records)
        ci.files.content.return_value = mock_resp

    def test_fetch_results_demuxes_by_custom_id_not_position(self):
        """
        TC-042: Records must be mapped by custom_id back to request_id.
        The response has cid2 before cid1 — order-independent demux required.
        """
        ci = MagicMock()
        # JSONL: cid2 comes first
        records = [
            {
                "id": "r2",
                "custom_id": "cid2",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "response for s2"}}],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                        "model": "gpt-4o",
                    },
                },
                "error": None,
            },
            {
                "id": "r1",
                "custom_id": "cid1",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "response for s1"}}],
                        "usage": {
                            "prompt_tokens": 20,
                            "completion_tokens": 8,
                            "total_tokens": 28,
                        },
                        "model": "gpt-4o",
                    },
                },
                "error": None,
            },
        ]
        self._setup_files_content(ci, records)

        adapter, _ = _make_adapter(client_instance=ci)
        request_id_map = {"s1": "cid1", "s2": "cid2"}
        results = list(
            adapter.fetch_results("batch-id", request_id_map, result_ref="file-out")
        )

        assert len(results) == 2
        by_spec = {r.request_id: r for r in results}
        assert "s1" in by_spec
        assert "s2" in by_spec
        assert by_spec["s1"].text == "response for s1"
        assert by_spec["s2"].text == "response for s2"

    def test_fetch_results_uses_result_ref_for_file_download(self):
        """fetch_results must call files.content(result_ref), not use provider_batch_id for file."""
        ci = MagicMock()
        records = [
            {
                "id": "r1",
                "custom_id": "cid1",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "hi"}}],
                        "usage": {
                            "prompt_tokens": 5,
                            "completion_tokens": 2,
                            "total_tokens": 7,
                        },
                        "model": "gpt-4o",
                    },
                },
                "error": None,
            }
        ]
        self._setup_files_content(ci, records)

        adapter, _ = _make_adapter(client_instance=ci)
        list(
            adapter.fetch_results(
                "batch-id", {"s1": "cid1"}, result_ref="file-output-123"
            )
        )

        ci.files.content.assert_called_once_with("file-output-123")

    def test_fetch_results_usage_normalization(self):
        """
        TC-043: OpenAI prompt_tokens → input_tokens, completion_tokens → output_tokens.
        Counter-factual: swapped fields would fail the assertions below.
        """
        ci = MagicMock()
        records = [
            {
                "id": "r1",
                "custom_id": "cid1",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "hello"}}],
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                            "total_tokens": 150,
                        },
                        "model": "gpt-4o",
                    },
                },
                "error": None,
            }
        ]
        self._setup_files_content(ci, records)

        adapter, _ = _make_adapter(client_instance=ci)
        results = list(
            adapter.fetch_results("batch-id", {"s1": "cid1"}, result_ref="file-out")
        )

        assert len(results) == 1
        rec = results[0]
        assert rec.request_id == "s1"
        assert rec.status == "succeeded"
        assert rec.usage is not None
        assert rec.usage.input_tokens == 100
        assert rec.usage.output_tokens == 50
        # OpenAI doesn't have cache fields; they should be None
        assert rec.usage.cache_creation_input_tokens is None
        assert rec.usage.cache_read_input_tokens is None

    def test_fetch_results_item_error_produces_result_record(self):
        """
        TC-044: An item with error field (no response) must produce
        LLMBatchResult with populated error, not raise.
        Counter-factual: if exception propagates, caller cannot distinguish
        item failure from fetch failure.
        """
        ci = MagicMock()
        records = [
            {
                "id": "r1",
                "custom_id": "cid1",
                "response": None,
                "error": {"code": "content_filter", "message": "content filtered"},
            }
        ]
        self._setup_files_content(ci, records)

        adapter, _ = _make_adapter(client_instance=ci)
        results = list(
            adapter.fetch_results("batch-id", {"s1": "cid1"}, result_ref="file-out")
        )

        assert len(results) == 1
        rec = results[0]
        assert rec.request_id == "s1"
        assert rec.status == "errored"
        assert rec.error is not None
        assert rec.usage is None

    def test_fetch_results_raises_on_missing_output_file_when_batch_completed(self):
        """
        F4 / TC-F4: fetch_results called with result_ref=None on a completed
        batch must raise LLMServiceError — NOT silently yield zero records.

        Counter-factual: current code returns early (yields nothing); callers
        see an empty result list and assume the batch had no items, masking
        data loss.
        """
        from agentmap.exceptions import LLMServiceError

        ci = MagicMock()
        adapter, _ = _make_adapter(client_instance=ci)

        with pytest.raises(LLMServiceError, match="output_file_id"):
            list(
                adapter.fetch_results("batch-done-123", {"s1": "cid1"}, result_ref=None)
            )

    def test_fetch_results_unknown_custom_id_skipped(self):
        """A custom_id not in request_id_map should not raise — skip or warn."""
        ci = MagicMock()
        records = [
            {
                "id": "r1",
                "custom_id": "unknown-cid",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "x"}}],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                        "model": "gpt-4o",
                    },
                },
                "error": None,
            }
        ]
        self._setup_files_content(ci, records)

        adapter, _ = _make_adapter(client_instance=ci)
        # Should not raise
        results = list(
            adapter.fetch_results("batch-id", {"s1": "cid1"}, result_ref="file-out")
        )
        # Result may be empty or contain a record with the unknown id as request_id — either is fine
        # as long as it doesn't raise
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# TC-003 (poll): OpenAI status → LLMBatchStatus
# ---------------------------------------------------------------------------


class TestPoll:
    """AC-T3: poll maps all OpenAI batch statuses to LLMBatchStatus."""

    def _poll_with_status(self, openai_status: str):
        ci = MagicMock()
        mock_batch = MagicMock()
        mock_batch.status = openai_status
        mock_batch.output_file_id = "file-out" if openai_status == "completed" else None
        mock_batch.request_counts = None
        mock_batch.expires_at = None
        ci.batches.retrieve.return_value = mock_batch

        adapter, _ = _make_adapter(client_instance=ci)
        return adapter.poll("batch-id")

    def test_poll_validating_maps_to_in_progress(self):
        result = self._poll_with_status("validating")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_poll_in_progress_maps_to_in_progress(self):
        result = self._poll_with_status("in_progress")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_poll_finalizing_maps_to_in_progress(self):
        result = self._poll_with_status("finalizing")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_poll_completed_maps_to_ended(self):
        result = self._poll_with_status("completed")
        assert result.status == LLMBatchStatus.ENDED

    def test_poll_failed_maps_to_failed(self):
        result = self._poll_with_status("failed")
        assert result.status == LLMBatchStatus.FAILED

    def test_poll_expired_maps_to_expired(self):
        result = self._poll_with_status("expired")
        assert result.status == LLMBatchStatus.EXPIRED

    def test_poll_cancelling_maps_to_canceling(self):
        result = self._poll_with_status("cancelling")
        assert result.status == LLMBatchStatus.CANCELING

    def test_poll_cancelled_maps_to_canceled(self):
        result = self._poll_with_status("cancelled")
        assert result.status == LLMBatchStatus.CANCELED

    def test_poll_unknown_status_maps_to_failed(self):
        """Unknown OpenAI status values map to FAILED (documented decision D-3)."""
        result = self._poll_with_status("some_unknown_status")
        assert result.status == LLMBatchStatus.FAILED

    def test_poll_returns_result_ref_as_output_file_id(self):
        """poll must surface output_file_id as result_ref on BatchPollResult."""
        ci = MagicMock()
        mock_batch = MagicMock()
        mock_batch.status = "completed"
        mock_batch.output_file_id = "file-output-456"
        mock_batch.request_counts = None
        mock_batch.expires_at = None
        ci.batches.retrieve.return_value = mock_batch

        adapter, _ = _make_adapter(client_instance=ci)
        result = adapter.poll("batch-id")
        assert result.result_ref == "file-output-456"

    def test_poll_returns_batch_poll_result(self):
        """poll must return a BatchPollResult instance."""
        from agentmap.models.llm_execution import BatchPollResult

        result = self._poll_with_status("in_progress")
        assert isinstance(result, BatchPollResult)


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestCancel:
    """cancel delegates to batches.cancel."""

    def test_cancel_calls_batches_cancel(self):
        ci = MagicMock()
        adapter, _ = _make_adapter(client_instance=ci)
        adapter.cancel("batch-to-cancel")
        ci.batches.cancel.assert_called_once_with("batch-to-cancel")


# ---------------------------------------------------------------------------
# T-E05-F04-010: Adapter-level serialization assertions
# ---------------------------------------------------------------------------


class TestOpenAISubmitSerializesResolvedParams:
    """
    TC-SER-O1 through TC-SER-O4: prove that resolved_params values actually
    reach the JSONL body lines staged via files.create.

    OpenAI adapter builds body = {"messages": ...}; body.update(rp), so
    temperature/max_tokens/passthroughs all end up inside body of each JSONL line.

    Counter-factual: removing body.update(rp) in _build_jsonl would drop all
    these keys and make every assertion below fail.
    """

    def _make_adapter_and_client(self):
        mock_sdk, client_instance = _make_mock_openai_module()

        batch_response = MagicMock()
        batch_response.id = "batch_ser_test"
        batch_response.expires_at = None
        client_instance.batches.create.return_value = batch_response

        file_response = MagicMock()
        file_response.id = "file-ser-001"
        client_instance.files.create.return_value = file_response

        adapter, ci = _make_adapter(client_instance=client_instance)
        return adapter, ci

    def _extract_jsonl_bodies(self, client_instance):
        """Parse the JSONL bytes passed to files.create and return list of body dicts."""
        call_args = client_instance.files.create.call_args
        # files.create(file=("batch_requests.jsonl", jsonl_bytes), purpose="batch")
        if call_args.kwargs:
            file_arg = call_args.kwargs.get("file")
        else:
            file_arg = call_args.args[0] if call_args.args else None

        if isinstance(file_arg, tuple):
            jsonl_bytes = file_arg[1]
        else:
            jsonl_bytes = file_arg

        import json as _json

        bodies = []
        for line in jsonl_bytes.split(b"\n"):
            line = line.strip()
            if line:
                record = _json.loads(line)
                bodies.append(record)
        return bodies

    def test_tc_ser_o1_temperature_appears_in_jsonl_body(self):
        """
        TC-SER-O1: resolved temperature=0.3 must appear in the JSONL body
        of the corresponding line staged via files.create.

        Counter-factual: removing body.update(rp) leaves body with only
        'messages' key; temperature would be missing.
        """
        adapter, client_instance = self._make_adapter_and_client()

        spec = _make_spec("spec-temp")
        resolved_params = [{"model": "gpt-4o", "max_tokens": 512, "temperature": 0.3}]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        bodies = self._extract_jsonl_bodies(client_instance)
        assert len(bodies) == 1
        body = bodies[0]["body"]
        assert "temperature" in body, (
            "temperature must be serialized into the JSONL body — "
            "counter-factual: removing body.update(rp) drops this key"
        )
        assert body["temperature"] == 0.3

    def test_tc_ser_o2_max_tokens_appears_in_jsonl_body(self):
        """
        TC-SER-O2: resolved max_tokens=128 must appear in the JSONL body.
        """
        adapter, client_instance = self._make_adapter_and_client()

        spec = _make_spec("spec-maxtok")
        resolved_params = [{"model": "gpt-4o", "max_tokens": 128}]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        bodies = self._extract_jsonl_bodies(client_instance)
        body = bodies[0]["body"]
        assert "max_tokens" in body, "max_tokens must appear in JSONL body"
        assert body["max_tokens"] == 128

    def test_tc_ser_o3_passthrough_key_appears_in_jsonl_body(self):
        """
        TC-SER-O3: a non-reserved passthrough key (frequency_penalty=0.3)
        from resolved_params must appear verbatim in the JSONL body.

        Proves non-conflicting request_options fills reach the payload.
        """
        adapter, client_instance = self._make_adapter_and_client()

        spec = _make_spec("spec-passthrough")
        resolved_params = [
            {"model": "gpt-4o", "max_tokens": 100, "frequency_penalty": 0.3}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        bodies = self._extract_jsonl_bodies(client_instance)
        body = bodies[0]["body"]
        assert "frequency_penalty" in body, (
            "passthrough key frequency_penalty must appear in JSONL body — "
            "proves non-reserved request_options fills are applied"
        )
        assert body["frequency_penalty"] == 0.3

    def test_tc_ser_o4_params_appear_on_correct_spec_not_all(self):
        """
        TC-SER-O4: per-spec params must land on the RIGHT JSONL line
        (matched by custom_id), not bleed into every line.

        Two specs with different temperatures; verify each line carries only its
        own value.
        """
        adapter, client_instance = self._make_adapter_and_client()

        spec_a = _make_spec("spec-a")
        spec_b = _make_spec("spec-b")
        resolved_params = [
            {"model": "gpt-4o", "max_tokens": 100, "temperature": 0.1},
            {"model": "gpt-4o", "max_tokens": 100, "temperature": 0.8},
        ]

        adapter.submit(specs=[spec_a, spec_b], resolved_params=resolved_params)

        bodies = self._extract_jsonl_bodies(client_instance)
        assert len(bodies) == 2

        # Build map: custom_id -> body
        by_custom_id = {r["custom_id"]: r["body"] for r in bodies}

        assert (
            by_custom_id["spec-a"]["temperature"] == 0.1
        ), "spec-a JSONL line must carry temperature=0.1, not spec-b's 0.8"
        assert (
            by_custom_id["spec-b"]["temperature"] == 0.8
        ), "spec-b JSONL line must carry temperature=0.8, not spec-a's 0.1"
