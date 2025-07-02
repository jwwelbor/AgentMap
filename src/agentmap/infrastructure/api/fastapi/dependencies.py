"""
FastAPI dependency injection adapter for clean architecture.

This module provides a clean adapter pattern for FastAPI's dependency injection
system without using global state or violating clean architecture principles.
"""

from typing import Callable, Optional

from fastapi import Depends, Request

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer


class FastAPIDependencyAdapter:
    """
    Adapter for FastAPI dependency injection that encapsulates container management.

    This adapter eliminates the need for global state while maintaining
    compatibility with FastAPI's dependency injection system.
    """

    def __init__(self, container: ApplicationContainer):
        """
        Initialize the adapter with a DI container.

        Args:
            container: The application's dependency injection container
        """
        self.container = container

    def get_container(self) -> Callable:
        """
        Get a FastAPI dependency function that returns the container.

        Returns:
            A dependency function that returns the ApplicationContainer
        """

        def _get_container() -> ApplicationContainer:
            return self.container

        return Depends(_get_container)

    def get_service_adapter(self) -> Callable:
        """
        Get a FastAPI dependency function for the service adapter.

        Returns:
            A dependency function that returns the service adapter
        """

        def _get_service_adapter() -> any:
            return create_service_adapter(self.container)

        return Depends(_get_service_adapter)

    def get_app_config_service(self) -> Callable:
        """
        Get a FastAPI dependency function for AppConfigService.

        Returns:
            A dependency function that returns AppConfigService
        """

        def _get_app_config_service() -> any:
            return self.container.app_config_service()

        return Depends(_get_app_config_service)

    def get_storage_service_manager(self) -> Callable:
        """
        Get a FastAPI dependency function for StorageServiceManager.

        Returns:
            A dependency function that returns StorageServiceManager
        """

        def _get_storage_service_manager() -> any:
            return self.container.storage_service_manager()

        return Depends(_get_storage_service_manager)

    def get_auth_service(self) -> Callable:
        """
        Get a FastAPI dependency function for AuthService.

        Returns:
            A dependency function that returns AuthService
        """

        def _get_auth_service() -> any:
            return self.container.auth_service()

        return Depends(_get_auth_service)

    def get_validation_service(self) -> Callable:
        """
        Get a FastAPI dependency function for ValidationService.

        Returns:
            A dependency function that returns ValidationService
        """

        def _get_validation_service() -> any:
            return self.container.validation_service()

        return Depends(_get_validation_service)

    def get_csv_parser_service(self) -> Callable:
        """
        Get a FastAPI dependency function for CSVGraphParserService.

        Returns:
            A dependency function that returns CSVGraphParserService
        """

        def _get_csv_parser_service() -> any:
            return self.container.csv_graph_parser_service()

        return Depends(_get_csv_parser_service)

    def get_features_service(self) -> Callable:
        """
        Get a FastAPI dependency function for FeaturesRegistryService.

        Returns:
            A dependency function that returns FeaturesRegistryService
        """

        def _get_features_service() -> any:
            return self.container.features_registry_service()

        return Depends(_get_features_service)

    def get_dependency_checker_service(self) -> Callable:
        """
        Get a FastAPI dependency function for DependencyCheckerService.

        Returns:
            A dependency function that returns DependencyCheckerService
        """

        def _get_dependency_checker_service() -> any:
            return self.container.dependency_checker_service()

        return Depends(_get_dependency_checker_service)

    def get_validation_cache_service(self) -> Callable:
        """
        Get a FastAPI dependency function for ValidationCacheService.

        Returns:
            A dependency function that returns ValidationCacheService
        """

        def _get_validation_cache_service() -> any:
            return self.container.validation_cache_service()

        return Depends(_get_validation_cache_service)

    def get_graph_definition_service(self) -> Callable:
        """
        Get a FastAPI dependency function for GraphDefinitionService.

        Returns:
            A dependency function that returns GraphDefinitionService
        """

        def _get_graph_definition_service() -> any:
            return self.container.graph_definition_service()

        return Depends(_get_graph_definition_service)

    def get_graph_runner_service(self) -> Callable:
        """
        Get a FastAPI dependency function for GraphRunnerService.

        Returns:
            A dependency function that returns GraphRunnerService
        """

        def _get_graph_runner_service() -> any:
            return self.container.graph_runner_service()

        return Depends(_get_graph_runner_service)

    def get_compilation_service(self) -> Callable:
        """
        Get a FastAPI dependency function for CompilationService.

        Returns:
            A dependency function that returns CompilationService
        """

        def _get_compilation_service() -> any:
            return self.container.compilation_service()

        return Depends(_get_compilation_service)

    def get_graph_scaffold_service(self) -> Callable:
        """
        Get a FastAPI dependency function for GraphScaffoldService.

        Returns:
            A dependency function that returns GraphScaffoldService
        """

        def _get_graph_scaffold_service() -> any:
            return self.container.graph_scaffold_service()

        return Depends(_get_graph_scaffold_service)

    def get_logging_service(self) -> Callable:
        """
        Get a FastAPI dependency function for LoggingService.

        Returns:
            A dependency function that returns LoggingService
        """

        def _get_logging_service() -> any:
            return self.container.logging_service()

        return Depends(_get_logging_service)


