"""
Base utilities for service configuration in AgentMap.

This module provides common helper functions and patterns used across
different service configurators to reduce code duplication.
"""

from typing import Any, Callable, Optional, Type


def configure_service_strict(
    agent: Any,
    protocol_class: Type,
    service: Any,
    service_name: str,
    configure_method: str,
    logger: Any,
    agent_name: str,
) -> bool:
    """
    Configure a service on an agent using strict mode (raise on failure).

    This helper encapsulates the common pattern for service configuration:
    1. Check if agent implements the protocol
    2. Verify service is available
    3. Call the configuration method
    4. Log success/failure

    Args:
        agent: Agent instance to configure
        protocol_class: Protocol class to check against
        service: Service instance to inject
        service_name: Human-readable service name for logging
        configure_method: Name of the configuration method to call
        logger: Logger instance for logging
        agent_name: Agent name for logging

    Returns:
        True if service was configured, False if agent doesn't implement protocol

    Raises:
        Exception: If service is None or configuration fails
    """
    if not isinstance(agent, protocol_class):
        return False

    if service is None:
        error_msg = f"{service_name} not available for agent {agent_name}"
        logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
        raise Exception(error_msg)

    try:
        getattr(agent, configure_method)(service)
        logger.debug(
            f"[AgentServiceInjectionService] ✅ Configured {service_name} for {agent_name}"
        )
        return True
    except Exception as e:
        logger.error(
            f"[AgentServiceInjectionService] ❌ Failed to configure {service_name} for {agent_name}: {e}"
        )
        raise


def configure_storage_service_strict(
    agent: Any,
    protocol_class: Type,
    storage_manager: Any,
    service_type: str,
    service_name: str,
    configure_method: str,
    logger: Any,
    agent_name: str,
) -> bool:
    """
    Configure a storage service on an agent using strict mode.

    Similar to configure_service_strict but fetches service from storage manager.

    Args:
        agent: Agent instance to configure
        protocol_class: Protocol class to check against
        storage_manager: Storage service manager to get service from
        service_type: Type of service to get from manager (e.g., "csv", "json")
        service_name: Human-readable service name for logging
        configure_method: Name of the configuration method to call
        logger: Logger instance for logging
        agent_name: Agent name for logging

    Returns:
        True if service was configured, False if agent doesn't implement protocol

    Raises:
        Exception: If service is unavailable or configuration fails
    """
    if not isinstance(agent, protocol_class):
        return False

    try:
        service = storage_manager.get_service(service_type)
        if service is None:
            error_msg = f"{service_name} not available for agent {agent_name}"
            logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
            raise Exception(error_msg)

        getattr(agent, configure_method)(service)
        logger.debug(
            f"[AgentServiceInjectionService] ✅ Configured {service_name} for {agent_name}"
        )
        return True
    except Exception as e:
        logger.error(
            f"[AgentServiceInjectionService] ❌ Failed to configure {service_name} for {agent_name}: {e}"
        )
        raise


class ServiceConfigSpec:
    """
    Specification for a service configuration.

    Encapsulates all the information needed to configure a specific service
    on an agent.
    """

    def __init__(
        self,
        protocol_class: Type,
        service_attr: str,
        service_name: str,
        configure_method: str,
    ):
        """
        Initialize a service configuration specification.

        Args:
            protocol_class: Protocol class to check against
            service_attr: Attribute name on the configurator containing the service
            service_name: Human-readable service name for logging
            configure_method: Name of the configuration method to call on agent
        """
        self.protocol_class = protocol_class
        self.service_attr = service_attr
        self.service_name = service_name
        self.configure_method = configure_method


class StorageServiceConfigSpec:
    """
    Specification for a storage service configuration.

    Similar to ServiceConfigSpec but includes storage type for manager lookup.
    """

    def __init__(
        self,
        protocol_class: Type,
        storage_type: str,
        service_name: str,
        configure_method: str,
    ):
        """
        Initialize a storage service configuration specification.

        Args:
            protocol_class: Protocol class to check against
            storage_type: Type of service to get from storage manager
            service_name: Human-readable service name for logging
            configure_method: Name of the configuration method to call on agent
        """
        self.protocol_class = protocol_class
        self.storage_type = storage_type
        self.service_name = service_name
        self.configure_method = configure_method
