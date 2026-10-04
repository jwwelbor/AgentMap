"""B102 review regressions for one physical request and honest settlement."""

from unittest.mock import Mock

import aiohttp
import httpx
import pytest

from agentmap.services.llm import response_observer
from agentmap.services.llm.response_observer import (
    ObservedTransport,
    ResponseCaptureFailure,
    ResponseCollector,
    response_collector,
)
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import Ledger
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    real_service,
)


@pytest.fixture(autouse=True)
def refuse_unstubbed_network(monkeypatch):
    def refuse_sync(*args, **kwargs):
        raise AssertionError("unstubbed sync HTTP request")

    async def refuse_async(*args, **kwargs):
        raise AssertionError("unstubbed async HTTP request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse_async)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", refuse_async)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_redirect_response_cannot_send_a_second_wire_request__b102(
    provider, model, monkeypatch
):
    requests = []

    async def send(transport, request):
        requests.append(request)
        if len(requests) > 1:
            raise AssertionError("a redirect sent an unadmitted request")
        return httpx.Response(
            307,
            headers={"location": str(request.url), "content-type": "text/plain"},
            content=b"redirect body",
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    ledger = Ledger()
    with pytest.raises(Exception):
        await invoke(real_service(provider, model), provider, model, ledger)
    assert len(requests) == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    outcome = ledger.rows["1"]
    assert outcome.classification == "provider_error"
    assert outcome.response_evidence.body == b"redirect body"
    assert outcome.response_evidence.http_status == 307


@pytest.mark.asyncio
async def test_forced_google_redirect_is_refused_before_second_dispatch__b102(
    monkeypatch,
):
    requests = []
    original_init = httpx.AsyncClient.__init__

    def force_redirects(client, *args, **kwargs):
        if isinstance(kwargs.get("transport"), ObservedTransport):
            kwargs["follow_redirects"] = True
        original_init(client, *args, **kwargs)

    async def send(transport, request):
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": str(request.url)},
            content=b"redirect body",
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "__init__", force_redirects)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    ledger = Ledger()
    with pytest.raises(ResponseCaptureFailure):
        await invoke(
            real_service("google", "gemini-2.5-flash"),
            "google",
            "gemini-2.5-flash",
            ledger,
        )
    assert len(requests) == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    outcome = ledger.rows["1"]
    assert outcome.classification == "capture_error"
    assert outcome.error_type == "ResponseCaptureFailure"
    assert outcome.response_evidence.body == b"redirect body"


@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.asyncio
async def test_sync_wrapper_redirect_cannot_send_a_second_wire_request__b102(
    provider, model, monkeypatch
):
    requests = []

    def send(transport, request):
        requests.append(request)
        if len(requests) > 1:
            raise AssertionError("a redirect sent an unadmitted request")
        return httpx.Response(
            307,
            headers={"location": str(request.url)},
            content=b"redirect body",
            request=request,
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    factory = LLMClientFactory(Mock())
    client = await factory.get_or_create_governed_client(
        provider, {"api_key": "offline", "model": model}
    )
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(Exception):
            client.invoke("synthetic request")
    finally:
        response_collector.reset(token)
    assert len(requests) == 1
    assert collector.seal().body == b"redirect body"
    await factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_observer_and_sdk_error_settle_capture_failure__b102(
    provider, model, monkeypatch
):
    requests = []

    async def send(transport, request):
        requests.append(request)
        return httpx.Response(500, content=b"provider error", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    monkeypatch.setattr(
        response_observer, "_evidence", Mock(side_effect=ValueError("observer secret"))
    )
    ledger = Ledger()
    with pytest.raises(ResponseCaptureFailure):
        await invoke(real_service(provider, model), provider, model, ledger)
    assert len(requests) == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    outcome = ledger.rows["1"]
    assert outcome.classification == "capture_error"
    assert outcome.error_type == "ResponseCaptureFailure"
    assert outcome.response_evidence.status == "available"
    assert outcome.response_evidence.body == b"provider error"


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.asyncio
async def test_observed_transport_blocks_second_request_before_dispatch__b102(
    mode, monkeypatch
):
    requests = []

    def send(transport, request):
        requests.append(request)
        return httpx.Response(200, content=b"first", request=request)

    async def asend(transport, request):
        return send(transport, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", asend)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        if mode == "sync":
            with httpx.Client(transport=ObservedTransport()) as client:
                assert client.get("https://offline.invalid/one").content == b"first"
                with pytest.raises(ResponseCaptureFailure):
                    client.get("https://offline.invalid/two")
        else:
            async with httpx.AsyncClient(transport=ObservedTransport()) as client:
                assert (
                    await client.get("https://offline.invalid/one")
                ).content == b"first"
                with pytest.raises(ResponseCaptureFailure):
                    await client.get("https://offline.invalid/two")
    finally:
        response_collector.reset(token)
    assert len(requests) == 1
    assert collector.failed
    assert collector.seal().body == b"first"


@pytest.mark.asyncio
async def test_complete_capture_releases_partial_accumulator__b102(monkeypatch):
    class ChunkedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield body_for("openai")[:20]
            yield body_for("openai")[20:]

    async def send(transport, request):
        return httpx.Response(200, stream=ChunkedBody(), request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        async with httpx.AsyncClient(transport=ObservedTransport()) as client:
            await client.get("https://offline.invalid/one")
    finally:
        response_collector.reset(token)
    assert collector.seal().body == body_for("openai")
    assert not collector._partial


@pytest.mark.asyncio
async def test_sealed_collector_blocks_late_async_dispatch__b102(monkeypatch):
    requests = []

    async def send(transport, request):
        requests.append(request)
        return httpx.Response(200, content=b"unexpected", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    collector = ResponseCollector()
    collector.seal()
    token = response_collector.set(collector)
    try:
        async with httpx.AsyncClient(transport=ObservedTransport()) as client:
            with pytest.raises(ResponseCaptureFailure):
                await client.get("https://offline.invalid/late")
    finally:
        response_collector.reset(token)
    assert requests == []
