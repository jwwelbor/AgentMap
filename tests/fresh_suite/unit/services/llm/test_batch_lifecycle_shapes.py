"""Malformed batch requests fail through the service validation contract."""

from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_batch import LLMBatchSubmitRequest
from agentmap.models.llm_execution import LLMRequest
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    service_with_client,
)


@pytest.mark.parametrize(
    ("malformed_shape", "message"),
    [
        ("request", "LLMBatchSubmitRequest"),
        ("request_options", "request_options must be a mapping"),
        ("requests", "requests must be a sequence"),
        ("request_spec", "LLMRequest values"),
        ("spec_options", "request_options mappings"),
    ],
)
def test_batch_rejects_malformed_request_shapes__b102(malformed_shape, message):
    svc = service_with_client(Mock())
    adapter = Mock()
    svc._batch_adapters = {"openai": adapter}
    spec = LLMRequest(
        request_id="one",
        messages=[{"role": "user", "content": "synthetic"}],
    )
    request: object = LLMBatchSubmitRequest(
        provider="openai", model="test-model", requests=[spec]
    )
    if malformed_shape == "request":
        request = object()
    elif malformed_shape == "request_options":
        object.__setattr__(request, "request_options", None)
    elif malformed_shape == "requests":
        object.__setattr__(request, "requests", None)
    elif malformed_shape == "request_spec":
        object.__setattr__(request, "requests", [object()])
    elif malformed_shape == "spec_options":
        object.__setattr__(spec, "request_options", None)

    with pytest.raises(LLMServiceError, match=message):
        getattr(svc, "submit_batch")(request)
    adapter.submit.assert_not_called()
