"""Core service configurator for AgentMap."""

from typing import Any, Optional
from agentmap.services.protocols import (
    BlobStorageCapableAgent, LLMCapableAgent, OrchestrationCapableAgent,
    PromptCapableAgent, StorageCapableAgent,
)
from .service_configurator_base import configure_service_strict, ServiceConfigSpec


class CoreServiceConfigurator:
    CORE_SERVICE_SPECS = [
        ServiceConfigSpec(LLMCapableAgent, "llm_service", "LLM service", "configure_llm_service"),
        ServiceConfigSpec(StorageCapableAgent, "storage_service_manager", "storage service", "configure_storage_service"),
        ServiceConfigSpec(PromptCapableAgent, "prompt_manager_service", "prompt service", "configure_prompt_service"),
        ServiceConfigSpec(OrchestrationCapableAgent, "orchestrator_service", "orchestrator service", "configure_orchestrator_service"),
        ServiceConfigSpec(BlobStorageCapableAgent, "blob_storage_service", "blob storage service", "configure_blob_storage_service"),
    ]

    def __init__(self, llm_service: Any, storage_service_manager: Any, logger: Any,
                 prompt_manager_service: Optional[Any] = None, orchestrator_service: Optional[Any] = None,
                 blob_storage_service: Optional[Any] = None):
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.blob_storage_service = blob_storage_service
        self.logger = logger

    def configure(self, agent: Any) -> int:
        agent_name = getattr(agent, "name", "unknown")
        self.logger.trace(f"[AgentServiceInjectionService] Configuring core services for agent: {agent_name}")
        services_configured = 0
        try:
            for spec in self.CORE_SERVICE_SPECS:
                service = getattr(self, spec.service_attr, None)
                if configure_service_strict(agent, spec.protocol_class, service, spec.service_name,
                                          spec.configure_method, self.logger, agent_name):
                    services_configured += 1
            if services_configured > 0:
                self.logger.debug(f"[AgentServiceInjectionService] Configured {services_configured} core services for {agent_name}")
            else:
                self.logger.trace(f"[AgentServiceInjectionService] No core services configured for {agent_name}")
            return services_configured
        except Exception as e:
            self.logger.error(f"[AgentServiceInjectionService] Critical failure during core service configuration for {agent_name}: {e}")
            raise
