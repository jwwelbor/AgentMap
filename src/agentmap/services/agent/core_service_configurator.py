"""
Core service configurator for AgentMap.

This module handles configuration of core AgentMap services (LLM, Storage,
Prompt, Orchestration, BlobStorage) on agent instances using protocol-based
injection.
"""

from typing import Any, Optional

from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    LLMCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
)

from .service_configurator_base import configure_service_strict, ServiceConfigSpec


class CoreServiceConfigurator:
    """
    Handles configuration of core AgentMap services on agent instances.

    This class encapsulates the logic for injecting core services (LLM, Storage,
    Prompt, Orchestration, BlobStorage) into agents that implement the
    corresponding capability protocols.
    """

    # Core service configuration specifications
    CORE_SERVICE_SPECS = [
        ServiceConfigSpec(
            LLMCapableAgent, "llm_service", "LLM service", "configure_llm_service"
        ),
        ServiceConfigSpec(
            StorageCapableAgent,
            "storage_service_manager",
            "storage service",
            "configure_storage_service",
        ),
        ServiceConfigSpec(
            PromptCapableAgent,
            "prompt_manager_service",
            "prompt service",
            "configure_prompt_service",
        ),
        ServiceConfigSpec(
            OrchestrationCapableAgent,
            "orchestrator_service",
            "orchestrator service",
            "configure_orchestrator_service",
        ),
        ServiceConfigSpec(
            BlobStorageCapableAgent,
            "blob_storage_service",
            "blob storage service",
            "configure_blob_storage_service",
        ),
    ]

    def __init__(
        self,
        llm_service: Any,
        storage_service_manager: Any,
        logger: Any,
        prompt_manager_service: Optional[Any] = None,
        orchestrator_service: Optional[Any] = None,
        blob_storage_service: Optional[Any] = None,
    ):
        """
        Initialize core service configurator.

        Args:
            llm_service: Service for LLM operations
            storage_service_manager: Manager for storage services
            logger: Logger instance for logging
            prompt_manager_service: Optional service for prompt template resolution
            orchestrator_service: Optional service for orchestration business logic
            blob_storage_service: Optional service for blob storage operations
        """
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.blob_storage_service = blob_storage_service
        self.logger = logger

    def configure(self, agent: Any) -> int:
        """
        Configure core AgentMap services on an agent using protocol-based injection.

        Performs isinstance() checks against agent capability protocols and calls
        the appropriate configuration methods for each supported service type.
        Uses strict exception handling - if agent implements protocol but service
        is unavailable, an exception is raised.

        Args:
            agent: Agent instance to configure services for

        Returns:
            Number of core services successfully configured

        Raises:
            Exception: If service is unavailable or configuration fails
        """
        agent_name = getattr(agent, "name", "unknown")
        self.logger.trace(
            f"[AgentServiceInjectionService] Configuring core services for agent: {agent_name}"
        )

        services_configured = 0

        try:
            for spec in self.CORE_SERVICE_SPECS:
                service = getattr(self, spec.service_attr, None)
                if configure_service_strict(
                    agent=agent,
                    protocol_class=spec.protocol_class,
                    service=service,
                    service_name=spec.service_name,
                    configure_method=spec.configure_method,
                    logger=self.logger,
                    agent_name=agent_name,
                ):
                    services_configured += 1

            # Log summary
            if services_configured > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] Configured {services_configured} core services for {agent_name}"
                )
            else:
                self.logger.trace(
                    f"[AgentServiceInjectionService] No core services configured for {agent_name} (agent does not implement core service protocols)"
                )

            return services_configured

        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] Critical failure during core service configuration for {agent_name}: {e}"
            )
            raise

    def get_protocol_specs(self) -> list:
        """
        Get list of core service protocol specifications.

        Returns:
            List of ServiceConfigSpec for core services
        """
        return self.CORE_SERVICE_SPECS

    def get_service_availability(self) -> dict:
        """
        Get availability status for all core services.

        Returns:
            Dictionary mapping service names to availability status
        """
        return {
            "llm_service_available": self.llm_service is not None,
            "storage_service_manager_available": self.storage_service_manager is not None,
            "prompt_manager_service_available": self.prompt_manager_service is not None,
            "orchestrator_service_available": self.orchestrator_service is not None,
            "blob_storage_service_available": self.blob_storage_service is not None,
        }
