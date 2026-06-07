"""
Unit tests for GeminiBatchAdapter.

All mocks in this file reflect the **real** google-genai SDK shape, confirmed
against https://ai.google.dev/gemini-api/docs/batch-api:

  - create(*, model, src, config=None)   NOT create(model=, requests=)
  - get(*, name=...)                     NOT get(positional_arg)
  - cancel(*, name=...)
  - Results at batch_job.dest.inlined_responses  NOT job.inline_responses
  - state is an enum; state.name == "JOB_STATE_*"
  - Inline request entries: {'contents': [...], 'config': {...}}  — NO 'key' field
  - Response correlation is positional (index), not by key

If the adapter is reverted to the wrong API shape (requests=, positional get,
job.inline_responses, etc.), the call-arg assertions in this file will fail.

Covers:
- TC-045: Gemini inline batch submit returns result_ref=None
- TC-046: fetch_results reads dest.inlined_responses positionally
- TC-047: Gemini usage normalization from usage_metadata shape
- TC-048: src entries contain contents + config, no key field
- TC-088: LLMDependencyError raised when google-genai not installed
- TC-089: With SDK installed (mocked), adapter instantiates successfully
- AC-T3: JOB_STATE_* values each map to a documented LLMBatchStatus
- AC-T5: provider_name == "google", supports_cancel == True
- cancel: calls client.batches.cancel(name=...) with keyword arg
- error items: inlined response with error attr yields errored record
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


def _make_spec(spec_id: str, messages=None, temperature=None) -> LLMCallSpec:
    """Build a minimal LLMCallSpec for testing."""
    if messages is None:
        messages = [{"role": "user", "content": f"hello from {spec_id}"}]
    return LLMCallSpec(spec_id=spec_id, messages=messages, temperature=temperature)


def _make_resolved(specs, model="gemini-2.0-flash", max_tokens=512, request_options=None, temperature=None):
    """Build a resolved_params list from old-style args (test helper only)."""
    rp = {"model": model, "max_tokens": max_tokens}
    if temperature is not None:
        rp["temperature"] = temperature
    elif specs and getattr(specs[0], "temperature", None) is not None:
        # propagate per-spec temperature for single-spec tests
        pass
    if request_options:
        rp.update(request_options)
    return [dict(rp) for _ in specs]


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
        if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
            del sys.modules["agentmap.services.llm.gemini_batch_adapter"]
        from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

        adapter = GeminiBatchAdapter(api_key="test-api-key", logger=MagicMock())
        adapter._client = client_instance
        return adapter


def _make_state_enum(name: str) -> MagicMock:
    """Build a mock enum object whose .name attribute returns the JOB_STATE_* string.

    The real google-genai SDK returns state as an enum, not a raw string.
    Confirmed: https://ai.google.dev/gemini-api/docs/batch-api uses state.name
    """
    state = MagicMock()
    state.name = name
    return state


def _make_inlined_response(text: str, prompt_tokens=80, candidates_tokens=40):
    """Build a mock inlined response item as returned by dest.inlined_responses.

    Real shape (confirmed against SDK docs):
      item.error  — None for success
      item.response.candidates[0].content.parts[0].text
      item.response.usage_metadata.prompt_token_count
      item.response.usage_metadata.candidates_token_count
    """
    item = MagicMock()
    item.error = None  # no error — success path
    part = MagicMock()
    part.text = text
    item.response = MagicMock()
    item.response.candidates = [MagicMock()]
    item.response.candidates[0].content = MagicMock()
    item.response.candidates[0].content.parts = [part]
    item.response.usage_metadata = MagicMock()
    item.response.usage_metadata.prompt_token_count = prompt_tokens
    item.response.usage_metadata.candidates_token_count = candidates_tokens
    return item


def _make_job_with_responses(items, batch_name="batches/test-123"):
    """Build a mock batch job with dest.inlined_responses.

    Real shape (confirmed): batch_job.dest.inlined_responses
    NOT job.inline_responses (that attribute does not exist in the real SDK).
    """
    mock_job = MagicMock()
    mock_job.name = batch_name
    mock_job.dest = MagicMock()
    mock_job.dest.inlined_responses = items
    return mock_job


# ---------------------------------------------------------------------------
# TC-045 / TC-048: submit
# ---------------------------------------------------------------------------


class TestGeminiSubmit:
    def test_tc045_inline_submit_returns_result_ref_none(self):
        """TC-045: submit returns (job.name, spec_id_map, None).

        expires_at is always None for inline Gemini batches.
        """
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/test-batch-123"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)

        spec = _make_spec("s1")
        specs_s1 = [spec]
        provider_batch_id, spec_id_map, expires_at = adapter.submit(
            specs_s1, resolved_params=_make_resolved(specs_s1)
        )

        assert provider_batch_id == "batches/test-batch-123"
        assert expires_at is None
        # spec_id_map encodes ordered list for positional demux
        assert "__ordered__" in spec_id_map
        assert spec_id_map["__ordered__"] == ["s1"]

    def test_submit_calls_create_with_src_not_requests(self):
        """TC-048 / regression guard: create is called with 'src=', NOT 'requests='.

        If the adapter is reverted to the wrong API shape (requests=), this
        assertion catches it.  Confirmed real shape:
        client.batches.create(*, model, src, config=None)
        https://ai.google.dev/gemini-api/docs/batch-api
        """
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-abc"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)
        spec = _make_spec("spec-1")
        specs_sp1 = [spec]
        adapter.submit(
            specs_sp1, resolved_params=_make_resolved(specs_sp1, max_tokens=256)
        )

        call_kwargs = client_instance.batches.create.call_args
        assert call_kwargs is not None
        # 'src' must be present as a keyword argument
        assert "src" in call_kwargs.kwargs, (
            "create() must be called with src=..., not requests=... "
            "(the old shape does not exist in the real SDK)"
        )
        # 'requests' must NOT appear — it's the wrong (non-existent) parameter
        assert (
            "requests" not in call_kwargs.kwargs
        ), "create() was called with requests= which is not the real SDK shape"

    def test_submit_src_entries_have_contents_and_config_no_key(self):
        """TC-048: each src entry has 'contents' and 'config', NO 'key' field.

        For inline batches the real SDK takes GenerateContentRequest dicts.
        There is no 'key' field on inline src entries — keys are only for
        file-based JSONL input.  Confirmed: https://ai.google.dev/gemini-api/docs/batch-api
        """
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-x"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)
        spec = _make_spec("my-spec", temperature=0.5)
        specs_ms = [spec]
        adapter.submit(
            specs_ms,
            resolved_params=[{"model": "gemini-2.0-flash", "max_tokens": 100, "temperature": 0.5}],
        )

        call_kwargs = client_instance.batches.create.call_args
        src_list = call_kwargs.kwargs["src"]
        assert len(src_list) == 1
        entry = src_list[0]
        assert "contents" in entry, "src entry must have 'contents'"
        assert "config" in entry, "src entry must have 'config'"
        assert "key" not in entry, (
            "src entry must NOT have 'key' — inline batches use positional "
            "correlation, not key-based (key is only for file-based JSONL)"
        )
        # Config must contain max_output_tokens (snake_case SDK name)
        assert "max_output_tokens" in entry["config"]
        assert entry["config"]["temperature"] == 0.5

    def test_submit_spec_id_map_preserves_order(self):
        """The __ordered__ list preserves submission order for positional demux."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-order"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)
        specs = [_make_spec("alpha"), _make_spec("beta"), _make_spec("gamma")]
        _, spec_id_map, _ = adapter.submit(
            specs, resolved_params=_make_resolved(specs, max_tokens=100)
        )

        assert spec_id_map["__ordered__"] == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------------
