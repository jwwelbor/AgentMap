"""
Integration test suite for E05-F04 universal batch interface.

Exercises multiple components together:
- TC-009..014: Registry dispatch (LLMService._get_adapter routes by provider key)
- TC-037..040: Async surfaces confirm asyncio.to_thread is invoked
- TC-056..060: F03 handle back-compat (from_dict without result_ref key)
- TC-094: No provider guard literals in batch methods of llm_service.py

Components under test:
  LLMService → _batch_adapters registry → {Anthropic,OpenAI,Gemini}BatchAdapter
  LLMBatchHandle.from_dict (back-compat deserialization)

Seam: provider SDK adapter methods are mocked; LLMService public API is the entrypoint.
Forbidden mocks: do not mock LLMService._get_adapter (must exercise real registry lookup).
"""

import asyncio
import re
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchHandle,
    LLMBatchStatus,
    LLMBatchSubmitRequest,
    LLMRequest,
)
from agentmap.services.llm_batch_errors import LLMBatchUnsupportedProviderError
from agentmap.services.llm_batch_repository import BatchHandleRepository
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(request_id: str) -> LLMRequest:
    return LLMRequest(
        request_id=request_id,
        messages=[{"role": "user", "content": f"prompt for {request_id}"}],
    )


def _make_batch_request(
    provider: str = "anthropic",
    specs=None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> LLMBatchSubmitRequest:
    if specs is None:
        specs = [_make_spec("s1")]
    return LLMBatchSubmitRequest(
        provider=provider,
        model=model,
        requests=specs,
        max_tokens=max_tokens,
    )


def _make_handle(
    provider: str = "anthropic",
    status: LLMBatchStatus = LLMBatchStatus.IN_PROGRESS,
    **kwargs,
) -> LLMBatchHandle:
    defaults = dict(
        agentmap_batch_id="amatch_" + "a1b2c3d4" * 4,
        provider_batch_id="batch_abc123",
        status=status,
        provider=provider,
        model="test-model",
        request_id_map={"s1": "s1"},
        results_url=None,
        result_ref=None,
        expires_at="2026-07-01T00:00:00Z",
        request_counts=None,
    )
    defaults.update(kwargs)
    return LLMBatchHandle(**defaults)


def _make_service(batch_dir: str = None) -> tuple:
    """Construct LLMService with three mocked adapters in the registry."""
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
        "model": f"{provider}-default",
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

    # Build three named mock adapters
    anthropic_adapter = MagicMock()
    anthropic_adapter.provider_name = "anthropic"
    anthropic_adapter.supports_cancel = True

    openai_adapter = MagicMock()
    openai_adapter.provider_name = "openai"
    openai_adapter.supports_cancel = True

    google_adapter = MagicMock()
    google_adapter.provider_name = "google"
    google_adapter.supports_cancel = False

    service._batch_adapters = {
        "anthropic": anthropic_adapter,
        "openai": openai_adapter,
        "google": google_adapter,
    }

    if batch_dir is not None:
        repo = BatchHandleRepository(batch_dir=batch_dir)
    else:
        repo = MagicMock()
    service._batch_repo = repo

    return (
        service,
        {
            "anthropic": anthropic_adapter,
            "openai": openai_adapter,
            "google": google_adapter,
        },
        repo,
    )


# ---------------------------------------------------------------------------
# TC-009..014: Registry dispatch
# ---------------------------------------------------------------------------


class TestRegistryDispatch:
    """
    TC-009..014: LLMService._get_adapter routes by request.provider and handle.provider.
    Real registry lookup — _get_adapter is NOT mocked.
    """

    def test_tc009_submit_routes_to_openai_adapter(self, tmp_path):
        """TC-009: submit_batch with provider='openai' calls OpenAI adapter, not Anthropic."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["openai"].submit.return_value = (
            "batch_openai001",
            {"s1": "openai_req_s1"},
            "2026-07-01T00:00:00Z",
        )
        request = _make_batch_request(provider="openai", model="gpt-4o")
        service.submit_batch(request)

        adapters["openai"].submit.assert_called_once()
        adapters["anthropic"].submit.assert_not_called()
        adapters["google"].submit.assert_not_called()

    def test_tc010_submit_routes_to_google_adapter(self, tmp_path):
        """TC-010: submit_batch with provider='google' calls Google adapter."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["google"].submit.return_value = (
            "amatch_google001",
            {"s1": "google_req_s1"},
            None,
        )
        request = _make_batch_request(provider="google", model="gemini-1.5-flash")
        service.submit_batch(request)

        adapters["google"].submit.assert_called_once()
        adapters["anthropic"].submit.assert_not_called()
        adapters["openai"].submit.assert_not_called()

    def test_tc011_submit_routes_to_anthropic_adapter(self, tmp_path):
        """TC-011: submit_batch with provider='anthropic' calls Anthropic adapter."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_ant001",
            {"s1": "ant_req_s1"},
            "2026-07-01T00:00:00Z",
        )
        request = _make_batch_request(provider="anthropic")
        service.submit_batch(request)

        adapters["anthropic"].submit.assert_called_once()
        adapters["openai"].submit.assert_not_called()
        adapters["google"].submit.assert_not_called()

    def test_tc012_poll_routes_by_handle_provider(self, tmp_path):
        """TC-012: poll_batch routes by handle.provider, not by a hardcoded string."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["openai"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
        )
        handle = _make_handle(provider="openai")
        service.poll_batch(handle)

        adapters["openai"].poll.assert_called_once()
        adapters["anthropic"].poll.assert_not_called()

    def test_tc013_unregistered_provider_raises_correct_error(self, tmp_path):
        """
        TC-013: Submitting with an unregistered provider raises
        LLMBatchUnsupportedProviderError with a message naming registered providers.

        Counter-factual: if dispatch is hardcoded to anthropic, this would call
        anthropic adapter instead of raising.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        request = _make_batch_request(provider="mistral")
        with pytest.raises(LLMBatchUnsupportedProviderError) as exc_info:
            service.submit_batch(request)
        msg = str(exc_info.value)
        assert "mistral" in msg.lower() or "mistral" in msg

    def test_tc014_unregistered_provider_error_lists_registered(self, tmp_path):
        """TC-014: Error message from unregistered provider names what IS registered."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        service._batch_adapters = {"anthropic": adapters["anthropic"]}
        request = _make_batch_request(provider="openai")
        with pytest.raises(LLMBatchUnsupportedProviderError) as exc_info:
            service.submit_batch(request)
        msg = str(exc_info.value)
        # Error must name the registered providers so caller can discover them
        assert "anthropic" in msg


