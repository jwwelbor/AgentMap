"""B102 provider-error confidentiality across observed real wrappers."""

import json
from contextlib import nullcontext
from unittest.mock import Mock

import httpx
import pytest

from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import Ledger
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    invoke,
    real_service,
)


def provider_error_markers():
    return {
        "body": "body-marker-b102",
        "authorization": "auth-marker-b102",
        "header": "header-marker-b102",
        "query": "query-marker-b102",
        "sdk_repr": "sdk-repr-marker-b102",
        "client_repr": "client-repr-marker-b102",
        "observer": "observer-marker-b102",
    }


def mark_sdk_error_repr(provider, monkeypatch, marker):
    """Seed the real provider exception representation without replacing it."""
    if provider == "openai":
        import openai

        error_type = openai.BadRequestError
    elif provider == "anthropic":
        import anthropic

        error_type = anthropic.BadRequestError
    else:
        from google.genai import errors as google_errors

        error_type = google_errors.ClientError
    seen = []
    original_init = error_type.__init__

    def capture_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        seen.append(self)

    monkeypatch.setattr(error_type, "__init__", capture_init)
    monkeypatch.setattr(error_type, "__repr__", lambda self: marker)
    return seen


def marked_error_transport(monkeypatch, provider, markers, body):
    """Run supported wrappers against fake HTTP and refuse alternate network."""
    import aiohttp

    requests = []
    hosts = {
        "openai": "api.openai.com",
        "anthropic": "api.anthropic.com",
        "google": "generativelanguage.googleapis.com",
    }

    class SDKVisibleResponse(httpx.Response):
        def __repr__(self):
            return "response-repr-marker-b102"

    def send(transport, request):
        if requests or request.url.host != hosts[provider]:
            raise AssertionError("unexpected fake-HTTP request")
        request.url = request.url.copy_add_param("private", markers["query"])
        requests.append(request)
        return SDKVisibleResponse(
            400,
            content=body,
            headers={
                "content-type": "application/json",
                "x-private": markers["header"],
            },
            request=request,
        )

    async def asend(transport, request):
        return send(transport, request)

    async def refuse_aiohttp(*args, **kwargs):
        raise AssertionError("unstubbed aiohttp request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", asend)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", refuse_aiohttp)
    monkeypatch.setattr(
        httpx.AsyncClient, "__repr__", lambda self: markers["client_repr"]
    )
    return requests


def assert_error_markers_confined(
    markers, body, outcome, caught, service, span, caplog
):
    projections = (str(outcome), repr(outcome), str(caught), repr(caught))
    projections += (str(service._logger.mock_calls), str(span.mock_calls), caplog.text)
    pending = [caught]
    seen = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        projections += (str(error), repr(error))
        pending.extend(e for e in (error.__cause__, error.__context__) if e is not None)
    for name, marker in {
        **markers,
        "response_repr": "response-repr-marker-b102",
    }.items():
        if name == "body":
            assert marker in body.decode()
        else:
            assert marker not in body.decode()
        assert all(marker not in projection for projection in projections), name


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("capture_failure", [False, True])
async def test_provider_error_secrets_reach_only_response_evidence__b102(
    provider, model, capture_failure, monkeypatch, caplog
):
    """A real SDK error must not project transport objects into public sinks."""
    from agentmap.exceptions import LLMResolvedCallError
    from agentmap.services.llm import response_observer
    from agentmap.services.llm.response_observer import ResponseCaptureFailure
    from agentmap.services.telemetry.otel_telemetry_service import OTELTelemetryService

    markers = provider_error_markers()
    body = json.dumps({"error": {"message": markers["body"], "code": 400}}).encode()
    seen_sdk_errors = mark_sdk_error_repr(provider, monkeypatch, markers["sdk_repr"])
    requests = marked_error_transport(monkeypatch, provider, markers, body)
    if capture_failure:
        monkeypatch.setattr(
            response_observer,
            "_evidence",
            Mock(side_effect=ValueError(markers["observer"])),
        )

    telemetry = OTELTelemetryService()
    span = Mock()
    telemetry._tracer = Mock(start_as_current_span=Mock(return_value=nullcontext(span)))
    service = real_service(provider, model)
    service._telemetry_service = telemetry
    service._get_provider_config = Mock(
        return_value={"api_key": markers["authorization"], "model": model}
    )
    ledger = Ledger()
    expected_error = ResponseCaptureFailure if capture_failure else LLMResolvedCallError
    with pytest.raises(expected_error) as caught:
        await invoke(service, provider, model, ledger)

    assert len(requests) == 1
    assert ledger.events == [("begin", "1"), ("settle", "1")]
    outcome = ledger.rows["1"]
    assert outcome.response_evidence.body == body
    assert outcome.response_evidence.status == "available"
    assert outcome.classification == (
        "capture_error" if capture_failure else "provider_error"
    )
    assert len(seen_sdk_errors) == 1
    assert repr(seen_sdk_errors[0]) == markers["sdk_repr"]
    assert_error_markers_confined(
        markers, body, outcome, caught.value, service, span, caplog
    )
    assert span.record_exception.call_count == 1
