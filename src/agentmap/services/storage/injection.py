"""
Declarative storage service injection for AgentMap.

This module provides utilities for injecting storage services into agents
based on the protocols they implement, following a declarative approach.
"""

from typing import TYPE_CHECKING, Any

from agentmap.exceptions import AgentInitializationError
from agentmap.services.storage.protocols import (
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    StorageCapableAgent,
    VectorCapableAgent,
)

if TYPE_CHECKING:
    from agentmap.services.logging_service import LoggingService
    from agentmap.services.storage.manager import StorageServiceManager


class StorageServiceInjectionError(AgentInitializationError):
    """Raised when storage service injection fails."""


def inject_storage_services(
    agent_instance: Any,
    storage_service_manager: "StorageServiceManager",
    logger: "LoggingService",
) -> None:
    """
    Inject appropriate storage services based on protocols the agent implements.

    This function uses isinstance checks to determine which specific storage
    services an agent needs and injects them declaratively.

    Args:
        agent_instance: Agent to inject services into
        storage_service_manager: Manager for creating storage services
        logger: Logger for debugging injection process

    Raises:
        StorageServiceInjectionError: If service injection fails
    """
    agent_name = getattr(agent_instance, "name", agent_instance.__class__.__name__)
    injected_services = []

    try:
        # Check each specific service protocol and inject accordingly
        if isinstance(agent_instance, CSVCapableAgent):
            csv_service = storage_service_manager.get_service("csv")
            if csv_service is None:
                raise StorageServiceInjectionError(
                    f"CSV storage service not available for agent '{agent_name}'"
                )
            agent_instance.csv_service = csv_service
            injected_services.append("csv")
            logger.debug(f"[ServiceInjection] Injected CSV service into {agent_name}")

        if isinstance(agent_instance, JSONCapableAgent):
            json_service = storage_service_manager.get_service("json")
            if json_service is None:
                raise StorageServiceInjectionError(
                    f"JSON storage service not available for agent '{agent_name}'"
                )
            agent_instance.json_service = json_service
            injected_services.append("json")
            logger.debug(f"[ServiceInjection] Injected JSON service into {agent_name}")

        if isinstance(agent_instance, FileCapableAgent):
            file_service = storage_service_manager.get_service("file")
            if file_service is None:
                raise StorageServiceInjectionError(
                    f"File storage service not available for agent '{agent_name}'"
                )
            agent_instance.file_service = file_service
            injected_services.append("file")
            logger.debug(f"[ServiceInjection] Injected File service into {agent_name}")

        if isinstance(agent_instance, VectorCapableAgent):
            vector_service = storage_service_manager.get_service("vector")
            if vector_service is None:
                raise StorageServiceInjectionError(
                    f"Vector storage service not available for agent '{agent_name}'"
                )
            agent_instance.vector_service = vector_service
            injected_services.append("vector")
            logger.debug(
                f"[ServiceInjection] Injected Vector service into {agent_name}"
            )

        if isinstance(agent_instance, MemoryCapableAgent):
            memory_service = storage_service_manager.get_service("memory")
            if memory_service is None:
                raise StorageServiceInjectionError(
                    f"Memory storage service not available for agent '{agent_name}'"
                )
            agent_instance.memory_service = memory_service
            injected_services.append("memory")
            logger.debug(
                f"[ServiceInjection] Injected Memory service into {agent_name}"
            )

        # Handle generic StorageCapableAgent for backward compatibility
        # Only inject if no specific services were injected and agent has the property
        if (
            not injected_services
            and isinstance(agent_instance, StorageCapableAgent)
            and hasattr(agent_instance, "storage_service")
        ):

            # Default to file service for generic storage operations
            default_service = storage_service_manager.get_service("file")
            if default_service is None:
                raise StorageServiceInjectionError(
                    f"Default file storage service not available for agent '{agent_name}'"
                )
            agent_instance.storage_service = default_service
            injected_services.append("file (default)")
            logger.debug(
                f"[ServiceInjection] Injected default storage service into {agent_name}"
            )

        if injected_services:
            services_list = ", ".join(injected_services)
            logger.debug(
                f"[ServiceInjection] Successfully injected services into {agent_name}: {services_list}"
            )

    except Exception as e:
        error_msg = (
            f"Failed to inject storage services into agent '{agent_name}': {str(e)}"
        )
        logger.error(f"[ServiceInjection] {error_msg}")
        raise StorageServiceInjectionError(error_msg) from e


def requires_storage_services(agent_instance: Any) -> bool:
    """
    Check if an agent requires any storage services.

    Args:
        agent_instance: Agent to check

    Returns:
        True if agent implements any storage service user protocols
    """
    return (
        isinstance(agent_instance, CSVCapableAgent)
        or isinstance(agent_instance, JSONCapableAgent)
        or isinstance(agent_instance, FileCapableAgent)
        or isinstance(agent_instance, VectorCapableAgent)
        or isinstance(agent_instance, MemoryCapableAgent)
        or isinstance(agent_instance, StorageCapableAgent)
    )


def get_required_service_types(agent_instance: Any) -> list[str]:
    """
    Get list of storage service types required by an agent.

    Args:
        agent_instance: Agent to check

    Returns:
        List of required service type names
    """
    required_services = []

    if isinstance(agent_instance, CSVCapableAgent):
        required_services.append("csv")
    if isinstance(agent_instance, JSONCapableAgent):
        required_services.append("json")
    if isinstance(agent_instance, FileCapableAgent):
        required_services.append("file")
    if isinstance(agent_instance, VectorCapableAgent):
        required_services.append("vector")
    if isinstance(agent_instance, MemoryCapableAgent):
        required_services.append("memory")
    if isinstance(agent_instance, StorageCapableAgent) and not required_services:
        required_services.append("storage (generic)")

    return required_services
