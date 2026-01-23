"""
Task type loading and validation for LLM routing configuration.

This module provides functionality for loading and validating task type
definitions used in the routing system.
"""

from typing import Any, Dict, List

from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.types import get_valid_complexity_levels


# Default task types configuration
DEFAULT_TASK_TYPES = {
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


def validate_task_type_config(
    task_name: str,
    task_config: Dict[str, Any],
    logger: LoggingService
) -> bool:
    """
    Validate a single task type configuration.

    Args:
        task_name: Name of the task type
        task_config: Configuration for the task type
        logger: Logger instance for error messages

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["provider_preference", "default_complexity"]

    for field in required_fields:
        if field not in task_config:
            logger.error(
                f"Task type '{task_name}' missing required field '{field}'"
            )
            return False

    # Validate default complexity
    default_complexity = task_config.get("default_complexity", "medium")
    if default_complexity.lower() not in get_valid_complexity_levels():
        logger.error(
            f"Task type '{task_name}' has invalid default_complexity: {default_complexity}"
        )
        return False

    # Validate provider preference is a list
    provider_preference = task_config.get("provider_preference", [])
    if not isinstance(provider_preference, list):
        logger.error(
            f"Task type '{task_name}' provider_preference must be a list"
        )
        return False

    return True


def load_task_types(
    config: Dict[str, Any],
    logger: LoggingService
) -> Dict[str, Dict[str, Any]]:
    """
    Load task type definitions with application-configurable types.

    Args:
        config: Configuration dictionary
        logger: Logger instance for error messages

    Returns:
        Dictionary mapping task type -> configuration
    """
    # Start with built-in task types
    default_task_types = DEFAULT_TASK_TYPES.copy()

    # Load user-defined task types
    user_task_types = config.get("task_types", {})

    # Merge with defaults (user types override defaults)
    merged_task_types = {**default_task_types, **user_task_types}

    # Validate and normalize each task type
    validated_task_types = {}
    for task_name, task_config in merged_task_types.items():
        if validate_task_type_config(task_name, task_config, logger):
            validated_task_types[task_name] = task_config

    return validated_task_types


def get_task_type_config(
    task_types: Dict[str, Dict[str, Any]],
    task_type: str
) -> Dict[str, Any]:
    """
    Get configuration for a specific task type.

    Args:
        task_types: Dictionary of task type configurations
        task_type: Task type name

    Returns:
        Task type configuration or general config if not found
    """
    return task_types.get(task_type, task_types.get("general", {}))


def get_provider_preference(
    task_types: Dict[str, Dict[str, Any]],
    task_type: str
) -> List[str]:
    """
    Get provider preference list for a task type.

    Args:
        task_types: Dictionary of task type configurations
        task_type: Task type name

    Returns:
        List of preferred providers in order
    """
    task_config = get_task_type_config(task_types, task_type)
    return task_config.get("provider_preference", ["anthropic"])


def get_default_complexity(
    task_types: Dict[str, Dict[str, Any]],
    task_type: str
) -> str:
    """
    Get default complexity for a task type.

    Args:
        task_types: Dictionary of task type configurations
        task_type: Task type name

    Returns:
        Default complexity level
    """
    task_config = get_task_type_config(task_types, task_type)
    return task_config.get("default_complexity", "medium")


def get_complexity_keywords(
    task_types: Dict[str, Dict[str, Any]],
    task_type: str
) -> Dict[str, List[str]]:
    """
    Get complexity keywords for a task type.

    Args:
        task_types: Dictionary of task type configurations
        task_type: Task type name

    Returns:
        Dictionary mapping complexity levels to keyword lists
    """
    task_config = get_task_type_config(task_types, task_type)
    return task_config.get("complexity_keywords", {})


def get_available_task_types(task_types: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Get list of configured task types.

    Args:
        task_types: Dictionary of task type configurations

    Returns:
        List of available task type names
    """
    return list(task_types.keys())
