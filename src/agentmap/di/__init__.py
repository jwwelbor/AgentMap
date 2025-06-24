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

from pathlib import Path
from typing import Optional

from .containers import ApplicationContainer, create_optional_service, safe_get_service


def initialize_di(config_file: Optional[str] = None) -> ApplicationContainer:
    """
    Initialize dependency injection container for AgentMap application.

    This is the main bootstrap function used by all entry points (CLI, FastAPI,
    serverless handlers, etc.) to create and configure the DI container with
    all necessary services.

    Args:
        config_file: Optional path to custom config file override

    Returns:
        ApplicationContainer: Fully configured DI container ready for use

    Example:
        # CLI usage
        container = initialize_di("/path/to/config.yaml")
        graph_runner = container.graph_runner_service()

        # FastAPI usage
        container = initialize_di()
        dependency_checker = container.dependency_checker_service()
    """
    # Create the main DI container
    container = ApplicationContainer()

    # Override config path if provided
    if config_file:
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        container.config_path.override(str(config_path))

    # Optional: Wire the container for faster service resolution
    # This pre-resolves dependencies but can be skipped for lazy initialization
    try:
        container.wire(modules=[])
    except Exception:
        # If wiring fails, continue - services will be resolved lazily
        pass

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
        "storage_service_manager",
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


def initialize_application(config_file: Optional[str] = None) -> ApplicationContainer:
    """
    Complete application initialization: DI container setup + agent bootstrap.

    This function provides full application initialization by combining DI container
    setup with agent registration and feature discovery. Use this for complete
    application startup when agents are needed.

    Args:
        config_file: Optional path to custom config file override

    Returns:
        ApplicationContainer: Fully configured DI container with agents registered

    Example:
        # CLI usage with complete bootstrap
        container = initialize_application("/path/to/config.yaml")
        graph_runner = container.graph_runner_service()  # Agents are available

        # API server startup
        container = initialize_application()
        # All agents registered and ready for graph execution
    """
    # Step 1: Initialize DI container (existing functionality)
    container = initialize_di(config_file)

    # Step 2: Bootstrap agents (new functionality)
    bootstrap_agents(container)

    return container


def bootstrap_agents(container: ApplicationContainer) -> None:
    """
    Bootstrap agent registration using existing DI services.

    This function provides explicit control over agent bootstrap timing,
    allowing DI setup and agent registration to be separated if needed.
    Uses graceful degradation - bootstrap failures are logged but don't crash.

    Args:
        container: DI container with bootstrap service configured

    Example:
        # Explicit control over bootstrap timing
        container = initialize_di(config_file)
        # ... do other setup ...
        bootstrap_agents(container)  # Agents now registered

        # Testing with partial bootstrap
        container = initialize_di()
        if test_needs_agents:
            bootstrap_agents(container)
    """
    try:
        # Get bootstrap service from DI container
        bootstrap_service = container.application_bootstrap_service()

        # Execute the main bootstrap process
        bootstrap_service.bootstrap_application()

    except Exception as e:
        # Graceful degradation following storage service patterns
        # Log warning but don't crash - allows partial functionality
        logging_service = safe_get_service(container, "logging_service")
        if logging_service:
            logger = logging_service.get_logger("agentmap.bootstrap")
            logger.warning(f"Agent bootstrap failed: {e}")
            logger.warning("Application will continue with limited agent functionality")
        # Note: Don't re-raise - graceful degradation allows app to continue


__all__ = [
    "ApplicationContainer",
    "initialize_di",
    "initialize_di_for_testing",
    "initialize_application",
    "bootstrap_agents",
    "get_service_status",
    "create_optional_service",
    "safe_get_service",
]
