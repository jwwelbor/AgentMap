"""
ProtocolBasedRequirementsAnalyzer service for AgentMap.

Service that analyzes graph requirements from agent protocols without instantiating agents.
This service determines which services are needed by examining which protocols each agent
implements (LLMCapableAgent, StorageCapableAgent, etc).
"""

from pathlib import Path
from typing import Any, Dict, Optional, Set, Type

from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.csv_graph_parser_service import CSVGraphParserService
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


class ProtocolBasedRequirementsAnalyzer:
    """
    Analyzes graph requirements from agent protocols without instantiation.

    This service maps agent protocols to their required services and analyzes
    graphs to determine which services are needed. It works by examining which
    protocols each agent class implements using runtime protocol checking.

    Follows clean architecture principles with dependency injection and
    separation of concerns. Business logic is isolated and testable.
    """

    # Mapping from protocol names to their required service names
    PROTOCOL_TO_SERVICE: Dict[str, str] = {
        "LLMCapableAgent": "llm_service",
        "StorageCapableAgent": "storage_service_manager",
        "PromptCapableAgent": "prompt_manager_service",
        "CSVCapableAgent": "csv_service",
        "JSONCapableAgent": "json_service",
        "FileCapableAgent": "file_service",
        "VectorCapableAgent": "vector_service",
        "MemoryCapableAgent": "memory_service",
        "BlobStorageCapableAgent": "blob_storage_service",
        "DatabaseCapableAgent": "database_service",
        "OrchestrationCapableAgent": "orchestrator_service",
    }

    def __init__(
        self,
        csv_parser: CSVGraphParserService,
        agent_factory_service: AgentFactoryService,
        logging_service: LoggingService,
    ):
        """
        Initialize the service with dependency injection.

        Args:
            csv_parser: Service for parsing CSV files into GraphSpec models
            agent_factory_service: Service for resolving agent classes
            logging_service: Service for logging operations
        """
        self.csv_parser = csv_parser
        self.agent_factory = agent_factory_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[ProtocolBasedRequirementsAnalyzer] Initialized")

    def analyze_graph_requirements(self, nodes: Dict[str, Any]) -> Dict[str, Set[str]]:
        """
        Analyze graph requirements from agent protocols.

        Takes already-parsed nodes, resolves agent classes for each node type,
        checks which protocols each agent implements, and returns the required
        agents and services.

        Args:
            nodes: Dictionary of Node objects (either Node domain objects or dict)

        Returns:
            Dictionary with "required_agents" and "required_services" sets
        """
        self.logger.info(
            f"[ProtocolBasedRequirementsAnalyzer] Analyzing requirements for "
            f"{len(nodes)} nodes"
        )

        # Convert nodes to list-like format for compatibility with existing logic
        node_list = list(nodes.values()) if isinstance(nodes, dict) else nodes
        self.logger.debug(
            f"[ProtocolBasedRequirementsAnalyzer] Processing {len(node_list)} nodes"
        )

        # Start with default services that all graphs need
        required_services = self._get_default_services()
        required_agents = set()

        # Analyze each node to determine required services and collect agent types
        for node in node_list:
            # DEBUG: Enhanced logging to understand node structure
            self.logger.debug(
                f"[ProtocolBasedRequirementsAnalyzer] Processing node: {repr(node)}"
            )

            self.logger.debug(
                f"[ProtocolBasedRequirementsAnalyzer] Node type: {type(node)}"
            )

            # Extract agent type from Node object
            agent_type = getattr(node, "agent_type", None)

            node_name = getattr(node, "name", None) or (
                node.get("name", "unknown") if hasattr(node, "get") else "unknown"
            )

            # DEBUG: Log extraction results
            self.logger.debug(
                f"[ProtocolBasedRequirementsAnalyzer] Node '{node_name}': "
                f"agent_type={agent_type}"
            )

            if not agent_type:
                self.logger.warning(
                    f"[ProtocolBasedRequirementsAnalyzer] Node '{node_name}' "
                    "has no agent type, skipping"
                )
                continue

            # Add agent type to required agents
            required_agents.add(agent_type)

            # Resolve agent class
            agent_class = self.agent_factory.get_agent_class(agent_type)
            if agent_class is None:
                self.logger.warning(
                    f"[ProtocolBasedRequirementsAnalyzer] Could not resolve "
                    f"agent type '{agent_type}' for node '{node_name}', "
                    "using default services"
                )
                continue

            # Check which protocols the agent implements
            node_services = self._analyze_agent_protocols(agent_class, node_name)
            required_services.update(node_services)

        self.logger.info(
            f"[ProtocolBasedRequirementsAnalyzer] Analysis complete. "
            f"Required agents: {sorted(required_agents)}, "
            f"Required services: {sorted(required_services)}"
        )

        return {
            "required_agents": required_agents,
            "required_services": required_services,
        }

    def _analyze_agent_protocols(self, agent_class: Type, node_name: str) -> Set[str]:
        """
        Analyze which protocols an agent class implements.

        Args:
            agent_class: Agent class to analyze
            node_name: Name of the node (for logging)

        Returns:
            Set of service names required by the agent's protocols
        """
        required_services = set()

        self.logger.debug(
            f"[ProtocolBasedRequirementsAnalyzer] Analyzing protocols for "
            f"agent '{agent_class.__name__}' (node: {node_name})"
        )

        # Check each known protocol
        for protocol_name, service_name in self.PROTOCOL_TO_SERVICE.items():
            if self._implements_protocol(agent_class, protocol_name):
                required_services.add(service_name)
                self.logger.debug(
                    f"[ProtocolBasedRequirementsAnalyzer] Agent '{agent_class.__name__}' "
                    f"implements {protocol_name}, requires {service_name}"
                )

        return required_services

    def _implements_protocol(
        self, agent_class: Optional[Type], protocol_name: str
    ) -> bool:
        """
        Check if an agent class implements a specific protocol.

        Uses Protocol's runtime checking to determine if the agent class
        implements the specified protocol interface.

        Args:
            agent_class: Agent class to check (can be None)
            protocol_name: Name of the protocol to check

        Returns:
            True if the agent class implements the protocol, False otherwise
        """
        if agent_class is None:
            return False

        try:
            # Get the protocol class from the protocols module
            protocol_class = self._get_protocol_class(protocol_name)
            if protocol_class is None:
                return False

            # Use isinstance to check if the class implements the protocol
            # For classes (not instances), we need to check if it's a subclass
            return issubclass(agent_class, protocol_class)

        except (TypeError, AttributeError) as e:
            self.logger.debug(
                f"[ProtocolBasedRequirementsAnalyzer] Error checking protocol "
                f"'{protocol_name}' for agent '{agent_class.__name__ if agent_class else None}': {e}"
            )
            return False

    def _get_protocol_class(self, protocol_name: str) -> Optional[Type]:
        """
        Get the protocol class by name.

        Args:
            protocol_name: Name of the protocol class

        Returns:
            Protocol class or None if not found
        """
        # Map protocol names to their actual classes
        protocol_classes = {
            "LLMCapableAgent": LLMCapableAgent,
            "StorageCapableAgent": StorageCapableAgent,
            "PromptCapableAgent": PromptCapableAgent,
            "CSVCapableAgent": CSVCapableAgent,
            "JSONCapableAgent": JSONCapableAgent,
            "FileCapableAgent": FileCapableAgent,
            "VectorCapableAgent": VectorCapableAgent,
            "MemoryCapableAgent": MemoryCapableAgent,
            "BlobStorageCapableAgent": BlobStorageCapableAgent,
            "OrchestrationCapableAgent": OrchestrationCapableAgent,
        }

        return protocol_classes.get(protocol_name)

    def _get_default_services(self) -> Set[str]:
        """
        Get the default services that all graphs need.

        These are the core infrastructure services that every agent execution
        requires, regardless of the specific agent types used.

        Returns:
            Set of default service names
        """
        return {
            "state_adapter_service",
            "execution_tracking_service",
        }
