"""
Agent service injection service - main orchestration service.

Coordinates service injection across all agent service types using
specialized configurator modules. This service maintains backward
compatibility while delegating to focused, single-responsibility modules.
"""

from typing import Any, Optional

from agentmap.services.agent.core_service_configurator import CoreServiceConfigurator
from agentmap.services.agent.host_service_configurator import HostServiceConfigurator
from agentmap.services.agent.service_status_analyzer import ServiceStatusAnalyzer
from agentmap.services.agent.storage_service_configurator import (
    StorageServiceConfigurator,
)
from agentmap.services.host_protocol_configuration_service import (
    HostProtocolConfigurationService,
)
from agentmap.services.llm_service import LLMService
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    LLMCapableAgent,
    MemoryCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
    VectorCapableAgent,
)
from agentmap.services.storage.manager import StorageServiceManager



class AgentServiceInjectionService:
    """

    Delegates to specialized configurator classes for different service categories:
    - CoreServiceConfigurator: LLM, Storage, Prompt, Orchestration, BlobStorage services
    - StorageServiceConfigurator: CSV, JSON, File, Vector, Memory services
    - ServiceStatusAnalyzer: Status and debugging methods
    """

    def __init__(
        self,
        llm_service: LLMService,
        storage_service_manager: StorageServiceManager,
        logging_service: LoggingService,
        host_protocol_configuration_service: Optional[
            HostProtocolConfigurationService
        ] = None,
        prompt_manager_service: Optional[Any] = None,
        orchestrator_service: Optional[Any] = None,
        graph_checkpoint_service: Optional[Any] = None,
        blob_storage_service: Optional[Any] = None,
    ):
        """
        Initialize agent service injection service.

        Args:
            llm_service: Service for LLM operations and injection
            storage_service_manager: Manager for storage service injection
            logging_service: Service for logging operations
            host_protocol_configuration_service: Optional service for host protocol configuration
            prompt_manager_service: Optional service for prompt template resolution and formatting
            orchestrator_service: Optional service for orchestration business logic
            graph_checkpoint_service: Optional service for graph execution checkpoints
            blob_storage_service: Optional service for blob storage operations
        """
        # Core required services
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self._logger = logging_service.get_class_logger(self)

        # Optional core services
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.graph_checkpoint_service = graph_checkpoint_service
        self.blob_storage_service = blob_storage_service

        # Host services (optional)
        self.host_protocol_configuration = host_protocol_configuration_service
        self._host_services_available = host_protocol_configuration_service is not None

        # Initialize specialized configurator modules
        self._core_configurator = CoreServiceConfigurator(
            llm_service=llm_service,
            storage_service_manager=storage_service_manager,
            logging_service=logging_service,
            prompt_manager_service=prompt_manager_service,
            orchestrator_service=orchestrator_service,
            blob_storage_service=blob_storage_service,
        )

        self._storage_configurator = StorageServiceConfigurator(
            storage_service_manager=storage_service_manager,
            logging_service=logging_service,
        )

        self._host_configurator = HostServiceConfigurator(
            logging_service=logging_service,
            host_protocol_configuration_service=host_protocol_configuration_service,
        )

        self._status_analyzer = ServiceStatusAnalyzer(
            llm_service=llm_service,
            storage_service_manager=storage_service_manager,
            logging_service=logging_service,
            prompt_manager_service=prompt_manager_service,
            orchestrator_service=orchestrator_service,
            graph_checkpoint_service=graph_checkpoint_service,
            blob_storage_service=blob_storage_service,
            host_protocol_configuration_service=host_protocol_configuration_service,
        )

        self._logger.debug(
            "[AgentServiceInjectionService] Initialized with core service dependencies"
        )

    @property
    def logger(self):
        """Get the logger instance."""
        return self._logger

    @logger.setter
    def logger(self, value):
        """Set the logger and propagate to configurators."""
        self._logger = value
        if hasattr(self, "_core_configurator"):
            self._core_configurator.logger = value
        if hasattr(self, "_storage_configurator"):
            self._storage_configurator.logger = value

    def configure_core_services(self, agent: Any) -> int:
        """
        Configure core AgentMap services on an agent using protocol-based injection.

        Args:
            agent: Agent instance to configure services for

        Returns:
            Number of core services successfully configured

        Raises:
            Exception: If service is unavailable or configuration fails
        """
        return self._core_configurator.configure_core_services(agent)

    def configure_storage_services(self, agent: Any) -> int:
        """
        Configure storage services on an agent using protocol-based injection.

        Args:
            agent: Agent instance to configure storage services for

        Returns:
            Number of storage services successfully configured

        Raises:
            Exception: If storage service is unavailable or configuration fails
        """
        return self._storage_configurator.configure_storage_services(agent)

    def requires_storage_services(self, agent: Any) -> bool:
        """
        Check if an agent requires any storage services.

        Args:
            agent: Agent instance to check

        Returns:
            True if agent implements any storage service capability protocols
        """
        return self._storage_configurator.requires_storage_services(agent)

    def get_required_service_types(self, agent: Any) -> list[str]:
        """
        Get list of storage service types required by an agent.

        Args:
            agent: Agent instance to check

        Returns:
            List of required storage service type names
        """
        return self._storage_configurator.get_required_service_types(agent)

    def configure_host_services(self, agent: Any) -> int:
        """
        Configure host-defined services using HostProtocolConfigurationService.

        Args:
            agent: Agent instance to configure host services for

        Returns:
            Number of host services successfully configured
        """
        return self._host_configurator.configure_host_services(agent)

    def configure_execution_tracker(
        self, agent: Any, tracker: Optional[Any] = None
    ) -> bool:
        """
        Configure execution tracker on an agent if the agent supports it.

        Args:
            agent: Agent instance to configure execution tracker for
            tracker: ExecutionTracker instance or None

        Returns:
            True if tracker was configured successfully, False otherwise
        """
        return self._host_configurator.configure_execution_tracker(agent, tracker)

    def configure_all_services(self, agent: Any, tracker: Optional[Any] = None) -> dict:
        """
        Configure core services, storage services, host services, and execution tracker for an agent.

        Args:
            agent: Agent instance to configure all services for
            tracker: Optional ExecutionTracker instance for execution monitoring

        Returns:
            Dictionary with configuration summary including counts and status
        """
        agent_name = getattr(agent, "name", "unknown")
        self._logger.debug(
            f"[AgentServiceInjectionService] Configuring all services for agent: {agent_name}"
        )

        # Configure all service categories
        core_configured = self.configure_core_services(agent)
        storage_configured = self.configure_storage_services(agent)
        host_configured = self.configure_host_services(agent)
        tracker_configured = self.configure_execution_tracker(agent, tracker)

        total_configured = (
            core_configured
            + storage_configured
            + host_configured
            + (1 if tracker_configured else 0)
        )

        summary = {
            "agent_name": agent_name,
            "core_services_configured": core_configured,
            "storage_services_configured": storage_configured,
            "host_services_configured": host_configured,
            "execution_tracker_configured": tracker_configured,
            "total_services_configured": total_configured,
            "configuration_status": (
                "success" if total_configured > 0 else "no_services_configured"
            ),
            "service_details": {
                "core_services_success": core_configured > 0,
                "storage_services_success": storage_configured > 0,
                "host_services_available": self._host_services_available,
                "host_services_success": (
                    host_configured > 0 if self._host_services_available else None
                ),
                "execution_tracker_available": tracker is not None,
                "execution_tracker_success": tracker_configured,
            },
        }

        self._logger.debug(
            f"[AgentServiceInjectionService] Configuration summary for {agent_name}: "
            f"core={core_configured}, storage={storage_configured}, host={host_configured}, "
            f"tracker={tracker_configured}, total={total_configured}"
        )

        return summary

    def get_service_injection_status(self, agent: Any) -> dict:
        """
        Get detailed service injection status for a specific agent for debugging.

        Args:
            agent: Agent instance to analyze

        Returns:
            Dictionary with detailed service injection status and capabilities
        """
        return self._status_analyzer.get_service_injection_status(agent)

    def get_service_availability_status(self) -> dict:
        """
        Get status of service availability for debugging and monitoring.

        Returns:
            Dictionary with service availability information
        """
        return self._status_analyzer.get_service_availability_status()
