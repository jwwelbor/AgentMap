# agentmap/di/__init__.py
"""
Dependency injection and service wiring.

This module manages:
- Service dependencies and lifecycle
- Configuration of DI container
- Service wiring and initialization
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
    config_overrides: Optional[dict] = None,
    mock_services: Optional[dict] = None
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
    status = {
        "container_initialized": True,
        "services": {},
        "errors": []
    }
    
    # List of key services to check
    key_services = [
        "app_config_service",
        "logging_service", 
        "features_registry_service",
        "dependency_checker_service",
        "graph_builder_service",
        "graph_runner_service",
        "llm_service",
        "storage_service_manager"
    ]
    
    for service_name in key_services:
        try:
            service = getattr(container, service_name)()
            status["services"][service_name] = {
                "available": True,
                "type": type(service).__name__
            }
        except Exception as e:
            status["services"][service_name] = {
                "available": False,
                "error": str(e)
            }
            status["errors"].append(f"{service_name}: {e}")
    
    return status


__all__ = [
    'ApplicationContainer',
    'initialize_di',
    'initialize_di_for_testing', 
    'get_service_status',
    'create_optional_service',
    'safe_get_service'
]
