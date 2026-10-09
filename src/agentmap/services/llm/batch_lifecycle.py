"""Validation for batch-only LLM service lifecycle options."""

from collections.abc import Mapping, Sequence

from agentmap.exceptions import LLMConfigurationError, LLMServiceError
from agentmap.models.llm_batch import LLMBatchSubmitRequest
from agentmap.models.llm_execution import LLMRequest


def _validate_request_spec_shape(spec: object) -> None:
    if not isinstance(spec, LLMRequest) or not isinstance(
        spec.request_options, Mapping
    ):
        raise LLMServiceError(
            "requests must contain LLMRequest values with request_options mappings"
        )


def _validate_batch_request_shape(request: LLMBatchSubmitRequest) -> None:
    if not isinstance(request, LLMBatchSubmitRequest):
        raise LLMServiceError("request must be an LLMBatchSubmitRequest")
    if not isinstance(request.request_options, Mapping):
        raise LLMServiceError("request_options must be a mapping")
    if not isinstance(request.requests, Sequence):
        raise LLMServiceError("requests must be a sequence of LLMRequest values")
    for spec in request.requests:
        _validate_request_spec_shape(spec)


def _has_attempt_lifecycle(options: Mapping) -> bool:
    return bool(options) and "attempt_lifecycle" in options


def reject_batch_lifecycle_options(request: LLMBatchSubmitRequest) -> None:
    """Keep per-attempt callbacks on the single-call async entrypoint."""
    _validate_batch_request_shape(request)
    option_sets = [request.request_options] + [
        spec.request_options for spec in request.requests
    ]
    if any(_has_attempt_lifecycle(options) for options in option_sets):
        raise LLMConfigurationError(
            "attempt_lifecycle is supported only by call_llm_async"
        )
