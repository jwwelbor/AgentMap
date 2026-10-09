"""B102 body collector isolation, interruption, and admission controls."""

import asyncio
import gzip
from contextlib import suppress
from decimal import Decimal
from threading import Event
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from agentmap.exceptions import (
    LLMDependencyError,
    ResponseCaptureFailure,
)
from agentmap.models.llm_attempt import LLMResponseEvidence
from agentmap.services.llm.response_observer import (
    ResponseCollector,
    observe_async_response,
    observe_response,
    response_collector,
)
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
    raw_response,
    service_with_client,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    real_service,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (  # noqa: F401
    real_service_factory_fixture as _real_service_factory_fixture,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    setup_transport,
)


def inject_timeout_after_worker_state(service, ready):
    """Exercise settlement after the worker reached a proved observation state."""
    invoke_provider = service._invoke_provider_async

    async def interrupted_provider(client, messages):
        running = asyncio.create_task(invoke_provider(client, messages))
        try:
            assert await asyncio.to_thread(ready.wait, 5)
        finally:
            running.cancel()
            with suppress(asyncio.CancelledError):
                await running
        raise TimeoutError("injected after worker progress")

    service._invoke_provider_async = interrupted_provider


@pytest.mark.asyncio
async def test_multiple_http_responses_fail_loud_after_known_settlement__b102():
    first_body = body_for("openai", "first")

    async def dispatch(messages):
        await observe_async_response(httpx.Response(200, content=first_body))
        await observe_async_response(httpx.Response(200, content=b"second"))
        return raw_response()

    ledger = Ledger()
    with pytest.raises(ResponseCaptureFailure):
        await call(
            service_with_client(Mock(ainvoke=AsyncMock(side_effect=dispatch))), ledger
        )
    assert ledger.rows["1"].cost_usd == Decimal("0.20")
    assert ledger.rows["1"].response_evidence.body == first_body
    assert ledger.events == [("begin", "1"), ("settle", "1")]


@pytest.mark.asyncio
async def test_two_managed_calls_keep_distinct_bodies_before_next_admission__b102(
    monkeypatch, real_service_factory_fixture
):
    bodies = [body_for("openai", "first"), body_for("openai", "second")]
    calls = []

    async def send(transport, request):
        calls.append(request)
        return httpx.Response(200, content=bodies[len(calls) - 1])

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    ledger = Ledger("1")
    service = real_service_factory_fixture("openai", "test-model")
    assert (await invoke(service, "openai", "test-model", ledger)).text == "first"
    assert (await invoke(service, "openai", "test-model", ledger)).text == "second"
    assert [row.response_evidence.body for row in ledger.rows.values()] == bodies
    assert ledger.events == [
        ("begin", "1"),
        ("settle", "1"),
        ("begin", "2"),
        ("settle", "2"),
    ]
    assert sum(row.cost_usd for row in ledger.rows.values()) == Decimal("0.40")


@pytest.mark.asyncio
@pytest.mark.parametrize("cap,expected_calls", [("0.20", 1), ("1", 2)])
async def test_real_body_survives_normalization_and_retry_admission__b102(
    monkeypatch, cap, expected_calls, real_service_factory_fixture
):
    body = body_for("openai")
    calls = setup_transport(monkeypatch, body)
    ledger = Ledger(cap)
    service = real_service_factory_fixture("openai", "test-model")
    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=[RuntimeError("connection timeout"), ("ok", "text")],
    ):
        if expected_calls == 1:
            with pytest.raises(AccountingRefusal, match="cap reached"):
                await invoke(service, "openai", "test-model", ledger)
        else:
            assert (await invoke(service, "openai", "test-model", ledger)).text == "ok"
    assert len(calls) == expected_calls
    assert ledger.rows["1"].response_evidence.body == body
    assert ledger.rows["1"].cost_usd == Decimal("0.20")


@pytest.mark.asyncio
async def test_concurrent_real_clients_do_not_share_bodies__b102(
    monkeypatch, real_service_factory_fixture
):
    barrier = asyncio.Event()
    arrived = []

    async def send(transport, request):
        text = "one" if b'"one"' in request.content else "two"
        arrived.append(text)
        if len(arrived) == 2:
            barrier.set()
        await asyncio.wait_for(barrier.wait(), timeout=10)
        return httpx.Response(200, content=body_for("openai", text))

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    service = real_service_factory_fixture("openai", "test-model")
    ledgers = [Ledger("1"), Ledger("1")]

    async def run(text, ledger):
        return await service.call_llm_async(
            [{"role": "user", "content": text}],
            provider="openai",
            model="test-model",
            attempt_lifecycle=ledger,
        )

    tasks = [
        asyncio.create_task(run("one", ledgers[0])),
        asyncio.create_task(run("two", ledgers[1])),
    ]
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
    finally:
        barrier.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert ledgers[0].rows["1"].response_evidence.body == body_for("openai", "one")
    assert ledgers[1].rows["1"].response_evidence.body == body_for("openai", "two")
    assert response_collector.get() is None


