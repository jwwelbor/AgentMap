"""B102: govern physical attempts through the public service entrypoint."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agentmap.services.llm.cost_calculator import LLMCostCalculator
from tests.fresh_suite.unit.services.test_llm_resilience import _make_service


class AccountingRefusal(RuntimeError):
    pass


class Ledger:
    """In-memory host policy; no provider error implies a free attempt."""

    def __init__(self, cap="0.20"):
        self.cap = Decimal(cap)
        self.rows = {}
        self.descriptions = []
        self.events = []

    async def before_attempt(self, description):
        if any(row is None or row.cost_usd is None for row in self.rows.values()):
            raise AccountingRefusal("unresolved charge")
        if sum((row.cost_usd for row in self.rows.values()), Decimal(0)) >= self.cap:
            raise AccountingRefusal("cap reached")
        identity = str(len(self.rows) + 1)
        self.rows[identity] = None
        self.descriptions.append(description)
        self.events.append(("begin", identity))
        return identity

    async def after_attempt(self, attempt_id, outcome):
        self.events.append(("settle", attempt_id))
        self.rows[attempt_id] = outcome


def raw_response(text="ok", tokens=10):
    return SimpleNamespace(
        content=text,
        usage_metadata={"input_tokens": tokens, "output_tokens": tokens},
        response_metadata={
            "headers": {"x-request-id": "provider-request"},
            "finish_reason": "stop",
        },
        tool_calls=[],
    )


def service_with_client(client, **kwargs):
    svc = _make_service(**kwargs)
    svc._resilience_config["retry"].update(backoff_base=0, backoff_max=0)
    svc._cost_calculator = LLMCostCalculator(
        {
            "catalog_version": "test-v1",
            "models": {
                "openai": {
                    "test-model": {
                        "currency": "USD",
                        "input_per_1m": 10000,
                        "output_per_1m": 10000,
                    }
                }
            },
        },
        Mock(),
    )
    svc._client_factory.get_or_create_client = Mock(return_value=client)
    svc._client_factory.get_or_create_governed_client = AsyncMock(return_value=client)
    return svc


async def call(svc, ledger, **kwargs):
    return await svc.call_llm_async(
        messages=[{"role": "user", "content": "synthetic"}],
        provider="openai",
        model="test-model",
        max_tokens=77,
        attempt_lifecycle=ledger,
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("tools", [None, [{"name": "extract", "parameters": {}}]])
async def test_billed_non_text_response_prevents_another_dispatch_at_cap__b102(tools):
    client = Mock()
    client.ainvoke = AsyncMock(return_value=raw_response([{"type": "thinking"}]))
    client.bind_tools.return_value = client
    svc = service_with_client(client)
    ledger = Ledger()
    first = await call(svc, ledger, tools=tools)
    assert first.text_status == "non_text"
    with pytest.raises(AccountingRefusal, match="cap reached"):
        await call(svc, ledger, tools=tools)
    assert client.ainvoke.await_count == 1
    assert len(ledger.rows) == 1
    outcome = ledger.rows["1"]
    assert outcome.cost_usd == Decimal("0.20")
    assert outcome.usage.input_tokens == outcome.usage.output_tokens == 10
    assert outcome.provider_request_id == "provider-request"
    assert ledger.descriptions[0].max_output_tokens == 77


@pytest.mark.asyncio
async def test_unknown_provider_failure_settles_before_retry_admission__b102():
    client = Mock(ainvoke=AsyncMock(side_effect=RuntimeError("connection timeout")))
    svc = service_with_client(client)
    ledger = Ledger()
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(svc, ledger)
    assert client.ainvoke.await_count == 1
    assert ledger.rows["1"].cost_usd is None
    assert ledger.rows["1"].usage is None
    assert ledger.rows["1"].classification == "provider_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("cap,calls", [("0.20", 1), ("0.50", 2)])
async def test_billed_normalization_failure_settles_before_inner_retry__b102(
    cap, calls
):
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    svc = service_with_client(client)
    ledger = Ledger(cap)
    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=[RuntimeError("connection timeout"), ("ok", "text")],
    ):
        if calls == 1:
            with pytest.raises(AccountingRefusal, match="cap reached"):
                await call(svc, ledger)
        else:
            assert (await call(svc, ledger)).text == "ok"
    assert client.ainvoke.await_count == calls
    assert ledger.rows["1"].cost_usd == Decimal("0.20")
    assert ledger.rows["1"].classification == "normalization_error"
    assert ledger.events[:2] == [("begin", "1"), ("settle", "1")]
    assert [d.retry_ordinal for d in ledger.descriptions] == list(range(1, calls + 1))


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["before_attempt", "after_attempt"])
async def test_host_failure_is_preserved_and_completion_is_never_retried__b102(stage):
    client = Mock(ainvoke=AsyncMock(return_value=raw_response()))
    telemetry = Mock()
    telemetry.start_span.return_value.__enter__ = Mock(return_value=Mock())
    telemetry.start_span.return_value.__exit__ = Mock(return_value=False)
    svc = service_with_client(client, telemetry_service=telemetry)
    ledger = Ledger()
    failure = RuntimeError("tenant-secret connection timeout")
    callback = AsyncMock(side_effect=failure)
    setattr(ledger, stage, callback)
    with pytest.raises(RuntimeError) as caught:
        await call(svc, ledger)
    assert caught.value is failure
    assert client.ainvoke.await_count == (stage == "after_attempt")
    assert callback.await_count == 1
    assert "tenant-secret" not in str(telemetry.record_exception.call_args_list)


@pytest.mark.asyncio
async def test_cancelled_provider_settles_unknown_and_preserves_cancellation__b102():
    started = asyncio.Event()

    async def wait_for_cancel(messages):
        started.set()
        await asyncio.Event().wait()

    client = Mock(ainvoke=AsyncMock(side_effect=wait_for_cancel))
    svc = service_with_client(client)
    ledger = Ledger()
    task = asyncio.create_task(call(svc, ledger))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ledger.rows["1"].classification == "cancelled"
    assert ledger.rows["1"].cost_usd is None
    assert client.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_provider_timeout_settles_unknown_before_any_retry__b102():
    client = Mock(ainvoke=AsyncMock(side_effect=lambda messages: asyncio.sleep(5)))

    # AsyncMock does not await a returned coroutine; use an actual async fake.
    async def hang(messages):
        await asyncio.Event().wait()

    client.ainvoke.side_effect = hang
    svc = service_with_client(client)
    svc._resilience_config["retry"]["attempt_timeout"] = 0.01
    ledger = Ledger()
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(svc, ledger)
    assert ledger.rows["1"].classification == "timeout"
    assert client.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_plain_calls_keep_existing_retry_behavior__b102():
    client = Mock(
        ainvoke=AsyncMock(
            side_effect=[RuntimeError("connection timeout"), raw_response()]
        )
    )
    svc = service_with_client(client)
    result = await svc.call_llm_async(
        [{"role": "user", "content": "synthetic"}], provider="openai"
    )
    assert result.text == "ok"
    assert client.ainvoke.await_count == 2