# ---------------------------------------------------------------------------
# TC-037..040: Async surfaces confirm asyncio.to_thread
# ---------------------------------------------------------------------------


class TestAsyncSurfaces:
    """
    TC-037..040: Async methods delegate to asyncio.to_thread.

    Entrypoint: public async methods (asubmit_batch, apoll_batch, etc.)
    Lowest allowed mock seam: asyncio.to_thread (spy to verify it is called)
    Forbidden mocks: do not replace asyncio.to_thread with a direct sync call
    Counter-factual: if async method calls sync on loop thread without to_thread,
    the spy records zero calls and the assertion fails.
    """

    @pytest.fixture
    def service_with_adapters(self, tmp_path):
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["anthropic"].submit.return_value = (
            "msgbatch_async001",
            {"s1": "ant_req_s1"},
            "2026-07-01T00:00:00Z",
        )
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
        )
        adapters["anthropic"].cancel.return_value = None
        adapters["anthropic"].fetch_results.return_value = []
        return service, adapters

    @pytest.mark.asyncio
    async def test_tc038_apoll_batch_uses_to_thread(self, service_with_adapters):
        """
        TC-038: apoll_batch confirms asyncio.to_thread is invoked.

        Counter-factual: apoll_batch calls adapter.poll() directly on event loop
        thread → to_thread spy records zero calls → assertion fails.
        """
        service, adapters = service_with_adapters
        handle = _make_handle(provider="anthropic")
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
        )

        real_to_thread = asyncio.to_thread
        to_thread_calls = []

        async def spy_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return await real_to_thread(func, *args, **kwargs)

        with patch("asyncio.to_thread", side_effect=spy_to_thread):
            await service.apoll_batch(handle)

        assert len(to_thread_calls) >= 1, (
            "apoll_batch must delegate via asyncio.to_thread; "
            "zero calls recorded — sync call on event loop detected"
        )

    @pytest.mark.asyncio
    async def test_tc039_acancel_batch_uses_to_thread(self, service_with_adapters):
        """TC-039: acancel_batch routes through asyncio.to_thread."""
        service, adapters = service_with_adapters
        handle = _make_handle(provider="anthropic", status=LLMBatchStatus.IN_PROGRESS)

        real_to_thread = asyncio.to_thread
        to_thread_calls = []

        async def spy_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return await real_to_thread(func, *args, **kwargs)

        with patch("asyncio.to_thread", side_effect=spy_to_thread):
            await service.acancel_batch(handle)

        assert len(to_thread_calls) >= 1

    @pytest.mark.asyncio
    async def test_tc040_afetch_batch_results_uses_to_thread(
        self, service_with_adapters
    ):
        """TC-040: afetch_batch_results routes through asyncio.to_thread."""
        service, adapters = service_with_adapters
        handle = _make_handle(
            provider="anthropic",
            status=LLMBatchStatus.ENDED,
            results_url="https://api.anthropic.com/v1/messages/batches/batch_abc123/results",
        )

        real_to_thread = asyncio.to_thread
        to_thread_calls = []

        async def spy_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return await real_to_thread(func, *args, **kwargs)

        with patch("asyncio.to_thread", side_effect=spy_to_thread):
            await service.afetch_batch_results(handle)

        assert len(to_thread_calls) >= 1

    @pytest.mark.asyncio
    async def test_tc037_asubmit_batch_uses_to_thread(self, service_with_adapters):
        """TC-037: asubmit_batch routes through asyncio.to_thread."""
        service, adapters = service_with_adapters
        request = _make_batch_request(provider="anthropic")

        real_to_thread = asyncio.to_thread
        to_thread_calls = []

        async def spy_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return await real_to_thread(func, *args, **kwargs)

        with patch("asyncio.to_thread", side_effect=spy_to_thread):
            await service.asubmit_batch(request)

        assert len(to_thread_calls) >= 1


