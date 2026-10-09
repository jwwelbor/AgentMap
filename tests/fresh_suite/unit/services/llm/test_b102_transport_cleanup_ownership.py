"""B102 cleanup must retain actual transport close failures."""

import httpx
import pytest

from agentmap.services.llm.observed_transports import (
    ObservedAsyncTransport,
    ObservedSyncTransport,
    ObservedTransport,
)


def test_shared_transport_does_not_hide_sync_inner_close_failure__b102(monkeypatch):
    transport = ObservedTransport()
    client = transport._sync
    attempts = []
    failure = RuntimeError("offline inner transport close failure")

    def fail_close(inner):
        attempts.append(inner)
        raise failure

    monkeypatch.setattr(httpx.HTTPTransport, "close", fail_close)
    with pytest.raises(RuntimeError) as first:
        transport.close()
    with pytest.raises(RuntimeError) as second:
        transport.close()

    assert first.value is second.value is failure
    assert attempts == [client._transport]
    assert transport._sync_client is client
    assert transport._sync_closed


@pytest.mark.asyncio
async def test_shared_transport_does_not_hide_async_inner_close_failure__b102(
    monkeypatch,
):
    transport = ObservedTransport()
    client = transport._async
    attempts = []
    failure = RuntimeError("offline inner async transport close failure")

    async def fail_close(inner):
        attempts.append(inner)
        raise failure

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", fail_close)
    with pytest.raises(RuntimeError) as first:
        await transport.aclose()
    with pytest.raises(RuntimeError) as second:
        await transport.aclose()

    assert first.value is second.value is failure
    assert attempts == [client._transport]
    assert transport._async_client is client
    assert transport._async_closed


def test_sync_transport_retains_inner_close_failure__b102(monkeypatch):
    transport = ObservedSyncTransport()
    attempts = []
    failure = RuntimeError("offline inner HTTP close failure")

    def fail_close(inner):
        attempts.append(inner)
        raise failure

    monkeypatch.setattr(httpx.HTTPTransport, "close", fail_close)
    with pytest.raises(RuntimeError) as first:
        transport.close()
    with pytest.raises(RuntimeError) as second:
        transport.close()

    assert first.value is second.value is failure
    assert attempts == [transport._sync._transport]
    assert transport._closed


@pytest.mark.asyncio
async def test_async_transport_retains_inner_close_failure__b102(monkeypatch):
    transport = ObservedAsyncTransport()
    attempts = []
    failure = RuntimeError("offline inner async HTTP close failure")

    async def fail_close(inner):
        attempts.append(inner)
        raise failure

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", fail_close)
    with pytest.raises(RuntimeError) as first:
        await transport.aclose()
    with pytest.raises(RuntimeError) as second:
        await transport.aclose()

    assert first.value is second.value is failure
    assert attempts == [transport._async._transport]
    assert transport._closed
