# agentmap/agents/features.py
"""
Feature flags for AgentMap agents.

This module defines flags that indicate which optional agent features
are available in the current environment. This module should have minimal
dependencies to avoid circular imports.
"""
from agentmap.features_registry import features

# Flag getters with backward compatibility
def is_llm_enabled() -> bool:
    """Check if LLM agents are enabled."""
    return features.is_feature_enabled("llm")

def is_storage_enabled() -> bool:
    """Check if storage agents are enabled."""
    return features.is_feature_enabled("storage")

# For backward compatibility - these properties read from the registry
@property
def HAS_LLM_AGENTS() -> bool:
    """Property for backward compatibility."""
    return features.is_feature_enabled("llm")

@property
def HAS_STORAGE_AGENTS() -> bool:
    """Property for backward compatibility."""
    return features.is_feature_enabled("storage")

# Feature enablers
def enable_llm_agents():
    """Enable LLM agent functionality."""
    features.enable_feature("llm")

def enable_storage_agents():
    """Enable storage agent functionality."""
    features.enable_feature("storage")

# Provider availability
def set_provider_available(provider: str, available: bool = True):
    """Set availability for a specific LLM provider."""
    features.set_provider_available("llm", provider, available)

def is_provider_available(provider: str) -> bool:
    """Check if a specific LLM provider is available."""
    return features.is_provider_available("llm", provider)

def get_available_providers():
    """Get a list of available LLM providers."""
    return features.get_available_providers("llm")