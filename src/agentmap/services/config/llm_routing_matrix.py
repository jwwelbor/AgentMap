"""
Matrix loading and model lookup for LLM routing configuration.

This module provides functionality for loading and normalizing the
provider x complexity routing matrix.
"""

from typing import Any, Dict, Optional

from agentmap.services.logging_service import LoggingService


def load_routing_matrix(
    config: Dict[str, Any], logger: LoggingService
) -> Dict[str, Dict[str, str]]:
    """
    Load the provider x complexity matrix.

    Args:
        config: Configuration dictionary
        logger: Logger instance for warnings

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
            logger.warning(f"Invalid routing matrix entry for provider {provider}")

    return normalized_matrix


def get_model_for_complexity(
    routing_matrix: Dict[str, Dict[str, str]], provider: str, complexity: str
) -> Optional[str]:
    """
    Get the model for a given provider and complexity.

    Args:
        routing_matrix: The loaded routing matrix
        provider: Provider name (e.g., "anthropic", "openai")
        complexity: Complexity level (e.g., "low", "medium", "high", "critical")

    Returns:
        Model name or None if not found
    """
    provider_matrix = routing_matrix.get(provider.lower(), {})
    return provider_matrix.get(complexity.lower())


def get_available_providers(routing_matrix: Dict[str, Dict[str, str]]) -> list:
    """
    Get list of providers configured in the routing matrix.

    Args:
        routing_matrix: The loaded routing matrix

    Returns:
        List of available provider names
    """
    return list(routing_matrix.keys())


def is_provider_available(
    routing_matrix: Dict[str, Dict[str, str]], provider: str
) -> bool:
    """
    Check if a provider is configured in the routing matrix.

    Args:
        routing_matrix: The loaded routing matrix
        provider: Provider name to check

    Returns:
        True if provider is available
    """
    return provider.lower() in routing_matrix
