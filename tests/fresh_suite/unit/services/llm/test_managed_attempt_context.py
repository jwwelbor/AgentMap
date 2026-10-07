"""B102 context and timeout boundaries for managed attempts."""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.services.llm_service import LLMService, _attempt_lifecycle
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
    call,
    observed_response,
    raw_response,
    service_with_client,
)


@pytest.mark.parametrize("managed", [False, True])
def test_budget_check_identifies_the_active_attempt_lifecycle__b102(
    managed: bool,
) -> None:
    service = object.__new__(LLMService)
    service._cost_calculator = SimpleNamespace(
        get_rates=lambda _provider, _model: None, catalog_version="test-v1"
    )
    token = _attempt_lifecycle.set(object() if managed else None)
    try:
        check = service._build_budget_check(
            [], "openai", "test-model", "fallback", None
        )
    finally:
        _attempt_lifecycle.reset(token)

    assert check.attempt_lifecycle_active is managed


@pytest.mark.asyncio
async def test_admission_and_settlement_are_outside_provider_timeout__b102(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def invoke_provider(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        events.append("provider")
        return raw_response()

    async def invoke_observed(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return observed_response(await invoke_provider(*args, **kwargs))

    client = Mock(ainvoke=AsyncMock(side_effect=invoke_observed))
    service = service_with_client(client)
    service._resilience_config["retry"]["attempt_timeout"] = 0.01
    ledger = Ledger()
    before, after = ledger.before_attempt, ledger.after_attempt

    async def tracked_before(description: Any) -> str:
        attempt_id = await before(description)
        events.append("admitted")
        return attempt_id

    async def tracked_after(identity: str, outcome: Any) -> None:
        await after(identity, outcome)
        events.append("settled")

    @asynccontextmanager
    async def provider_timeout(seconds: float) -> AsyncIterator[None]:
        assert seconds == 0.01
        assert events == ["admitted"]
        yield
        events.append("timeout_exited")

    monkeypatch.setattr(asyncio, "timeout", provider_timeout)
    ledger.before_attempt, ledger.after_attempt = tracked_before, tracked_after
    assert (await call(service, ledger)).text == "ok"
    assert ledger.rows["1"].cost_usd == Decimal("0.20")
    assert events == ["admitted", "provider", "timeout_exited", "settled"]
