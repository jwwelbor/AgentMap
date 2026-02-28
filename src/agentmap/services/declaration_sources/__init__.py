"""
Declaration source implementations for AgentMap.

Provides pluggable architecture for loading agent and service declarations
from different sources (Python dicts, YAML files, etc.).
"""

from agentmap.services.declaration_sources.base import DeclarationSource
from agentmap.services.declaration_sources.custom_agent_yaml_source import (
    CustomAgentYAMLSource,
)
from agentmap.services.declaration_sources.host_service_yaml_source import (
    HostServiceYAMLSource,
)
from agentmap.services.declaration_sources.python_source import PythonDeclarationSource
from agentmap.services.declaration_sources.yaml_source import YAMLDeclarationSource

__all__ = [
    "DeclarationSource",
    "PythonDeclarationSource",
    "YAMLDeclarationSource",
    "HostServiceYAMLSource",
    "CustomAgentYAMLSource",
]
