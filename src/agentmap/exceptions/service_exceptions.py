"""
LLM Service exceptions for AgentMap.
"""

from typing import Optional

from agentmap.exceptions.base_exceptions import (
    AgentMapException,
    ConfigurationException,
)


class LLMServiceError(AgentMapException):
    """Base exception for LLM service errors."""


class LLMProviderError(LLMServiceError):
    """Exception raised when there's an error with a specific LLM provider."""


class LLMConfigurationError(LLMServiceError):
    """Exception raised when there's a configuration error."""


class LLMDependencyError(LLMServiceError):
    """Exception raised when required dependencies are missing."""


class LLMTimeoutError(LLMProviderError):
    """Exception raised on timeout or connection errors (retryable)."""


class LLMRateLimitError(LLMProviderError):
    """Exception raised on 429/rate limit errors (retryable)."""


class LLMResolvedCallError(LLMServiceError):
    """Raised when execution fails after a concrete provider/model was resolved.

    Carries the resolved identity so the fan-out result builder (and any
    single-call caller) can populate ``LLMFanoutResult.provider``/``.model``
    with the provider that was actually attempted, not just the requested spec
    values.  ``cause`` is the underlying typed error (e.g. ``LLMProviderError``,
    ``LLMTimeoutError``) that triggered the failure.

    Raise sites:
    - ``LLMService._call_llm_async_direct`` — wraps all three failure exits
      (typed-error early raise, fallback exhaustion re-wrap, terminal raise)
      using the ``current_model`` resolved at that point.
    - ``LLMFallbackHandler.try_with_fallback_async`` — raised on tier exhaustion,
      carrying the last-attempted tier's identity (policy: last tier wins).

    Catch site:
    - ``LLMService._execute_fan_out_item`` — populates ``LLMFanoutResult.provider``
      and ``.model`` from this exception's attributes.  The bare
      ``except Exception`` block below it handles pre-resolution failures where
      no concrete provider was selected.
    """

    def __init__(
        self,
        resolved_provider: Optional[str],
        resolved_model: Optional[str],
        cause: BaseException,
    ) -> None:
        self.resolved_provider = resolved_provider
        self.resolved_model = resolved_model
        self.cause = cause
        super().__init__(
            f"{type(cause).__name__} after resolving "
            f"{resolved_provider}:{resolved_model} — {cause}"
        )


class LLMBudgetExceededError(LLMServiceError):
    """Raised by a host-registered budget guard to refuse a call before dispatch.

    Canonical typed refusal for ``LLMBudgetGuardProtocol.check_before_dispatch``
    (E05-F06 REQ-F-003). Subclassing ``LLMServiceError`` means a refusal is a
    non-retryable service error, not a transient provider failure: it must
    propagate to the caller unconditionally and never be routed into the
    fallback ladder, because falling back to a different tier would still
    spend money against the same policy the guard just refused.

    Not re-raised directly: ``LLMService._check_budget_before_dispatch``
    wraps whatever a guard raises -- typed (this class) or not -- in the
    internal ``BudgetGuardRefusal`` marker (``services/llm/_budget_guard_refusal.py``)
    so it can pass unrecognized through every blanket ``except Exception``
    net on the async dispatch/fallback path (direct, routing,
    telemetry-retry, and each ``LLMFallbackHandler`` fallback tier) without
    being reclassified as a transient provider failure or triggering a
    further fallback attempt. The wrapper is unwrapped back to the
    original exception at the single outermost boundary each entrypoint
    owns (``LLMService._dispatch_call_llm_async`` for ``call_llm_async``;
    ``LLMService.call_llm_stream_async`` for the streaming sibling) and
    never surfaces to a caller (see spec.md Component Change 7/8,
    NFR-F-003 -- pre-dispatch failures fail closed).
    """


class StorageConfigurationNotAvailableException(ConfigurationException):
    """Exception raised when storage configuration is not available or invalid."""


class LoggingNotConfiguredException(AgentMapException):
    """Exception raised when trying to use logging service before initialization."""


class FunctionResolutionException(AgentMapException):
    """Exception raised when a function cannot be resolved."""


class CacheNotFoundError(AgentMapException):
    """Exception raised when the availability cache file doesn't exist."""
