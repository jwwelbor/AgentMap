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
import datetime
import sys
from unittest.mock import MagicMock, patch

import pytest

from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import (
    LLMBatchStatus,
    LLMRequest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(request_id: str, messages=None, temperature=None) -> LLMRequest:
    """Build a minimal LLMRequest for testing."""
    if messages is None:
        messages = [{"role": "user", "content": f"hello from {request_id}"}]
    return LLMRequest(request_id=request_id, messages=messages, temperature=temperature)


def _make_resolved(
    specs,
    model="gemini-2.0-flash",
    max_tokens=512,
    request_options=None,
    temperature=None,
):
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
        """TC-045: submit returns (job.name, request_id_map, None).

        expires_at is always None for inline Gemini batches.
        """
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/test-batch-123"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)

        spec = _make_spec("s1")
        specs_s1 = [spec]
        provider_batch_id, request_id_map, expires_at = adapter.submit(
            specs_s1, resolved_params=_make_resolved(specs_s1)
        )

        assert provider_batch_id == "batches/test-batch-123"
        assert expires_at is None
        # request_id_map encodes ordered list for positional demux
        assert "__ordered__" in request_id_map
        assert request_id_map["__ordered__"] == ["s1"]

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
            resolved_params=[
                {"model": "gemini-2.0-flash", "max_tokens": 100, "temperature": 0.5}
            ],
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

    def test_submit_request_id_map_preserves_order(self):
        """The __ordered__ list preserves submission order for positional demux."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-order"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)
        specs = [_make_spec("alpha"), _make_spec("beta"), _make_spec("gamma")]
        _, request_id_map, _ = adapter.submit(
            specs, resolved_params=_make_resolved(specs, max_tokens=100)
        )

        assert request_id_map["__ordered__"] == ["alpha", "beta", "gamma"]

    def test_submit_rejects_heterogeneous_models(self):
        """Gemini batch submit must fail fast when resolved specs use multiple models."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)
        specs = [_make_spec("s1"), _make_spec("s2")]

        with pytest.raises(LLMServiceError, match="single model"):
            adapter.submit(
                specs,
                resolved_params=[
                    {"model": "gemini-2.0-flash", "max_tokens": 100},
                    {"model": "gemini-2.0-pro", "max_tokens": 100},
                ],
            )

        client_instance.batches.create.assert_not_called()

    def test_submit_routes_system_messages_to_system_instruction(self):
        """Gemini system-role messages should be emitted as system_instruction, not contents."""
        client_instance = MagicMock()
        mock_job = MagicMock()
        mock_job.name = "batches/job-system"
        client_instance.batches.create.return_value = mock_job

        adapter = _make_adapter(client_instance)
        spec = _make_spec(
            "s1",
            messages=[
                {"role": "system", "content": "Answer tersely."},
                {"role": "user", "content": "Summarize this."},
            ],
        )
        adapter.submit([spec], resolved_params=_make_resolved([spec], max_tokens=64))

        src_entry = client_instance.batches.create.call_args.kwargs["src"][0]
        assert src_entry["config"]["system_instruction"] == "Answer tersely."
        assert src_entry["contents"] == [
            {"role": "user", "parts": [{"text": "Summarize this."}]}
        ]

    def test_submit_rejects_non_string_message_content(self):
        """Gemini batch submit must reject multimodal/list content instead of stringifying it."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)
        spec = _make_spec(
            "s1",
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello"}],
                }
            ],
        )

        with pytest.raises(LLMServiceError, match="request_id='s1'"):
            adapter.submit(
                [spec], resolved_params=_make_resolved([spec], max_tokens=32)
            )

        client_instance.batches.create.assert_not_called()


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

        request_id_map = {"__ordered__": ["s1", "s2"]}
        item1 = _make_inlined_response("Answer 1")
        item2 = _make_inlined_response("Answer 2")
        mock_job = _make_job_with_responses([item1, item2])
        # get() must be called with name= keyword arg
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", request_id_map, result_ref=None)
        )

        # Verify get was called with keyword name= (NOT positional)
        client_instance.batches.get.assert_called_once_with(name="batches/test-123")

        assert len(results) == 2
        assert results[0].request_id == "s1"
        assert results[1].request_id == "s2"

    def test_tc046_get_called_with_keyword_name_not_positional(self):
        """Regression guard: batches.get must use keyword name=, not positional.

        Real SDK: get(*, name, ...) keyword-only.
        If the adapter reverts to get(positional_arg), this fails.
        Confirmed: https://ai.google.dev/gemini-api/docs/batch-api
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        request_id_map = {"__ordered__": ["s1"]}
        item = _make_inlined_response("Hello")
        mock_job = _make_job_with_responses([item])
        client_instance.batches.get.return_value = mock_job

        list(adapter.fetch_results("batches/abc", request_id_map))

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

        request_id_map = {"__ordered__": ["s1"]}
        item = _make_inlined_response("Result", prompt_tokens=80, candidates_tokens=40)
        mock_job = _make_job_with_responses([item])
        client_instance.batches.get.return_value = mock_job

        results = list(
            adapter.fetch_results("batches/test-123", request_id_map, result_ref=None)
        )

        assert len(results) == 1
        record = results[0]
        assert record.usage is not None
        assert record.usage.input_tokens == 80
        assert record.usage.output_tokens == 40
        assert record.usage.cache_creation_input_tokens is None
        assert record.usage.cache_read_input_tokens is None

    def test_fetch_results_positional_demux_by_index(self):
        """Results are matched to request_ids by position, not by any key."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        request_id_map = {"__ordered__": ["first-spec", "second-spec"]}
        item0 = _make_inlined_response("text for first")
        item1 = _make_inlined_response("text for second")
        mock_job = _make_job_with_responses([item0, item1])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/test", request_id_map))

        assert results[0].request_id == "first-spec"
        assert results[0].text == "text for first"
        assert results[1].request_id == "second-spec"
        assert results[1].text == "text for second"

    def test_fetch_results_item_error_yields_errored_record(self):
        """An inlined response with an error attr yields an errored LLMBatchResult."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        request_id_map = {"__ordered__": ["s1"]}
        item = MagicMock()
        item.error = MagicMock()
        item.error.__str__ = lambda self: "rate limit exceeded"
        item.response = None
        mock_job = _make_job_with_responses([item])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/test", request_id_map))

        assert len(results) == 1
        assert results[0].status == "errored"
        assert results[0].request_id == "s1"

    def test_fetch_results_excess_responses_raises_integrity_error(self):
        """N2 / D-9: over-count (responses > specs) raises LLMBatchResultIntegrityError.

        Extra responses mean NO position is trustworthy — every result could be
        misattributed.  The adapter must raise, not silently skip the tail.
        Per spec.md § Gemini Result Demux Integrity N2.1(1) and D-9.
        """
        from agentmap.services.llm_batch_errors import LLMBatchResultIntegrityError

        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        request_id_map = {"__ordered__": ["s1"]}  # only 1 spec submitted
        item0 = _make_inlined_response("ok")
        item1 = _make_inlined_response("extra — more responses than specs")
        mock_job = _make_job_with_responses([item0, item1])  # 2 responses, 1 spec
        client_instance.batches.get.return_value = mock_job

        with pytest.raises(LLMBatchResultIntegrityError) as exc_info:
            list(adapter.fetch_results("batches/test", request_id_map))

        error_msg = str(exc_info.value)
        # Error must name submitted count and returned count
        assert "1" in error_msg  # submitted
        assert "2" in error_msg  # returned


# ---------------------------------------------------------------------------
# N2: Demux integrity tests (D-9 / spec.md § Gemini Result Demux Integrity)
# ---------------------------------------------------------------------------


class TestGeminiDemuxIntegrity:
    """N2.2 test cases for count-equality enforcement in fetch_results.

    Per spec N5.2:
    - short-tail (N-1 responses for N specs) → synthesize errored missing_result records
    - over-count (N+1 responses for N specs) → raise LLMBatchResultIntegrityError
    - equal count → positional demux proceeds unchanged (happy path)
    - reorder-bound: equal-count shuffled content does NOT trigger an error (just
      demonstrates the positional contract; the guard does not fire on equal counts)
    """

    def _make_adapter_with_responses(self, request_ids, num_responses):
        """Build adapter + client with num_responses inlined items for len(request_ids) specs."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)
        items = [
            _make_inlined_response(f"text for idx {i}") for i in range(num_responses)
        ]
        mock_job = _make_job_with_responses(items)
        client_instance.batches.get.return_value = mock_job
        request_id_map = {"__ordered__": list(request_ids)}
        return adapter, client_instance, request_id_map

    def test_n2_short_tail_synthesizes_missing_result_records(self):
        """N2 / D-9: short-tail → errored missing_result records for missing request_ids.

        Submit 3 specs, provider returns only 2 responses.  The adapter must
        yield 2 succeeded records for the present indices AND synthesize 1 errored
        record for the missing request_id.  No shifting of positions.
        Per spec N2.1(2): short tail → synthesize errored LLMBatchResult.
        """
        adapter, _, request_id_map = self._make_adapter_with_responses(
            ["spec-A", "spec-B", "spec-C"], num_responses=2  # 3 specs, 2 responses
        )

        results = list(
            adapter.fetch_results("batches/short", request_id_map, result_ref=None)
        )

        # Must have 3 total results — 2 present + 1 synthesized
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        # First two positionally correct — no shifting
        assert results[0].request_id == "spec-A"
        assert results[1].request_id == "spec-B"

        # Third is synthesized errored record for the missing tail request_id
        missing = results[2]
        assert missing.request_id == "spec-C"
        assert missing.status == "errored"
        assert missing.error is not None
        assert missing.error.error_type == "missing_result"
        assert missing.error.retryable is True

    def test_n2_short_tail_multi_missing_synthesizes_all(self):
        """N2: short tail of 2 produces errored records for both missing request_ids."""
        adapter, _, request_id_map = self._make_adapter_with_responses(
            ["s1", "s2", "s3", "s4"], num_responses=2  # 4 specs, 2 responses
        )

        results = list(
            adapter.fetch_results(
                "batches/short-multi", request_id_map, result_ref=None
            )
        )

        assert len(results) == 4

        # Present results at correct positions
        assert results[0].request_id == "s1"
        assert results[0].status == "succeeded"
        assert results[1].request_id == "s2"
        assert results[1].status == "succeeded"

        # Missing results synthesized, correct request_ids, not shifted
        assert results[2].request_id == "s3"
        assert results[2].status == "errored"
        assert results[2].error.error_type == "missing_result"
        assert results[3].request_id == "s4"
        assert results[3].status == "errored"
        assert results[3].error.error_type == "missing_result"

    def test_n2_over_count_raises_integrity_error(self):
        """N2 / D-9: over-count (responses > specs) raises LLMBatchResultIntegrityError.

        With more responses than specs, no position can be trusted — raise,
        yield nothing.  Per spec N2.1(1).
        """
        from agentmap.services.llm_batch_errors import LLMBatchResultIntegrityError

        adapter, _, request_id_map = self._make_adapter_with_responses(
            ["spec-X", "spec-Y"], num_responses=3  # 2 specs, 3 responses
        )

        with pytest.raises(LLMBatchResultIntegrityError) as exc_info:
            list(adapter.fetch_results("batches/over", request_id_map, result_ref=None))

        error_msg = str(exc_info.value)
        # Must name the batch, submitted count, and returned count
        assert "2" in error_msg  # submitted spec count
        assert "3" in error_msg  # returned response count

    def test_n2_over_count_names_batch_id_in_error(self):
        """LLMBatchResultIntegrityError names the batch id per spec N2.2."""
        from agentmap.services.llm_batch_errors import LLMBatchResultIntegrityError

        adapter, _, request_id_map = self._make_adapter_with_responses(
            ["s1"], num_responses=2
        )

        with pytest.raises(LLMBatchResultIntegrityError) as exc_info:
            list(
                adapter.fetch_results(
                    "batches/sentinel-batch-id", request_id_map, result_ref=None
                )
            )

        assert "sentinel-batch-id" in str(exc_info.value)

    def test_n2_equal_count_proceeds_without_error(self):
        """N2 equal-count happy path: positional demux runs normally, no error raised."""
        adapter, _, request_id_map = self._make_adapter_with_responses(
            ["alpha", "beta", "gamma"], num_responses=3
        )

        results = list(
            adapter.fetch_results("batches/equal", request_id_map, result_ref=None)
        )

        assert len(results) == 3
        assert results[0].request_id == "alpha"
        assert results[1].request_id == "beta"
        assert results[2].request_id == "gamma"
        for r in results:
            assert r.status == "succeeded"

    def test_n2_reorder_bound_equal_count_does_not_raise(self):
        """N2 reorder-bound: equal-count demux proceeds even if content appears shuffled.

        The guard fires on COUNT mismatch only; reordering within equal count is the
        accepted (unavoidable) positional contract.  This test documents the assumption
        and guards against an over-eager guard that fires on equal counts.
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        # Two specs, two responses, but content "looks" swapped
        request_id_map = {"__ordered__": ["first", "second"]}
        item0 = _make_inlined_response("content that would belong to second")
        item1 = _make_inlined_response("content that would belong to first")
        mock_job = _make_job_with_responses([item0, item1])
        client_instance.batches.get.return_value = mock_job

        # Must NOT raise — equal count is the valid positional case
        results = list(adapter.fetch_results("batches/reorder", request_id_map))

        assert len(results) == 2
        # Positional attribution: index 0 → "first", index 1 → "second"
        assert results[0].request_id == "first"
        assert results[1].request_id == "second"

    def test_n2_short_tail_present_records_correct_request_id_attribution(self):
        """N2: present records carry correct request_id, proving no silent shift.

        The request_id on each record must match the submitted spec at that
        index — not shifted by 1 because one record was dropped.
        """
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)

        request_id_map = {"__ordered__": ["X", "Y", "Z"]}
        item0 = _make_inlined_response("text-X")
        item1 = _make_inlined_response("text-Y")
        # Z response is missing (short tail)
        mock_job = _make_job_with_responses([item0, item1])
        client_instance.batches.get.return_value = mock_job

        results = list(adapter.fetch_results("batches/noshift", request_id_map))

        assert len(results) == 3
        # Positional: idx 0 → X, idx 1 → Y
        assert results[0].request_id == "X"
        assert results[0].text == "text-X"
        assert results[1].request_id == "Y"
        assert results[1].text == "text-Y"
        # Synthesized missing for Z — NOT shifted (Y content must not appear under Z)
        assert results[2].request_id == "Z"
        assert results[2].status == "errored"
        assert results[2].error.error_type == "missing_result"


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

    def test_poll_converts_end_time_to_iso_string(self):
        """Gemini poll should serialize datetime end_time to ISO-8601."""
        client_instance = MagicMock()
        adapter = _make_adapter(client_instance)
        mock_job = MagicMock()
        mock_job.state = _make_state_enum("JOB_STATE_SUCCEEDED")
        mock_job.end_time = datetime.datetime(
            2026, 6, 8, 12, 30, tzinfo=datetime.timezone.utc
        )
        client_instance.batches.get.return_value = mock_job

        result = adapter.poll("batches/test-123")

        assert result.ended_at == "2026-06-08T12:30:00+00:00"


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