# ---------------------------------------------------------------------------
# TC-056..060: F03 Anthropic handle back-compat
# ---------------------------------------------------------------------------


class TestF03HandleBackcompat:
    """
    TC-056..060: F03 persisted-handle dicts (no result_ref key) must load and
    remain pollable/fetchable through the refactored service.

    Counter-factual: from_dict raises KeyError on missing result_ref → TC-056 fails.
    """

    # F03-era handle dict — result_ref key was not present in F03 serialization
    F03_HANDLE_DICT = {
        "agentmap_batch_id": "amatch_" + "f03aaaa0" * 4,
        "provider_batch_id": "msgbatch_f03compat001",
        "status": "in_progress",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "request_id_map": {"s1": "ant_req_s1"},
        "results_url": "https://api.anthropic.com/v1/messages/batches/msgbatch_f03compat001/results",
        # result_ref intentionally absent — F03 did not persist this field
        "expires_at": "2026-07-01T00:00:00Z",
        "ended_at": None,
        "request_counts": None,
    }

    def test_tc056_f03_handle_loads_without_error(self):
        """
        TC-056: LLMBatchHandle.from_dict does not raise when result_ref is absent.

        Counter-factual: from_dict raises KeyError("result_ref") → fails.
        """
        handle = LLMBatchHandle.from_dict(self.F03_HANDLE_DICT)
        assert handle.agentmap_batch_id.startswith("amatch_")
        assert handle.result_ref is None  # absent key defaults to None

    def test_tc057_f03_handle_pollable_via_anthropic_adapter(self, tmp_path):
        """
        TC-057: F03 handle is pollable — Anthropic adapter is dispatched.

        The handle.provider == "anthropic" must route to the Anthropic adapter.
        Counter-factual: if dispatch is broken, wrong adapter called or KeyError raised.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["anthropic"].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.IN_PROGRESS,
        )

        handle = LLMBatchHandle.from_dict(self.F03_HANDLE_DICT)
        updated = service.poll_batch(handle)

        adapters["anthropic"].poll.assert_called_once_with(handle.provider_batch_id)
        assert updated is not None

    def test_tc058_f03_handle_fetch_uses_results_url_when_result_ref_none(
        self, tmp_path
    ):
        """
        TC-058: When result_ref is None, fetch_results is called without result_ref.

        Counter-factual: if adapter.fetch_results requires result_ref,
        it would raise TypeError — but the contract allows None.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters["anthropic"].fetch_results.return_value = []
        handle = LLMBatchHandle.from_dict(self.F03_HANDLE_DICT)
        # Manually mark ENDED to pass status gate; results_url already set in F03 dict
        handle = LLMBatchHandle(**{**handle.__dict__, "status": LLMBatchStatus.ENDED})
        service.fetch_batch_results(handle)
        adapters["anthropic"].fetch_results.assert_called_once()

    def test_tc059_canceled_is_terminal_status(self):
        """
        TC-059: LLMBatchStatus.CANCELED is treated as a terminal status by the service.

        Attempting to cancel a CANCELED handle raises because it is in _TERMINAL_STATUSES.
        """
        assert LLMBatchStatus.CANCELED in LLMService._TERMINAL_STATUSES

    def test_tc060_anthropic_adapter_fetch_accepts_result_ref_kwarg(self):
        """
        TC-060: AnthropicBatchAdapter.fetch_results signature accepts result_ref argument.

        The method must accept result_ref (it is ignored per contract) so that
        the service can pass it uniformly across all adapters.
        """
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())

        import inspect

        sig = inspect.signature(adapter.fetch_results)
        assert "result_ref" in sig.parameters, (
            "AnthropicBatchAdapter.fetch_results must accept result_ref kwarg "
            "for protocol compatibility"
        )


