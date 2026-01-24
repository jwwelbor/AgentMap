"""Storage service configurator for AgentMap."""

from typing import Any, Optional, Set

from agentmap.services.protocols import (
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    StorageCapableAgent,
    VectorCapableAgent,
)

from .service_configurator_base import (
    StorageServiceConfigSpec,
    configure_storage_service_strict,
)


class StorageServiceConfigurator:
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

    # All storage-related service names for early exit check
    STORAGE_SERVICE_NAMES = {"csv", "json", "file", "vector", "memory", "storage"}

    def __init__(self, storage_service_manager: Any, logging_service: Any):
        self.storage_service_manager = storage_service_manager
        self.logger = logging_service.get_class_logger(self)

    def _should_check_storage(self, required_services: Optional[Set[str]]) -> bool:
        """Check if any storage services are needed based on required_services."""
        if required_services is None:
            return True  # No filter, check all
        return bool(self.STORAGE_SERVICE_NAMES & required_services)

    def configure_storage_services(
        self, agent: Any, required_services: Optional[Set[str]] = None
    ) -> int:
        """
        Configure storage services on an agent using protocol-based injection.

        Args:
            agent: Agent instance to configure storage services for
            required_services: Optional set of service names to filter by.
                              If provided, only storage services matching these names are checked.

        Returns:
            Number of storage services successfully configured
        """
        agent_name = getattr(agent, "name", "unknown")
        self.logger.trace(
            f"[AgentServiceInjectionService] Configuring storage services for agent: {agent_name}"
        )

        # Early exit if no storage services are required
        if not self._should_check_storage(required_services):
            self.logger.trace(
                f"[AgentServiceInjectionService] Skipping storage services for {agent_name} (not in required_services)"
            )
            return 0

        services_configured = 0
        specs_checked = 0
        try:
            for spec in self.STORAGE_SERVICE_SPECS:
                # Skip storage types not in required_services filter
                if (
                    required_services is not None
                    and spec.storage_type not in required_services
                ):
                    continue
                specs_checked += 1
                if configure_storage_service_strict(
                    agent,
                    spec.protocol_class,
                    self.storage_service_manager,
                    spec.storage_type,
                    spec.service_name,
                    spec.configure_method,
                    self.logger,
                    agent_name,
                ):
                    services_configured += 1
            if services_configured == 0 and isinstance(agent, StorageCapableAgent):
                # Check if storage is in required services before configuring default
                if required_services is None or "storage" in required_services:
                    default_service = self.storage_service_manager.get_service("file")
                    agent.configure_storage_service(default_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] Configured default storage service for {agent_name}"
                    )
                    services_configured += 1
            if services_configured > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] Configured {services_configured} storage services for {agent_name} "
                    f"(checked {specs_checked}/{len(self.STORAGE_SERVICE_SPECS)} specs)"
                )
            return services_configured
        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] Critical failure during storage service configuration for {agent_name}: {e}"
            )
            raise

    def requires_storage_services(self, agent: Any) -> bool:
        return isinstance(
            agent,
            (
                CSVCapableAgent,
                JSONCapableAgent,
                FileCapableAgent,
                VectorCapableAgent,
                MemoryCapableAgent,
                StorageCapableAgent,
            ),
        )

    def get_required_service_types(self, agent: Any) -> list[str]:
        required = []
        if isinstance(agent, CSVCapableAgent):
            required.append("csv")
        if isinstance(agent, JSONCapableAgent):
            required.append("json")
        if isinstance(agent, FileCapableAgent):
            required.append("file")
        if isinstance(agent, VectorCapableAgent):
            required.append("vector")
        if isinstance(agent, MemoryCapableAgent):
            required.append("memory")
        if isinstance(agent, StorageCapableAgent) and not required:
            required.append("storage (generic)")
        return required