@pytest.mark.asyncio
async def test_interrupted_read_retains_partial_entity_before_refusal__b102(
    monkeypatch, real_service_factory_fixture
):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial entity"
            raise httpx.ReadError("read-secret")

    async def send(transport, request):
        return httpx.Response(200, stream=BrokenStream())

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    ledger = Ledger()
    with pytest.raises(ResponseCaptureFailure):
        await invoke(
            real_service_factory_fixture("openai", "test-model"),
            "openai",
            "test-model",
            ledger,
        )
    evidence = ledger.rows["1"].response_evidence
    assert evidence.status == "partial"
    assert evidence.body == b"partial entity"
    assert evidence.unavailable_reason == "interrupted_read"
    assert ledger.rows["1"].cost_usd is None


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"", gzip.compress("decoded café".encode())])
async def test_empty_and_compressed_entities_are_distinct_from_missing__b102(payload):
    collector = ResponseCollector()
    token = response_collector.set(collector)
    headers = {"content-encoding": "gzip"} if payload else {}
    try:
        await observe_async_response(
            httpx.Response(200, content=payload, headers=headers)
        )
    finally:
        response_collector.reset(token)
    evidence = collector.seal()
    assert evidence.status == "available"
    assert evidence.body == ("decoded café".encode() if payload else b"")


@pytest.mark.asyncio
async def test_late_thread_body_cannot_mutate_timed_out_attempt__b102():
    started, release, ended = Event(), Event(), Event()

    def dispatch(messages):
        started.set()
        release.wait(5)
        observe_response(httpx.Response(200, content=b"late body"))
        ended.set()
        return raw_response()

    service = service_with_client(Mock(ainvoke=None, invoke=dispatch))
    inject_timeout_after_worker_state(service, started)
    ledger = Ledger()
    try:
        task = asyncio.create_task(call(service, ledger))
        with pytest.raises(AccountingRefusal, match="unresolved charge"):
            await task
        assert started.is_set()
        original = ledger.rows["1"].response_evidence
        assert original.status == "unavailable"
        release.set()
        assert await asyncio.to_thread(ended.wait, 2)
        assert ledger.rows["1"].response_evidence is original
        assert original.body is None
        assert response_collector.get() is None
    finally:
        release.set()


@pytest.mark.asyncio
async def test_cancel_after_full_body_keeps_available_evidence__b102():
    async def dispatch(messages):
        await observe_async_response(httpx.Response(200, content=b"full body"))
        raise asyncio.CancelledError()

    ledger = Ledger()
    with pytest.raises(asyncio.CancelledError):
        await call(
            service_with_client(Mock(ainvoke=AsyncMock(side_effect=dispatch))), ledger
        )
    assert ledger.rows["1"].response_evidence.body == b"full body"
    assert ledger.rows["1"].classification == "cancelled"
    assert response_collector.get() is None


@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.asyncio
async def test_unqualified_sdk_is_rejected_before_dispatch__b102(
    provider, model, monkeypatch
):
    monkeypatch.setattr(
        "agentmap.services.llm.observed_clients.version", lambda name: "999.0"
    )
    with pytest.raises(LLMDependencyError, match="qualified"):
        await LLMClientFactory(Mock()).get_or_create_governed_client(
            provider, {"model": model, "api_key": "offline"}
        )


def test_response_body_cannot_leak_through_repr__b102():
    evidence = LLMResponseEvidence(
        status="available", body=b"body-secret", unavailable_reason=None
    )
    assert "body-secret" not in repr(evidence)


@pytest.mark.asyncio
async def test_plain_invocation_does_not_inherit_response_collector__b102(monkeypatch):
    setup_transport(monkeypatch, body_for("openai"))
    collector = ResponseCollector()
    token = response_collector.set(collector)
    service = real_service("openai", "test-model")
    try:
        await service.call_llm_async(
            [{"role": "user", "content": "plain"}],
            provider="openai",
            model="test-model",
        )
        assert response_collector.get() is collector
        assert collector.seal().status == "unavailable"
    finally:
        response_collector.reset(token)


@pytest.mark.asyncio
async def test_partial_thread_read_is_sealed_at_timeout__b102(monkeypatch):
    release, ended, prefix_observed = Event(), Event(), Event()
    original_progress = ResponseCollector.progress

    def record_progress(collector, chunk):
        original_progress(collector, chunk)
        if collector.partial_body() == b"observed prefix":
            prefix_observed.set()

    monkeypatch.setattr(ResponseCollector, "progress", record_progress)

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"observed prefix"
            release.wait(5)
            yield b" late tail"

    def dispatch(messages):
        observe_response(httpx.Response(200, stream=SlowStream()))
        ended.set()
        return raw_response()

    service = service_with_client(Mock(ainvoke=None, invoke=dispatch))
    inject_timeout_after_worker_state(service, prefix_observed)
    ledger = Ledger()
    try:
        task = asyncio.create_task(call(service, ledger))
        with pytest.raises(AccountingRefusal):
            await task
        assert prefix_observed.is_set()
        evidence = ledger.rows["1"].response_evidence
        assert evidence.status == "partial"
        assert evidence.body == b"observed prefix"
        release.set()
        assert await asyncio.to_thread(ended.wait, 2)
        assert ledger.rows["1"].response_evidence is evidence
    finally:
        release.set()
