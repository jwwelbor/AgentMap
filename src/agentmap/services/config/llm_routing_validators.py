"""
Configuration validation for LLM routing system.

This module provides validation functions for routing configuration,
including the routing matrix, task types, and provider settings.
"""

from typing import Any, Dict, List

from agentmap.services.routing.types import get_valid_complexity_levels


def validate_routing_config(
    routing_matrix: Dict[str, Dict[str, str]],
    task_types: Dict[str, Dict[str, Any]],
    complexity_analysis: Dict[str, Any],
) -> List[str]:
    """
    Validate the complete routing configuration.

    Args:
        routing_matrix: The loaded routing matrix
        task_types: Dictionary of task type configurations
        complexity_analysis: Complexity analysis configuration

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate routing matrix
    if not routing_matrix:
        errors.append("Routing matrix is empty")
    else:
        valid_complexities = set(get_valid_complexity_levels())

        for provider, complexity_map in routing_matrix.items():
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
    for task_name, task_config in task_types.items():
        # Check provider preferences reference valid providers
        provider_preference = task_config.get("provider_preference", [])
        for provider in provider_preference:
            if provider.lower() not in routing_matrix:
                errors.append(
                    f"Task type '{task_name}' references unknown provider '{provider}'"
                )

    # Validate complexity analysis configuration
    if complexity_analysis:
        thresholds = complexity_analysis.get("prompt_length_thresholds", {})
        if thresholds:
            required_thresholds = ["low", "medium", "high"]
            for threshold in required_thresholds:
                if threshold not in thresholds:
                    errors.append(f"Missing prompt length threshold for '{threshold}'")

    return errors


def _validate_max_tokens_value(value: Any, location: str, errors: List[str]) -> None:
    """Validate a single max_tokens value."""
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(
            f"{location}: max_tokens must be a non-negative integer or null, "
            f"got {type(value).__name__}: {value}"
        )
    elif value < 0:
        errors.append(f"{location}: max_tokens must be non-negative, got {value}")


def validate_activities_config(
    activities: Dict[str, Any],
) -> List[str]:
    """
    Validate activities routing configuration, including max_tokens values.

    Args:
        activities: Activities configuration dictionary

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: List[str] = []
    if not activities or not isinstance(activities, dict):
        return errors

    valid_tiers = set(get_valid_complexity_levels()) | {"any"}

    for activity_name, tier_map in activities.items():
        if not isinstance(tier_map, dict):
            errors.append(
                f"Activity '{activity_name}': must be a dictionary of complexity tiers"
            )
            continue

        for tier_key, plan in tier_map.items():
            if tier_key not in valid_tiers:
                errors.append(
                    f"Activity '{activity_name}': invalid complexity tier '{tier_key}'"
                )
                continue

            if not isinstance(plan, dict):
                continue

            location = f"Activity '{activity_name}'.{tier_key}"

            # Validate tier-level max_tokens
            _validate_max_tokens_value(plan.get("max_tokens"), location, errors)

            # Validate primary candidate max_tokens
            primary = plan.get("primary")
            if isinstance(primary, dict):
                _validate_max_tokens_value(
                    primary.get("max_tokens"), f"{location}.primary", errors
                )

            # Validate fallback candidates max_tokens
            for i, fallback in enumerate(plan.get("fallbacks", [])):
                if isinstance(fallback, dict):
                    _validate_max_tokens_value(
                        fallback.get("max_tokens"),
                        f"{location}.fallbacks[{i}]",
                        errors,
                    )

    return errors


def validate_provider_routing(
    routing_matrix: Dict[str, Dict[str, str]], app_config_service, logger
) -> List[str]:
    """
    Validate provider routing matrix configuration.

    Args:
        routing_matrix: The loaded routing matrix
        app_config_service: Application configuration service
        logger: Logger instance

    Returns:
        List of validation error messages
    """
    errors = []

    try:
        # Get all providers from routing matrix
        available_providers = list(routing_matrix.keys())

        # Get provider configurations
        llm_config = app_config_service.get_section("llm", {})
        providers_config = llm_config.get("providers", {})

        # Validate each provider in routing matrix has configuration
        for provider in available_providers:
            if provider not in providers_config:
                errors.append(
                    f"Provider '{provider}' in routing matrix but missing from LLM configuration"
                )
            else:
                provider_config = providers_config[provider]
                if not provider_config.get("api_key"):
                    errors.append(
                        f"Provider '{provider}' missing API key configuration"
                    )

        # Check for configured providers not in routing matrix
        for provider in providers_config:
            if provider not in available_providers:
                errors.append(
                    f"Provider '{provider}' configured but not in routing matrix"
                )

    except Exception as e:
        errors.append(f"Provider routing validation failed: {str(e)}")

    return errors
