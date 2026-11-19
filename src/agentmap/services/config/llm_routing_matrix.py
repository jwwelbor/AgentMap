"""
Matrix loading and model lookup for LLM routing configuration.

This module provides functionality for loading and normalizing the
provider x complexity routing matrix.
"""

import logging
from typing import Any, Dict, List, Optional

from agentmap.services.llm.provider_names import canonicalize_provider


def load_routing_matrix(
    config: Dict[str, Any], logger: logging.Logger
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
    normalized_matrix: Dict[str, Dict[str, str]] = {}
    for provider, complexity_map in matrix.items():
        if isinstance(complexity_map, dict):
            normalized_complexity_map = {}
            for complexity, model in complexity_map.items():
                normalized_complexity_map[complexity.lower()] = model
            provider_key = canonicalize_provider(provider)
            existing = normalized_matrix.setdefault(provider_key, {})
            if provider.lower() == provider_key:
                # The canonical spelling remains authoritative when aliases
                # and canonical rows define the same provider.
                existing.update(normalized_complexity_map)
            else:
                # Alias rows can supply missing tiers without replacing values
                # from a canonical row, regardless of config order.
                for complexity, model in normalized_complexity_map.items():
                    existing.setdefault(complexity, model)
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
    provider_matrix = routing_matrix.get(canonicalize_provider(provider), {})
    return provider_matrix.get(complexity.lower())


def get_available_providers(routing_matrix: Dict[str, Dict[str, str]]) -> List[str]:
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
    return canonicalize_provider(provider) in routing_matrix