# Compatibility functions for routes that expect direct imports
def get_dependency_adapter(request: Request):
    """Get the dependency adapter from app state."""
    return request.app.state.dependency_adapter


def get_container(request: Request) -> ApplicationContainer:
    """Get DI container for FastAPI dependency injection."""
    adapter = get_dependency_adapter(request)
    return adapter.container


def get_service_adapter(container: ApplicationContainer = Depends(get_container)):
    """Get service adapter for FastAPI dependency injection."""
    return create_service_adapter(container)


def get_app_config_service(container: ApplicationContainer = Depends(get_container)):
    """Get AppConfigService through DI container."""
    return container.app_config_service()


def get_storage_service_manager(
    container: ApplicationContainer = Depends(get_container),
):
    """Get StorageServiceManager through DI container."""
    return container.storage_service_manager()


def get_auth_service(container: ApplicationContainer = Depends(get_container)):
    """Get AuthService through DI container."""
    return container.auth_service()


def get_validation_service(container: ApplicationContainer = Depends(get_container)):
    """Get ValidationService through DI container."""
    return container.validation_service()


def get_csv_parser_service(container: ApplicationContainer = Depends(get_container)):
    """Get CSVGraphParserService through DI container."""
    return container.csv_graph_parser_service()


def get_features_service(container: ApplicationContainer = Depends(get_container)):
    """Get FeaturesRegistryService through DI container."""
    return container.features_registry_service()


def get_dependency_checker_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Get DependencyCheckerService through DI container."""
    return container.dependency_checker_service()


def get_validation_cache_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Get ValidationCacheService through DI container."""
    return container.validation_cache_service()


def get_graph_definition_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Get GraphDefinitionService through DI container."""
    return container.graph_definition_service()


def get_graph_runner_service(container: ApplicationContainer = Depends(get_container)):
    """Get GraphRunnerService through DI container."""
    return container.graph_runner_service()


def get_compilation_service(container: ApplicationContainer = Depends(get_container)):
    """Get CompilationService through DI container."""
    return container.compilation_service()


def get_graph_scaffold_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Get GraphScaffoldService through DI container."""
    return container.graph_scaffold_service()


def get_logging_service(container: ApplicationContainer = Depends(get_container)):
    """Get LoggingService through DI container."""
    return container.logging_service()


# Export the adapter class and compatibility functions
__all__ = [
    "FastAPIDependencyAdapter",
    "get_container",
    "get_service_adapter",
    "get_app_config_service",
    "get_storage_service_manager",
    "get_auth_service",
    "get_validation_service",
    "get_csv_parser_service",
    "get_features_service",
    "get_dependency_checker_service",
    "get_validation_cache_service",
    "get_graph_definition_service",
    "get_graph_runner_service",
    "get_compilation_service",
    "get_graph_scaffold_service",
    "get_logging_service",
]