# ---------------------------------------------------------------------------
# TC-094: No provider guard literals in llm_service.py batch methods
# ---------------------------------------------------------------------------


class TestNoProviderGuardLiterals:
    """
    TC-094: llm_service.py batch methods must not contain provider=='anthropic'
    guard literals. Registry dispatch renders such guards incorrect.

    Counter-factual: if a guard exists, adding a new provider without modifying
    the guard causes silent dispatch failure.
    """

    def test_tc094_no_anthropic_guard_in_batch_methods(self):
        """
        TC-094: grep llm_service.py — no 'provider == "anthropic"' or
        'provider == \'anthropic\'' in batch lifecycle methods.

        The one permitted occurrence is in _extract_request_id (non-batch helper).
        """
        llm_service_path = (
            Path(__file__).parents[3]
            / "src"
            / "agentmap"
            / "services"
            / "llm_service.py"
        )
        assert (
            llm_service_path.exists()
        ), f"llm_service.py not found at {llm_service_path}"

        source = llm_service_path.read_text()

        # Find all batch method bodies: from submit_batch through batch_capabilities
        # We look for the specific pattern in batch methods only.
        # Strategy: find lines with provider guard literals, then verify they are
        # NOT in the batch method section.
        guard_pattern = re.compile(r'provider\s*==\s*["\']anthropic["\']')

        # Collect all line numbers with guard literals
        lines = source.splitlines()
        guard_lines = [
            (i + 1, line) for i, line in enumerate(lines) if guard_pattern.search(line)
        ]

        # The permitted occurrence is _extract_request_id — it is not a batch method.
        # Batch methods are: submit_batch, poll_batch, cancel_batch,
        # fetch_batch_results, asubmit_batch, apoll_batch, acancel_batch,
        # afetch_batch_results, wait_for_batch, submit_and_wait, batch_capabilities.
        # Any guard literal in those methods is a violation.
        batch_method_pattern = re.compile(
            r"def (submit_batch|poll_batch|cancel_batch|fetch_batch_results"
            r"|asubmit_batch|apoll_batch|acancel_batch|afetch_batch_results"
            r"|wait_for_batch|submit_and_wait|batch_capabilities|_get_adapter"
            r"|_validate_batch_submit_request)\b"
        )

        # Build a simple range map of batch method extents
        batch_ranges = []
        i = 0
        while i < len(lines):
            if batch_method_pattern.search(lines[i]):
                start = i
                # Find next def at same or higher indent level to mark end
                indent = len(lines[i]) - len(lines[i].lstrip())
                end = i + 1
                while end < len(lines):
                    stripped = lines[end].lstrip()
                    if stripped and not stripped.startswith("#"):
                        this_indent = len(lines[end]) - len(stripped)
                        if this_indent <= indent and stripped.startswith("def "):
                            break
                    end += 1
                batch_ranges.append((start + 1, end + 1))
            i += 1

        violations = []
        for lineno, line in guard_lines:
            for start, end in batch_ranges:
                if start <= lineno <= end:
                    violations.append((lineno, line.strip()))
                    break

        assert violations == [], (
            "Found provider guard literals in batch methods of llm_service.py:\n"
            + "\n".join(f"  Line {ln}: {txt}" for ln, txt in violations)
            + "\nRegistry dispatch must be used instead of provider-specific guards."
        )


