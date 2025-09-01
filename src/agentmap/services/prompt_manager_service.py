"""
PromptManagerService for AgentMap.

Service that provides prompt template loading, resolution, and formatting capabilities.
Handles embedded resources, external files, and YAML configurations with proper
dependency injection following established service patterns.
"""

import importlib.resources
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class PromptManagerService:
    """
    Service for prompt template loading, resolution, and formatting.

    Provides capabilities for loading templates from embedded resources, external files,
    and YAML configurations with proper dependency injection and caching.
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """Initialize service with dependency injection."""
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

        # Get prompts configuration using specific getter method
        prompts_config = self.config.get_prompts_config()
        self.prompts_config = prompts_config
        # TODO: move this to ConfigPathService
        self.prompts_dir = Path(
            prompts_config.get("directory", "agentmap_data/prompts")
        )
        self.registry_path = Path(
            prompts_config.get("registry_file", "prompts/registry.yaml")
        )
        self.enable_cache = prompts_config.get("enable_cache", True)
        self.template_location = "agentmap.templates.system"
        self._cache = {}
        self._registry = self._load_registry()

        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("[PromptManagerService] Initialized")
        self.logger.debug(f"Prompts directory: {self.prompts_dir}")
        self.logger.debug(f"Registry path: {self.registry_path}")
        self.logger.debug(f"Cache enabled: {self.enable_cache}")

    def _load_registry(self) -> Dict[str, str]:
        """Load prompt registry from configuration files."""
        registry = {}

        # Try to load from configured registry path first
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r") as f:
                    registry = yaml.safe_load(f) or {}
                    self.logger.debug(
                        f"Loaded {len(registry)} prompts from registry at {self.registry_path}"
                    )
                    return registry
            except Exception as e:
                self.logger.error(
                    f"Error loading prompt registry from {self.registry_path}: {e}"
                )

        # Try to load from system registry as fallback
        try:
            system_registry = self._find_resource("registry.yaml")
            if system_registry and system_registry.exists():
                with open(system_registry, "r") as f:
                    registry = yaml.safe_load(f) or {}
                    self.logger.debug(
                        f"Loaded {len(registry)} prompts from system registry"
                    )
                    return registry
            else:
                self.logger.debug(
                    "No system registry file found, continuing with empty registry"
                )
        except Exception as e:
            self.logger.debug(
                f"Could not load system registry (this is normal if not provided): {e}"
            )

        # Return empty registry if no files found (this is acceptable)
        self.logger.debug("No prompt registry files found, using empty registry")
        return registry

    def _find_resource(self, resource_path: str) -> Optional[Path]:
        """Find resource file in local directory or embedded resources."""
        path = Path(resource_path)
        if path.is_absolute() and path.exists():
            return path

        local_path = self.prompts_dir / path
        if local_path.exists():
            return local_path

        return self._try_get_resource(resource_path)

    def _try_get_resource(self, resource_path: str) -> Optional[Path]:
        """Try to find embedded resource using importlib."""
        parts = resource_path.split("/")
        package = self.template_location

        if len(parts) > 1:
            subdir = ".".join(parts[:-1])
            package = f"{package}.{subdir}"

        resource_name = parts[-1]

        try:
            if sys.version_info >= (3, 9):
                try:
                    f = importlib.resources.files(package).joinpath(resource_name)
                    return f if f.exists() else None
                except (ImportError, AttributeError, ValueError):
                    pass

            elif sys.version_info >= (3, 7):
                try:
                    with importlib.resources.path(package, resource_name) as p:
                        return p if p.exists() else None
                except (ImportError, FileNotFoundError):
                    pass

            spec = importlib.util.find_spec(package)
            if spec and spec.origin:
                full_path = Path(os.path.dirname(spec.origin)) / resource_name
                return full_path if full_path.exists() else None

        except Exception as e:
            self.logger.debug(f"Error locating package resource '{resource_path}': {e}")

        return None

    def resolve_prompt(self, prompt_ref: str) -> str:
        """
        Resolve prompt reference to actual prompt text.

        Args:
            prompt_ref: Prompt reference (prompt:name, file:path, yaml:path#key, or plain text)

        Returns:
            Resolved prompt text
        """
        if not prompt_ref or not isinstance(prompt_ref, str):
            return prompt_ref

        if self.enable_cache and prompt_ref in self._cache:
            self.logger.debug(f"Prompt cache hit: {prompt_ref}")
            return self._cache[prompt_ref]

        try:
            if prompt_ref.startswith("prompt:"):
                result = self._resolve_registry_prompt(prompt_ref[7:])
            elif prompt_ref.startswith("file:"):
                result = self._resolve_file_prompt(prompt_ref[5:])
            elif prompt_ref.startswith("yaml:"):
                result = self._resolve_yaml_prompt(prompt_ref[5:])
            else:
                return prompt_ref

            if self.enable_cache:
                self._cache[prompt_ref] = result

            return result
        except Exception as e:
            self.logger.error(f"Error resolving prompt reference '{prompt_ref}': {e}")
            return f"[Error resolving prompt: {prompt_ref}]"

    def _resolve_registry_prompt(self, prompt_name: str) -> str:
        """Resolve prompt from registry by name."""
        if prompt_name in self._registry:
            self.logger.debug(f"Found prompt '{prompt_name}' in registry")
            return self._registry[prompt_name]

        self.logger.warning(f"Prompt '{prompt_name}' not found in registry")
        return f"[Prompt not found: {prompt_name}]"

    def _resolve_file_prompt(self, file_path: str) -> str:
        """Resolve prompt from file path."""
        path = self._find_resource(file_path)
        if not path:
            self.logger.warning(f"Prompt file not found: {file_path}")
            return f"[Prompt file not found: {file_path}]"

        try:
            with open(path, "r") as f:
                content = f.read().strip()
                self.logger.debug(
                    f"Loaded prompt from file: {path} ({len(content)} chars)"
                )
                return content
        except Exception as e:
            self.logger.error(f"Error reading prompt file '{path}': {e}")
            return f"[Error reading prompt file: {file_path}]"

    def _resolve_yaml_prompt(self, yaml_ref: str) -> str:
        """Resolve prompt from YAML file with key path."""
        if "#" not in yaml_ref:
            self.logger.warning(
                f"Invalid YAML prompt reference (missing #key): {yaml_ref}"
            )
            return f"[Invalid YAML reference (missing #key): {yaml_ref}]"

        file_path, key_path = yaml_ref.split("#", 1)
        path = self._find_resource(file_path)

        if not path:
            self.logger.warning(f"YAML prompt file not found: {yaml_ref}")
            return f"[YAML prompt file not found: {file_path}]"

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)

            keys = key_path.split(".")
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    self.logger.warning(
                        f"Key '{key}' not found in YAML prompt path: {key_path}"
                    )
                    return f"[Key not found in YAML: {key_path}]"

            if not isinstance(value, (str, int, float, bool)):
                self.logger.warning(
                    f"YAML prompt value is not a scalar type: {type(value)}"
                )
                return f"[Invalid prompt type in YAML: {type(value)}]"

            result = str(value)
            self.logger.debug(
                f"Loaded prompt from YAML: {path}#{key_path} ({len(result)} chars)"
            )
            return result

        except Exception as e:
            self.logger.error(f"Error reading YAML prompt file '{path}': {e}")
            return f"[Error reading YAML prompt file: {file_path}]"

    def get_registry(self) -> Dict[str, str]:
        """Get copy of current prompt registry."""
        return self._registry.copy()

    def clear_cache(self) -> None:
        """Clear prompt resolution cache."""
        self._cache.clear()
        self.logger.debug("Cleared prompt cache")

    def format_prompt(self, prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
        """
        Format prompt with variable substitution.

        Args:
            prompt_ref_or_text: Prompt reference or text to format
            values: Dictionary of values for variable substitution

        Returns:
            Formatted prompt text
        """
        known_prefixes = ["prompt:", "file:", "yaml:"]
        is_reference = any(
            prompt_ref_or_text.startswith(prefix) for prefix in known_prefixes
        )

        prompt_text = (
            self.resolve_prompt(prompt_ref_or_text)
            if is_reference
            else prompt_ref_or_text
        )

        try:
            from langchain.prompts import PromptTemplate

            prompt_template = PromptTemplate(
                template=prompt_text, input_variables=list(values.keys())
            )
            return prompt_template.format(**values)
        except Exception as e:
            self.logger.warning(
                f"Error using LangChain PromptTemplate: {e}, falling back to standard formatting"
            )
            try:
                return prompt_text.format(**values)
            except Exception as e2:
                self.logger.error(
                    f"Error formatting prompt with standard formatting: {e2}"
                )
                result = prompt_text
                for key, value in values.items():
                    placeholder = "{" + key + "}"
                    result = result.replace(placeholder, str(value))
                return result

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the prompt manager service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "PromptManagerService",
            "config_available": self.config is not None,
            "prompts_dir": str(self.prompts_dir),
            "registry_path": str(self.registry_path),
            "cache_enabled": self.enable_cache,
            "cache_size": len(self._cache),
            "registry_size": len(self._registry),
            "supported_prefixes": ["prompt:", "file:", "yaml:"],
        }


# Global singleton instance for backward compatibility
_prompt_manager = None


def get_prompt_manager(
    config_path: Optional[Union[str, Path]] = None,
) -> PromptManagerService:
    """Get global PromptManagerService instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManagerService()
    return _prompt_manager


def resolve_prompt(prompt_ref: str) -> str:
    """Convenience function to resolve prompt reference."""
    if not prompt_ref or not isinstance(prompt_ref, str):
        return prompt_ref
    if any(prompt_ref.startswith(prefix) for prefix in ["prompt:", "file:", "yaml:"]):
        return get_prompt_manager().resolve_prompt(prompt_ref)
    return prompt_ref


def format_prompt(prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
    """Convenience function to format prompt with values."""
    return get_prompt_manager().format_prompt(prompt_ref_or_text, values)


def get_formatted_prompt(
    primary_prompt: Optional[str],
    template_file: str,
    default_template: str,
    values: Dict[str, Any],
    logger: logging.Logger,
    context_name: str = "Agent",
) -> str:
    """
    Get formatted prompt with fallback options.

    Tries primary_prompt, then template_file, then default_template.
    """
    prompt_manager = get_prompt_manager()
    logger.debug(f"[{context_name}] Getting formatted prompt")

    for prompt_option, desc in [
        (primary_prompt, "primary prompt"),
        (template_file, "file template"),
        (default_template, "default template"),
    ]:
        if not prompt_option:
            continue
        try:
            resolved_text = resolve_prompt(prompt_option)
            logger.debug(f"[{context_name}] Using {desc}")
            return prompt_manager.format_prompt(resolved_text, values)
        except Exception as e:
            logger.warning(f"[{context_name}] Failed to use {desc}: {str(e)}")

    logger.warning(f"[{context_name}] All prompt formatting methods failed")
    return f"Error: Unable to format prompt properly.\nValues: {values}"