# TC-046 + TC-047: fetch_results reads dest.inlined_responses positionally
# ---------------------------------------------------------------------------


class TestGeminiFetchResults:
    def test_tc046_fetch_results_reads_dest_inlined_responses(self):
        """TC-046: fetch_results reads from batch_job.dest.inlined_responses.

        NOT from job.inline_responses — that attribute does not exist in the
        real google-genai SDK.  Confirmed: https://ai.google.dev/gemini-api/docs/batch-api
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["s1", "s2"]}
        item1 = _make_inlined_response("Answer 1")
        item2 = _make_inlined_response("Answer 2")
        mock_job = _make_job_with_responses([item1, item2])
        # get() must be called with name= keyword arg
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", spec_id_map, result_ref=None)
        )

        # Verify get was called with keyword name= (NOT positional)
        client_instance.batches.get.assert_called_once_with(name="batches/test-123")

        assert len(results) == 2
        assert results[0].spec_id == "s1"
        assert results[1].spec_id == "s2"

    def test_tc046_get_called_with_keyword_name_not_positional(self):
        """Regression guard: batches.get must use keyword name=, not positional.

        Real SDK: get(*, name, ...) keyword-only.
        If the adapter reverts to get(positional_arg), this fails.
        Confirmed: https://ai.google.dev/gemini-api/docs/batch-api
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["s1"]}
        item = _make_inlined_response("Hello")
        mock_job = _make_job_with_responses([item])
        client_instance.batches.get.return_value = mock_job

        list(adapter.fetch_results("batches/abc", spec_id_map))

        # Must be called as keyword arg, not positional
        call_kwargs = client_instance.batches.get.call_args
        assert (
            call_kwargs.kwargs.get("name") == "batches/abc"
        ), "batches.get() must use name= keyword arg (SDK is keyword-only)"
        assert not call_kwargs.args, "batches.get() must not use positional args"

    def test_tc047_usage_normalization_from_usage_metadata(self):
        """TC-047: prompt_token_count→input_tokens, candidates_token_count→output_tokens."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["s1"]}
        item = _make_inlined_response("Result", prompt_tokens=80, candidates_tokens=40)
        mock_job = _make_job_with_responses([item])
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

    def test_fetch_results_positional_demux_by_index(self):
        """Results are matched to spec_ids by position, not by any key."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["first-spec", "second-spec"]}
        item0 = _make_inlined_response("text for first")
        item1 = _make_inlined_response("text for second")
        mock_job = _make_job_with_responses([item0, item1])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/test", spec_id_map))

        assert results[0].spec_id == "first-spec"
        assert results[0].content == "text for first"
        assert results[1].spec_id == "second-spec"
        assert results[1].content == "text for second"

    def test_fetch_results_item_error_yields_errored_record(self):
        """An inlined response with an error attr yields an errored LLMBatchResultRecord."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["s1"]}
        item = MagicMock()
        item.error = MagicMock()
        item.error.__str__ = lambda self: "rate limit exceeded"
        item.response = None
        mock_job = _make_job_with_responses([item])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/test", spec_id_map))

        assert len(results) == 1
        assert results[0].status == "errored"
        assert results[0].spec_id == "s1"

    def test_fetch_results_excess_responses_are_skipped(self):
        """Extra inlined responses beyond spec_id_list length are skipped with a warning."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        spec_id_map = {"__ordered__": ["s1"]}  # only 1 spec
        item0 = _make_inlined_response("ok")
        item1 = _make_inlined_response("extra")
        mock_job = _make_job_with_responses([item0, item1])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/test", spec_id_map))

        # Only 1 result — the extra one is skipped
        assert len(results) == 1
        assert results[0].spec_id == "s1"


