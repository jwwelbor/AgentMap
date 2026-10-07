"""B102 lifecycle isolation, failure evidence, and fallback counterfactuals."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agentmap.exceptions import (
    LLMConfigurationError,
    LLMResolvedCallError,
    LLMServiceError,
)
from agentmap.models.llm_batch import LLMBatchSubmitRequest
from agentmap.models.llm_execution import LLMRequest
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
    observed_response,
    raw_response,
    service_with_client,
)


def fallback_service(client):
    features = Mock()
    features.is_provider_available.return_value = True
    routing = Mock()
    routing.fallback = {"default_provider": "anthropic"}
    routing.routing_matrix = {
        "openai": {"low": "test-model"},
        "anthropic": {"low": "other-model"},
    }
    routing.supports_prompt_caching.return_value = False
    svc = service_with_client(
        client, features_registry_service=features, routing_config_service=routing
    )
    svc._resilience_config["retry"]["max_attempts"] = 1
    svc._provider_utils.get_provider_config = Mock(
        side_effect=lambda provider: {
            "api_key": "offline",
            "model": "test-model",
            "max_tokens": 23,
        }
    )
    return svc


@pytest.mark.asyncio
@pytest.mark.parametrize("cap,expected_calls", [("0.20", 1), ("0.50", 2)])
async def test_fallback_rechecks_after_billed_normalization_error__b102(
    cap, expected_calls
):
    client = Mock()
    svc = fallback_service(client)
    ledger = Ledger(cap)
    client.ainvoke = AsyncMock(
        side_effect=lambda _: observed_response(
            raw_response(), ledger.descriptions[-1].resolved_provider
        )
    )
    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=[RuntimeError("connection timeout"), ("recovered", "text")],
    ):
        if expected_calls == 1:
            with pytest.raises(AccountingRefusal, match="cap reached"):
                await call(svc, ledger)
        else:
            assert (await call(svc, ledger)).text == "recovered"
    assert client.ainvoke.await_count == expected_calls
    assert ledger.rows["1"].cost_usd == Decimal("0.20")
    if expected_calls == 2:
        assert ledger.descriptions[1].attempt_kind == "fallback"
        assert ledger.descriptions[1].max_output_tokens == 23
        assert ledger.descriptions[1].resolved_provider == "anthropic"
        assert ledger.descriptions[1].resolved_model == "other-model"
        assert ledger.descriptions[1].retry_ordinal == 1
    assert all(
        c.kwargs == {"governed": True}
        for c in svc._client_factory.get_or_create_client.call_args_list
    )


@pytest.mark.asyncio
async def test_fallback_refusal_does_not_try_another_tier__b102():
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    svc = fallback_service(client)
    ledger = Ledger("1.00")
    refusal = RuntimeError("private host failure connection timeout")
    admitted = ledger.before_attempt

    async def refuse_fallback(description):
        if description.attempt_kind == "fallback":
            raise refusal
        return await admitted(description)

    ledger.before_attempt = refuse_fallback
    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=RuntimeError("connection timeout"),
    ):
        with pytest.raises(RuntimeError) as caught:
            await call(svc, ledger)
    assert caught.value is refusal
    assert client.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_pre_admission_rate_fault_refuses_primary_and_fallback__b102():
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    svc = fallback_service(client)
    ledger = Ledger("1.00")
    svc._cost_calculator.get_rates = Mock(
        side_effect=RuntimeError("private rate lookup timeout")
    )

    with pytest.raises(LLMConfigurationError) as caught:
        await call(svc, ledger)

    assert str(caught.value) == "governed attempt accounting unavailable"
    assert client.ainvoke.await_count == 0
    assert ledger.events == ledger.descriptions == []
    assert ledger.rows == {}
    assert svc._cost_calculator.get_rates.call_count == 1


@pytest.mark.asyncio
async def test_unavailable_raw_usage_ignores_normalized_defaults__b102():
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    svc = service_with_client(client)
    ledger = Ledger("1.00")

    result = await call(svc, ledger)

    assert result.usage is result.cost is None
    assert ledger.rows["1"].response_evidence.status == "unavailable"
    assert ledger.rows["1"].usage is ledger.rows["1"].cost_usd is None
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(svc, ledger)
    assert client.ainvoke.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_bucket", ["input_tokens", "output_tokens"])
async def test_partial_usage_keeps_spend_unknown_and_refuses_next_wire_call__b102(
    missing_bucket,
):
    response = raw_response()
    response.usage_metadata[missing_bucket] = None
    client = Mock(
        ainvoke=AsyncMock(
            side_effect=lambda _: observed_response(response, **{missing_bucket: None})
        )
    )
    svc = service_with_client(client)
    ledger = Ledger()
    await call(svc, ledger)
    outcome = ledger.rows["1"]
    assert getattr(outcome.usage, missing_bucket) is None
    assert outcome.cost_usd is None
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(svc, ledger)
    assert client.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_tool_bound_failure_keeps_fallback_suppressed__b102():
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    client.bind_tools.return_value = client
    svc = fallback_service(client)
    ledger = Ledger("1.00")
    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=RuntimeError("connection timeout"),
    ):
        with pytest.raises(LLMResolvedCallError):
            await call(svc, ledger, tools=[{"name": "extract", "parameters": {}}])
    assert client.ainvoke.await_count == 1
    assert ledger.rows["1"].cost_usd == Decimal("0.20")


@pytest.mark.asyncio
async def test_concurrent_and_nested_plain_calls_do_not_inherit_host_lifecycle__b102():
    arrivals = asyncio.Queue()
    release = asyncio.Event()

    async def dispatch(messages):
        label = messages[0].content
        if label in {"a", "b"}:
            await arrivals.put(label)
            await release.wait()
        tokens = 5 if label == "a" else 10
        return observed_response(
            raw_response(tokens=tokens), input_tokens=tokens, output_tokens=tokens
        )

    client = Mock(ainvoke=AsyncMock(side_effect=dispatch))
    svc = service_with_client(client)
    a, b = Ledger(), Ledger()

    async def invoke(label, ledger):
        return await svc.call_llm_async(
            [{"role": "user", "content": label}],
            provider="openai",
            model="test-model",
            attempt_lifecycle=ledger,
        )

    original_begin = a.before_attempt

    async def nested_plain(description):
        await svc.call_llm_async(
            [{"role": "user", "content": "plain"}], provider="openai"
        )
        return await original_begin(description)

    a.before_attempt = nested_plain
    tasks = [asyncio.create_task(invoke("a", a)), asyncio.create_task(invoke("b", b))]
    await asyncio.wait_for(arrivals.get(), 1)
    await asyncio.wait_for(arrivals.get(), 1)
    tasks[1].cancel()
    with pytest.raises(asyncio.CancelledError):
        await tasks[1]
    release.set()
    assert (await tasks[0]).text == "ok"
    assert a.rows["1"].cost_usd == Decimal("0.10")
    assert b.rows["1"].cost_usd is None
    assert b.rows["1"].classification == "cancelled"
    await svc.call_llm_async([{"role": "user", "content": "later"}], provider="openai")
    assert len(a.rows) == len(b.rows) == 1
    assert client.ainvoke.await_count == 4


@pytest.mark.asyncio
async def test_receipt_calculation_failure_retains_usage_and_request_identity__b102():
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    svc = service_with_client(client)
    ledger = Ledger()
    with patch.object(
        svc._cost_calculator, "calculate", side_effect=ValueError("bad rates")
    ):
        with pytest.raises(LLMConfigurationError):
            await call(svc, ledger)
    assert client.ainvoke.await_count == 1
    assert ledger.rows["1"].usage.input_tokens == 10
    assert ledger.rows["1"].provider_request_id == "provider-request"
    assert ledger.rows["1"].cost_usd is None
    assert ledger.rows["1"].classification == "receipt_error"


@pytest.mark.asyncio
async def test_streaming_rejects_lifecycle_instead_of_ignoring_it__b102():
    svc = service_with_client(Mock())
    with pytest.raises(LLMConfigurationError, match="attempt_lifecycle"):
        async for _ in svc.call_llm_stream_async(
            [{"role": "user", "content": "synthetic"}],
            provider="openai",
            attempt_lifecycle=Ledger(),
        ):
            pytest.fail("unsupported governed streaming dispatched")
    svc._client_factory.get_or_create_client.assert_not_called()


def test_sync_api_rejects_lifecycle_instead_of_ignoring_it__b102():
    svc = service_with_client(Mock())
    with pytest.raises(LLMConfigurationError, match="attempt_lifecycle"):
        svc.call_llm(
            [{"role": "user", "content": "synthetic"}],
            provider="openai",
            attempt_lifecycle=Ledger(),
        )
    svc._client_factory.get_or_create_client.assert_not_called()


@pytest.mark.parametrize("surface", ["request", "item"])
def test_batch_rejects_lifecycle_before_adapter_dispatch__b102(surface):
    svc = service_with_client(Mock())
    adapter = Mock()
    svc._batch_adapters = {"openai": adapter}
    options = {"attempt_lifecycle": Ledger()}
    spec = LLMRequest(
        request_id="one",
        messages=[{"role": "user", "content": "synthetic"}],
        request_options=options if surface == "item" else {},
    )
    request = LLMBatchSubmitRequest(
        provider="openai",
        model="test-model",
        requests=[spec],
        request_options=options if surface == "request" else {},
    )
    with pytest.raises(LLMServiceError, match="attempt_lifecycle"):
        svc.submit_batch(request)
    adapter.submit.assert_not_called()


@pytest.mark.asyncio
async def test_routed_settlement_failure_preserves_host_error_without_rerouting__b102():
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    svc = fallback_service(client)
    svc.routing_service.route_request.return_value = Mock(
        provider="openai",
        model="test-model",
        complexity="low",
        confidence=1.0,
        max_tokens=31,
        cache_hit=False,
        fallback_used=False,
    )
    ledger = Ledger()
    error = RuntimeError("host reconciliation failed connection timeout")
    ledger.after_attempt = AsyncMock(side_effect=error)
    with pytest.raises(RuntimeError) as caught:
        await svc.call_llm_async(
            [{"role": "user", "content": "synthetic"}],
            routing_context={"task_type": "general"},
            attempt_lifecycle=ledger,
        )
    assert caught.value is error
    assert client.ainvoke.await_count == 1
    assert ledger.descriptions[0].max_output_tokens == 31
    assert ledger.rows == {"1": None}
