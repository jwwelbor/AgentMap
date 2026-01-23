"""
Template loading and caching functionality for IndentedTemplateComposer.

Handles loading templates from embedded resources or filesystem with caching support.
"""

import importlib.resources
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class TemplateLoader:
    """
    Handles template loading from various sources with caching support.

    Loads templates from:
    1. Embedded package resources (primary)
    2. Filesystem prompts directory (fallback)

    Provides simple LRU-style caching for performance.
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize template loader with dependencies.

        Args:
            app_config_service: Application configuration service
            logging_service: Logging service for error handling
        """
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

        # Template caching
        self._template_cache: Dict[str, str] = {}
        self._cache_stats = {"hits": 0, "misses": 0}
        self._template_base_package = "agentmap.templates.system.scaffold"

        self.logger.debug("[TemplateLoader] Initialized with caching enabled")

    def load_template(self, template_path: str) -> str:
        """
        Load template content with caching support.

        Args:
            template_path: Template path (e.g., "scaffold/master_template.txt" or "file:scaffold/master_template.txt")

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be loaded from any source
        """
        # Normalize template path (remove "file:" prefix if present)
        normalized_path = template_path.replace("file:", "").strip()

        # Check cache first
        if normalized_path in self._template_cache:
            self._cache_stats["hits"] += 1
            self.logger.trace(
                f"[TemplateLoader] Cache hit for template: {normalized_path}"
            )
            return self._template_cache[normalized_path]

        # Cache miss - load template
        self._cache_stats["misses"] += 1
        self.logger.debug(f"[TemplateLoader] Loading template: {normalized_path}")

        try:
            content = self._discover_and_load(normalized_path)

            # Cache the loaded content
            self._template_cache[normalized_path] = content

            self.logger.debug(
                f"[TemplateLoader] Successfully loaded and cached template: {normalized_path}"
            )
            return content

        except Exception as e:
            self.logger.error(
                f"[TemplateLoader] Failed to load template {normalized_path}: {e}"
            )
            raise

    def _discover_and_load(self, template_path: str) -> str:
        """
        Discover and load template from embedded resources or filesystem.

        Args:
            template_path: Relative template path (e.g., "scaffold/master_template.txt")

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be found in any location
        """
        # Try loading from embedded resources first
        try:
            content = self._load_from_embedded_resources(template_path)
            if content:
                return content
        except Exception as e:
            self.logger.debug(
                f"[TemplateLoader] Embedded resource loading failed for {template_path}: {e}"
            )

        # Try loading from prompts directory
        try:
            prompts_config = self.config.get_prompts_config()
            prompts_dir = Path(prompts_config.get("directory", "prompts"))
            # Add back scaffold/ for prompts directory since it expects full path
            file_path = (
                prompts_dir / f"scaffold/{template_path}"
                if not template_path.startswith("scaffold/")
                else prompts_dir / template_path
            )

            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    self.logger.debug(
                        f"[TemplateLoader] Loaded from prompts directory: {file_path}"
                    )
                    return content
        except Exception as e:
            self.logger.debug(
                f"[TemplateLoader] Prompts directory loading failed for {template_path}: {e}"
            )

        # If all methods fail, raise exception
        raise FileNotFoundError(f"Template not found: {template_path}")

    def _load_from_embedded_resources(self, template_path: str) -> str:
        """
        Load template from embedded package resources.

        Args:
            template_path: Relative template path within the scaffold package

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be loaded from embedded resources
        """
        # Remove leading "scaffold/" since base package already points to scaffold directory
        if template_path.startswith("scaffold/"):
            template_path = template_path[len("scaffold/") :]

        # Split path to determine package and resource
        path_parts = template_path.split("/")

        if len(path_parts) == 1:
            # Direct file in scaffold directory
            package = self._template_base_package
            resource_name = path_parts[0]
        else:
            # File in subdirectory (e.g., modular/header.txt)
            subdir = ".".join(path_parts[:-1])
            package = f"{self._template_base_package}.{subdir}"
            resource_name = path_parts[-1]

        try:
            # Use importlib.resources to load the template
            if sys.version_info >= (3, 9):
                # Python 3.9+ method
                try:
                    files = importlib.resources.files(package)
                    template_file = files.joinpath(resource_name)
                    if template_file.exists():
                        content = template_file.read_text(encoding="utf-8")
                        return content.strip()
                except (ImportError, AttributeError, ValueError):
                    pass

            # Fallback for Python 3.7-3.8
            if sys.version_info >= (3, 7):
                try:
                    with importlib.resources.path(
                        package, resource_name
                    ) as template_path_obj:
                        if template_path_obj.exists():
                            with open(template_path_obj, "r", encoding="utf-8") as f:
                                content = f.read().strip()
                                return content
                except (ImportError, FileNotFoundError):
                    pass

            # Final fallback using spec location
            spec = importlib.util.find_spec(package)
            if spec and spec.origin:
                package_dir = Path(os.path.dirname(spec.origin))
                template_file_path = package_dir / resource_name
                if template_file_path.exists():
                    with open(template_file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        return content

            raise FileNotFoundError(
                f"Template resource not found: {package}/{resource_name}"
            )

        except Exception as e:
            self.logger.debug(f"[TemplateLoader] Embedded resource loading error: {e}")
            raise

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get template caching statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "cache_size": len(self._template_cache),
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "cached_templates": list(self._template_cache.keys()),
        }

    def clear_cache(self):
        """
        Clear template cache and reset statistics.
        """
        self._template_cache.clear()
        self._cache_stats = {"hits": 0, "misses": 0}
        self.logger.debug("[TemplateLoader] Template cache cleared")
