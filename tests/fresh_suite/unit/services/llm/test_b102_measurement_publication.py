"""Validated measurements survive every downstream pricing fault."""

import asyncio
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import (
    changed_body,
    priced_service,
)
from tests.fresh_suite.unit.services.llm.test_b102_usage_failures import cache_body
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)


def pricing_fault(monkeypatch, service, kind):
    calculator = service._cost_calculator
    original_rates, original_calculate = calculator.get_rates, calculator.calculate
    read_count = 0

    class FaultyRates:
        def __getattribute__(self, name):
            raise RuntimeError("private rate inspection timeout")

    def get_rates(provider, model):
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return original_rates(provider, model)
        if kind == "rates":
            raise RuntimeError("private rate lookup timeout")
        return (
            FaultyRates() if kind == "inspection" else original_rates(provider, model)
        )

    monkeypatch.setattr(calculator, "get_rates", get_rates)
    if kind == "calculation":
        monkeypatch.setattr(
            calculator,
            "calculate",
            Mock(side_effect=RuntimeError("private cost timeout")),
        )

    def clear():
        monkeypatch.setattr(calculator, "get_rates", original_rates)
        monkeypatch.setattr(calculator, "calculate", original_calculate)

    return clear


def measured_body(provider, value):
    return (
        cache_body(provider, 5)
        if value == "cache"
        else changed_body(provider, "output_tokens", value)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("fault", ["rates", "inspection", "calculation"])
@pytest.mark.parametrize("value", [10, 0, "absent", -1, "cache"])
async def test_downstream_fault_keeps_published_measurements_and_unknown_total__b102(
    monkeypatch, provider, model, fault, value
):
    body = measured_body(provider, value)
    calls = setup_transport(monkeypatch, body)
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    clear = pricing_fault(monkeypatch, service, fault)
    expected_output = {0: 0, 10: 10, "cache": 10}.get(value)
    try:
        if value == -1 and fault == "inspection":
            assert (await invoke(service, provider, model, ledger)).cost is None
        else:
            with pytest.raises(LLMConfigurationError) as caught:
                await invoke(service, provider, model, ledger)
            assert "private" not in str(caught.value)
        row = ledger.rows["1"]
        assert row.usage.input_tokens == 10
        assert row.usage.output_tokens == expected_output
        if value == "cache":
            assert row.usage.cache_read_input_tokens == 5
        assert row.cost_usd is None
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        clear()
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_persistent_rate_fault_never_becomes_retryable_provider_timeout__b102(
    monkeypatch, provider, model
):
    calls = setup_transport(monkeypatch, body_for(provider))
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    clear = pricing_fault(monkeypatch, service, "rates")
    try:
        for _ in range(2):
            with pytest.raises(LLMConfigurationError):
                await invoke(service, provider, model, ledger)
        assert len(calls) == 1
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        clear()
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_pre_admission_rate_fault_has_no_call_or_completion__b102(
    monkeypatch, provider, model
):
    calls = setup_transport(monkeypatch, body_for(provider))
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    monkeypatch.setattr(
        service._cost_calculator,
        "get_rates",
        Mock(side_effect=RuntimeError("private rate timeout")),
    )
    try:
        with pytest.raises(LLMConfigurationError) as caught:
            await invoke(service, provider, model, ledger)
        assert "private" not in str(caught.value)
        assert calls == ledger.events == []
        assert ledger.rows == {}
    finally:
        await service._client_factory.shutdown()


def broken_content(provider):
    import json

    payload = json.loads(body_for(provider))
    if provider == "google":
        payload["candidates"] = [{"content": {"parts": 5}}]
    else:
        payload["choices" if provider == "openai" else "content"] = "bad"
    return json.dumps(payload).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("cancel", [False, True])
async def test_parse_or_cancel_with_rate_fault_keeps_observed_measurements__b102(
    monkeypatch, provider, model, cancel
):
    from agentmap.services.llm import response_observer

    body = body_for(provider) if cancel else broken_content(provider)
    calls = setup_transport(monkeypatch, body)
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    clear = pricing_fault(monkeypatch, service, "rates")
    observed = asyncio.Event()
    original = response_observer.observe_async_response

    async def wait_after_body(response):
        await original(response)
        observed.set()
        await asyncio.wait_for(asyncio.Event().wait(), timeout=10)

    try:
        if cancel:
            monkeypatch.setattr(
                response_observer, "observe_async_response", wait_after_body
            )
            task = asyncio.create_task(invoke(service, provider, model, ledger))
            await asyncio.wait_for(observed.wait(), 10)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(LLMConfigurationError):
                await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert row.usage.input_tokens == row.usage.output_tokens == 10
        assert row.cost_usd is None
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        clear()
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_fault_immediately_after_publication_finalizes_same_accumulator__b102(
    monkeypatch, provider, model
):
    body = changed_body(provider, "output_tokens", 0)
    calls = setup_transport(monkeypatch, body)
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")

    def fail_after_publication(*args, outcome, **kwargs):
        assert outcome.usage.input_tokens == 10
        assert outcome.usage.output_tokens == 0
        raise RuntimeError("private downstream timeout")

    monkeypatch.setattr(
        "agentmap.services.llm.governed_accounting.collect_evidence",
        fail_after_publication,
    )
    try:
        with pytest.raises(LLMConfigurationError):
            await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert row.usage.input_tokens == 10
        assert row.usage.output_tokens == 0
        assert row.cost_usd is None
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_pricing_and_completion_failure_never_reenter_recovery__b102(
    monkeypatch, provider, model
):
    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    calculator = Mock(side_effect=RuntimeError("private cost timeout"))
    monkeypatch.setattr(service._cost_calculator, "calculate", calculator)
    completions = []
    failure = RuntimeError("private completion timeout")

    async def fail_completion(attempt_id, outcome):
        completions.append((attempt_id, outcome))
        raise failure

    ledger.after_attempt = fail_completion
    try:
        with pytest.raises(RuntimeError) as caught:
            await invoke(service, provider, model, ledger)
        assert caught.value is failure
        assert ledger.rows == {"1": None}
        assert completions[0][1].usage.input_tokens == 10
        assert completions[0][1].cost_usd is None
        assert completions[0][1].response_evidence.body == body
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == len(completions) == calculator.call_count == 1
    finally:
        await service._client_factory.shutdown()
