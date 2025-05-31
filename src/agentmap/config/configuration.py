# agentmap/config/configuration.py
from pathlib import Path
from typing import Any, Dict, Optional, Union, TypeVar
import yaml

T = TypeVar('T')

class Configuration:
    """Unified configuration access for AgentMap with full feature set."""

    def __init__(self, config_data: Dict[str, Any]):
        self._config = config_data

    # # Core access methods
    def get_section(self, section: str, default: T = None) -> Dict[str, Any]:
        """Get a configuration section."""
        return self._config.get(section, default)

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

    # Path accessors (replacing agentmap.config.sections.paths)
    def get_custom_agents_path(self) -> Path:
        """Get the path for custom agents."""
        return Path(self.get_value("paths.custom_agents", "agentmap/agents/custom"))

    def get_functions_path(self) -> Path:
        """Get the path for functions."""
        return Path(self.get_value("paths.functions", "agentmap/functions"))

    def get_compiled_graphs_path(self) -> Path:
        """Get the path for compiled graphs."""
        return Path(self.get_value("paths.compiled_graphs", "compiled_graphs"))

    def get_csv_path(self) -> Path:
        """Get the path for the workflow CSV file."""
        return Path(self.get_value("csv_path", "examples/SingleNodeGraph.csv"))

    def get_logging_config(self) -> Dict[str, Any]:
        """Get the prompt configuration."""
        return self.get_section("logging")

    # LLM accessors (replacing agentmap.config.sections.llm)
    def get_llm_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for a specific LLM provider."""
        return self.get_value(f"llm.{provider}", {})

    # Prompts accessors (replacing agentmap.config.sections.prompts)  
    def get_prompts_config(self) -> Dict[str, Any]:
        """Get the prompt configuration."""
        return self.get_section("prompts")

    def get_prompts_directory(self) -> Path:
        """Get the path for the prompts directory."""
        return Path(self.get_value("prompts.directory", "prompts"))

    def get_prompt_registry_path(self) -> Path:
        """Get the path for the prompt registry file."""
        return Path(self.get_value("prompts.registry_file", "prompts/registry.yaml"))

    # Storage accessors (replacing agentmap.config.sections.storage)
    def get_storage_config_path(self) -> Path:
        """Get the path for the storage configuration file."""
        return Path(self.get_value("storage_config_path", "storage_config.yaml"))

    def load_storage_config(self) -> Dict[str, Any]:
        """Load storage configuration from YAML file."""
        storage_config_path = self.get_storage_config_path()
        
        if storage_config_path.exists():
            with storage_config_path.open() as f:
                storage_config = yaml.safe_load(f) or {}
        else:
            storage_config = {}
        
        # Default storage configuration
        defaults = {
            "csv": {"default_directory": "data/csv", "collections": {}},
            "vector": {"default_provider": "local", "collections": {}},
            "kv": {"default_provider": "local", "collections": {}}
        }
        
        # Merge with defaults
        return self._merge_with_defaults(storage_config, defaults)

    # Execution accessors
    def get_execution_config(self) -> Dict[str, Any]:
        """Get execution configuration."""
        return self.get_section("execution")

    def get_tracking_config(self) -> Dict[str, Any]:
        """Get tracking configuration."""
        return self.get_value("execution.tracking", {})

    # Utility methods
    def _merge_with_defaults(self, config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration with defaults."""
        result = defaults.copy()
        
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                result[key] = value
        
        return result