# ---------------------------------------------------------------------------
# batch_capabilities is registry-driven
# ---------------------------------------------------------------------------


class TestBatchCapabilities:
    """Verify batch_capabilities returns adapter-driven data (not hardcoded)."""

    def test_capabilities_reads_adapter_supports_cancel(self, tmp_path):
        """batch_capabilities returns supports_cancel from the adapter, not hardcoded."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        # google adapter has supports_cancel=False
        caps = service.batch_capabilities("google")
        # F7 fix: protocol keys are supports_cancel / provider_name
        assert caps["supports_cancel"] is False
        assert caps["provider_name"] == "google"

    def test_capabilities_unregistered_raises(self, tmp_path):
        """batch_capabilities raises LLMBatchUnsupportedProviderError for unknown provider."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        with pytest.raises(LLMBatchUnsupportedProviderError):
            service.batch_capabilities("unknown_provider")


# ---------------------------------------------------------------------------
# Parametrized end-to-end lifecycle through LLMService (all three providers)
# ---------------------------------------------------------------------------


# Provider-specific configuration for the e2e lifecycle fixture.
# Each entry drives submit→poll→fetch_results through LLMService.
#
# result_ref_after_poll: the result_ref that the mock poll returns (None for
#   Anthropic and Gemini inline; "file-output-xyz" for OpenAI).
# results_url_after_poll: the results_url that the mock poll returns (set for
#   Anthropic; None for OpenAI and Gemini).
# expected_fetch_call: the kwargs assert on adapter.fetch_results.
#
# Critically: the OpenAI fixture does NOT inject a fabricated results_url into
# the handle.  The original bug was masked by tests that did exactly that —
# inject results_url=<something> for OpenAI so the guard passed.  Here we use
# the real OpenAI handle shape (results_url=None, result_ref=<file_id>) so that
# any reintroduction of the results_url guard would make the fetch assert fail.

_PROVIDER_LIFECYCLE_PARAMS = [
    pytest.param(
        "anthropic",
        # submit returns
        ("msgbatch_ant001", {"s1": "ant_req_s1"}, "2026-07-01T00:00:00Z"),
        # poll returns
        BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            results_url="https://api.anthropic.com/v1/messages/batches/msgbatch_ant001/results",
            result_ref=None,
            ended_at="2026-06-08T01:00:00Z",
        ),
        # expected fetch call kwargs
        {"result_ref": None},
        id="anthropic",
    ),
    pytest.param(
        "openai",
        # submit returns
        ("batch_openai_001", {"s1": "openai_req_s1"}, "2026-07-01T00:00:00Z"),
        # poll returns (result_ref = output_file_id; results_url intentionally None)
        BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            results_url=None,
            result_ref="file-output-xyz",
            ended_at="2026-06-08T01:00:00Z",
        ),
        # expected fetch call kwargs
        {"result_ref": "file-output-xyz"},
        id="openai",
    ),
    pytest.param(
        "google",
        # submit returns
        ("job_gemini_abc", {"s1": "gemini_req_s1"}, None),
        # poll returns (neither results_url nor result_ref for inline Gemini)
        BatchPollResult(
            status=LLMBatchStatus.ENDED,
            request_counts=None,
            results_url=None,
            result_ref=None,
            ended_at="2026-06-08T01:00:00Z",
        ),
        # expected fetch call kwargs
        {"result_ref": None},
        id="google",
    ),
]


