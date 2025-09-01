"""
System Storage Manager for AgentMap.

This module provides a manager for system-level storage services that use
the cache_folder as their base directory. Supports creating JSON and file
storage services with namespace isolation.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.file_service import FileStorageService
from agentmap.services.storage.json_service import JSONStorageService


class SystemStorageManager:
    """
    Manager for system-level storage services.
    Uses cache_folder as base directory for all system storage.
    """

    def __init__(
        self,
        app_config: AppConfigService,
        logging_service: LoggingService,
        file_path_service: FilePathService,
    ):
        self.app_config = app_config
        self.logging_service = logging_service
        self._logger = logging_service.get_class_logger(self)
        self.file_path_service = file_path_service

        # Get cache folder from app config
        self._cache_folder = app_config.get_cache_path()

        # Validate cache folder is safe
        if not self.file_path_service.validate_safe_path(self._cache_folder):
            raise ValueError(f"Unsafe cache folder: {self._cache_folder}")

        # Storage for service instances
        self._services: Dict[str, Any] = {}

        self._logger.info(
            f"SystemStorageManager initialized with cache_folder: {self._cache_folder}"
        )

    def get_json_storage(self, namespace: Optional[str] = None) -> JSONStorageService:
        """
        Get JSON storage service for system use.

        Args:
            namespace: Optional namespace for isolation (e.g., "bundles", "registry")

        Returns:
            JSON storage service configured for system use
        """
        # Treat empty string like None
        if not namespace:
            namespace = None

        cache_key = f"json_{namespace}" if namespace else "json"

        if cache_key not in self._services:
            # Calculate base directory
            if namespace:
                base_dir = str(Path(self._cache_folder) / namespace)
            else:
                base_dir = str(self._cache_folder)

            # Create minimal config for system storage
            config = {
                "base_directory": base_dir,
                "encoding": "utf-8",
                "indent": 2,
            }

            self._services[cache_key] = JSONStorageService(
                provider_name=(
                    f"system_json_{namespace}" if namespace else "system_json"
                ),
                configuration=config,
                logging_service=self.logging_service,
                base_directory=base_dir,
                file_path_service=self.file_path_service,
            )

        return self._services[cache_key]

    def get_file_storage(self, namespace: Optional[str] = None) -> FileStorageService:
        """
        Get file storage service for system use.

        Args:
            namespace: Optional namespace for isolation

        Returns:
            File storage service configured for system use
        """
        # Treat empty string like None
        if not namespace:
            namespace = None

        cache_key = f"file_{namespace}" if namespace else "file"

        if cache_key not in self._services:
            # Calculate base directory
            if namespace:
                base_dir = str(Path(self._cache_folder) / namespace)
            else:
                base_dir = str(self._cache_folder)

            # Create minimal config
            config = {
                "base_directory": base_dir,
            }

            self._services[cache_key] = FileStorageService(
                provider_name=(
                    f"system_file_{namespace}" if namespace else "system_file"
                ),
                configuration=config,
                logging_service=self.logging_service,
                base_directory=base_dir,
                file_path_service=self.file_path_service,
            )

        return self._services[cache_key]
