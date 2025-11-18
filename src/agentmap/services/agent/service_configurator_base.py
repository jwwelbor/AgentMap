"""Base utilities for service configuration in AgentMap."""

from typing import Any, Type


def configure_service_strict(
    agent: Any, protocol_class: Type, service: Any, service_name: str,
    configure_method: str, logger: Any, agent_name: str,
) -> bool:
    """Configure a service on an agent using strict mode."""
    if not isinstance(agent, protocol_class):
        return False
    if service is None:
        error_msg = f"{service_name} not available for agent {agent_name}"
        logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
        raise Exception(error_msg)
    try:
        getattr(agent, configure_method)(service)
        logger.debug(f"[AgentServiceInjectionService] ✅ Configured {service_name} for {agent_name}")
        return True
    except Exception as e:
        logger.error(f"[AgentServiceInjectionService] ❌ Failed to configure {service_name} for {agent_name}: {e}")
        raise


def configure_storage_service_strict(
    agent: Any, protocol_class: Type, storage_manager: Any, service_type: str,
    service_name: str, configure_method: str, logger: Any, agent_name: str,
) -> bool:
    """Configure a storage service on an agent using strict mode."""
    if not isinstance(agent, protocol_class):
        return False
    try:
        service = storage_manager.get_service(service_type)
        if service is None:
            error_msg = f"{service_name} not available for agent {agent_name}"
            logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
            raise Exception(error_msg)
        getattr(agent, configure_method)(service)
        logger.debug(f"[AgentServiceInjectionService] ✅ Configured {service_name} for {agent_name}")
        return True
    except Exception as e:
        logger.error(f"[AgentServiceInjectionService] ❌ Failed to configure {service_name} for {agent_name}: {e}")
        raise


class ServiceConfigSpec:
    def __init__(self, protocol_class: Type, service_attr: str, service_name: str, configure_method: str):
        self.protocol_class = protocol_class
        self.service_attr = service_attr
        self.service_name = service_name
        self.configure_method = configure_method


class StorageServiceConfigSpec:
    def __init__(self, protocol_class: Type, storage_type: str, service_name: str, configure_method: str):
        self.protocol_class = protocol_class
        self.storage_type = storage_type
        self.service_name = service_name
        self.configure_method = configure_method
