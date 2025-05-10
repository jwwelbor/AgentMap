"""
Prompt management for AgentMap.

This module provides utilities for loading and managing prompts from
various sources, including files, YAML configs, and a prompt registry.
"""

# Export main functionality
from agentmap.prompts.manager import (
    PromptManager,
    get_prompt_manager,
    resolve_prompt
)

# Export version info
__version__ = "0.1.0"

# Define public API
__all__ = [
    'PromptManager',
    'get_prompt_manager',
    'resolve_prompt',
]