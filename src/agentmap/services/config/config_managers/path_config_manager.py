"""Path configuration manager."""

from pathlib import Path
from typing import Optional

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class PathConfigManager(BaseConfigManager):
    """
    Configuration manager for path-related settings.

    Handles all path accessors including cache, custom agents, functions,
    metadata bundles, CSV repository, prompts, and storage paths.
    """

    def get_cache_path(self) -> Path:
        """Get the path for cache directory."""
        return Path(self.get_value("paths.cache", "agentmap_data/cache"))

    def get_custom_agents_path(self) -> Path:
        """Get the path for custom agents."""
        return Path(
            self.get_value("paths.custom_agents", "agentmap_data/custom_agents")
        )

    def get_functions_path(self) -> Path:
        """Get the path for functions."""
        return Path(self.get_value("paths.functions", "agentmap_data/custom_functions"))

    def get_metadata_bundles_path(self) -> Path:
        """Get the path for metadata bundles (does not create directory)."""
        return Path(
            self.get_value("paths.metadata_bundles", "agentmap_data/metadata_bundles")
        )

    def get_csv_repository_path(self) -> Path:
        """Get the path for the CSV repository directory where workflows are stored (does not create directory)."""
        return Path(self.get_value("paths.csv_repository", "agentmap_data/workflows"))

    def get_prompts_directory(self) -> Path:
        """Get the path for the prompts directory."""
        return Path(self.get_value("prompts.directory", "agentmap_data/prompts"))

    def get_prompt_registry_path(self) -> Path:
        """Get the path for the prompt registry file."""
        return Path(
            self.get_value(
                "prompts.registry_file", "agentmap_data/prompts/prompt_registry.yaml"
            )
        )

    def get_storage_config_path(self) -> Optional[Path]:
        """Get the path for the storage configuration file."""
        storage_path = self.get_value("storage_config_path")
        return Path(storage_path) if storage_path else None
