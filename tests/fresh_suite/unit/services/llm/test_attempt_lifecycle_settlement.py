"""B102 response identity and cancellation settlement boundaries."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import LLMTimeoutError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
    observed_response,
    raw_response,
    service_with_client,
)
from tests.runtime_manager_test_support import cancel_tasks_for_test


class ControlFlowFailure(BaseException):
    pass


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
        await asyncio.wait_for(asyncio.Event().wait(), timeout=10)

    ledger.after_attempt = AsyncMock(side_effect=interrupted)
    task = asyncio.create_task(call(service, ledger))
    try:
        await asyncio.wait_for(settling.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert ledger.rows == {"1": None}
        assert ledger.after_attempt.await_count == 1
        with pytest.raises(AccountingRefusal, match="unresolved charge"):
            await call(service, ledger)
        assert client.ainvoke.await_count == 1
    finally:
        await cancel_tasks_for_test(task)


@pytest.mark.asyncio
async def test_provider_control_flow_failure_settles_once_and_propagates_exactly__b102():
    failure = ControlFlowFailure("provider control flow")
    client = Mock(ainvoke=AsyncMock(side_effect=failure))
    ledger = Ledger()

    with pytest.raises(ControlFlowFailure) as caught:
        await call(service_with_client(client), ledger)

    assert caught.value is failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].classification == "provider_error"


@pytest.mark.asyncio
async def test_measurement_control_flow_failure_settles_and_retains_request_id__b102():
    from unittest.mock import patch

    failure = ControlFlowFailure("measurement control flow")
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    ledger = Ledger()

    with patch(
        "agentmap.services.llm.governed_accounting.capture_measurements",
        side_effect=failure,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service_with_client(client), ledger)

    assert caught.value is failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].provider_request_id == "provider-request"


@pytest.mark.asyncio
async def test_evidence_calculation_control_flow_retains_later_request_id__b102():
    from unittest.mock import patch

    failure = ControlFlowFailure("evidence calculation control flow")
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    ledger = Ledger()

    with patch(
        "agentmap.services.llm.governed_accounting.governed_cost",
        side_effect=failure,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service_with_client(client), ledger)

    assert caught.value is failure
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].usage.input_tokens == 10
    assert ledger.rows["1"].provider_request_id == "provider-request"


@pytest.mark.asyncio
async def test_later_raw_evidence_failure_supersedes_measurement_failure__b102():
    from unittest.mock import patch

    measurement_error = RuntimeError("measurement unavailable")
    control_failure = ControlFlowFailure("request identity control flow")
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    ledger = Ledger()
    service = service_with_client(client)
    service._extract_provider_request_id = Mock(side_effect=control_failure)

    with patch(
        "agentmap.services.llm.governed_accounting.capture_measurements",
        side_effect=measurement_error,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service, ledger)

    assert caught.value is control_failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].classification == "receipt_error"


@pytest.mark.asyncio
async def test_later_raw_request_id_failure_supersedes_cost_error__b102():
    from unittest.mock import patch

    cost_error = RuntimeError("cost calculation failed")
    control_failure = ControlFlowFailure("request identity control flow")
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    ledger = Ledger()
    service = service_with_client(client)
    service._extract_provider_request_id = Mock(side_effect=control_failure)

    with patch(
        "agentmap.services.llm.governed_accounting.governed_cost",
        side_effect=cost_error,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service, ledger)

    assert caught.value is control_failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]


@pytest.mark.asyncio
async def test_raw_measurement_failure_supersedes_retryable_provider_failure__b102():
    from unittest.mock import patch

    provider_error = LLMTimeoutError("provider timeout")
    control_failure = ControlFlowFailure("measurement control flow")
    client = Mock(ainvoke=AsyncMock(side_effect=provider_error))
    ledger = Ledger()

    with patch(
        "agentmap.services.llm.governed_accounting.capture_measurements",
        side_effect=control_failure,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service_with_client(client), ledger)

    assert caught.value is control_failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].classification == "receipt_error"


@pytest.mark.asyncio
async def test_response_builder_control_flow_failure_settles_once__b102():
    from unittest.mock import patch

    failure = ControlFlowFailure("response builder control flow")
    client = Mock(
        ainvoke=AsyncMock(side_effect=lambda _: observed_response(raw_response()))
    )
    ledger = Ledger()

    with patch(
        "agentmap.services.llm_service.normalize_response_content",
        side_effect=failure,
    ):
        with pytest.raises(ControlFlowFailure) as caught:
            await call(service_with_client(client), ledger)

    assert caught.value is failure
    assert client.ainvoke.await_count == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert ledger.rows["1"].classification == "normalization_error"
