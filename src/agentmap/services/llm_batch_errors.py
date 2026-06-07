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


class LLMBatchParamConflictError(LLMServiceError):
    """
    Raised when the same logical batch parameter is set on two parameter
    surfaces with different values (AC-8: one canonical parameter path).

    The message names the spec_id, the logical parameter, and each conflicting
    surface with its value.  A parameter set on one surface — or on several
    surfaces with the SAME value — is accepted and not an error.

    Subclasses ``LLMServiceError`` so existing ``except LLMServiceError``
    callers still catch it.

    Decision: D-8 (spec.md § Canonical Parameter Resolution).
    """


class LLMBatchResultIntegrityError(LLMServiceError):
    """
    Raised when batch results cannot be safely correlated back to caller
    spec_ids — e.g. the provider returned a different number of inline
    responses than were submitted (positional demux would misattribute).

    Names the batch id, submitted count, and returned count.

    Only relevant for Gemini inline batches where positional demux is the
    only available correlation mechanism.  OpenAI and Anthropic demux by
    custom_id/key and are unaffected.

    Decision: D-9 (spec.md § Gemini Result Demux Integrity).
    """
