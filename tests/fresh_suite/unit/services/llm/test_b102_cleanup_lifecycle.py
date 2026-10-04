"""B102: public governed outcomes retain sanitized response-cleanup failure."""

import asyncio
from unittest.mock import Mock

import httpx
import pytest

from agentmap.services.llm.response_observer import (
    ResponseCaptureFailure,
    observe_async_response,
    observe_response,
)
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
    call,
    service_with_client,
)
from tests.fresh_suite.unit.services.llm.test_b102_response_cleanup import (
    FailingAsyncStream,
    FailingSyncStream,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_public_read_failure_retains_cleanup_discriminator__b102(
    mode, cleanup_fails
):
    failure = httpx.ReadError("private-read-secret")
    stream = (
        FailingSyncStream(failure) if mode == "sync" else FailingAsyncStream(failure)
    )
    if cleanup_fails:
        if mode == "sync":
            stream.close = lambda: (_ for _ in ()).throw(
                RuntimeError("private-cleanup-secret")
            )
        else:

            async def fail_close():
                raise RuntimeError("private-cleanup-secret")

            stream.aclose = fail_close
    response = httpx.Response(200, stream=stream)

    async def invoke(*args, **kwargs):
        if mode == "sync":
            observe_response(response)
        else:
            await observe_async_response(response)

    service = service_with_client(Mock(ainvoke=invoke))
    ledger = Ledger()
    with pytest.raises(ResponseCaptureFailure) as caught:
        await call(service, ledger)
    outcome = ledger.rows["1"]
    assert outcome.cleanup_failed is cleanup_fails
    assert caught.value.cleanup_failed is cleanup_fails
    assert outcome.response_evidence.body == b"partial"
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert "private-" not in repr(outcome) + repr(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_public_cancellation_retains_cleanup_discriminator__b102(
    mode, cleanup_fails
):
    failure = asyncio.CancelledError("private-cancel-secret")
    stream = (
        FailingSyncStream(failure) if mode == "sync" else FailingAsyncStream(failure)
    )
    if cleanup_fails:
        if mode == "sync":
            stream.close = lambda: (_ for _ in ()).throw(
                RuntimeError("private-cleanup-secret")
            )
        else:

            async def fail_close():
                raise RuntimeError("private-cleanup-secret")

            stream.aclose = fail_close
    response = httpx.Response(200, stream=stream)

    async def invoke(*args, **kwargs):
        if mode == "sync":
            observe_response(response)
        else:
            await observe_async_response(response)

    service = service_with_client(Mock(ainvoke=invoke))
    ledger = Ledger()
    with pytest.raises(asyncio.CancelledError):
        await call(service, ledger)
    outcome = ledger.rows["1"]
    assert outcome.cleanup_failed is cleanup_fails
    assert outcome.response_evidence.body == b"partial"
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    assert "private-" not in repr(outcome)
