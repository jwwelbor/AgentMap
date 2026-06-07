"""
Batch-specific error types for provider-native LLM batch execution (E05-F03).

All errors subclass ``LLMServiceError`` from the existing exception hierarchy.
They are data-only and carry no business logic.
"""

from agentmap.exceptions.service_exceptions import LLMServiceError


class LLMBatchUnsupportedProviderError(LLMServiceError):
    """
    Raised when the caller requests batch execution for a provider that does
    not support provider-native batching.

    Only ``"anthropic"`` is supported in the current implementation.
    Raised before any network call is made.
    """


class LLMBatchCancelNotSupportedError(LLMServiceError):
    """
    Raised when ``cancel_batch`` is called on a handle that is already in a
    terminal status (``"ended"`` or ``"expired"``).

    Canceling a terminal batch is a programming error; the caller should check
    ``handle.status`` before attempting to cancel.
    """


class LLMBatchNotReadyError(LLMServiceError):
    """
    Raised when ``fetch_batch_results`` is called on a batch whose status is
    not yet ``"ended"``.

    The caller must poll until status transitions to ``"ended"`` before
    fetching results.
    """


class LLMBatchExpiredError(LLMServiceError):
    """
    Raised when an operation is attempted on a batch that has expired.

    Anthropic expires batches that are not polled within their retention window.
    Results are no longer available once a batch has expired.
    """
