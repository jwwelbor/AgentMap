"""B102 response identity and cancellation settlement boundaries."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
    observed_response,
    raw_response,
    service_with_client,
)


@pytest.mark.asyncio
async def test_invalid_returned_request_identity_is_unavailable__b102():
    raw = raw_response()
    raw.response_metadata = {"headers": {"x-request-id": 123}}
    client = Mock(ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw)))
    ledger = Ledger()

    await call(service_with_client(client), ledger)

    assert ledger.rows["1"].provider_request_id is None


@pytest.mark.asyncio
async def test_cancel_during_settlement_leaves_pending_intent_without_second_completion__b102():
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    service = service_with_client(client)
    ledger = Ledger()
    settling = asyncio.Event()

    async def interrupted(identity, outcome):
        settling.set()
        await asyncio.Event().wait()

    ledger.after_attempt = AsyncMock(side_effect=interrupted)
    task = asyncio.create_task(call(service, ledger))
    await asyncio.wait_for(settling.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert ledger.rows == {"1": None}
    assert ledger.after_attempt.await_count == 1
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(service, ledger)
    assert client.ainvoke.await_count == 1
