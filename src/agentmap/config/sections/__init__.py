"""
Configuration sections for AgentMap.
"""

# Import section functions for re-export
from agentmap.config.sections.paths import (
    get_custom_agents_path,
    get_functions_path,
    get_compiled_graphs_path,
    get_csv_path
)

from agentmap.config.sections.llm import get_llm_config

from agentmap.config.sections.routing import (
    get_routing_config,
    get_routing_matrix,
    get_task_types_config,
    is_routing_enabled,
    RoutingConfigSection
)

from agentmap.config.sections.storage import (
    get_storage_config_path,
    load_storage_config
)

from agentmap.config.sections.prompts import (
    get_prompts_config,
    get_prompts_directory,
    get_prompt_registry_path
)

# Export all functions
__all__ = [
    'get_custom_agents_path',
    'get_functions_path',
    'get_compiled_graphs_path',
    'get_csv_path',
    'get_llm_config',
    'get_routing_config',
    'get_routing_matrix',
    'get_task_types_config',
    'is_routing_enabled',
    'RoutingConfigSection',
    'get_storage_config_path',
    'load_storage_config',
    'get_prompts_config',
    'get_prompts_directory',
    'get_prompt_registry_path',
]