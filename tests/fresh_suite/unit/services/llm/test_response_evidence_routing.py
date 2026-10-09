"""B102 real primary/fallback response observation and non-text cap controls."""

from decimal import Decimal
from unittest.mock import Mock, patch

import httpx
import pytest

from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    body_for,
    invoke,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (  # noqa: F401
    real_service_factory_fixture as _real_service_factory_fixture,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    setup_transport,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("cap,expected_calls", [("0.20", 1), ("1", 2)])
async def test_real_fallback_clients_both_have_observed_transports__b102(
    monkeypatch, cap, expected_calls
):
    from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle_boundaries import (
        fallback_service,
    )

    bodies = [body_for("openai", "primary"), body_for("anthropic", "fallback")]
    calls = []

    async def send(transport, request):
        calls.append(request)
        return httpx.Response(200, content=bodies[len(calls) - 1])

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    service = fallback_service(Mock())
    service._client_factory = LLMClientFactory(Mock())
    ledger = Ledger(cap)
    try:
        with patch(
            "agentmap.services.llm_service.normalize_response_content",
            side_effect=[RuntimeError("connection timeout"), ("fallback", "text")],
        ):
            if expected_calls == 1:
                with pytest.raises(AccountingRefusal, match="cap reached"):
                    await call(service, ledger)
            else:
                assert (await call(service, ledger)).text == "fallback"
        assert len(calls) == expected_calls
        assert [r.response_evidence.body for r in ledger.rows.values()] == bodies[
            :expected_calls
        ]
        if expected_calls == 2:
            assert ledger.descriptions[1].attempt_kind == "fallback"
            assert ledger.descriptions[1].resolved_provider == "anthropic"
    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_real_non_text_body_survives_cap_refusal__b102(
    monkeypatch, real_service_factory_fixture
):
    import json

    from agentmap.services.llm.cost_calculator import LLMCostCalculator

    data = json.loads(body_for("anthropic"))
    data["content"] = [
        {"type": "thinking", "thinking": "discarded-body", "signature": "offline"}
    ]
    body = json.dumps(data).encode()
    calls = setup_transport(monkeypatch, body)
    service = real_service_factory_fixture("anthropic", "claude-sonnet-4-5")
    service._cost_calculator = LLMCostCalculator(
        {
            "catalog_version": "offline",
            "models": {
                "anthropic": {
                    "claude-sonnet-4-5": {
                        "currency": "USD",
                        "input_per_1m": 10000,
                        "output_per_1m": 10000,
                    }
                }
            },
        },
        Mock(),
    )
    ledger = Ledger()
    first = await invoke(service, "anthropic", "claude-sonnet-4-5", ledger)
    assert first.text_status == "non_text"
    with pytest.raises(AccountingRefusal, match="cap reached"):
        await invoke(service, "anthropic", "claude-sonnet-4-5", ledger)
    assert len(calls) == 1
    assert ledger.rows["1"].response_evidence.body == body
    assert ledger.rows["1"].cost_usd == Decimal("0.20")


def test_governed_streaming_client_is_rejected_before_construction__b102():
    from agentmap.exceptions import LLMConfigurationError

    factory = LLMClientFactory(Mock())
    with pytest.raises(LLMConfigurationError, match="non-streaming"):
        factory.get_or_create_client(
            "openai",
            {"api_key": "offline", "model": "test"},
            streaming=True,
            governed=True,
        )
    assert factory._clients == {}


@pytest.mark.asyncio
async def test_real_tool_wrapper_preserves_multiple_blocks_and_unknown_fields__b102(
    monkeypatch, real_service_factory_fixture
):
    import json

    data = json.loads(body_for("anthropic"))
    data["content"] = [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
        {
            "type": "tool_use",
            "id": "tool-offline",
            "name": "extract",
            "input": {"value": "café", "nullable": None},
        },
    ]
    data["stop_reason"] = "tool_use"
    body = (" \n" + json.dumps(data, ensure_ascii=False) + " \n").encode()
    calls = setup_transport(monkeypatch, body)
    ledger = Ledger()
    service = real_service_factory_fixture("anthropic", "claude-sonnet-4-5")
    result = await service.call_llm_async(
        [{"role": "user", "content": "synthetic request"}],
        provider="anthropic",
        model="claude-sonnet-4-5",
        tools=[
            {
                "name": "extract",
                "description": "offline",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
            }
        ],
        attempt_lifecycle=ledger,
    )
    assert len(calls) == 1
    assert result.text == "firstsecond"
    assert result.tool_calls[0].arguments == {"value": "café", "nullable": None}
    assert ledger.rows["1"].response_evidence.body == body


@pytest.mark.asyncio
async def test_real_available_body_survives_host_completion_failure__b102(
    monkeypatch, real_service_factory_fixture
):
    body = body_for("openai")
    calls = setup_transport(monkeypatch, body)
    ledger = Ledger()
    original = ledger.after_attempt
    failure = RuntimeError("private host failure")

    async def fail_completion(attempt_id, outcome):
        await original(attempt_id, outcome)
        raise failure

    ledger.after_attempt = fail_completion
    with pytest.raises(RuntimeError) as caught:
        await invoke(
            real_service_factory_fixture("openai", "test-model"),
            "openai",
            "test-model",
            ledger,
        )
    assert caught.value is failure
    assert len(calls) == 1
    assert ledger.rows["1"].response_evidence.body == body
    assert ledger.rows["1"].cost_usd == Decimal("0.20")
    assert ledger.events == [("begin", "1"), ("settle", "1")]