# ---------------------------------------------------------------------------
# T-E05-F04-010: Adapter-level serialization assertions
# ---------------------------------------------------------------------------


class TestGeminiSubmitSerializesResolvedParams:
    """
    TC-SER-G1 through TC-SER-G5: prove that resolved_params values actually
    reach the src entries passed to client.batches.create.

    Gemini adapter builds config from rp, applying max_tokens→max_output_tokens
    rename and passing temperature and non-reserved keys through verbatim.

    Counter-factual: removing the generation_config assembly in _build_src would
    produce empty config dicts; every assertion below would fail.
    """

    def _make_adapter_and_client(self):
        adapter = _make_adapter()
        client_instance = adapter._client

        batch_response = MagicMock()
        batch_response.name = "batches/ser-test-001"
        client_instance.batches.create.return_value = batch_response

        return adapter, client_instance

    def _extract_src(self, client_instance):
        """Extract the src list passed to client.batches.create."""
        call_args = client_instance.batches.create.call_args
        if call_args.kwargs:
            return call_args.kwargs.get("src", [])
        return []

    def test_tc_ser_g1_temperature_appears_in_src_config(self):
        """
        TC-SER-G1: resolved temperature=0.6 must appear in src[i].config
        for the corresponding spec entry.

        Counter-factual: removing generation_config["temperature"] = rp["temperature"]
        leaves config with no temperature key.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-temp", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [
            {"model": "gemini-2.0-flash", "max_tokens": 256, "temperature": 0.6}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        assert len(src) == 1
        config = src[0]["config"]
        assert "temperature" in config, (
            "temperature must appear in src[0].config — "
            "counter-factual: removing config assembly drops this key"
        )
        assert config["temperature"] == 0.6

    def test_tc_ser_g2_max_tokens_renamed_to_max_output_tokens(self):
        """
        TC-SER-G2: resolved max_tokens must be renamed to max_output_tokens
        in src[i].config (Gemini-specific rename applied by _build_src).

        Counter-factual: removing the rename produces max_tokens key instead of
        max_output_tokens, which the Gemini SDK would reject.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-maxtok", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [{"model": "gemini-2.0-flash", "max_tokens": 512}]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        config = src[0]["config"]
        assert (
            "max_output_tokens" in config
        ), "max_tokens must be renamed to max_output_tokens in Gemini src config"
        assert config["max_output_tokens"] == 512
        assert (
            "max_tokens" not in config
        ), "max_tokens (unrenamed) must NOT appear in Gemini src config"

    def test_tc_ser_g3_passthrough_key_appears_in_src_config(self):
        """
        TC-SER-G3: a non-reserved passthrough key (top_k=40) must appear
        verbatim in src[i].config.

        Proves non-conflicting request_options fills reach the Gemini payload.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-passthrough", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [
            {"model": "gemini-2.0-flash", "max_tokens": 100, "top_k": 40}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        config = src[0]["config"]
        assert "top_k" in config, (
            "passthrough key top_k must appear in Gemini src config — "
            "proves non-reserved request_options fills are applied"
        )
        assert config["top_k"] == 40

    def test_tc_ser_g4_model_not_leaked_into_config(self):
        """
        TC-SER-G4: the model key must NOT appear in src[i].config.

        Model is passed as a batch-level argument to batches.create(model=...);
        _build_src explicitly excludes it from generation_config.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-nomodel", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [
            {"model": "gemini-2.0-flash", "max_tokens": 64, "temperature": 0.5}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        config = src[0]["config"]
        assert (
            "model" not in config
        ), "model must not leak into src[i].config — it belongs at batch level only"

    def test_tc_ser_g5_params_appear_on_correct_spec_by_position(self):
        """
        TC-SER-G5: per-spec params must land at the correct positional index,
        not bleed across entries.

        Two specs with different temperatures; verify each src[i].config carries
        only its own value (Gemini uses positional demux).
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec_a = LLMRequest(
            request_id="spec-a", messages=[{"role": "user", "content": "a"}]
        )
        spec_b = LLMRequest(
            request_id="spec-b", messages=[{"role": "user", "content": "b"}]
        )
        resolved_params = [
            {"model": "gemini-2.0-flash", "max_tokens": 100, "temperature": 0.15},
            {"model": "gemini-2.0-flash", "max_tokens": 100, "temperature": 0.85},
        ]

        adapter.submit(specs=[spec_a, spec_b], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        assert len(src) == 2

        assert (
            src[0]["config"]["temperature"] == 0.15
        ), "src[0] must carry temperature=0.15 (spec-a), not spec-b's 0.85"
        assert (
            src[1]["config"]["temperature"] == 0.85
        ), "src[1] must carry temperature=0.85 (spec-b), not spec-a's 0.15"

    def test_tc_ser_g6_raw_max_output_tokens_in_resolved_excluded_from_passthrough(
        self,
    ):
        """
        TC-SER-G6 / CR5-1 adapter-level regression: if a resolved dict
        hypothetically contains the raw alias key ``max_output_tokens`` (e.g.
        if the central resolver were bypassed), _build_src must NOT write it as
        a second pass-through entry in generation_config.

        The adapter's pass-through loop explicitly excludes ``max_output_tokens``
        (alongside ``max_tokens``, ``temperature``, and ``model``).  This test
        asserts the exclusion is effective: only ONE ``max_output_tokens`` key
        appears in config, carrying the value from the canonical ``max_tokens``
        rename path, not the raw alias.

        Counter-factual: removing ``max_output_tokens`` from the exclusion set
        in the pass-through loop would cause it to appear twice in the dict
        assignment — the second write would silently overwrite the first,
        carrying the wrong (raw alias) value; this test would detect that because
        the resolved max_tokens value (512) differs from the injected raw alias
        value (9999), so the final config value would be 9999 instead of 512.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-alias-guard",
            messages=[{"role": "user", "content": "check alias exclusion"}],
        )
        # Simulate a resolved dict where both max_tokens (canonical) and
        # max_output_tokens (raw alias) are present.  The resolver would never
        # produce this — it collapses aliases.  This test drives _build_src
        # directly to prove the adapter-level exclusion guard holds.
        resolved_params = [
            {
                "model": "gemini-2.0-flash",
                "max_tokens": 512,
                "max_output_tokens": 9999,  # raw alias — must be excluded from passthrough
            }
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        src = self._extract_src(client_instance)
        config = src[0]["config"]

        # The rename path must have produced max_output_tokens = 512 (from max_tokens).
        assert (
            "max_output_tokens" in config
        ), "max_tokens must be renamed to max_output_tokens in Gemini src config"
        assert config["max_output_tokens"] == 512, (
            "max_output_tokens must carry the resolved max_tokens value (512), "
            "not the raw alias value (9999) — proves the pass-through loop "
            "excludes max_output_tokens and cannot overwrite the renamed value"
        )
        # max_tokens (unrenamed) must not appear
        assert (
            "max_tokens" not in config
        ), "raw max_tokens must not appear in Gemini src config after rename"
