"""Every admitted attempt has one guarded finalization and completion owner."""

import asyncio
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMServiceError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import priced_service
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)


def inject_accounting_fault(monkeypatch, service, fault):
    failure = Mock(side_effect=RuntimeError("private accounting timeout"))
    if fault == "extraction":
        monkeypatch.setattr(
            "agentmap.services.llm.usage_presence.provider_usage_presence", failure
        )
    elif fault == "rates":
        rates = service._cost_calculator.get_rates
        read_count = 0

        def fail_after_admission(provider, model):
            nonlocal read_count
            read_count += 1
            if read_count > 1:
                return failure()
            return rates(provider, model)

        monkeypatch.setattr(service._cost_calculator, "get_rates", fail_after_admission)
    elif fault == "validation":
        monkeypatch.setattr(
            "agentmap.services.llm.governed_accounting.capture_measurements", failure
        )
    elif fault == "pricing":
        monkeypatch.setattr(service._cost_calculator, "calculate", failure)
    elif fault == "request_id":
        monkeypatch.setattr(service, "_extract_provider_request_id", failure)
    else:
        monkeypatch.setattr(
            "agentmap.services.llm_service.normalize_response_content", failure
        )
    return rates if fault == "rates" else None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize(
    "fault",
    ["extraction", "validation", "rates", "pricing", "request_id", "normalization"],
)
async def test_exceptional_accounting_paths_complete_once_with_available_evidence__b102(
    monkeypatch, provider, model, fault
):
    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("0.20")
    original_rates = inject_accounting_fault(monkeypatch, service, fault)
    try:
        with pytest.raises((LLMServiceError, AccountingRefusal, RuntimeError)):
            await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert row is not None, "accounting/recovery failure bypassed completion"
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if fault not in {"extraction", "validation"}:
            assert row.usage.input_tokens == row.usage.output_tokens == 10
        if fault in {"request_id", "normalization"}:
            assert row.cost_usd is not None
        else:
            assert row.cost_usd is None
        if original_rates is not None:
            monkeypatch.setattr(service._cost_calculator, "get_rates", original_rates)
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_recovery_failure_after_real_sdk_parse_failure_still_completes__b102(
    monkeypatch, provider, model
):
    body = b"{invalid json"
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    monkeypatch.setattr(
        "agentmap.services.llm.governed_accounting.capture_measurements",
        Mock(side_effect=RuntimeError("recovery secret")),
    )
    ledger = Ledger("1")
    try:
        with pytest.raises((LLMServiceError, AccountingRefusal)):
            await invoke(service, provider, model, ledger)
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert ledger.rows["1"].response_evidence.body == body
        assert ledger.rows["1"].cost_usd is None
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
async def test_usage_capture_failure_retains_independent_request_id__b102(monkeypatch):
    body = body_for("anthropic")
    calls = setup_transport(monkeypatch, body)
    service = priced_service("anthropic", "claude-sonnet-4-5", "input_tokens")
    ledger = Ledger("1")
    monkeypatch.setattr(
        "agentmap.services.llm.governed_accounting.capture_measurements",
        Mock(side_effect=RuntimeError("private measurement failure")),
    )
    try:
        with pytest.raises((LLMServiceError, AccountingRefusal)):
            await invoke(service, "anthropic", "claude-sonnet-4-5", ledger)
        outcome = ledger.rows["1"]
        assert outcome.provider_request_id == "msg-offline"
        assert outcome.response_evidence.body == body
        assert outcome.cost_usd is None
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        with pytest.raises(AccountingRefusal):
            await invoke(service, "anthropic", "claude-sonnet-4-5", ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("stage", ["admission", "completion"])
async def test_host_failure_cannot_retry_fallback_or_complete_twice__b102(
    monkeypatch, provider, model, stage
):
    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger, completions = Ledger("1"), []
    failure = RuntimeError("private host timeout")

    async def refuse_admission(description):
        raise failure

    async def refuse_completion(attempt_id, outcome):
        completions.append((attempt_id, outcome))
        raise failure

    setattr(
        ledger,
        "before_attempt" if stage == "admission" else "after_attempt",
        refuse_admission if stage == "admission" else refuse_completion,
    )
    try:
        with pytest.raises(RuntimeError) as caught:
            await invoke(service, provider, model, ledger)
        assert caught.value is failure
        assert len(calls) == (stage == "completion")
        assert len(completions) == (stage == "completion")
        if stage == "completion":
            assert completions[0][1].response_evidence.body == body
            assert completions[0][1].usage.input_tokens == 10
            assert ledger.rows == {"1": None}
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
            assert len(calls) == len(completions) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_repeated_cancel_during_completion_preserves_pending_identity__b102(
    monkeypatch, provider, model
):
    from agentmap.services.llm import response_observer

    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger, completions = Ledger("1"), []
    observed, completing = asyncio.Event(), asyncio.Event()
    original = response_observer.observe_async_response

    async def wait_after_body(response):
        await original(response)
        observed.set()
        await asyncio.wait_for(asyncio.Event().wait(), timeout=10)

    async def wait_in_completion(attempt_id, outcome):
        completions.append((attempt_id, outcome))
        completing.set()
        await asyncio.wait_for(asyncio.Event().wait(), timeout=10)

    monkeypatch.setattr(response_observer, "observe_async_response", wait_after_body)
    ledger.after_attempt = wait_in_completion
    try:
        task = asyncio.create_task(invoke(service, provider, model, ledger))
        await asyncio.wait_for(observed.wait(), 10)
        task.cancel()
        await asyncio.wait_for(completing.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ledger.rows == {"1": None}
        assert completions[0][1].response_evidence.body == body
        assert completions[0][1].usage.input_tokens == 10
        assert completions[0][1].classification == "cancelled"
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == len(completions) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("partial", [False, True])
async def test_absent_or_partial_body_completes_unknown_before_redispatch__b102(
    monkeypatch, provider, model, partial
):
    import httpx

    from agentmap.exceptions import ResponseCaptureFailure

    calls = setup_transport(monkeypatch, b"")

    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial entity"
            raise httpx.ReadError("read secret")

    async def send(transport, request):
        calls.append(request)
        if partial:
            return httpx.Response(200, stream=BrokenStream())
        raise httpx.ConnectError("connection secret", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    service, ledger = priced_service(provider, model, "input_tokens"), Ledger("1")
    try:
        with pytest.raises(
            (LLMServiceError, AccountingRefusal, ResponseCaptureFailure)
        ):
            await invoke(service, provider, model, ledger)
        outcome = ledger.rows["1"]
        assert outcome.cost_usd is None
        assert outcome.response_evidence.status == (
            "partial" if partial else "unavailable"
        )
        assert outcome.response_evidence.body == (
            b"partial entity" if partial else None
        )
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
