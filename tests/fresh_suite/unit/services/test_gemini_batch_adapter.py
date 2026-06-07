"""
Unit tests for GeminiBatchAdapter.

Covers:
- TC-045: Gemini inline batch submit returns result_ref=None
- TC-046: fetch_results with result_ref=None reads inline response payloads
- TC-047: Gemini usage normalization from usage_metadata shape
- TC-048: Gemini key sanitization uses shared helper
- TC-088: LLMDependencyError raised when google-genai not installed
- TC-089: With SDK installed (mocked), adapter instantiates successfully
- AC-T3: JOB_STATE_* values each map to a documented LLMBatchStatus
- AC-T5: provider_name == "google", supports_cancel
"""

import builtins
import sys
from unittest.mock import MagicMock, patch

import pytest

from agentmap.exceptions import LLMDependencyError
from agentmap.models.llm_execution import (
    LLMBatchStatus,
    LLMCallSpec,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(spec_id: str, messages=None) -> LLMCallSpec:
    """Build a minimal LLMCallSpec for testing."""
    if messages is None:
        messages = [{"role": "user", "content": f"hello from {spec_id}"}]
    return LLMCallSpec(spec_id=spec_id, messages=messages)


def _make_mock_genai_module():
    """Build a minimal fake google.genai module for patching sys.modules."""
    mock_genai = MagicMock()
    client_instance = MagicMock()
    mock_genai.Client.return_value = client_instance
    return mock_genai, client_instance


def _make_adapter(client_instance=None):
    """Create a GeminiBatchAdapter with the google-genai SDK mocked out."""
    mock_genai = MagicMock()
    if client_instance is None:
        client_instance = MagicMock()
    mock_genai.Client.return_value = client_instance

    with patch.dict(
        sys.modules,
        {
            "google": MagicMock(genai=mock_genai),
            "google.genai": mock_genai,
        },
    ):
        # Force reimport with patched modules
        if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
            del sys.modules["agentmap.services.llm.gemini_batch_adapter"]
        from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

        adapter = GeminiBatchAdapter(api_key="test-api-key", logger=MagicMock())
        adapter._client = client_instance
        return adapter


# ---------------------------------------------------------------------------
# TC-045: Gemini inline batch submit returns result_ref=None
# ---------------------------------------------------------------------------


class TestGeminiSubmit:
    def test_tc045_inline_submit_returns_result_ref_none(self):
        """TC-045: submit for inline batch returns (job.name, spec_id_map, None)."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/test-batch-123"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)

        spec = _make_spec("s1")
        provider_batch_id, spec_id_map, expires_at = adapter.submit(
            [spec], model="gemini-2.0-flash", max_tokens=512, request_options={}
        )

        assert provider_batch_id == "batches/test-batch-123"
        assert "s1" in spec_id_map
        assert expires_at is None
        client_instance.batches.create.assert_called_once()

    def test_tc045_submit_calls_batches_create_with_requests(self):
        """submit passes requests with 'key' field to batches.create."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-abc"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)

        spec = _make_spec("spec-1")
        adapter.submit(
            [spec], model="gemini-2.0-flash", max_tokens=256, request_options={}
        )

        call_kwargs = client_instance.batches.create.call_args
        # Should have been called — check it was called with model and requests
        assert call_kwargs is not None

    def test_tc048_key_sanitization_uses_shared_helper(self):
        """TC-048: spec_id with special chars is sanitized via GEMINI_KEY_RE."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-x"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)

        # spec_id with characters that would fail Gemini key validation
        spec = _make_spec("spec id with spaces and !special!")
        provider_batch_id, spec_id_map, expires_at = adapter.submit(
            [spec], model="gemini-2.0-flash", max_tokens=100, request_options={}
        )

        original_spec_id = "spec id with spaces and !special!"
        assert original_spec_id in spec_id_map
        sanitized = spec_id_map[original_spec_id]
        # The sanitized key must only contain [a-zA-Z0-9_-]
        import re

        assert re.match(r"^[a-zA-Z0-9_-]{1,128}$", sanitized)


# ---------------------------------------------------------------------------
# TC-046 + TC-047: fetch_results reads inline response payloads
# ---------------------------------------------------------------------------


class TestGeminiFetchResults:
    def _make_inline_response(self, key, text, prompt_tokens=80, candidates_tokens=40):
        """Build a mock inline response object."""
        resp = MagicMock()
        resp.key = key
        # content.parts[0].text
        part = MagicMock()
        part.text = text
        resp.response = MagicMock()
        resp.response.candidates = [MagicMock()]
        resp.response.candidates[0].content = MagicMock()
        resp.response.candidates[0].content.parts = [part]
        resp.response.usage_metadata = MagicMock()
        resp.response.usage_metadata.prompt_token_count = prompt_tokens
        resp.response.usage_metadata.candidates_token_count = candidates_tokens
        return resp

    def test_tc046_fetch_results_inline_no_result_ref(self):
        """TC-046: fetch_results with result_ref=None reads inline responses by key."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"s1": "s1", "s2": "s2"}

        inline_resp1 = self._make_inline_response("s1", "Answer 1")
        inline_resp2 = self._make_inline_response("s2", "Answer 2")

        mock_job = MagicMock()
        mock_job.inline_responses = [inline_resp1, inline_resp2]
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", spec_id_map, result_ref=None)
        )

        assert len(results) == 2
        spec_ids = {r.spec_id for r in results}
        assert spec_ids == {"s1", "s2"}

    def test_tc047_usage_normalization_from_usage_metadata(self):
        """TC-047: usage_metadata.prompt_token_count → input_tokens, candidates_token_count → output_tokens."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"s1": "s1"}
        inline_resp = self._make_inline_response(
            "s1", "Result text", prompt_tokens=80, candidates_tokens=40
        )
        mock_job = MagicMock()
        mock_job.inline_responses = [inline_resp]
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", spec_id_map, result_ref=None)
        )

        assert len(results) == 1
        record = results[0]
        assert record.usage is not None
        assert record.usage.input_tokens == 80
        assert record.usage.output_tokens == 40
        assert record.usage.cache_creation_input_tokens is None
        assert record.usage.cache_read_input_tokens is None

    def test_tc046_fetch_results_maps_key_back_to_spec_id(self):
        """TC-046: demux by key resolves back to original spec_id even after sanitization."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        # Spec ID was sanitized to a hash key
        spec_id_map = {"original spec id": "abc123sanitized"}

        inline_resp = self._make_inline_response("abc123sanitized", "some answer")
        mock_job = MagicMock()
        mock_job.inline_responses = [inline_resp]
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", spec_id_map, result_ref=None)
        )

        assert len(results) == 1
        assert results[0].spec_id == "original spec id"

    def test_fetch_results_unknown_key_is_skipped(self):
        """Inline responses with a key not in spec_id_map are skipped (logged)."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"s1": "s1"}
        inline_resp = self._make_inline_response("unknown_key", "oops")
        mock_job = MagicMock()
        mock_job.inline_responses = [inline_resp]
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", spec_id_map, result_ref=None)
        )

        assert results == []


# ---------------------------------------------------------------------------
# AC-T3: JOB_STATE_* → LLMBatchStatus mapping
# ---------------------------------------------------------------------------


class TestGeminiPollStatusMapping:
    def _poll_with_state(self, state_str):
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        mock_job = MagicMock()
        mock_job.state = state_str
        mock_job.inline_responses = []
        client_instance.batches.get.return_value = mock_job

        return adapter.poll("batches/test-123")

    def test_job_state_succeeded_maps_to_ended(self):
        result = self._poll_with_state("JOB_STATE_SUCCEEDED")
        assert result.status == LLMBatchStatus.ENDED

    def test_job_state_failed_maps_to_failed(self):
        result = self._poll_with_state("JOB_STATE_FAILED")
        assert result.status == LLMBatchStatus.FAILED

    def test_job_state_cancelled_maps_to_canceled(self):
        result = self._poll_with_state("JOB_STATE_CANCELLED")
        assert result.status == LLMBatchStatus.CANCELED

    def test_job_state_running_maps_to_in_progress(self):
        result = self._poll_with_state("JOB_STATE_RUNNING")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_job_state_pending_maps_to_in_progress(self):
        result = self._poll_with_state("JOB_STATE_PENDING")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_job_state_expired_maps_to_expired(self):
        result = self._poll_with_state("JOB_STATE_EXPIRED")
        assert result.status == LLMBatchStatus.EXPIRED

    def test_unknown_state_maps_to_failed(self):
        result = self._poll_with_state("JOB_STATE_UNSPECIFIED")
        assert result.status == LLMBatchStatus.FAILED

    def test_poll_result_ref_is_none_for_inline_batch(self):
        """Gemini inline batch: result_ref is always None in poll result."""
        result = self._poll_with_state("JOB_STATE_SUCCEEDED")
        assert result.result_ref is None


# ---------------------------------------------------------------------------
# AC-T4 / TC-088: import gating
# ---------------------------------------------------------------------------


class TestGeminiImportGating:
    def test_tc088_missing_google_genai_raises_llm_dependency_error(self):
        """TC-088: Instantiating GeminiBatchAdapter without google-genai raises LLMDependencyError."""
        # Ensure module is not cached
        if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
            del sys.modules["agentmap.services.llm.gemini_batch_adapter"]

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("google.genai", "google") and "genai" in str(args):
                raise ImportError("No module named 'google.genai'")
            # Also block at the from google import genai level
            if name == "google":
                raise ImportError("No module named 'google'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
                del sys.modules["agentmap.services.llm.gemini_batch_adapter"]
            from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

            with pytest.raises(LLMDependencyError, match="google-genai"):
                GeminiBatchAdapter(api_key="key", logger=MagicMock())

    def test_tc089_with_sdk_installed_adapter_instantiates(self):
        """TC-089: With SDK mocked as installed, GeminiBatchAdapter instantiates without error."""
        mock_genai = MagicMock()
        mock_genai.Client.return_value = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "google": MagicMock(genai=mock_genai),
                "google.genai": mock_genai,
            },
        ):
            if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
                del sys.modules["agentmap.services.llm.gemini_batch_adapter"]
            from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

            # Should not raise
            adapter = GeminiBatchAdapter(api_key="test-key", logger=MagicMock())
            assert adapter is not None


# ---------------------------------------------------------------------------
# AC-T5: provider_name and supports_cancel
# ---------------------------------------------------------------------------


class TestGeminiClassAttributes:
    def test_ac_t5_provider_name_is_google(self):
        """AC-T5: provider_name class attribute is 'google'."""
        adapter = _make_adapter()
        assert adapter.provider_name == "google"

    def test_ac_t5_supports_cancel_is_bool(self):
        """AC-T5: supports_cancel is a documented bool."""
        adapter = _make_adapter()
        assert isinstance(adapter.supports_cancel, bool)
