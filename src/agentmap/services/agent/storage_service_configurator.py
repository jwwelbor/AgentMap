"""Storage service configurator for AgentMap."""

from typing import Any
from agentmap.services.protocols import StorageCapableAgent
from agentmap.services.storage.protocols import (
    CSVCapableAgent, FileCapableAgent, JSONCapableAgent, MemoryCapableAgent, VectorCapableAgent,
)
from .service_configurator_base import configure_storage_service_strict, StorageServiceConfigSpec


class StorageServiceConfigurator:
    STORAGE_SERVICE_SPECS = [
        StorageServiceConfigSpec(CSVCapableAgent, "csv", "CSV service", "configure_csv_service"),
        StorageServiceConfigSpec(JSONCapableAgent, "json", "JSON service", "configure_json_service"),
        StorageServiceConfigSpec(FileCapableAgent, "file", "File service", "configure_file_service"),
        StorageServiceConfigSpec(VectorCapableAgent, "vector", "Vector service", "configure_vector_service"),
        StorageServiceConfigSpec(MemoryCapableAgent, "memory", "Memory service", "configure_memory_service"),
    ]

    def __init__(self, storage_service_manager: Any, logger: Any):
        self.storage_service_manager = storage_service_manager
        self.logger = logger

    def configure(self, agent: Any) -> int:
        agent_name = getattr(agent, "name", "unknown")
        self.logger.trace(f"[AgentServiceInjectionService] Configuring storage services for agent: {agent_name}")
        services_configured = 0
        try:
            for spec in self.STORAGE_SERVICE_SPECS:
                if configure_storage_service_strict(agent, spec.protocol_class, self.storage_service_manager,
                                                   spec.storage_type, spec.service_name, spec.configure_method,
                                                   self.logger, agent_name):
                    services_configured += 1
            if services_configured == 0 and isinstance(agent, StorageCapableAgent):
                default_service = self.storage_service_manager.get_service("file")
                agent.configure_storage_service(default_service)
                self.logger.debug(f"[AgentServiceInjectionService] Configured default storage service for {agent_name}")
                services_configured += 1
            if services_configured > 0:
                self.logger.debug(f"[AgentServiceInjectionService] Configured {services_configured} storage services for {agent_name}")
            return services_configured
        except Exception as e:
            self.logger.error(f"[AgentServiceInjectionService] Critical failure during storage service configuration for {agent_name}: {e}")
            raise

    def requires_storage_services(self, agent: Any) -> bool:
        return isinstance(agent, (CSVCapableAgent, JSONCapableAgent, FileCapableAgent, VectorCapableAgent, MemoryCapableAgent, StorageCapableAgent))

    def get_required_service_types(self, agent: Any) -> list[str]:
        required = []
        if isinstance(agent, CSVCapableAgent): required.append("csv")
        if isinstance(agent, JSONCapableAgent): required.append("json")
        if isinstance(agent, FileCapableAgent): required.append("file")
        if isinstance(agent, VectorCapableAgent): required.append("vector")
        if isinstance(agent, MemoryCapableAgent): required.append("memory")
        if isinstance(agent, StorageCapableAgent) and not required: required.append("storage (generic)")
        return required
