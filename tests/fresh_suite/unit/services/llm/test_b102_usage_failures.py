"""Shared raw validation governs cache fields and terminal failure branches."""

import asyncio
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from agentmap.exceptions import LLMServiceError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_cache_measurements import cache_body
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


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("known", [False, True])
async def test_normalization_failure_keeps_shared_usage_before_retry__b102(
    monkeypatch, provider, model, known
):
    body = (
        body_for(provider)
        if known
        else changed_body(provider, "output_tokens", "absent")
    )
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "output_tokens")
    ledger = Ledger("0.20")
    try:
        with patch(
            "agentmap.services.llm_service.normalize_response_content",
            side_effect=RuntimeError("connection timeout"),
        ):
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert row.cost_usd == (Decimal("0.20") if known else None)
        assert row.usage.input_tokens == 10
        assert row.usage.output_tokens == (10 if known else None)
        assert row.response_evidence.body == body
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_sdk_content_failure_does_not_discard_observed_usage__b102(
    monkeypatch, provider, model
):
    payload = json.loads(body_for(provider))
    payload[
        {"openai": "choices", "anthropic": "content", "google": "candidates"}[provider]
    ] = "bad"
    if provider == "google":
        payload["candidates"] = [{"content": {"parts": 5}}]
    body = json.dumps(payload).encode()
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("0.20")
    try:
        with pytest.raises((LLMServiceError, AccountingRefusal)):
            await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert row.cost_usd == Decimal("0.20")
        assert row.usage.input_tokens == row.usage.output_tokens == 10
        assert row.response_evidence.body == body
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_cancel_after_body_keeps_same_known_accounting__b102(
    monkeypatch, provider, model
):
    from agentmap.services.llm import response_observer

    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("1")
    original = response_observer.observe_async_response
    started = asyncio.Event()

    async def cancel_after_observation(response):
        await original(response)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        response_observer, "observe_async_response", cancel_after_observation
    )
    try:
        task = asyncio.create_task(invoke(service, provider, model, ledger))
        await asyncio.wait_for(started.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ledger.rows["1"].cost_usd == Decimal("0.20")
        assert ledger.rows["1"].response_evidence.body == body
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize(
    "bucket", ["input_tokens", "output_tokens", "cache_read_input_tokens"]
)
@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.parametrize("value", [-1, -1.0, -0.5])
async def test_negative_count_at_zero_rate_refuses_even_sync_redispatch__b102(
    monkeypatch, provider, model, bucket, sync, value
):
    body = (
        cache_body(provider, value)
        if bucket == "cache_read_input_tokens"
        else changed_body(provider, bucket, value)
    )
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, bucket, free=True)
    service._cost_calculator._raw_rate_index[(provider, model)]["cache_read_per_1m"] = 0
    if sync:
        client = await service._client_factory.get_or_create_governed_client(
            provider, {"api_key": "authorization-secret", "model": model}
        )
        monkeypatch.setattr(type(client), "ainvoke", None)
    ledger = Ledger("1")
    try:
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            result = None
        row = ledger.rows["1"]
        assert row.cost_usd is None
        assert getattr(row.usage, bucket) is None
        other = "output_tokens" if bucket == "input_tokens" else "input_tokens"
        assert getattr(row.usage, other) == 10
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if result is not None:
            assert result.usage == row.usage
            assert result.cost is None
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("details", [None, [], "bad", 5, True, {"cached_tokens": 11}])
async def test_openai_invalid_cache_shape_or_excess_count_blocks_redispatch__b102(
    monkeypatch, details
):
    provider, model = "openai", "gpt-4o-mini"
    payload = json.loads(body_for(provider))
    payload["usage"]["prompt_tokens_details"] = details
    body = json.dumps(payload).encode()
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    service._cost_calculator._raw_rate_index[(provider, model)][
        "cache_read_per_1m"
    ] = 2000
    ledger = Ledger("1")
    try:
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            result = None
        row = ledger.rows["1"]
        assert row.usage.input_tokens == row.usage.output_tokens == 10
        assert row.usage.cache_read_input_tokens == (
            11 if isinstance(details, dict) else None
        )
        assert row.cost_usd is None
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if result is not None:
            assert result.usage == row.usage
            assert result.cost is None
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
