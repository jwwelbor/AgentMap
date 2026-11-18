"""Canonical identities for LLM providers."""

_ALIASES = {"gpt": "openai", "claude": "anthropic", "gemini": "google"}


def canonicalize_provider(provider: str) -> str:
    """Resolve case variants and aliases to a provider key."""
    key = provider.lower()
    return _ALIASES.get(key, key)
