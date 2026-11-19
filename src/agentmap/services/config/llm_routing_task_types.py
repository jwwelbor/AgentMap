"""
Task type loading and validation for LLM routing configuration.

This module provides functionality for loading and validating task type
definitions used in the routing system.
"""

import logging
from typing import Any, Dict, List

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
    task_name: str, task_config: Any, logger: logging.Logger
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
    if not isinstance(task_config, dict):
        logger.error(f"Task type '{task_name}' configuration must be a mapping")
        return False

    required_fields = ["provider_preference", "default_complexity"]

    for field in required_fields:
        if field not in task_config:
            logger.error(f"Task type '{task_name}' missing required field '{field}'")
            return False

    # Validate default complexity
    default_complexity = task_config.get("default_complexity", "medium")
    if not isinstance(default_complexity, str):
        logger.error(f"Task type '{task_name}' default_complexity must be a string")
        return False
    if default_complexity.lower() not in get_valid_complexity_levels():
        logger.error(
            f"Task type '{task_name}' has invalid default_complexity: {default_complexity}"
        )
        return False

    # Validate provider preference is a list
    provider_preference = task_config.get("provider_preference", [])
    if not isinstance(provider_preference, list) or not all(
        isinstance(provider, str) for provider in provider_preference
    ):
        logger.error(
            f"Task type '{task_name}' provider_preference must be a list of strings"
        )
        return False

    complexity_keywords = task_config.get("complexity_keywords", {})
    if not isinstance(complexity_keywords, dict) or any(
        not isinstance(level, str)
        or not isinstance(keywords, list)
        or not all(isinstance(keyword, str) for keyword in keywords)
        for level, keywords in complexity_keywords.items()
    ):
        logger.error(
            f"Task type '{task_name}' complexity_keywords must map strings to lists of strings"
        )
        return False

    return True


def load_task_types(
    config: Dict[str, Any], logger: logging.Logger
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
    if not isinstance(user_task_types, dict):
        logger.error("Configured task_types must be a mapping")
        user_task_types = {}

    # Merge with defaults (user types override defaults)
    merged_task_types = {**default_task_types, **user_task_types}

    # Validate and normalize each task type
    validated_task_types = {}
    for task_name, task_config in merged_task_types.items():
        if isinstance(task_name, str) and validate_task_type_config(
            task_name, task_config, logger
        ):
            validated_task_types[task_name] = task_config

    return validated_task_types


def get_task_type_config(
    task_types: Dict[str, Dict[str, Any]], task_type: str
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
    task_types: Dict[str, Dict[str, Any]], task_type: str
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
    providers = task_config.get("provider_preference", ["anthropic"])
    if isinstance(providers, list) and all(
        isinstance(provider, str) for provider in providers
    ):
        return providers
    return ["anthropic"]


def get_default_complexity(
    task_types: Dict[str, Dict[str, Any]], task_type: str
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
    complexity = task_config.get("default_complexity", "medium")
    return complexity if isinstance(complexity, str) else "medium"


def get_complexity_keywords(
    task_types: Dict[str, Dict[str, Any]], task_type: str
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
    keywords = task_config.get("complexity_keywords", {})
    if isinstance(keywords, dict) and all(
        isinstance(level, str)
        and isinstance(items, list)
        and all(isinstance(item, str) for item in items)
        for level, items in keywords.items()
    ):
        return keywords
    return {}


def get_available_task_types(task_types: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Get list of configured task types.

    Args:
        task_types: Dictionary of task type configurations

    Returns:
        List of available task type names
    """
    return list(task_types.keys())
