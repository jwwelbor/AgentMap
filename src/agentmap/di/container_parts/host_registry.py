"""Host registry container part with helper utilities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from dependency_injector import containers, providers


class HostRegistryContainer(containers.DeclarativeContainer):
    """Provides host registry services and helper utilities."""

    logging_service = providers.Dependency()

    host_service_registry = providers.Singleton(
        "agentmap.services.host_service_registry.HostServiceRegistry",
        logging_service,
    )

    host_protocol_configuration_service = providers.Singleton(
        "agentmap.services.host_protocol_configuration_service.HostProtocolConfigurationService",
        host_service_registry,
        logging_service,
    )

    # -- Helper methods ---------------------------------------------------------

    def register_host_service(
        self,
        service_name: str,
        service_class_path: str,
        dependencies: Optional[List[str]] = None,
        protocols: Optional[List[Type]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        singleton: bool = True,
    ) -> None:
        from dependency_injector import providers as _providers

        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not service_class_path:
            raise ValueError("Service class path cannot be empty")
        if hasattr(self, service_name):
            raise ValueError(
                f"Service '{service_name}' conflicts with existing AgentMap service"
            )

        registry = self.host_service_registry()
        if registry.is_service_registered(service_name):
            self.logging_service().get_logger("agentmap.di.host").warning(
                f"Overriding existing host service: {service_name}"
            )

        dep_providers = []
        if dependencies:
            for dependency in dependencies:
                if hasattr(self, dependency):
                    dep_providers.append(getattr(self, dependency))
                elif registry.is_service_registered(dependency):
                    provider = registry.get_service_provider(dependency)
                    if provider is None:
                        raise ValueError(
                            f"Host service '{dependency}' is registered but provider not found"
                        )
                    dep_providers.append(provider)
                else:
                    raise ValueError(
                        f"Dependency '{dependency}' not found for service '{service_name}'"
                    )

        provider = (
            _providers.Singleton(service_class_path, *dep_providers)
            if singleton
            else _providers.Factory(service_class_path, *dep_providers)
        )
        try:
            setattr(self, service_name, provider)
            registry.register_service_provider(
                service_name,
                provider,
                protocols=protocols,
                metadata=metadata,
            )
        except Exception as exc:  # pragma: no cover - safety net
            if hasattr(self, service_name):
                delattr(self, service_name)
            raise ValueError(
                f"Failed to register host service '{service_name}': {exc}"
            ) from exc

    def register_host_factory(
        self,
        service_name: str,
        factory_function: callable,
        dependencies: Optional[List[str]] = None,
        protocols: Optional[List[Type]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from dependency_injector import providers as _providers

        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not factory_function:
            raise ValueError("Factory function cannot be empty")
        if hasattr(self, service_name):
            raise ValueError(
                f"Service '{service_name}' conflicts with existing AgentMap service"
            )

        registry = self.host_service_registry()
        dep_providers = []
        if dependencies:
            for dependency in dependencies:
                if hasattr(self, dependency):
                    dep_providers.append(getattr(self, dependency))
                elif registry.is_service_registered(dependency):
                    provider = registry.get_service_provider(dependency)
                    if provider is None:
                        raise ValueError(
                            f"Host service '{dependency}' is registered but provider not found"
                        )
                    dep_providers.append(provider)
                else:
                    raise ValueError(
                        f"Dependency '{dependency}' not found for service '{service_name}'"
                    )

        provider = _providers.Singleton(factory_function, *dep_providers)
        try:
            setattr(self, service_name, provider)
            registry.register_service_provider(
                service_name,
                provider,
                protocols=protocols,
                metadata=metadata,
            )
        except Exception as exc:  # pragma: no cover - safety net
            if hasattr(self, service_name):
                delattr(self, service_name)
            raise ValueError(
                f"Failed to register host factory '{service_name}': {exc}"
            ) from exc

    def get_host_services(self) -> Dict[str, Dict[str, Any]]:
        registry = self.host_service_registry()
        result: Dict[str, Dict[str, Any]] = {}
        try:
            for name in registry.list_registered_services():
                if name.startswith("protocol:"):
                    continue
                provider = registry.get_service_provider(name)
                metadata = registry.get_service_metadata(name) or {}
                protocols = registry.get_service_protocols(name)
                result[name] = {
                    "provider": provider,
                    "metadata": metadata,
                    "protocols": [proto.__name__ for proto in protocols],
                }
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logging_service().get_logger("agentmap.di.host").error(
                f"Failed to get host services: {exc}"
            )
        return result

    def get_protocol_implementations(self) -> Dict[str, str]:
        registry = self.host_service_registry()
        implementations: Dict[str, str] = {}
        try:
            for name in registry.list_registered_services():
                if name.startswith("protocol:"):
                    continue
                for protocol in registry.get_service_protocols(name):
                    implementations[protocol.__name__] = name
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logging_service().get_logger("agentmap.di.host").error(
                f"Failed to get protocol implementations: {exc}"
            )
        return implementations

    def configure_host_protocols(self, agent: Any) -> int:
        try:
            return self.host_protocol_configuration_service().configure_host_protocols(
                agent
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            try:
                self.logging_service().get_logger("agentmap.di.host").error(
                    f"Failed to configure host protocols: {exc}"
                )
            except Exception:
                pass
            return 0

    def has_host_service(self, service_name: str) -> bool:
        try:
            return self.host_service_registry().is_service_registered(service_name)
        except Exception:
            return False

    def get_host_service_instance(self, service_name: str):
        try:
            provider = self.host_service_registry().get_service_provider(service_name)
            if provider and callable(provider):
                return provider()
            return provider
        except Exception:
            return None

    def clear_host_services(self) -> None:
        registry = self.host_service_registry()
        try:
            service_names = registry.list_registered_services()
            for name in service_names:
                if not name.startswith("protocol:") and hasattr(self, name):
                    delattr(self, name)
            registry.clear_registry()
            self.logging_service().get_logger("agentmap.di.host").info(
                "Cleared all host services"
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            try:
                self.logging_service().get_logger("agentmap.di.host").error(
                    f"Failed to clear host services: {exc}"
                )
            except Exception:
                pass
