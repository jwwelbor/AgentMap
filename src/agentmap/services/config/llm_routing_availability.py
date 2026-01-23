"""
Availability caching operations for LLM routing configuration.

This module provides functionality for caching and checking provider
availability status in the routing system.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def get_cached_availability(
    availability_cache_service,
    provider: str,
    logger
) -> Optional[Dict[str, Any]]:
    """
    Get cached availability using unified cache service.

    Args:
        availability_cache_service: The unified availability cache service
        provider: Provider name to check
        logger: Logger instance

    Returns:
        Cached availability data or None if not found/invalid
    """
    if not availability_cache_service:
        return None

    try:
        return availability_cache_service.get_availability(
            "llm_provider", provider.lower()
        )
    except Exception as e:
        logger.debug(f"Cache lookup failed for llm_provider.{provider}: {e}")
        return None


def set_cached_availability(
    availability_cache_service,
    provider: str,
    result: Dict[str, Any],
    logger
) -> bool:
    """
    Set cached availability using unified cache service.

    Args:
        availability_cache_service: The unified availability cache service
        provider: Provider name
        result: Availability result data to cache
        logger: Logger instance

    Returns:
        True if successfully cached, False otherwise
    """
    if not availability_cache_service:
        return False

    try:
        return availability_cache_service.set_availability(
            "llm_provider", provider.lower(), result
        )
    except Exception as e:
        logger.debug(f"Cache set failed for llm_provider.{provider}: {e}")
        return False


async def get_provider_availability(
    provider: str,
    routing_matrix: Dict[str, Dict[str, str]],
    availability_cache_service,
    logger
) -> Dict[str, Any]:
    """
    Get availability status for a specific provider.

    Args:
        provider: Provider name to check
        routing_matrix: The loaded routing matrix
        availability_cache_service: The unified availability cache service
        logger: Logger instance

    Returns:
        Dictionary with availability status and metadata
    """
    # Try cache first
    cached_result = get_cached_availability(availability_cache_service, provider, logger)
    if cached_result:
        logger.debug(f"Using cached availability for provider: {provider}")
        return cached_result

    # Fallback to basic availability check without actual validation
    # (Real validation should be done by LLM services and cached)
    is_configured = provider.lower() in routing_matrix
    result = {
        "enabled": is_configured,
        "validation_passed": is_configured,  # Assume configured = working for routing config
        "last_error": None if is_configured else "Provider not in routing matrix",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "warnings": (
            ["Basic availability check - no validation performed"]
            if not availability_cache_service
            else []
        ),
        "performance_metrics": {"validation_duration": 0.0},
        "validation_results": {"routing_matrix_configured": is_configured},
    }

    # Cache the result for future use
    set_cached_availability(availability_cache_service, provider, result, logger)

    return result


async def validate_all_providers(
    routing_matrix: Dict[str, Dict[str, str]],
    availability_cache_service,
    logger
) -> Dict[str, Dict[str, Any]]:
    """
    Validate availability of all configured providers.

    Args:
        routing_matrix: The loaded routing matrix
        availability_cache_service: The unified availability cache service
        logger: Logger instance

    Returns:
        Dictionary mapping provider names to availability status
    """
    results = {}
    for provider in routing_matrix.keys():
        try:
            results[provider] = await get_provider_availability(
                provider, routing_matrix, availability_cache_service, logger
            )
        except Exception as e:
            logger.error(
                f"Failed to get availability for provider {provider}: {e}"
            )
            results[provider] = {
                "enabled": False,
                "validation_passed": False,
                "last_error": f"Validation exception: {str(e)}",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {},
            }
    return results


async def is_provider_available_async(
    provider: str,
    routing_matrix: Dict[str, Dict[str, str]],
    availability_cache_service,
    logger
) -> bool:
    """
    Async version of provider availability check with caching.

    Args:
        provider: Provider name to check
        routing_matrix: The loaded routing matrix
        availability_cache_service: The unified availability cache service
        logger: Logger instance

    Returns:
        True if provider is available and working
    """
    try:
        availability = await get_provider_availability(
            provider, routing_matrix, availability_cache_service, logger
        )
        return availability.get("enabled", False) and availability.get(
            "validation_passed", False
        )
    except Exception as e:
        logger.error(f"Failed async availability check for {provider}: {e}")
        return False


def clear_provider_cache(
    availability_cache_service,
    provider: Optional[str],
    logger
):
    """
    Clear availability cache for specific provider or all providers.

    Args:
        availability_cache_service: The unified availability cache service
        provider: Provider name to clear, or None for all providers
        logger: Logger instance
    """
    if availability_cache_service:
        if provider:
            availability_cache_service.invalidate_cache(
                "llm_provider", provider.lower()
            )
            logger.info(
                f"Cleared availability cache for provider: {provider}"
            )
        else:
            availability_cache_service.invalidate_cache("llm_provider")
            logger.info("Cleared availability cache for all providers")
    else:
        logger.warning(
            "Cannot clear cache - unified availability cache service not available"
        )


def get_cache_stats(
    availability_cache_service,
    routing_matrix: Dict[str, Dict[str, str]],
    logger
) -> Dict[str, Any]:
    """
    Get availability cache statistics and health information.

    Args:
        availability_cache_service: The unified availability cache service
        routing_matrix: The loaded routing matrix
        logger: Logger instance

    Returns:
        Dictionary with cache statistics
    """
    total_providers = len(routing_matrix.keys())

    if availability_cache_service:
        try:
            cache_stats = availability_cache_service.get_cache_stats()
            # Filter for LLM provider data
            categories = cache_stats.get("categories", {})
            llm_provider_count = categories.get("llm_provider", 0)

            return {
                "cache_exists": cache_stats.get("cache_exists", False),
                "cache_enabled": True,
                "total_providers": total_providers,
                "cached_providers": llm_provider_count,
                "unified_cache_stats": cache_stats,
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {
                "cache_exists": False,
                "cache_enabled": True,
                "error": str(e),
                "total_providers": total_providers,
            }
    else:
        return {
            "cache_exists": False,
            "cache_enabled": False,
            "total_providers": total_providers,
            "cached_providers": 0,
        }
