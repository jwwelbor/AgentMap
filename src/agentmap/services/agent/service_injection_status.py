"""
Service injection status utilities for AgentMap.

This module provides status and debugging functionality for service injection,
including detailed analysis of agent capabilities and service availability.
"""

from typing import Any, Optional

from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    LLMCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
)
from agentmap.services.storage.protocols import (
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    VectorCapableAgent,
)


class ServiceInjectionStatusProvider:
    """
    Provides status and debugging information for service injection.

    This class encapsulates the logic for analyzing agent capabilities
    and service availability for debugging and monitoring purposes.
    """

    def __init__(
        self,
        llm_service: Any,
        storage_service_manager: Any,
        logger: Any,
        prompt_manager_service: Optional[Any] = None,
        orchestrator_service: Optional[Any] = None,
        graph_checkpoint_service: Optional[Any] = None,
        blob_storage_service: Optional[Any] = None,
        host_protocol_configuration: Optional[Any] = None,
    ):
        """
        Initialize service injection status provider.

        Args:
            llm_service: Service for LLM operations
            storage_service_manager: Manager for storage services
            logger: Logger instance for logging
            prompt_manager_service: Optional service for prompt template resolution
            orchestrator_service: Optional service for orchestration business logic
            graph_checkpoint_service: Optional service for graph execution checkpoints
            blob_storage_service: Optional service for blob storage operations
            host_protocol_configuration: Optional service for host protocol configuration
        """
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.graph_checkpoint_service = graph_checkpoint_service
        self.blob_storage_service = blob_storage_service
        self.host_protocol_configuration = host_protocol_configuration
        self._host_services_available = host_protocol_configuration is not None
        self.logger = logger

    def get_service_injection_status(self, agent: Any) -> dict:
        """
        Get detailed service injection status for a specific agent for debugging.

        Provides comprehensive information about which services can be injected
        into the agent, which protocols the agent implements, and the current
        service availability status.

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
