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


class StorageConfigurationNotAvailableException(ConfigurationException):
    """Exception raised when storage configuration is not available or invalid."""


class LoggingNotConfiguredException(AgentMapException):
    """Exception raised when trying to use logging service before initialization."""


class FunctionResolutionException(AgentMapException):
    """Exception raised when a function cannot be resolved."""


class CacheNotFoundError(AgentMapException):
    """Exception raised when the availability cache file doesn't exist."""
