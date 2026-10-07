"""Shared measurements remain isolated across cached provider clients/routes."""

import asyncio
from decimal import Decimal

import httpx
import pytest

from agentmap.exceptions import LLMConfigurationError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_measurement_publication import (
    pricing_fault,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import (
    changed_body,
    priced_service,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)

TOOLS = [{"name": "extract", "parameters": {"type": "object", "properties": {}}}]


async def force_sync_wrapper(monkeypatch, service, provider, model):
    client = await service._client_factory.get_or_create_governed_client(
        provider, {"api_key": "authorization-secret", "model": model}
    )
    bound = client.bind_tools(TOOLS)
    monkeypatch.setattr(type(client), "ainvoke", None)
    monkeypatch.setattr(type(bound), "ainvoke", None)


def cached_transport(monkeypatch, provider):
    bodies = {
        "first": body_for(provider),
        "second": changed_body(provider, "output_tokens", "absent"),
    }
    calls = setup_transport(monkeypatch, bodies["first"])
    arrived, release = [], asyncio.Event()

    async def send(transport, request):
        label = "first" if b'"first"' in request.content else "second"
        calls.append(request)
        arrived.append(label)
        if len(arrived) == 2:
            release.set()
        await asyncio.wait_for(release.wait(), 10)
        return httpx.Response(200, content=bodies[label])

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    return bodies, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("sync", [False, True])
async def test_tool_route_publishes_before_cost_fault_for_async_and_sync_clients__b102(
    monkeypatch, provider, model, sync
):
    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service, ledger = priced_service(provider, model, "output_tokens"), Ledger("1")
    if sync:
        await force_sync_wrapper(monkeypatch, service, provider, model)
    clear = pricing_fault(monkeypatch, service, "calculation")
    try:
        with pytest.raises(LLMConfigurationError):
            await service.call_llm_async(
                messages=[{"role": "user", "content": "synthetic"}],
                provider=provider,
                model=model,
                attempt_lifecycle=ledger,
                tools=[
                    {
                        "name": "extract",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            )
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
async def test_cached_client_keeps_task_accounting_distinct_across_json_and_tools__b102(
    monkeypatch, provider, model
):
    bodies, calls = cached_transport(monkeypatch, provider)
    service = priced_service(provider, model, "output_tokens")
    ledgers = {"first": Ledger("0.20"), "second": Ledger("1")}

    async def run(label):
        return await service.call_llm_async(
            messages=[{"role": "user", "content": label}],
            provider=provider,
            model=model,
            attempt_lifecycle=ledgers[label],
            **(
                {
                    "tools": [
                        {
                            "name": "extract",
                            "parameters": {"type": "object", "properties": {}},
                        }
                    ]
                }
                if label == "second"
                else {}
            ),
        )

    try:
        await asyncio.gather(run("first"), run("second"))
        for label, ledger in ledgers.items():
            assert ledger.rows["1"].response_evidence.body == bodies[label]
            assert ledger.rows["1"].usage.input_tokens == 10
            assert ledger.rows["1"].cost_usd == (
                None if label == "second" else Decimal("0.20")
            )
            with pytest.raises(AccountingRefusal):
                await run(label)
            assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert len(calls) == 2
    finally:
        await service._client_factory.shutdown()
