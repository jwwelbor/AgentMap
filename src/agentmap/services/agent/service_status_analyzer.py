"""Service status analyzer for AgentMap.

Provides detailed service injection status and capabilities analysis.
"""

from typing import Any, Optional


class ServiceStatusAnalyzer:
    """Analyzer for service injection status and availability."""

    def __init__(
        self,
        llm_service: Any,
        storage_service_manager: Any,
        logging_service: Any,
        prompt_manager_service: Optional[Any] = None,
        orchestrator_service: Optional[Any] = None,
        graph_checkpoint_service: Optional[Any] = None,
        blob_storage_service: Optional[Any] = None,
        host_protocol_configuration_service: Optional[Any] = None,
    ):
        """Initialize service status analyzer.

        Args:
            llm_service: LLM service instance
            storage_service_manager: Storage service manager instance
            logging_service: Logging service instance
            prompt_manager_service: Optional prompt manager service
            orchestrator_service: Optional orchestrator service
            graph_checkpoint_service: Optional graph checkpoint service
            blob_storage_service: Optional blob storage service
            host_protocol_configuration_service: Optional host protocol configuration service
        """
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service
        self.graph_checkpoint_service = graph_checkpoint_service
        self.blob_storage_service = blob_storage_service
        self.host_protocol_configuration_service = host_protocol_configuration_service
        self.logger = logging_service.get_class_logger(self)

    def get_service_injection_status(self, agent: Any) -> dict:
        """Get detailed service injection status for an agent.

        Args:
            agent: Agent instance to analyze

        Returns:
            Dictionary with detailed service injection status
        """
        from agentmap.services.protocols import (
            BlobStorageCapableAgent,
            LLMCapableAgent,
            OrchestrationCapableAgent,
            PromptCapableAgent,
        )
        from agentmap.services.storage.protocols import (
            CSVCapableAgent,
            FileCapableAgent,
            JSONCapableAgent,
            MemoryCapableAgent,
            StorageCapableAgent,
            VectorCapableAgent,
        )

        agent_name = getattr(agent, "name", "unknown")
        agent_type = type(agent).__name__

        # Check which protocols the agent implements
        protocols_implemented = {
            "LLMCapableAgent": isinstance(agent, LLMCapableAgent),
            "StorageCapableAgent": isinstance(agent, StorageCapableAgent),
            "PromptCapableAgent": isinstance(agent, PromptCapableAgent),
            "OrchestrationCapableAgent": isinstance(agent, OrchestrationCapableAgent),
            "BlobStorageCapableAgent": isinstance(agent, BlobStorageCapableAgent),
            "CSVCapableAgent": isinstance(agent, CSVCapableAgent),
            "JSONCapableAgent": isinstance(agent, JSONCapableAgent),
            "FileCapableAgent": isinstance(agent, FileCapableAgent),
            "VectorCapableAgent": isinstance(agent, VectorCapableAgent),
            "MemoryCapableAgent": isinstance(agent, MemoryCapableAgent),
        }

        # Check service availability
        services_available = {
            "llm_service": self.llm_service is not None,
            "storage_service_manager": self.storage_service_manager is not None,
            "prompt_manager_service": self.prompt_manager_service is not None,
            "orchestrator_service": self.orchestrator_service is not None,
            "graph_checkpoint_service": self.graph_checkpoint_service is not None,
            "blob_storage_service": self.blob_storage_service is not None,
            "host_protocol_configuration_service": (
                self.host_protocol_configuration_service is not None
            ),
        }

        # Determine which services can be injected
        injectable_services = []
        missing_services = []

        if protocols_implemented["LLMCapableAgent"]:
            if services_available["llm_service"]:
                injectable_services.append("llm_service")
            else:
                missing_services.append("llm_service")

        if protocols_implemented["PromptCapableAgent"]:
            if services_available["prompt_manager_service"]:
                injectable_services.append("prompt_manager_service")
            else:
                missing_services.append("prompt_manager_service")

        if protocols_implemented["OrchestrationCapableAgent"]:
            if services_available["orchestrator_service"]:
                injectable_services.append("orchestrator_service")
            else:
                missing_services.append("orchestrator_service")

        if protocols_implemented["BlobStorageCapableAgent"]:
            if services_available["blob_storage_service"]:
                injectable_services.append("blob_storage_service")
            else:
                missing_services.append("blob_storage_service")

        # Check storage services
        storage_protocols = [
            p
            for p in protocols_implemented
            if p.endswith("CapableAgent")
            and "Storage" in p
            or "CSV" in p
            or "JSON" in p
            or "File" in p
            or "Vector" in p
            or "Memory" in p
        ]
        storage_capable = any(protocols_implemented[p] for p in storage_protocols)

        return {
            "agent_name": agent_name,
            "agent_type": agent_type,
            "protocols_implemented": protocols_implemented,
            "services_available": services_available,
            "injectable_services": injectable_services,
            "missing_services": missing_services,
            "storage_capable": storage_capable,
            "can_inject_services": len(injectable_services) > 0,
        }

    def get_service_availability_status(self) -> dict:
        """Get status of service availability.

        Returns:
            Dictionary with service availability information
        """
        return {
            "llm_service_available": self.llm_service is not None,
            "storage_service_manager_available": self.storage_service_manager
            is not None,
            "prompt_manager_service_available": self.prompt_manager_service is not None,
            "orchestrator_service_available": self.orchestrator_service is not None,
            "graph_checkpoint_service_available": self.graph_checkpoint_service
            is not None,
            "blob_storage_service_available": self.blob_storage_service is not None,
            "host_protocol_configuration_service_available": (
                self.host_protocol_configuration_service is not None
            ),
        }
