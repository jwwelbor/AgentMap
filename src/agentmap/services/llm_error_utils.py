"""
LLM error classification utilities.

Shared by llm_service.py and llm_fallback_handler.py to classify provider
errors into typed exceptions and determine retryability.
"""

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def classify_llm_error(
    error: Exception, provider: str = "unknown"
) -> "LLMProviderError | LLMDependencyError | LLMConfigurationError":
    """
    Classify a raw provider exception into a typed AgentMap exception.

    Args:
        error: The original exception from an LLM provider call.
        provider: Provider name for context in error messages.

    Returns:
        A typed LLM exception (subclass of LLMServiceError).
    """
    msg = str(error).lower()

    # Already one of ours — pass through
    if isinstance(
        error,
        (
            LLMTimeoutError,
            LLMRateLimitError,
            LLMConfigurationError,
            LLMDependencyError,
            LLMProviderError,
        ),
    ):
        return error

    # Dependency / import errors — not retryable
    if isinstance(error, ImportError) or any(
        kw in msg for kw in ("no module named", "dependencies", "install")
    ):
        return LLMDependencyError(f"Missing dependencies for {provider}: {error}")

    # Authentication / config errors — not retryable
    if any(
        kw in msg
        for kw in (
            "api_key",
            "api key",
            "authentication",
            "unauthorized",
            "invalid api",
            "permission denied",
            "forbidden",
        )
    ):
        return LLMConfigurationError(f"Authentication failed for {provider}: {error}")

    # Model / config errors — not retryable
    if any(kw in msg for kw in ("model not found", "invalid model", "model_not_found")):
        return LLMConfigurationError(
            f"Model configuration error for {provider}: {error}"
        )

    # Rate limit — retryable
    if any(
        kw in msg
        for kw in ("rate limit", "rate_limit", "429", "too many requests", "quota")
    ):
        return LLMRateLimitError(f"Rate limited by {provider}: {error}")

    # Timeout / connection — retryable
    if any(
        kw in msg
        for kw in (
            "timeout",
            "timed out",
            "connection error",
            "connection reset",
            "connection refused",
            "connect timeout",
            "read timeout",
            "server disconnected",
            "502",
            "503",
            "504",
        )
    ):
        return LLMTimeoutError(f"Timeout/connection error for {provider}: {error}")

    # Server errors — retryable
    if any(kw in msg for kw in ("500", "internal server error", "server error")):
        return LLMTimeoutError(f"Server error for {provider}: {error}")

    # Default: generic provider error (not retryable)
    return LLMProviderError(f"Provider {provider} error: {error}")


def is_retryable(error: Exception) -> bool:
    """
    Determine whether an error is worth retrying.

    Args:
        error: The exception to check.

    Returns:
        True if the error is transient and retrying may succeed.
    """
    if isinstance(error, (LLMTimeoutError, LLMRateLimitError)):
        return True
    if isinstance(error, (LLMConfigurationError, LLMDependencyError)):
        return False
    # For unclassified errors, check the message for retryable patterns
    msg = str(error).lower()
    retryable_patterns = (
        "timeout",
        "timed out",
        "rate limit",
        "429",
        "502",
        "503",
        "504",
        "connection",
        "server error",
        "too many requests",
    )
    return any(kw in msg for kw in retryable_patterns)
