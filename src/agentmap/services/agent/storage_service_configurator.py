"""
Storage service configurator for AgentMap.

This module handles configuration of storage services (CSV, JSON, File, Vector, Memory)
on agent instances using protocol-based injection.
"""

from typing import Any

from agentmap.services.protocols import StorageCapableAgent
from agentmap.services.storage.protocols import (
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    VectorCapableAgent,
)

from .service_configurator_base import (
    configure_storage_service_strict,
    StorageServiceConfigSpec,
)


class StorageServiceConfigurator:
    """
    Handles configuration of storage services on agent instances.

    This class encapsulates the logic for injecting storage services (CSV, JSON,
    File, Vector, Memory) into agents that implement the corresponding capability
    protocols.
    """

    # Storage service configuration specifications
    STORAGE_SERVICE_SPECS = [
        StorageServiceConfigSpec(
            CSVCapableAgent, "csv", "CSV service", "configure_csv_service"
        ),
        StorageServiceConfigSpec(
            JSONCapableAgent, "json", "JSON service", "configure_json_service"
        ),
        StorageServiceConfigSpec(
            FileCapableAgent, "file", "File service", "configure_file_service"
        ),
        StorageServiceConfigSpec(
            VectorCapableAgent, "vector", "Vector service", "configure_vector_service"
        ),
        StorageServiceConfigSpec(
            MemoryCapableAgent, "memory", "Memory service", "configure_memory_service"
        ),
    ]

    def __init__(self, storage_service_manager: Any, logger: Any):
        """
        Initialize storage service configurator.

        Args:
            storage_service_manager: Manager for storage services
            logger: Logger instance for logging
        """
        self.storage_service_manager = storage_service_manager
        self.logger = logger

    def configure(self, agent: Any) -> int:
        """
        Configure storage services on an agent using protocol-based injection.

        Performs isinstance() checks against storage capability protocols and calls
        the appropriate configuration methods for each supported service type.
        Uses strict exception handling - if agent implements protocol but service
        is unavailable, an exception is raised.

        Args:
            agent: Agent instance to configure storage services for

        Returns:
            Number of storage services successfully configured

        Raises:
            Exception: If storage service is unavailable or configuration fails
        """
        agent_name = getattr(agent, "name", "unknown")
        self.logger.trace(
            f"[AgentServiceInjectionService] Configuring storage services for agent: {agent_name}"
        )

        services_configured = 0

        try:
            for spec in self.STORAGE_SERVICE_SPECS:
                if configure_storage_service_strict(
                    agent=agent,
                    protocol_class=spec.protocol_class,
                    storage_manager=self.storage_service_manager,
                    service_type=spec.storage_type,
                    service_name=spec.service_name,
                    configure_method=spec.configure_method,
                    logger=self.logger,
                    agent_name=agent_name,
                ):
                    services_configured += 1

            # Handle generic StorageCapableAgent for backward compatibility
            # Only configure if no specific storage services were configured
            if services_configured == 0 and isinstance(agent, StorageCapableAgent):
                try:
                    # Default to file service for generic storage operations
                    default_service = self.storage_service_manager.get_service("file")
                    agent.configure_storage_service(default_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] Configured default storage service for {agent_name}"
                    )
                    services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] Failed to configure default storage service for {agent_name}: {e}"
                    )
                    raise

            # Log summary
            if services_configured > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] Configured {services_configured} storage services for {agent_name}"
                )
            else:
                self.logger.trace(
                    f"[AgentServiceInjectionService] No storage services configured for {agent_name} (agent does not implement storage protocols)"
                )

            return services_configured

        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] Critical failure during storage service configuration for {agent_name}: {e}"
            )
            raise

    def requires_storage_services(self, agent: Any) -> bool:
        """
        Check if an agent requires any storage services.

        Args:
            agent: Agent instance to check

        Returns:
            True if agent implements any storage service capability protocols
        """
        return (
            isinstance(agent, CSVCapableAgent)
            or isinstance(agent, JSONCapableAgent)
            or isinstance(agent, FileCapableAgent)
            or isinstance(agent, VectorCapableAgent)
            or isinstance(agent, MemoryCapableAgent)
            or isinstance(agent, StorageCapableAgent)
        )

    def get_required_service_types(self, agent: Any) -> list[str]:
        """
        Get list of storage service types required by an agent.

        Args:
            agent: Agent instance to check

        Returns:
            List of required storage service type names
        """
        required_services = []

        if isinstance(agent, CSVCapableAgent):
            required_services.append("csv")
        if isinstance(agent, JSONCapableAgent):
            required_services.append("json")
        if isinstance(agent, FileCapableAgent):
            required_services.append("file")
        if isinstance(agent, VectorCapableAgent):
            required_services.append("vector")
        if isinstance(agent, MemoryCapableAgent):
            required_services.append("memory")
        if isinstance(agent, StorageCapableAgent) and not required_services:
            required_services.append("storage (generic)")

        return required_services

    def get_protocol_specs(self) -> list:
        """
        Get list of storage service protocol specifications.

        Returns:
            List of StorageServiceConfigSpec for storage services
        """
        return self.STORAGE_SERVICE_SPECS