class TestProviderParametrizedLifecycle:
    """
    Provider-parametrized full lifecycle through LLMService for all three providers.

    Entrypoint: LLMService.submit_batch → poll_batch → fetch_batch_results.
    Lowest allowed mock seam: provider SDK adapter methods (submit, poll, fetch_results).
    Forbidden mocks: LLMService._get_adapter, asyncio.to_thread.

    Counter-factual — this suite would FAIL against the three original blockers:
      Blocker 1 (poll drops result_ref): the openai case asserts
        ended_handle.result_ref == "file-output-xyz"; if poll_batch drops it the
        assertion fails immediately.
      Blocker 2 (fetch never passes result_ref): the openai assert_called_once_with
        includes result_ref="file-output-xyz"; without the kwarg the call-sig
        mismatch raises AssertionError.
      Blocker 3 (results_url guard applied to all): the openai fixture has
        results_url=None throughout; if the guard is present fetch_batch_results
        raises LLMServiceError before reaching the adapter and the test fails.

    The suite also verifies Gemini inline (neither locator) and Anthropic
    (results_url path) to confirm the guard replacement is provider-aware.
    """

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_submit_routes_correct_adapter(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """submit_batch calls exactly the matching provider adapter."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].submit.return_value = submit_rv
        model = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4o",
            "google": "gemini-2.0-flash",
        }[provider]
        request = _make_batch_request(provider=provider, model=model)

        service.submit_batch(request)

        adapters[provider].submit.assert_called_once()
        for other in ("anthropic", "openai", "google"):
            if other != provider:
                adapters[other].submit.assert_not_called()

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_poll_routes_correct_adapter_and_returns_handle(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """poll_batch dispatches to the matching adapter and returns an updated handle."""
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].poll.return_value = poll_rv
        handle = _make_handle(provider=provider)

        updated = service.poll_batch(handle)

        adapters[provider].poll.assert_called_once_with(handle.provider_batch_id)
        assert updated.status == poll_rv.status
        assert updated.provider == provider

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_poll_result_ref_survives_into_updated_handle(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """result_ref from poll must be carried into the updated LLMBatchHandle.

        Counter-factual for blocker 1: if poll_batch drops result_ref, the openai
        case asserts ended_handle.result_ref == "file-output-xyz" and FAILS.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].poll.return_value = poll_rv
        handle = _make_handle(provider=provider, result_ref=None)

        updated = service.poll_batch(handle)

        expected_result_ref = poll_rv.result_ref
        assert updated.result_ref == expected_result_ref, (
            f"[{provider}] poll_batch dropped result_ref: "
            f"expected {expected_result_ref!r}, got {updated.result_ref!r}"
        )

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_fetch_results_does_not_raise_for_provider_handle_shape(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """fetch_batch_results must not raise for the real handle shape of each provider.

        Counter-factual for blocker 3: the openai/google cases have results_url=None.
        If the results_url guard is present, LLMServiceError is raised and the test FAILS.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].fetch_results.return_value = []

        # Build ended handle with the real locator shape for this provider
        result_ref = poll_rv.result_ref
        results_url = poll_rv.results_url
        handle = _make_handle(
            provider=provider,
            status=LLMBatchStatus.ENDED,
            result_ref=result_ref,
            results_url=results_url,
        )

        # Must not raise for any provider
        results = service.fetch_batch_results(handle)
        assert results == []

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_fetch_results_passes_result_ref_to_adapter(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """fetch_batch_results must forward result_ref (from the handle) to the adapter.

        Counter-factual for blocker 2: if result_ref is not forwarded, the
        assert_called_once_with check fails for openai (expected result_ref=
        "file-output-xyz" but adapter received None or was called with 2 args).
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].fetch_results.return_value = []

        result_ref = poll_rv.result_ref
        results_url = poll_rv.results_url
        handle = _make_handle(
            provider=provider,
            status=LLMBatchStatus.ENDED,
            result_ref=result_ref,
            results_url=results_url,
        )

        service.fetch_batch_results(handle)

        adapters[provider].fetch_results.assert_called_once_with(
            handle.provider_batch_id,
            handle.request_id_map,
            **expected_fetch_kwargs,
        )

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        _PROVIDER_LIFECYCLE_PARAMS,
    )
    def test_full_lifecycle_submit_poll_fetch(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """Full submit→poll→fetch round-trip through LLMService for each provider.

        This is the primary end-to-end integration test.  It drives the real
        production call chain: submit_batch → handle persisted → poll_batch →
        updated handle (with result_ref carried through) → fetch_batch_results
        (with result_ref forwarded to adapter).

        Counter-factual summary:
          - Blocker 1: openai ended_handle.result_ref == "file-output-xyz" fails if dropped.
          - Blocker 2: assert_called_once_with(result_ref=...) fails if not forwarded.
          - Blocker 3: fetch raises LLMServiceError if results_url guard fires for openai/google.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        model = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4o",
            "google": "gemini-2.0-flash",
        }[provider]

        # --- submit ---
        adapters[provider].submit.return_value = submit_rv
        request = _make_batch_request(provider=provider, model=model)
        submitted_handle = service.submit_batch(request)

        assert submitted_handle.provider == provider
        # submit_batch returns a handle with SUBMITTED (or IN_PROGRESS) status
        assert submitted_handle.status in (
            LLMBatchStatus.SUBMITTED,
            LLMBatchStatus.IN_PROGRESS,
        )
        adapters[provider].submit.assert_called_once()

        # --- poll (transitions to ENDED, carries result_ref) ---
        adapters[provider].poll.return_value = poll_rv
        ended_handle = service.poll_batch(submitted_handle)

        assert ended_handle.status == LLMBatchStatus.ENDED
        assert (
            ended_handle.result_ref == poll_rv.result_ref
        ), f"[{provider}] poll_batch dropped result_ref"

        # --- fetch (result_ref must reach adapter; no results_url guard for openai/google) ---
        adapters[provider].fetch_results.return_value = []
        results = service.fetch_batch_results(ended_handle)

        assert results == []
        adapters[provider].fetch_results.assert_called_once_with(
            ended_handle.provider_batch_id,
            ended_handle.request_id_map,
            **expected_fetch_kwargs,
        )

    @pytest.mark.parametrize(
        "provider,submit_rv,poll_rv,expected_fetch_kwargs",
        [
            pytest.param(
                "anthropic",
                ("msgbatch_ant_cancel", {"s1": "ant_req_s1"}, "2026-07-01T00:00:00Z"),
                BatchPollResult(status=LLMBatchStatus.IN_PROGRESS),
                {},
                id="anthropic_cancel",
            ),
            pytest.param(
                "openai",
                (
                    "batch_openai_cancel",
                    {"s1": "openai_req_s1"},
                    "2026-07-01T00:00:00Z",
                ),
                BatchPollResult(status=LLMBatchStatus.IN_PROGRESS),
                {},
                id="openai_cancel",
            ),
        ],
    )
    def test_cancel_routes_to_correct_adapter(
        self, tmp_path, provider, submit_rv, poll_rv, expected_fetch_kwargs
    ):
        """cancel_batch dispatches to the matching adapter (Anthropic and OpenAI support cancel).

        Google adapter has supports_cancel=False so cancel_batch raises — tested
        separately below.
        """
        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        adapters[provider].cancel.return_value = None
        # cancel_batch calls poll_batch internally; provide a valid poll return value
        adapters[provider].poll.return_value = BatchPollResult(
            status=LLMBatchStatus.CANCELING,
        )

        handle = _make_handle(provider=provider, status=LLMBatchStatus.IN_PROGRESS)
        service.cancel_batch(handle)

        adapters[provider].cancel.assert_called_once()
        for other in ("anthropic", "openai", "google"):
            if other != provider:
                adapters[other].cancel.assert_not_called()

    def test_cancel_google_raises_not_supported(self, tmp_path):
        """cancel_batch on a google handle raises because google does not support cancel."""
        from agentmap.services.llm_batch_errors import LLMBatchCancelNotSupportedError

        service, adapters, repo = _make_service(batch_dir=str(tmp_path))
        handle = _make_handle(provider="google", status=LLMBatchStatus.IN_PROGRESS)

        with pytest.raises(LLMBatchCancelNotSupportedError):
            service.cancel_batch(handle)
