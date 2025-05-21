"""
Feature flags for AgentMap agents.

This module defines flags that indicate which optional agent features
are available in the current environment.
"""
from agentmap.features_registry import features

# Global variables for backward compatibility
# These will be updated whenever the getter functions are called
HAS_LLM_AGENTS = False
HAS_STORAGE_AGENTS = False

def is_llm_enabled() -> bool:
    """Check if LLM agents are enabled."""
    global HAS_LLM_AGENTS
    # Update the global variable
    HAS_LLM_AGENTS = features.is_feature_enabled("llm")
    return HAS_LLM_AGENTS

def is_storage_enabled() -> bool:
    """Check if storage agents are enabled."""
    global HAS_STORAGE_AGENTS
    # Update the global variable
    HAS_STORAGE_AGENTS = features.is_feature_enabled("storage")
    return HAS_STORAGE_AGENTS

def enable_llm_agents():
    """Enable LLM agent functionality."""
    global HAS_LLM_AGENTS
    features.enable_feature("llm")
    HAS_LLM_AGENTS = True

def enable_storage_agents():
    """Enable storage agent functionality."""
    global HAS_STORAGE_AGENTS
    features.enable_feature("storage")
    HAS_STORAGE_AGENTS = True

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