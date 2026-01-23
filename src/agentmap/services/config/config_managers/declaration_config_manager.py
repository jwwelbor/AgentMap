"""Declaration configuration manager."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class DeclarationConfigManager(BaseConfigManager):
    """
    Configuration manager for declaration settings.

    Handles declaration paths, host declaration paths, validation settings,
    and namespace configuration.
    """

    def get_declaration_paths(self) -> List[Path]:
        """
        Get list of custom declaration directories.

        Returns:
            List of Path objects for custom declaration directories
        """
        declaration_paths_config = self.get_value("declarations.custom", [])

        declaration_paths = []
        for path_config in declaration_paths_config:
            try:
                # Handle both string and dict formats
                if isinstance(path_config, str):
                    path = path_config
                elif isinstance(path_config, dict) and "path" in path_config:
                    path = path_config["path"]
                else:
                    self._logger.warning(
                        f"[DeclarationConfigManager] Invalid declaration path config: {path_config}"
                    )
                    continue

                # Expand environment variables
                expanded_path = os.path.expandvars(path)
                declaration_paths.append(Path(expanded_path))

            except Exception as e:
                self._logger.warning(
                    f"[DeclarationConfigManager] Invalid declaration path '{path_config}': {e}"
                )

        # Log configured paths
        if declaration_paths:
            path_strs = [str(p) for p in declaration_paths]
            self._logger.debug(
                f"[DeclarationConfigManager] Using custom declaration paths: {path_strs}"
            )
        else:
            self._logger.debug(
                "[DeclarationConfigManager] No custom declaration paths configured"
            )

        return declaration_paths

    def get_host_declaration_paths(self) -> List[Path]:
        """
        Get list of host application declaration directories.

        Returns:
            List of Path objects for host declaration directories
        """
        if not self.is_host_declarations_enabled():
            return []

        host_paths_config = self.get_value("declarations.host.paths", [])

        host_paths = []
        for path in host_paths_config:
            try:
                # Expand environment variables
                expanded_path = os.path.expandvars(path)
                host_paths.append(Path(expanded_path))
            except Exception as e:
                self._logger.warning(
                    f"[DeclarationConfigManager] Invalid host declaration path '{path}': {e}"
                )

        # Log configured paths
        if host_paths:
            path_strs = [str(p) for p in host_paths]
            self._logger.debug(
                f"[DeclarationConfigManager] Using host declaration paths: {path_strs}"
            )
        else:
            self._logger.debug(
                "[DeclarationConfigManager] No host declaration paths configured"
            )

        return host_paths

    def is_host_declarations_enabled(self) -> bool:
        """
        Check if host declarations are enabled.

        Returns:
            True if host declarations are enabled
        """
        return self.get_value("declarations.host.enabled", False)

    def get_host_declarations_namespace(self) -> Optional[str]:
        """
        Get the namespace for host declarations.

        Returns:
            Namespace string or None if not configured
        """
        return self.get_value("declarations.host.namespace", None)

    def get_declaration_validation_settings(self) -> Dict[str, Any]:
        """
        Get declaration validation settings.

        Returns:
            Dictionary with validation settings
        """
        validation_config = self.get_value("declarations.validation", {})

        # Default validation settings
        defaults = {
            "strict": False,
            "warn_on_missing": True,
            "require_versions": False,
            "allow_unknown_protocols": True,
            "validate_class_paths": False,
        }

        # Merge with defaults
        merged_settings = self._merge_with_defaults(validation_config, defaults)

        # Log validation settings
        if validation_config:
            self._logger.debug(
                f"[DeclarationConfigManager] Declaration validation settings: strict={merged_settings['strict']}, "
                f"warn_on_missing={merged_settings['warn_on_missing']}"
            )
        else:
            self._logger.debug(
                "[DeclarationConfigManager] Using default declaration validation settings"
            )

        return merged_settings
