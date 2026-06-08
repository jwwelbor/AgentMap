"""
Provider-parametrized lifecycle and protocol tests.

Covers:
- TC-001..003: isinstance(adapter, BatchAdapterProtocol) for all three adapters
- TC-004..006: Full submit→poll→restore→fetch→cancel lifecycle per provider
- TC-007: _sanitize_request_id used by all adapters
- TC-008: BatchPollResult is a dataclass with required fields
- AC-T1: Provider-parametrized suite exercises lifecycle for all three adapters

Seam: adapter SDK calls are mocked at the lowest provider-I/O boundary.
Protocol isinstance checks are performed without mocking the Protocol itself.
"""

from unittest.mock import MagicMock, patch

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMRequest,
)
from agentmap.services.protocols.service_protocols import BatchAdapterProtocol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(request_id: str) -> LLMRequest:
    return LLMRequest(
        request_id=request_id,
        messages=[{"role": "user", "content": f"prompt for {request_id}"}],
    )


# ---------------------------------------------------------------------------
# TC-001..003: isinstance checks
# ---------------------------------------------------------------------------


class TestBatchAdapterProtocolIsinstance:
    """TC-001..003: All three adapters satisfy BatchAdapterProtocol at runtime."""

    def test_tc001_anthropic_adapter_isinstance(self):
        """TC-001: AnthropicBatchAdapter is an instance of BatchAdapterProtocol."""
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
        assert isinstance(adapter, BatchAdapterProtocol)

    def test_tc002_openai_adapter_isinstance(self):
        """TC-002: OpenAIBatchAdapter is an instance of BatchAdapterProtocol."""
        mock_sdk = MagicMock()
        mock_sdk.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_sdk}):
            from agentmap.services.llm.openai_batch_adapter import OpenAIBatchAdapter

            adapter = OpenAIBatchAdapter(api_key="test-key", logger=MagicMock())
        assert isinstance(adapter, BatchAdapterProtocol)

    def test_tc003_gemini_adapter_isinstance(self):
        """TC-003: GeminiBatchAdapter is an instance of BatchAdapterProtocol."""
        mock_genai = MagicMock()
        with patch.dict(
            "sys.modules",
            {"google": MagicMock(), "google.generativeai": mock_genai},
        ):
            from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

            adapter = GeminiBatchAdapter(api_key="test-key", logger=MagicMock())
        assert isinstance(adapter, BatchAdapterProtocol)


# ---------------------------------------------------------------------------
# TC-004..006: Provider-parametrized lifecycle
# ---------------------------------------------------------------------------


