from typing import Any, Optional

from agentmap.services.host_protocol_configuration_service import (
    HostProtocolConfigurationService,
)
from agentmap.services.llm_service import LLMService
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    LLMCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
)
from agentmap.services.storage.manager import StorageServiceManager
from agentmap.services.storage.protocols import (
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    VectorCapableAgent,
)


class AgentServiceInjectionService:
    """
    Service responsible for injecting core services into agent instances.

    """

    def __init__(
        self,
        llm_service: LLMService,
        storage_service_manager: StorageServiceManager,
        logging_service: LoggingService,
        host_protocol_configuration_service: Optional[
            HostProtocolConfigurationService
        ] = None,
        prompt_manager_service: Optional[Any] = None,  # PromptManagerService - optional
        orchestrator_service: Optional[Any] = None,  # OrchestratorService - optional
        graph_checkpoint_service: Optional[
            Any
        ] = None,  # GraphCheckpointService - optional
        blob_storage_service: Optional[Any] = None,  # BlobStorageService - optional
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
        self.logger = logging_service.get_class_logger(self)

        # Optional core services
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.graph_checkpoint_service = graph_checkpoint_service
        self.blob_storage_service = blob_storage_service

        # Host services (optional)
        self.host_protocol_configuration = host_protocol_configuration_service
        self._host_services_available = host_protocol_configuration_service is not None

        self.logger.debug(
            "[AgentServiceInjectionService] Initialized with core service dependencies"
        )

    def configure_core_services(self, agent: Any) -> int:
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

        core_services_configured = 0

        try:
            # Configure LLM service (strict mode)
            if isinstance(agent, LLMCapableAgent):
                if self.llm_service is None:
                    error_msg = f"LLM service not available for agent {agent_name}"
                    self.logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
                    raise Exception(error_msg)

                try:
                    agent.configure_llm_service(self.llm_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured LLM service for {agent_name}"
                    )
                    core_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure LLM service for {agent_name}: {e}"
                    )
                    raise

            # Configure storage service (strict mode)
            if isinstance(agent, StorageCapableAgent):
                if self.storage_service_manager is None:
                    error_msg = (
                        f"Storage service manager not available for agent {agent_name}"
                    )
                    self.logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
                    raise Exception(error_msg)

                try:
                    agent.configure_storage_service(self.storage_service_manager)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured storage service for {agent_name}"
                    )
                    core_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure storage service for {agent_name}: {e}"
                    )
                    raise

            # Configure prompt service (strict mode)
            if isinstance(agent, PromptCapableAgent):
                if self.prompt_manager_service is None:
                    error_msg = f"Prompt service not available for agent {agent_name}"
                    self.logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
                    raise Exception(error_msg)

                try:
                    agent.configure_prompt_service(self.prompt_manager_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured prompt service for {agent_name}"
                    )
                    core_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure prompt service for {agent_name}: {e}"
                    )
                    raise

            # Configure orchestration service (strict mode)
            if isinstance(agent, OrchestrationCapableAgent):
                if self.orchestrator_service is None:
                    error_msg = (
                        f"Orchestrator service not available for agent {agent_name}"
                    )
                    self.logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
                    raise Exception(error_msg)

                try:
                    agent.configure_orchestrator_service(self.orchestrator_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured orchestrator service for {agent_name}"
                    )
                    core_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure orchestrator service for {agent_name}: {e}"
                    )
                    raise

            # Configure blob storage service (strict mode)
            if isinstance(agent, BlobStorageCapableAgent):
                if self.blob_storage_service is None:
                    error_msg = (
                        f"Blob storage service not available for agent {agent_name}"
                    )
                    self.logger.error(f"[AgentServiceInjectionService] ❌ {error_msg}")
                    raise Exception(error_msg)

                try:
                    agent.configure_blob_storage_service(self.blob_storage_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured blob storage service for {agent_name}"
                    )
                    core_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure blob storage service for {agent_name}: {e}"
                    )
                    raise

            # Log summary of core service configuration
            if core_services_configured > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] Configured {core_services_configured} core services for {agent_name}"
                )
            else:
                self.logger.trace(
                    f"[AgentServiceInjectionService] No core services configured for {agent_name} (agent does not implement core service protocols)"
                )

            return core_services_configured

        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] ❌ Critical failure during core service configuration for {agent_name}: {e}"
            )
            raise

    def configure_storage_services(self, agent: Any) -> int:
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

        storage_services_configured = 0

        try:
            # Configure CSV service (strict mode)
            if isinstance(agent, CSVCapableAgent):
                try:
                    csv_service = self.storage_service_manager.get_service("csv")
                    if csv_service is None:
                        error_msg = f"CSV service not available for agent {agent_name}"
                        self.logger.error(
                            f"[AgentServiceInjectionService] ❌ {error_msg}"
                        )
                        raise Exception(error_msg)

                    agent.configure_csv_service(csv_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured CSV service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure CSV service for {agent_name}: {e}"
                    )
                    raise

            # Configure JSON service (strict mode)
            if isinstance(agent, JSONCapableAgent):
                try:
                    json_service = self.storage_service_manager.get_service("json")
                    if json_service is None:
                        error_msg = f"JSON service not available for agent {agent_name}"
                        self.logger.error(
                            f"[AgentServiceInjectionService] ❌ {error_msg}"
                        )
                        raise Exception(error_msg)

                    agent.configure_json_service(json_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured JSON service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure JSON service for {agent_name}: {e}"
                    )
                    raise

            # Configure File service (strict mode)
            if isinstance(agent, FileCapableAgent):
                try:
                    file_service = self.storage_service_manager.get_service("file")
                    if file_service is None:
                        error_msg = f"File service not available for agent {agent_name}"
                        self.logger.error(
                            f"[AgentServiceInjectionService] ❌ {error_msg}"
                        )
                        raise Exception(error_msg)

                    agent.configure_file_service(file_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured File service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure File service for {agent_name}: {e}"
                    )
                    raise

            # Configure Vector service (strict mode)
            if isinstance(agent, VectorCapableAgent):
                try:
                    vector_service = self.storage_service_manager.get_service("vector")
                    if vector_service is None:
                        error_msg = (
                            f"Vector service not available for agent {agent_name}"
                        )
                        self.logger.error(
                            f"[AgentServiceInjectionService] ❌ {error_msg}"
                        )
                        raise Exception(error_msg)

                    agent.configure_vector_service(vector_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured Vector service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure Vector service for {agent_name}: {e}"
                    )
                    raise

            # Configure Memory service (strict mode)
            if isinstance(agent, MemoryCapableAgent):
                try:
                    memory_service = self.storage_service_manager.get_service("memory")
                    if memory_service is None:
                        error_msg = (
                            f"Memory service not available for agent {agent_name}"
                        )
                        self.logger.error(
                            f"[AgentServiceInjectionService] ❌ {error_msg}"
                        )
                        raise Exception(error_msg)

                    agent.configure_memory_service(memory_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured Memory service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure Memory service for {agent_name}: {e}"
                    )
                    raise

            # Handle generic StorageCapableAgent for backward compatibility
            # Only configure if no specific storage services were configured
            if storage_services_configured == 0 and isinstance(
                agent, StorageCapableAgent
            ):
                try:
                    # Default to file service for generic storage operations
                    default_service = self.storage_service_manager.get_service("file")
                    agent.configure_storage_service(default_service)
                    self.logger.debug(
                        f"[AgentServiceInjectionService] ✅ Configured default storage service for {agent_name}"
                    )
                    storage_services_configured += 1
                except Exception as e:
                    self.logger.error(
                        f"[AgentServiceInjectionService] ❌ Failed to configure default storage service for {agent_name}: {e}"
                    )
                    raise

            # Log summary of storage service configuration
            if storage_services_configured > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] Configured {storage_services_configured} storage services for {agent_name}"
                )
            else:
                self.logger.trace(
                    f"[AgentServiceInjectionService] No storage services configured for {agent_name} (agent does not implement storage protocols)"
                )

            return storage_services_configured

        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] ❌ Critical failure during storage service configuration for {agent_name}: {e}"
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

    def configure_host_services(self, agent: Any) -> int:
        """
        Configure host-defined services using HostProtocolConfigurationService.

        Delegates to the host protocol configuration service to handle host-specific
        service injection patterns. This maintains separation of concerns between
        core AgentMap services and host application services.

        Args:
            agent: Agent instance to configure host services for

        Returns:
            Number of host services successfully configured
        """
        agent_name = getattr(agent, "name", "unknown")

        if not self._host_services_available:
            self.logger.debug(
                f"[AgentServiceInjectionService] Host services not available for {agent_name}"
            )
            return 0

        try:
            configured_count = (
                self.host_protocol_configuration.configure_host_protocols(agent)
            )

            if configured_count > 0:
                self.logger.debug(
                    f"[AgentServiceInjectionService] ✅ Configured {configured_count} host services for {agent_name}"
                )
            else:
                self.logger.trace(
                    f"[AgentServiceInjectionService] Agent {agent_name} does not implement host protocols"
                )

            return configured_count

        except Exception as e:
            self.logger.error(
                f"[AgentServiceInjectionService] ❌ Failed to configure host services for {agent_name}: {e}"
            )
            # Graceful degradation - continue without host services
            return 0

    def configure_execution_tracker(
        self, agent: Any, tracker: Optional[Any] = None
    ) -> bool:
        """
        Configure execution tracker on an agent if the agent supports it.

        Checks if the agent has a set_execution_tracker method and calls it
        with the provided tracker. This enables execution tracking for agents
        that support it without requiring all agents to implement this capability.

        Args:
            agent: Agent instance to configure execution tracker for
            tracker: ExecutionTracker instance or None

        Returns:
            True if tracker was configured successfully, False otherwise
        """
        if tracker is None:
            return False

        agent_name = getattr(agent, "name", "unknown")

        if hasattr(agent, "set_execution_tracker"):
            try:
                agent.set_execution_tracker(tracker)
                self.logger.debug(
                    f"[AgentServiceInjectionService] ✅ Configured execution tracker for {agent_name}"
                )
                return True
            except Exception as e:
                self.logger.error(
                    f"[AgentServiceInjectionService] ❌ Failed to configure execution tracker for {agent_name}: {e}"
                )
                # Graceful degradation - continue without execution tracking
                return False
        else:
            self.logger.debug(
                f"[AgentServiceInjectionService] Agent {agent_name} does not support execution tracking"
            )
            return False

    def configure_all_services(self, agent: Any, tracker: Optional[Any] = None) -> dict:
        """
        Configure core services, storage services, host services, and execution tracker for an agent.

        Unified entry point that calls all configuration methods in the proper order:
        1. Core services (required for basic agent functionality)
        2. Storage services (storage-specific service injection)
        3. Host services (host application specific services)
        4. Execution tracker (for execution monitoring)

        Args:
            agent: Agent instance to configure all services for
            tracker: Optional ExecutionTracker instance for execution monitoring

        Returns:
            Dictionary with configuration summary including counts and status
        """
        agent_name = getattr(agent, "name", "unknown")
        self.logger.debug(
            f"[AgentServiceInjectionService] Configuring all services for agent: {agent_name}"
        )

        # Configure core services first
        core_configured = self.configure_core_services(agent)

        # Configure storage services after core services
        storage_configured = self.configure_storage_services(agent)

        # Configure host services after storage services
        host_configured = self.configure_host_services(agent)

        # Configure execution tracker if provided
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

        self.logger.debug(
            f"[AgentServiceInjectionService] Configuration summary for {agent_name}: "
            f"core={core_configured}, storage={storage_configured}, host={host_configured}, tracker={tracker_configured}, total={total_configured}"
        )

        return summary

    def get_service_injection_status(self, agent: Any) -> dict:
        """
        Get detailed service injection status for a specific agent for debugging.

        Provides comprehensive information about which services can be injected
        into the agent, which protocols the agent implements, and the current
        service availability status. Similar to HostProtocolConfigurationService.

        Args:
            agent: Agent instance to analyze

        Returns:
            Dictionary with detailed service injection status and capabilities
        """
        agent_name = getattr(agent, "name", "unknown")

        status = {
            "agent_name": agent_name,
            "agent_type": type(agent).__name__,
            "implemented_protocols": [],
            "service_injection_potential": [],
            "execution_tracking_support": {
                "has_set_execution_tracker_method": hasattr(
                    agent, "set_execution_tracker"
                ),
                "supports_execution_tracking": hasattr(agent, "set_execution_tracker"),
            },
            "error": None,
        }

        try:
            # Check core service protocols
            core_protocols = [
                (LLMCapableAgent, "llm_service", "configure_llm_service"),
                (
                    StorageCapableAgent,
                    "storage_service_manager",
                    "configure_storage_service",
                ),
                (
                    PromptCapableAgent,
                    "prompt_manager_service",
                    "configure_prompt_service",
                ),
                (
                    OrchestrationCapableAgent,
                    "orchestrator_service",
                    "configure_orchestrator_service",
                ),
                (
                    BlobStorageCapableAgent,
                    "blob_storage_service",
                    "configure_blob_storage_service",
                ),
            ]

            # Check storage service protocols
            storage_protocols = [
                (CSVCapableAgent, "csv_service", "configure_csv_service"),
                (JSONCapableAgent, "json_service", "configure_json_service"),
                (FileCapableAgent, "file_service", "configure_file_service"),
                (VectorCapableAgent, "vector_service", "configure_vector_service"),
                (MemoryCapableAgent, "memory_service", "configure_memory_service"),
            ]

            # Process core protocols
            for protocol_class, service_name, configure_method in core_protocols:
                service_available = getattr(self, service_name, None) is not None
                agent_implements = isinstance(agent, protocol_class)
                method_exists = (
                    hasattr(agent, configure_method) if agent_implements else False
                )

                protocol_info = {
                    "protocol": protocol_class.__name__,
                    "service": service_name,
                    "configure_method": configure_method,
                    "agent_implements": agent_implements,
                    "service_available": service_available,
                    "method_exists": method_exists,
                    "injection_ready": agent_implements
                    and service_available
                    and method_exists,
                }

                if agent_implements:
                    status["implemented_protocols"].append(protocol_class.__name__)

                status["service_injection_potential"].append(protocol_info)

            # Process storage protocols (use storage manager availability)
            for protocol_class, service_name, configure_method in storage_protocols:
                storage_type = service_name.replace(
                    "_service", ""
                )  # csv_service -> csv
                try:
                    # Check if storage service manager can provide this service
                    service_available = (
                        self.storage_service_manager.is_provider_available(storage_type)
                    )
                except Exception:
                    service_available = False

                agent_implements = isinstance(agent, protocol_class)
                method_exists = (
                    hasattr(agent, configure_method) if agent_implements else False
                )

                protocol_info = {
                    "protocol": protocol_class.__name__,
                    "service": service_name,
                    "configure_method": configure_method,
                    "agent_implements": agent_implements,
                    "service_available": service_available,
                    "method_exists": method_exists,
                    "injection_ready": agent_implements
                    and service_available
                    and method_exists,
                }

                if agent_implements:
                    status["implemented_protocols"].append(protocol_class.__name__)

                status["service_injection_potential"].append(protocol_info)

            # Get host service status if available
            host_service_status = None
            if self._host_services_available:
                try:
                    host_service_status = (
                        self.host_protocol_configuration.get_configuration_status(agent)
                    )
                except Exception as e:
                    self.logger.debug(
                        f"[AgentServiceInjectionService] Could not get host service status: {e}"
                    )

            # Summary
            ready_injections = sum(
                1 for p in status["service_injection_potential"] if p["injection_ready"]
            )
            available_services = sum(
                1
                for p in status["service_injection_potential"]
                if p["service_available"]
            )

            status["summary"] = {
                "total_protocols_implemented": len(status["implemented_protocols"]),
                "injection_ready_count": ready_injections,
                "available_services_count": available_services,
                "core_services_ready": ready_injections > 0,
                "host_services_available": self._host_services_available,
                "execution_tracking_ready": status["execution_tracking_support"][
                    "supports_execution_tracking"
                ],
            }

            # Include host service status if available
            if host_service_status:
                status["host_services"] = host_service_status
                if "summary" in host_service_status:
                    status["summary"]["host_protocols_implemented"] = (
                        host_service_status["summary"].get(
                            "total_protocols_implemented", 0
                        )
                    )
                    status["summary"]["host_injection_ready_count"] = (
                        host_service_status["summary"].get("configuration_ready", 0)
                    )

        except Exception as e:
            status["error"] = str(e)
            self.logger.error(
                f"[AgentServiceInjectionService] Error analyzing agent {agent_name}: {e}"
            )

        return status

    def get_service_availability_status(self) -> dict:
        """
        Get status of service availability for debugging and monitoring.

        Returns:
            Dictionary with service availability information
        """
        return {
            "core_services": {
                "llm_service_available": self.llm_service is not None,
                "storage_service_manager_available": self.storage_service_manager
                is not None,
                "prompt_manager_service_available": self.prompt_manager_service
                is not None,
                "orchestrator_service_available": self.orchestrator_service is not None,
                "graph_checkpoint_service_available": self.graph_checkpoint_service
                is not None,
                "blob_storage_service_available": self.blob_storage_service is not None,
            },
            "host_services": {
                "host_protocol_configuration_available": self._host_services_available,
            },
            "service_readiness": {
                "core_services_ready": all(
                    [
                        self.llm_service is not None,
                        self.storage_service_manager is not None,
                    ]
                ),
                "optional_services_count": sum(
                    [
                        self.prompt_manager_service is not None,
                        self.orchestrator_service is not None,
                        self.graph_checkpoint_service is not None,
                        self.blob_storage_service is not None,
                    ]
                ),
                "host_services_ready": self._host_services_available,
            },
        }
