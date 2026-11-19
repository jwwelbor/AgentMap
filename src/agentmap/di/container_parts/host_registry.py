"""Host registry container part."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dependency_injector import containers, providers

if TYPE_CHECKING:
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
    )
    from agentmap.services.host_protocol_configuration_service import (
        HostProtocolConfigurationService,
    )
    from agentmap.services.host_service_registry import HostServiceRegistry
    from agentmap.services.logging_service import LoggingService


class HostRegistryContainer(containers.DeclarativeContainer):
    """Provides host registry services."""

    logging_service: Any = providers.Dependency()
    declaration_registry_service: Any = providers.Dependency()
    app_config_service: Any = providers.Dependency()

    @staticmethod
    def _create_host_service_registry(
        logging_service: LoggingService,
    ) -> HostServiceRegistry:
        from agentmap.services.host_service_registry import HostServiceRegistry

        return HostServiceRegistry(logging_service)

    host_service_registry = providers.Singleton(
        _create_host_service_registry,
        logging_service,
    )

    @staticmethod
    def _create_host_protocol_configuration_service(
        host_service_registry: HostServiceRegistry,
        logging_service: LoggingService,
        declaration_registry_service: DeclarationRegistryService,
        app_config_service: AppConfigService,
    ) -> HostProtocolConfigurationService:
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