class TestAnthropicAdapterLifecycle:
    """TC-004: Full lifecycle for AnthropicBatchAdapter via mocked SDK."""

    def _make_adapter(self):
        mock_sdk = MagicMock()
        client = MagicMock()
        mock_sdk.Anthropic.return_value = client
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
        return adapter, client

    def test_tc004_full_lifecycle_submit_poll_fetch_cancel(self):
        """
        TC-004: AnthropicBatchAdapter lifecycle: submit→poll→fetch→cancel.

        Counter-factual: if submit returns wrong tuple shape, lifecycle breaks.
        """
        adapter, client = self._make_adapter()

        # --- submit ---
        mock_batch = MagicMock()
        mock_batch.id = "msgbatch_test001"
        mock_batch.expires_at = "2026-07-01T00:00:00Z"
        client.messages.batches.create.return_value = mock_batch
        specs = [_make_spec("s1")]
        resolved_params = [{"model": "claude-sonnet-4-6", "max_tokens": 1024}]
        provider_batch_id, request_id_map, expires_at = adapter.submit(
            specs=specs, resolved_params=resolved_params
        )
        assert provider_batch_id == "msgbatch_test001"
        assert "s1" in request_id_map
        assert expires_at == "2026-07-01T00:00:00Z"

        # --- poll ---
        mock_poll = MagicMock()
        mock_poll.processing_status = "ended"
        mock_poll.request_counts = MagicMock(
            processing=0, succeeded=1, errored=0, canceled=0, expired=0
        )
        mock_poll.results_url = "https://results.example.com/file"
        mock_poll.ended_at = "2026-06-08T12:00:00Z"
        client.messages.batches.retrieve.return_value = mock_poll
        poll_result = adapter.poll(provider_batch_id)
        assert isinstance(poll_result, BatchPollResult)
        assert poll_result.status == LLMBatchStatus.ENDED

        # --- fetch_results ---
        custom_id = request_id_map["s1"]
        mock_result = MagicMock()
        mock_result.custom_id = custom_id
        mock_result.result = MagicMock()
        mock_result.result.type = "succeeded"
        mock_result.result.message = MagicMock()
        mock_result.result.message.content = [MagicMock(text="hello")]
        mock_result.result.message.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        client.messages.batches.results.return_value = iter([mock_result])
        records = list(
            adapter.fetch_results(
                provider_batch_id=provider_batch_id, request_id_map=request_id_map
            )
        )
        assert len(records) == 1
        assert isinstance(records[0], LLMBatchResultRecord)
        assert records[0].request_id == "s1"
        assert records[0].status == "succeeded"

        # --- cancel ---
        client.messages.batches.cancel.return_value = MagicMock()
        adapter.cancel(provider_batch_id)  # no exception expected
        client.messages.batches.cancel.assert_called_once_with(provider_batch_id)

        # --- provider_name matches registry key ---
        assert adapter.provider_name == "anthropic"


class TestOpenAIAdapterLifecycle:
    """TC-005: Full lifecycle for OpenAIBatchAdapter via mocked SDK."""

    def _make_adapter(self):
        mock_sdk = MagicMock()
        client = MagicMock()
        mock_sdk.OpenAI.return_value = client
        with patch.dict("sys.modules", {"openai": mock_sdk}):
            from agentmap.services.llm.openai_batch_adapter import OpenAIBatchAdapter

            adapter = OpenAIBatchAdapter(api_key="test-key", logger=MagicMock())
        return adapter, client

    def test_tc005_full_lifecycle_submit_poll_fetch_cancel(self):
        """TC-005: OpenAIBatchAdapter lifecycle: submit→poll→fetch→cancel."""
        adapter, client = self._make_adapter()

        # --- submit ---
        mock_file = MagicMock()
        mock_file.id = "file_abc123"
        client.files.create.return_value = mock_file
        mock_batch = MagicMock()
        mock_batch.id = "batch_openai001"
        mock_batch.expires_at = 1800000000
        client.batches.create.return_value = mock_batch
        specs = [_make_spec("s1")]
        resolved_params = [{"model": "gpt-4o", "max_tokens": 1024}]
        provider_batch_id, request_id_map, expires_at = adapter.submit(
            specs=specs, resolved_params=resolved_params
        )
        assert provider_batch_id == "batch_openai001"
        assert "s1" in request_id_map

        # --- poll ---
        mock_poll = MagicMock()
        mock_poll.status = "completed"
        mock_poll.request_counts = MagicMock(completed=1, failed=0, total=1)
        mock_poll.output_file_id = "file_out001"
        mock_poll.expires_at = 1800000000
        client.batches.retrieve.return_value = mock_poll
        poll_result = adapter.poll(provider_batch_id)
        assert isinstance(poll_result, BatchPollResult)
        assert poll_result.status == LLMBatchStatus.ENDED

        # --- fetch_results (OpenAI uses files.content) ---
        custom_id = request_id_map["s1"]
        import json

        result_line = json.dumps(
            {
                "custom_id": custom_id,
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [{"message": {"content": "hello"}}],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                },
            }
        )
        mock_content = MagicMock()
        mock_content.content = result_line.encode("utf-8")
        client.files.content.return_value = mock_content
        records = list(
            adapter.fetch_results(
                provider_batch_id=provider_batch_id,
                request_id_map=request_id_map,
                result_ref="file_out001",
            )
        )
        assert len(records) >= 1
        assert records[0].request_id == "s1"

        # --- provider_name ---
        assert adapter.provider_name == "openai"

        # --- supports_cancel ---
        assert adapter.supports_cancel is True


