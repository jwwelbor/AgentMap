# agentmap/agents/features.py
"""
Feature flags for AgentMap agents.

This module defines flags that indicate which optional agent features
are available in the current environment. This module should have minimal
dependencies to avoid circular imports.
"""

# Initialize feature flags
HAS_LLM_AGENTS = False
HAS_STORAGE_AGENTS = False

# Will be set to True in agents/__init__.py if dependencies are available
def enable_llm_agents():
    global HAS_LLM_AGENTS
    HAS_LLM_AGENTS = True

def enable_storage_agents():
    global HAS_STORAGE_AGENTS
    HAS_STORAGE_AGENTS = True