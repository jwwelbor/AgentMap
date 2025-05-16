# agentmap/config/__init__.py
"""
Configuration loader for AgentMap.
Supports loading from YAML or environment variable fallback.
"""

# Import and re-export core functions
from agentmap.config.base import load_config, get_config_section

# Import and re-export section functions
from agentmap.config.sections import (
    # Paths
    get_custom_agents_path,
    get_functions_path,
    get_compiled_graphs_path,
    get_csv_path,
    
    # LLM
    get_llm_config,
    
    # Storage
    get_storage_config_path,
    load_storage_config,
    
    # Prompts
    get_prompts_config,
    get_prompts_directory,
    get_prompt_registry_path,
)

# Export all public functions
__all__ = [
    'load_config',
    'get_config_section',
    'get_custom_agents_path',
    'get_functions_path',
    'get_compiled_graphs_path',
    'get_csv_path',
    'get_llm_config',
    'get_storage_config_path',
    'load_storage_config',
    'get_prompts_config',
    'get_prompts_directory',
    'get_prompt_registry_path',
]