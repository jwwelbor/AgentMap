# agentmap/di/__init__.py
"""
Dependency injection and service wiring.

This module manages:
- Service dependencies and lifecycle
- Configuration of DI container
- Service wiring and initialization
- Agent bootstrap and registration
- Graceful degradation for optional services
"""

import os
from pathlib import Path
from typing import Optional

from agentmap.models.graph_bundle import GraphBundle

from .containers import ApplicationContainer, create_optional_service, safe_get_service


def create_container(config_path: Optional[str] = None) -> ApplicationContainer:
    """
    Create a DI container with optional config path - simple factory method.

    This is a simplified factory that directly creates the container with the
    config path set. Use this when you want direct, explicit container creation
    without auto-discovery logic.

    Args:
        config_path: Optional path to config file (None for defaults)

    Returns:
        ApplicationContainer: Configured DI container

    Example:
        # Simple direct usage
        container = create_container("/path/to/config.yaml")
        service = container.app_config_service()

        # Use defaults
        container = create_container()
    """
    container = ApplicationContainer()
    container.config.path.from_value(config_path)

    return container


def discover_config_file() -> Optional[str]:
    """
    Discover agentmap_config.yaml in the current working directory.

    Returns:
        Path to agentmap_config.yaml if found in cwd, None otherwise
    """
    config_filename = "agentmap_config.yaml"
    cwd_config_path = Path.cwd() / config_filename

    if cwd_config_path.exists() and cwd_config_path.is_file():
        return str(cwd_config_path)

    return None


def initialize_di(config_file: Optional[str] = None) -> ApplicationContainer:
    """
    Initialize dependency injection container for AgentMap application.

    This is the main bootstrap function used by all entry points (CLI, FastAPI,
    serverless handlers, etc.) to create and configure the DI container with
    all necessary services.

    Args:
        config_file: Optional path to custom config file override.
                    If None, automatically discovers agentmap_config.yaml in cwd.

    Returns:
        ApplicationContainer: Fully configured DI container ready for use

    Example:
        # CLI usage with explicit config
        container = initialize_di("/path/to/config.yaml")
        graph_runner = container.graph_runner_service()

        # Automatic config discovery
        container = initialize_di()
        dependency_checker = container.dependency_checker_service()
    """
    import logging

    # Set up bootstrap logging to show config discovery result
    bootstrap_logger = logging.getLogger("agentmap.bootstrap")
    if not bootstrap_logger.handlers:
        logging.basicConfig(
            level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
        )

    # # Create the main DI container
    # container = ApplicationContainer()

    # Determine which config file to use with precedence:
    # 1. Explicit config_file parameter (highest priority)
    # 2. agentmap_config.yaml in current working directory
    # 3. Default (no config file - uses system defaults)
    actual_config_path = None
    config_source = "system defaults"

    if config_file:
        # Explicit config file provided - validate it exists
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        actual_config_path = str(config_path)
        config_source = f"explicit config: {actual_config_path}"
    else:
        # Try auto-discovery
        discovered_config = discover_config_file()
        if discovered_config:
            actual_config_path = discovered_config
            config_source = f"auto-discovered: {actual_config_path}"

    bootstrap_logger.info(f"Using configuration from: {config_source}")

    container = create_container(actual_config_path)

    # Optional: Wire the container for faster service resolution
    # This pre-resolves dependencies but can be skipped for lazy initialization
    # try:
    #     container.wire(modules=[])
    # except Exception:
    #     # If wiring fails, continue - services will be resolved lazily
    #     pass

    return container


def initialize_di_for_testing(
    config_overrides: Optional[dict] = None, mock_services: Optional[dict] = None
) -> ApplicationContainer:
    """
    Initialize DI container specifically for testing with mocks and overrides.

    Args:
        config_overrides: Dict of config values to override
        mock_services: Dict of service_name -> mock_instance mappings

    Returns:
        ApplicationContainer: Test-configured DI container

    Example:
        container = initialize_di_for_testing(
            config_overrides={"csv_path": "/test/data.csv"},
            mock_services={"llm_service": MockLLMService()}
        )
    """
    container = ApplicationContainer()

    # Apply config overrides
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(container, key):
                getattr(container, key).override(value)

    # Apply service mocks
    if mock_services:
        for service_name, mock_instance in mock_services.items():
            if hasattr(container, service_name):
                getattr(container, service_name).override(mock_instance)

    return container


def get_service_status(container: ApplicationContainer) -> dict:
    """
    Get comprehensive status of all services in the DI container.

    Useful for debugging and health checks.

    Args:
        container: DI container to check

    Returns:
        Dict with service availability and status information
    """
    status = {"container_initialized": True, "services": {}, "errors": []}

    # List of key services to check
    key_services = [
        "app_config_service",
        "logging_service",
        "features_registry_service",
        "dependency_checker_service",
        "graph_builder_service",
        "graph_runner_service",
        "llm_service",
        "json_service",
    ]

    for service_name in key_services:
        try:
            service = getattr(container, service_name)()
            status["services"][service_name] = {
                "available": True,
                "type": type(service).__name__,
            }
        except Exception as e:
            status["services"][service_name] = {"available": False, "error": str(e)}
            status["errors"].append(f"{service_name}: {e}")

    return status


__all__ = [
    "ApplicationContainer",
    "create_container",
    "discover_config_file",
    "initialize_di",
    "initialize_di_for_testing",
    # "initialize_application",
    # "bootstrap_agents",
    "get_service_status",
    "create_optional_service",
    "safe_get_service",
]
