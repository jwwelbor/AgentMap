"""Host registry container part."""

from __future__ import annotations

from dependency_injector import containers, providers


class HostRegistryContainer(containers.DeclarativeContainer):
    """Provides host registry services."""

    logging_service = providers.Dependency()
    declaration_registry_service = providers.Dependency()
    app_config_service = providers.Dependency()

    @staticmethod
    def _create_host_service_registry(logging_service):
        from agentmap.services.host_service_registry import HostServiceRegistry

        return HostServiceRegistry(logging_service)

    host_service_registry = providers.Singleton(
        _create_host_service_registry,
        logging_service,
    )

    @staticmethod
    def _create_host_protocol_configuration_service(
        host_service_registry,
        logging_service,
        declaration_registry_service,
        app_config_service,
    ):
        from agentmap.services.host_protocol_configuration_service import (
            HostProtocolConfigurationService,
        )

        return HostProtocolConfigurationService(
            host_service_registry,
            logging_service,
            declaration_registry_service,
            app_config_service,
        )

    host_protocol_configuration_service = providers.Singleton(
        _create_host_protocol_configuration_service,
        host_service_registry,
        logging_service,
        declaration_registry_service,
        app_config_service,
    )
