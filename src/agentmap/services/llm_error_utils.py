"""
LLM error classification utilities.

Shared by llm_service.py and llm_fallback_handler.py to classify provider
errors into typed exceptions and determine retryability.
"""

import re

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)

# Matches common API key patterns (sk-..., key-..., AIza..., etc.)
_SENSITIVE_RE = re.compile(
    r"""(?x)
    (?:sk-[a-zA-Z0-9]{20,})           |  # OpenAI-style
    (?:key-[a-zA-Z0-9]{20,})          |  # Generic key-prefixed
    (?:AIza[a-zA-Z0-9_-]{30,})        |  # Google-style
    (?:ant-api[a-zA-Z0-9_-]{20,})     |  # Anthropic-style
    (?:[a-zA-Z0-9_-]{32,})               # Long opaque tokens
    """
)


def _sanitize_error_message(error: Exception) -> str:
    """Return the error message with potential API keys redacted."""
    raw = str(error)
    return _SENSITIVE_RE.sub("[REDACTED]", raw)


def classify_llm_error(
    error: Exception, provider: str = "unknown"
) -> "LLMServiceError":
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

    safe_msg = _sanitize_error_message(error)

    # Dependency / import errors — not retryable
    if isinstance(error, ImportError) or any(
        kw in msg for kw in ("no module named", "dependencies", "install")
    ):
        return LLMDependencyError(f"Missing dependencies for {provider}: {safe_msg}")

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
        return LLMConfigurationError(
            f"Authentication failed for {provider}: {safe_msg}"
        )

    # Model / config errors — not retryable
    if any(kw in msg for kw in ("model not found", "invalid model", "model_not_found")):
        return LLMConfigurationError(
            f"Model configuration error for {provider}: {safe_msg}"
        )

    # Rate limit — retryable
    if any(
        kw in msg
        for kw in ("rate limit", "rate_limit", "429", "too many requests", "quota")
    ):
        return LLMRateLimitError(f"Rate limited by {provider}: {safe_msg}")

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
        return LLMTimeoutError(f"Timeout/connection error for {provider}: {safe_msg}")

    # Server errors — retryable
    if any(kw in msg for kw in ("500", "internal server error", "server error")):
        return LLMTimeoutError(f"Server error for {provider}: {safe_msg}")

    # Default: generic provider error (not retryable)
    return LLMProviderError(f"Provider {provider} error: {safe_msg}")


def is_retryable(error: Exception) -> bool:
    """
    Determine whether an already-classified error is worth retrying.

    This function assumes the error has already been classified by
    ``classify_llm_error`` and relies solely on exception type.

    Args:
        error: The (classified) exception to check.

    Returns:
        True if the error is transient and retrying may succeed.
    """
    return isinstance(error, (LLMTimeoutError, LLMRateLimitError))
