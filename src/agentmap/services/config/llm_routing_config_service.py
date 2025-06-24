"""
Routing configuration section for AgentMap LLM routing system.

This module provides configuration management for the matrix-based LLM routing
system, including provider × complexity matrix, task types, and routing policies.
"""

from typing import Any, Dict, List, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.types import (
    get_valid_complexity_levels,
)


class LLMRoutingConfigService:
    """
    Configuration section for LLM routing.

    Handles loading, validation, and access to routing configuration including
    the provider × complexity matrix and task type definitions.
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize routing configuration from dictionary.

        Args:
            config_dict: Configuration dictionary from YAML or defaults
        """
        self._logger = logging_service.get_class_logger(self)
        self.config_dict = app_config_service.get_routing_config()
        self.enabled = self.config_dict.get("enabled", False)
        self.routing_matrix = self._load_routing_matrix(self.config_dict)
        self.task_types = self._load_task_types(self.config_dict)
        self.complexity_analysis = self.config_dict.get("complexity_analysis", {})
        self.cost_optimization = self.config_dict.get("cost_optimization", {})
        self.fallback = self.config_dict.get("fallback", {})
        self.performance = self.config_dict.get("performance", {})

        # Validate configuration on load
        validation_errors = self.validate_AppConfigService()
        if validation_errors:
            self._logger.warning(
                f"Routing configuration validation errors: {validation_errors}"
            )

    def _load_routing_matrix(self, config: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """
        Load the provider × complexity matrix.

        Args:
            config: Configuration dictionary

        Returns:
            Dictionary mapping provider -> complexity -> model
        """
        matrix = config.get("routing_matrix", {})

        # Normalize complexity keys to lowercase
        normalized_matrix = {}
        for provider, complexity_map in matrix.items():
            if isinstance(complexity_map, dict):
                normalized_complexity_map = {}
                for complexity, model in complexity_map.items():
                    normalized_complexity_map[complexity.lower()] = model
                normalized_matrix[provider.lower()] = normalized_complexity_map
            else:
                self._logger.warning(
                    f"Invalid routing matrix entry for provider {provider}"
                )

        return normalized_matrix

    def _load_task_types(self, config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Load task type definitions with application-configurable types.

        Args:
            config: Configuration dictionary

        Returns:
            Dictionary mapping task type -> configuration
        """
        # Start with built-in task types
        default_task_types = {
            "general": {
                "description": "General purpose tasks",
                "provider_preference": ["anthropic", "openai", "google"],
                "default_complexity": "medium",
                "complexity_keywords": {
                    "low": ["simple", "basic", "quick"],
                    "medium": ["analyze", "process", "standard"],
                    "high": ["complex", "detailed", "comprehensive", "advanced"],
                    "critical": ["urgent", "critical", "important", "emergency"],
                },
            }
        }

        # Load user-defined task types
        user_task_types = config.get("task_types", {})

        # Merge with defaults (user types override defaults)
        merged_task_types = {**default_task_types, **user_task_types}

        # Validate and normalize each task type
        validated_task_types = {}
        for task_name, task_config in merged_task_types.items():
            if self._validate_task_type_config(task_name, task_config):
                validated_task_types[task_name] = task_config

        return validated_task_types

    def _validate_task_type_config(
        self, task_name: str, task_config: Dict[str, Any]
    ) -> bool:
        """
        Validate a single task type configuration.

        Args:
            task_name: Name of the task type
            task_config: Configuration for the task type

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["provider_preference", "default_complexity"]

        for field in required_fields:
            if field not in task_config:
                self._logger.error(
                    f"Task type '{task_name}' missing required field '{field}'"
                )
                return False

        # Validate default complexity
        default_complexity = task_config.get("default_complexity", "medium")
        if default_complexity.lower() not in get_valid_complexity_levels():
            self._logger.error(
                f"Task type '{task_name}' has invalid default_complexity: {default_complexity}"
            )
            return False

        # Validate provider preference is a list
        provider_preference = task_config.get("provider_preference", [])
        if not isinstance(provider_preference, list):
            self._logger.error(
                f"Task type '{task_name}' provider_preference must be a list"
            )
            return False

        return True

    def validate_AppConfigService(self) -> List[str]:
        """
        Validate the complete routing configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate routing matrix
        if not self.routing_matrix:
            errors.append("Routing matrix is empty")
        else:
            valid_complexities = set(get_valid_complexity_levels())

            for provider, complexity_map in self.routing_matrix.items():
                if not isinstance(complexity_map, dict):
                    errors.append(
                        f"Invalid routing matrix for provider '{provider}': must be a dictionary"
                    )
                    continue

                # Check that all complexity levels are covered
                for complexity in valid_complexities:
                    if complexity not in complexity_map:
                        errors.append(
                            f"Provider '{provider}' missing model for complexity '{complexity}'"
                        )

                # Check for invalid complexity levels
                for complexity in complexity_map.keys():
                    if complexity not in valid_complexities:
                        errors.append(
                            f"Provider '{provider}' has invalid complexity level '{complexity}'"
                        )

        # Validate task types
        for task_name, task_config in self.task_types.items():
            # Check provider preferences reference valid providers
            provider_preference = task_config.get("provider_preference", [])
            for provider in provider_preference:
                if provider.lower() not in self.routing_matrix:
                    errors.append(
                        f"Task type '{task_name}' references unknown provider '{provider}'"
                    )

        # Validate complexity analysis configuration
        complexity_config = self.complexity_analysis
        if complexity_config:
            thresholds = complexity_config.get("prompt_length_thresholds", {})
            if thresholds:
                required_thresholds = ["low", "medium", "high"]
                for threshold in required_thresholds:
                    if threshold not in thresholds:
                        errors.append(
                            f"Missing prompt length threshold for '{threshold}'"
                        )

        return errors

    def get_model_for_complexity(self, provider: str, complexity: str) -> Optional[str]:
        """
        Get the model for a given provider and complexity.

        Args:
            provider: Provider name (e.g., "anthropic", "openai")
            complexity: Complexity level (e.g., "low", "medium", "high", "critical")

        Returns:
            Model name or None if not found
        """
        provider_matrix = self.routing_matrix.get(provider.lower(), {})
        return provider_matrix.get(complexity.lower())

    def get_task_type_config(self, task_type: str) -> Dict[str, Any]:
        """
        Get configuration for a specific task type.

        Args:
            task_type: Task type name

        Returns:
            Task type configuration or general config if not found
        """
        return self.task_types.get(task_type, self.task_types.get("general", {}))

    def get_provider_preference(self, task_type: str) -> List[str]:
        """
        Get provider preference list for a task type.

        Args:
            task_type: Task type name

        Returns:
            List of preferred providers in order
        """
        task_config = self.get_task_type_config(task_type)
        return task_config.get("provider_preference", ["anthropic"])

    def get_default_complexity(self, task_type: str) -> str:
        """
        Get default complexity for a task type.

        Args:
            task_type: Task type name

        Returns:
            Default complexity level
        """
        task_config = self.get_task_type_config(task_type)
        return task_config.get("default_complexity", "medium")

    def get_complexity_keywords(self, task_type: str) -> Dict[str, List[str]]:
        """
        Get complexity keywords for a task type.

        Args:
            task_type: Task type name

        Returns:
            Dictionary mapping complexity levels to keyword lists
        """
        task_config = self.get_task_type_config(task_type)
        return task_config.get("complexity_keywords", {})

    def get_available_providers(self) -> List[str]:
        """
        Get list of providers configured in the routing matrix.

        Returns:
            List of available provider names
        """
        return list(self.routing_matrix.keys())

    def get_available_task_types(self) -> List[str]:
        """
        Get list of configured task types.

        Returns:
            List of available task type names
        """
        return list(self.task_types.keys())

    def is_provider_available(self, provider: str) -> bool:
        """
        Check if a provider is configured in the routing matrix.

        Args:
            provider: Provider name to check

        Returns:
            True if provider is available
        """
        return provider.lower() in self.routing_matrix

    def get_fallback_provider(self) -> str:
        """
        Get the configured fallback provider.

        Returns:
            Fallback provider name
        """
        return self.fallback.get("default_provider", "anthropic")

    def get_fallback_model(self) -> str:
        """
        Get the configured fallback model.

        Returns:
            Fallback model name
        """
        return self.fallback.get("default_model", "claude-3-haiku-20240307")

    def is_cost_optimization_enabled(self) -> bool:
        """
        Check if cost optimization is enabled.

        Returns:
            True if cost optimization is enabled
        """
        return self.cost_optimization.get("enabled", True)

    def get_max_cost_tier(self) -> str:
        """
        Get the maximum cost tier allowed.

        Returns:
            Maximum cost tier (low, medium, high, critical)
        """
        return self.cost_optimization.get("max_cost_tier", "high")

    def is_routing_cache_enabled(self) -> bool:
        """
        Check if routing decision caching is enabled.

        Returns:
            True if caching is enabled
        """
        return self.performance.get("enable_routing_cache", True)

    def get_cache_ttl(self) -> int:
        """
        Get the cache time-to-live in seconds.

        Returns:
            Cache TTL in seconds
        """
        return self.performance.get("cache_ttl", 300)


# def get_routing_matrix(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, str]]:
#     """
#     Get the routing matrix configuration.

#     Args:
#         config_path: Optional path to a custom config file

#     Returns:
#         Dictionary containing the provider × complexity matrix
#     """
#     routing_config = get_routing_config(config_path)
#     return routing_config.routing_matrix


# def get_task_types_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, Any]]:
#     """
#     Get task types configuration.

#     Args:
#         config_path: Optional path to a custom config file

#     Returns:
#         Dictionary containing task type definitions
#     """
#     routing_config = get_routing_config(config_path)
#     return routing_config.task_types


# def is_routing_enabled(config_path: Optional[Union[str, Path]] = None) -> bool:
#     """
#     Check if routing is globally enabled.

#     Args:
#         config_path: Optional path to a custom config file

#     Returns:
#         True if routing is enabled
#     """
#     routing_config = get_routing_config(config_path)
#     return routing_config.enabled