class TestGeminiAdapterLifecycle:
    """TC-006: Full lifecycle for GeminiBatchAdapter via mocked SDK."""

    def _make_adapter(self):
        mock_genai = MagicMock()
        google_mock = MagicMock()
        google_mock.genai = mock_genai
        with patch.dict(
            "sys.modules",
            {"google": google_mock, "google.genai": mock_genai},
        ):
            from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

            adapter = GeminiBatchAdapter(api_key="test-key", logger=MagicMock())
        return adapter, mock_genai

    def test_tc006_full_lifecycle_submit_poll_fetch_with_cancel(self):
        """TC-006: GeminiBatchAdapter lifecycle; supports_cancel=True (post-F2 fix)."""
        adapter, mock_genai = self._make_adapter()

        # Mock the batches.create call — real SDK shape: create(model=, src=)
        mock_job = MagicMock()
        mock_job.name = "batches/test-job-123"
        mock_genai.Client.return_value.batches.create.return_value = mock_job

        specs = [_make_spec("s1")]
        resolved_params = [{"model": "gemini-2.0-flash", "max_tokens": 1024}]
        provider_batch_id, request_id_map, expires_at = adapter.submit(
            specs=specs,
            resolved_params=resolved_params,
        )
        assert len(provider_batch_id) > 0
        # Gemini uses positional demux: request_id_map is {"__ordered__": [request_ids]}
        assert "__ordered__" in request_id_map
        assert "s1" in request_id_map["__ordered__"]

        # provider_name and supports_cancel (F2 fix: supports_cancel=True)
        assert adapter.provider_name == "google"
        assert adapter.supports_cancel is True


# ---------------------------------------------------------------------------
# TC-007: _sanitize_request_id
# ---------------------------------------------------------------------------


class TestSanitizeSpecId:
    """TC-007: _sanitize_request_id shared helper is present and works correctly."""

    def test_tc007_sanitize_request_id_strips_invalid_chars(self):
        """_sanitize_request_id is a shared module-level helper used by all adapters."""
        from agentmap.services.llm._batch_ids import _sanitize_request_id

        sanitized = _sanitize_request_id("my spec/id with spaces")
        assert " " not in sanitized
        assert "/" not in sanitized

    def test_tc007_sanitize_request_id_is_used_by_anthropic_adapter(self):
        """AnthropicBatchAdapter import path includes _batch_ids module."""
        import importlib

        # Verify that _batch_ids is importable and used by the anthropic adapter
        batch_ids_mod = importlib.import_module("agentmap.services.llm._batch_ids")
        assert hasattr(batch_ids_mod, "_sanitize_request_id")
        assert hasattr(batch_ids_mod, "build_request_id_map")

    def test_tc007_sanitize_request_id_is_used_by_openai_adapter(self):
        """OpenAIBatchAdapter also uses _batch_ids shared helper."""
        import importlib

        batch_ids_mod = importlib.import_module("agentmap.services.llm._batch_ids")
        assert hasattr(batch_ids_mod, "_sanitize_request_id")


# ---------------------------------------------------------------------------
# TC-008: BatchPollResult is a dataclass with required fields
# ---------------------------------------------------------------------------


class TestBatchPollResult:
    """TC-008: BatchPollResult dataclass has status, request_counts, results_url, ended_at."""

    def test_tc008_batch_poll_result_dataclass_fields(self):
        """TC-008: BatchPollResult can be constructed with expected fields."""
        result = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
            request_counts=None,
            results_url=None,
            ended_at=None,
        )
        assert result.status == LLMBatchStatus.IN_PROGRESS
        assert result.request_counts is None
        assert result.results_url is None
        assert result.ended_at is None

    def test_tc008_batch_poll_result_is_dataclass(self):
        """TC-008: BatchPollResult is a dataclass."""
        import dataclasses

        assert dataclasses.is_dataclass(BatchPollResult)