# ---------------------------------------------------------------------------
# Poll: state enum, get keyword arg, status mapping
# ---------------------------------------------------------------------------


class TestGeminiPoll:
    def _poll_with_state(self, state_name: str):
        """Helper: poll with a state enum mock whose .name == state_name."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        mock_job = MagicMock()
        # Real SDK: state is an enum, access state.name for string
        mock_job.state = _make_state_enum(state_name)
        client_instance.batches.get.return_value = mock_job

        return adapter.poll("batches/test-123"), client_instance

    def test_poll_calls_get_with_keyword_name(self):
        """poll calls client.batches.get(name=...) keyword-only.

        Real SDK: get(*, name, ...) — keyword-only, NOT positional.
        If reverted to get(provider_batch_id) positional, this fails.
        """
        _, client_instance = self._poll_with_state("JOB_STATE_RUNNING")
        call_kwargs = client_instance.batches.get.call_args
        assert (
            call_kwargs.kwargs.get("name") == "batches/test-123"
        ), "batches.get() must use name= keyword (SDK is keyword-only)"
        assert not call_kwargs.args, "batches.get() must not use positional args"

    def test_poll_reads_state_via_dot_name(self):
        """State is an enum; adapter reads state.name, not state directly."""
        result, _ = self._poll_with_state("JOB_STATE_SUCCEEDED")
        assert result.status == LLMBatchStatus.ENDED

    def test_job_state_succeeded_maps_to_ended(self):
        result, _ = self._poll_with_state("JOB_STATE_SUCCEEDED")
        assert result.status == LLMBatchStatus.ENDED

    def test_job_state_failed_maps_to_failed(self):
        result, _ = self._poll_with_state("JOB_STATE_FAILED")
        assert result.status == LLMBatchStatus.FAILED

    def test_job_state_cancelled_maps_to_canceled(self):
        result, _ = self._poll_with_state("JOB_STATE_CANCELLED")
        assert result.status == LLMBatchStatus.CANCELED

    def test_job_state_running_maps_to_in_progress(self):
        result, _ = self._poll_with_state("JOB_STATE_RUNNING")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_job_state_pending_maps_to_in_progress(self):
        result, _ = self._poll_with_state("JOB_STATE_PENDING")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_job_state_expired_maps_to_expired(self):
        result, _ = self._poll_with_state("JOB_STATE_EXPIRED")
        assert result.status == LLMBatchStatus.EXPIRED

    def test_unknown_state_maps_to_failed(self):
        result, _ = self._poll_with_state("JOB_STATE_UNSPECIFIED")
        assert result.status == LLMBatchStatus.FAILED

    def test_poll_result_ref_is_none(self):
        """Gemini inline batch: result_ref is always None in poll result."""
        result, _ = self._poll_with_state("JOB_STATE_SUCCEEDED")
        assert result.result_ref is None


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestGeminiCancel:
    def test_cancel_calls_batches_cancel_with_keyword_name(self):
        """cancel() calls client.batches.cancel(name=...) — keyword-only.

        Real SDK: cancel(*, name) confirmed.
        https://ai.google.dev/gemini-api/docs/batch-api
        If reverted to always-raise or wrong signature, this fails.
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        adapter.cancel("batches/test-batch-456")

        client_instance.batches.cancel.assert_called_once_with(
            name="batches/test-batch-456"
        )

    def test_cancel_with_positional_arg_would_be_wrong_shape(self):
        """Regression: cancel must use name= keyword, not positional.

        This test verifies the call_args show keyword usage.
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        adapter.cancel("batches/xyz")

        call_kwargs = client_instance.batches.cancel.call_args
        assert call_kwargs.kwargs.get("name") == "batches/xyz"
        assert not call_kwargs.args


# ---------------------------------------------------------------------------
# AC-T4 / TC-088: import gating
# ---------------------------------------------------------------------------


class TestGeminiImportGating:
    def test_tc088_missing_google_genai_raises_llm_dependency_error(self):
        """TC-088: Instantiating GeminiBatchAdapter without google-genai raises LLMDependencyError."""
        if "agentmap.services.llm.gemini_batch_adapter" in sys.modules:
            del sys.modules["agentmap.services.llm.gemini_batch_adapter"]

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
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

    def test_ac_t5_supports_cancel_is_true(self):
        """AC-T5: supports_cancel is True — Gemini Developer API supports cancel.

        Confirmed: client.batches.cancel(name=...) exists in the real SDK.
        https://ai.google.dev/gemini-api/docs/batch-api
        Previously incorrectly set to False.
        """
        adapter = _make_adapter()
        assert adapter.supports_cancel is True
