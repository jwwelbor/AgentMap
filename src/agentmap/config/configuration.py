# agentmap/config/configuration.py
from pathlib import Path
from typing import Any, Dict, Optional, Union, TypeVar

T = TypeVar('T')


class Configuration:
    """Unified configuration access for AgentMap."""

    def __init__(self, config_data: Dict[str, Any]):
        self._config = config_data

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get a configuration section."""
        return self._config.get(section, {})

    def get_value(self, path: str, default: T = None) -> T:
        """Get a specific configuration value using dot notation."""
        parts = path.split('.')
        current = self._config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def get_path_value(self, section: str, key: str, default: str) -> Path:
        """Get a path value from a section."""
        section_data = self.get_section(section)
        return Path(section_data.get(key, default))

    # Common path accessors for convenience
    def get_custom_agents_path(self) -> Path:
        """Get the path for custom agents."""
        return self.get_path_value("paths", "custom_agents", "agentmap/agents/custom")

    def get_functions_path(self) -> Path:
        """Get the path for functions."""
        return self.get_path_value("paths", "functions", "agentmap/functions")

    def get_compiled_graphs_path(self) -> Path:
        """Get the path for compiled graphs."""
        return self.get_path_value("paths", "compiled_graphs", "compiled_graphs")

    def get_csv_path(self) -> Path:
        """Get the path for the workflow CSV file."""
        return Path(self._config.get("csv_path", "examples/SingleNodeGraph.csv"))

    def get_llm_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for a specific LLM provider."""
        return self.get_section("llm").get(provider, {})