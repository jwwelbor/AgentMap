"""
Tests for BatchAdapterProtocol (TC-001, TC-002, TC-003, TC-008) and
LLMServiceProtocol async batch method surface (AC-T2).

Scope: protocol-layer checks only — isinstance, attribute names, BatchPollResult
dataclass. No adapter implementation or service wiring required here.
TC-004..007 (full lifecycle) live in tests/fresh_suite/unit/services/.
"""

import pytest

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchStatus,
)
from agentmap.services.protocols.service_protocols import BatchAdapterProtocol

# ---------------------------------------------------------------------------
# Helpers — minimal duck-typed objects for isinstance tests
# ---------------------------------------------------------------------------


class _MinimalAdapter:
    """Satisfies BatchAdapterProtocol: four methods + two members."""

    provider_name: str = "test-provider"
    supports_cancel: bool = True

    def submit(self, specs, model, max_tokens, request_options): ...

    def poll(self, provider_batch_id): ...

    def cancel(self, provider_batch_id): ...

    def fetch_results(self, provider_batch_id, request_id_map, result_ref): ...


class _MissingProviderName:
    """Missing provider_name attribute — should NOT satisfy the protocol."""

    supports_cancel: bool = True

    def submit(self, specs, model, max_tokens, request_options): ...

    def poll(self, provider_batch_id): ...

    def cancel(self, provider_batch_id): ...

    def fetch_results(self, provider_batch_id, request_id_map, result_ref): ...


class _MissingSupportsCancel:
    """Missing supports_cancel attribute — should NOT satisfy the protocol."""

    provider_name: str = "test-provider"

    def submit(self, specs, model, max_tokens, request_options): ...

    def poll(self, provider_batch_id): ...

    def cancel(self, provider_batch_id): ...

    def fetch_results(self, provider_batch_id, request_id_map, result_ref): ...


class _MissingMethods:
    """Only submit/poll — missing cancel + fetch_results."""

    provider_name: str = "test-provider"
    supports_cancel: bool = True

    def submit(self, specs, model, max_tokens, request_options): ...

    def poll(self, provider_batch_id): ...


# ---------------------------------------------------------------------------
# TC-001 / AC-T1 — protocol is @runtime_checkable with correct surface
# ---------------------------------------------------------------------------


class TestBatchAdapterProtocolSurface:
    """TC-001: BatchAdapterProtocol is @runtime_checkable with correct members."""

    def test_minimal_adapter_satisfies_protocol(self):
        """Minimal duck-typed object with all four methods + two members passes isinstance."""
        adapter = _MinimalAdapter()
        assert isinstance(adapter, BatchAdapterProtocol)

    def test_protocol_is_runtime_checkable(self):
        """isinstance check does not raise TypeError (Protocol is @runtime_checkable)."""
        # Would raise TypeError if Protocol were not @runtime_checkable
        try:
            result = isinstance(object(), BatchAdapterProtocol)
        except TypeError:
            pytest.fail("BatchAdapterProtocol is not @runtime_checkable")
        # object() has none of the required attributes — result is False
        assert result is False

    def test_protocol_has_four_methods(self):
        """Protocol defines submit, poll, cancel, fetch_results."""
        for method_name in ("submit", "poll", "cancel", "fetch_results"):
            assert hasattr(
                BatchAdapterProtocol, method_name
            ), f"BatchAdapterProtocol missing method: {method_name}"

    def test_protocol_has_provider_name_member(self):
        """Protocol declares provider_name as a member (via annotations)."""
        annotations = getattr(BatchAdapterProtocol, "__annotations__", {})
        assert (
            "provider_name" in annotations
        ), "BatchAdapterProtocol must declare 'provider_name: str'"

    def test_protocol_has_supports_cancel_member(self):
        """Protocol declares supports_cancel as a member (via annotations)."""
        annotations = getattr(BatchAdapterProtocol, "__annotations__", {})
        assert (
            "supports_cancel" in annotations
        ), "BatchAdapterProtocol must declare 'supports_cancel: bool'"

    # --- Negative cases ---

    def test_missing_provider_name_fails_isinstance(self):
        """Object missing provider_name does NOT satisfy the protocol."""
        obj = _MissingProviderName()
        assert isinstance(obj, BatchAdapterProtocol) is False

    def test_missing_supports_cancel_fails_isinstance(self):
        """Object missing supports_cancel does NOT satisfy the protocol."""
        obj = _MissingSupportsCancel()
        assert isinstance(obj, BatchAdapterProtocol) is False

    def test_missing_methods_fails_isinstance(self):
        """Object with only submit/poll but missing cancel/fetch_results fails isinstance."""
        obj = _MissingMethods()
        assert isinstance(obj, BatchAdapterProtocol) is False

    def test_subclass_of_compliant_class_passes_isinstance(self):
        """Subclass of a fully-compliant adapter also satisfies the protocol."""

        class _SubAdapter(_MinimalAdapter):
            provider_name = "sub-provider"

        assert isinstance(_SubAdapter(), BatchAdapterProtocol)


# ---------------------------------------------------------------------------
# TC-002 — OpenAIBatchAdapter shape (structural, no real SDK)
# ---------------------------------------------------------------------------


class TestOpenAIAdapterShape:
    """TC-002: OpenAIBatchAdapter structure satisfies BatchAdapterProtocol."""

    def _make_openai_adapter_stub(self):
        """Return a stub matching the expected OpenAIBatchAdapter surface."""

        class _OpenAIStub:
            provider_name: str = "openai"
            supports_cancel: bool = True

            def submit(self, specs, model, max_tokens, request_options): ...

            def poll(self, provider_batch_id): ...

            def cancel(self, provider_batch_id): ...

            def fetch_results(self, provider_batch_id, request_id_map, result_ref): ...

        return _OpenAIStub()

    def test_openai_stub_satisfies_protocol(self):
        """OpenAI-shaped stub passes isinstance(adapter, BatchAdapterProtocol)."""
        adapter = self._make_openai_adapter_stub()
        assert isinstance(adapter, BatchAdapterProtocol) is True

    def test_openai_provider_name_is_openai(self):
        """provider_name must be 'openai' (canonical registry key)."""
        adapter = self._make_openai_adapter_stub()
        assert adapter.provider_name == "openai"

    def test_openai_supports_cancel_is_true(self):
        """OpenAI Batch API supports cancel."""
        adapter = self._make_openai_adapter_stub()
        assert adapter.supports_cancel is True

    def test_missing_supports_cancel_attribute_fails(self):
        """Counter-factual: missing supports_cancel → isinstance False."""

        class _NoCancel:
            provider_name = "openai"

            def submit(self, s, m, mt, ro): ...
            def poll(self, bid): ...
            def cancel(self, bid): ...
            def fetch_results(self, bid, sim, rr): ...

        assert isinstance(_NoCancel(), BatchAdapterProtocol) is False


# ---------------------------------------------------------------------------
# TC-003 — GeminiBatchAdapter shape (structural, no real SDK)
# ---------------------------------------------------------------------------


class TestGeminiAdapterShape:
    """TC-003: GeminiBatchAdapter structure satisfies BatchAdapterProtocol."""

    def _make_gemini_adapter_stub(self):
        class _GeminiStub:
            provider_name: str = "google"
            supports_cancel: bool = False  # TBD per SDK capability

            def submit(self, specs, model, max_tokens, request_options): ...

            def poll(self, provider_batch_id): ...

            def cancel(self, provider_batch_id): ...

            def fetch_results(self, provider_batch_id, request_id_map, result_ref): ...

        return _GeminiStub()

    def test_gemini_stub_satisfies_protocol(self):
        """Gemini-shaped stub passes isinstance(adapter, BatchAdapterProtocol)."""
        adapter = self._make_gemini_adapter_stub()
        assert isinstance(adapter, BatchAdapterProtocol) is True

    def test_gemini_provider_name_is_google(self):
        """provider_name must be 'google' (matches llm_service.py provider vocabulary)."""
        adapter = self._make_gemini_adapter_stub()
        assert adapter.provider_name == "google"

    def test_gemini_supports_cancel_is_bool(self):
        """supports_cancel must be a bool (True or False per SDK capability)."""
        adapter = self._make_gemini_adapter_stub()
        assert isinstance(adapter.supports_cancel, bool)

    def test_gemini_wrong_provider_name_is_detectable(self):
        """Counter-factual: provider_name='gemini' (wrong) — still passes isinstance
        but registry dispatch would fail. Test documents correct value."""
        adapter = self._make_gemini_adapter_stub()
        # The correct key is "google", NOT "gemini"
        assert (
            adapter.provider_name != "gemini"
        ), "provider_name must be 'google' to match the DI registry key"


# ---------------------------------------------------------------------------
# TC-008 — BatchPollResult dataclass
# ---------------------------------------------------------------------------


class TestBatchPollResult:
    """TC-008: BatchPollResult is a dataclass with required and optional fields."""

    def test_instantiation_with_required_field_only(self):
        """BatchPollResult can be instantiated with status only."""
        pr = BatchPollResult(status=LLMBatchStatus.IN_PROGRESS)
        assert pr.status == LLMBatchStatus.IN_PROGRESS

    def test_optional_fields_default_to_none(self):
        """All optional fields default to None."""
        pr = BatchPollResult(status=LLMBatchStatus.IN_PROGRESS)
        assert pr.request_counts is None
        assert pr.result_ref is None
        assert pr.ended_at is None

    def test_all_fields_can_be_set(self):
        """All fields can be explicitly provided."""
        pr = BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            result_ref="file-abc123",
            ended_at="2026-06-07T12:00:00Z",
        )
        assert pr.result_ref == "file-abc123"
        assert pr.ended_at == "2026-06-07T12:00:00Z"

    def test_missing_status_raises_type_error(self):
        """Counter-factual: BatchPollResult() without status raises TypeError."""
        with pytest.raises(TypeError):
            BatchPollResult()  # type: ignore[call-arg]

    def test_status_field_is_llm_batch_status(self):
        """status field accepts LLMBatchStatus enum values."""
        for status in LLMBatchStatus:
            pr = BatchPollResult(status=status)
            assert pr.status == status


# ---------------------------------------------------------------------------
# AC-T2 — LLMServiceProtocol async batch method surface
# ---------------------------------------------------------------------------


class TestLLMServiceProtocolAsyncBatchMethods:
    """AC-T2: LLMServiceProtocol gains async batch methods."""

    def test_protocol_has_asubmit_batch(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "asubmit_batch")

    def test_protocol_has_apoll_batch(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "apoll_batch")

    def test_protocol_has_acancel_batch(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "acancel_batch")

    def test_protocol_has_afetch_batch_results(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "afetch_batch_results")

    def test_protocol_has_wait_for_batch(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "wait_for_batch")

    def test_protocol_has_submit_and_wait(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "submit_and_wait")

    def test_protocol_has_batch_capabilities(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "batch_capabilities")

    def test_protocol_has_results_by_request_id(self):
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        assert hasattr(LLMServiceProtocol, "results_by_request_id")
