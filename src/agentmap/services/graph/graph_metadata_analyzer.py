# services/graph/graph_metadata_analyzer.py

from typing import Dict, Optional, Set, Tuple

from agentmap.models.node import Node
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.logging_service import LoggingService


class GraphMetadataAnalyzer:
    """
    Analyzes graph metadata for Phase 1 critical metadata extraction.

    This service handles:
    - Filtering actual services from dependency lists
    - Extracting agent type to class mappings
    - Classifying agents into builtin vs custom
    - Identifying entry points in graphs
    - Extracting protocol mappings
    """

    def __init__(
        self,
        logging_service: LoggingService,
        agent_factory_service: AgentFactoryService,
        declaration_registry_service: DeclarationRegistryService,
    ):
        """Initialize GraphMetadataAnalyzer.

        Args:
            logging_service: LoggingService for logging
            agent_factory_service: Service for agent creation and management
            declaration_registry_service: Declaration registry service
        """
        self.logger = logging_service.get_class_logger(self)
        self.agent_factory_service = agent_factory_service
        self.declaration_registry = declaration_registry_service

    def filter_actual_services(self, services: Set[str]) -> Set[str]:
        """Filter out non-service entries from service requirements.

        Some entries in dependency trees are configuration values or cache objects,
        not actual services that need to be loaded.

        Args:
            services: Set of all items from dependency analysis

        Returns:
            Set of actual service names only
        """
        # Known non-service entries that appear in dependency trees
        non_services = {
            "config_path",  # Configuration value, not a service
            "routing_cache",  # Cache object, not a service
        }

        actual_services = set()

        for service_name in services:
            # Skip known non-services
            if service_name in non_services:
                self.logger.debug(f"Filtering out non-service entry: {service_name}")
                continue

            # Services typically follow naming patterns
            if (
                service_name.endswith("_service")
                or service_name.endswith("_manager")
                or service_name.endswith("_analyzer")
                or service_name.endswith("_factory")
            ):
                actual_services.add(service_name)
            else:
                # Include uncertain entries to be safe - they might be valid services
                # Log for future investigation
                self.logger.debug(
                    f"Including uncertain entry (may not be a service): {service_name}"
                )
                actual_services.add(service_name)

        self.logger.debug(
            f"Filtered {len(services)} entries to {len(actual_services)} actual services"
        )
        return actual_services

    def extract_agent_mappings(self, agent_types: Set[str]) -> Dict[str, str]:
        """Extract agent type to class path mappings.

        Args:
            agent_types: Set of agent types to map

        Returns:
            Dictionary mapping agent types to their class import paths
        """
        try:
            mappings = self.agent_factory_service.get_agent_class_mappings(agent_types)

            self.logger.debug(
                f"Extracted {len(mappings)} agent mappings: {list(mappings.keys())}"
            )
            return mappings

        except Exception as e:
            self.logger.warning(f"Failed to extract agent mappings: {e}. ")
            raise e

    def classify_agents(self, agent_types: Set[str]) -> Tuple[Set[str], Set[str]]:
        """Classify agents into builtin and custom categories.

        Args:
            agent_types: Set of agent types to classify

        Returns:
            Tuple of (builtin_agents, custom_agents)
        """
        builtin_agents = set()
        custom_agents = set()

        # Standard framework agent types
        framework_agents = DeclarationRegistryService.get_all_agent_types()

        for agent_type in agent_types:
            if agent_type in framework_agents:
                builtin_agents.add(agent_type)
            else:
                custom_agents.add(agent_type)

        self.logger.debug(
            f"Classified agents: {len(builtin_agents)} builtin, {len(custom_agents)} custom"
        )
        return builtin_agents, custom_agents

    def identify_entry_point(self, nodes: Dict[str, Node]) -> Optional[str]:
        """Identify the entry point node in the graph.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Name of the entry point node, or None if not found
        """
        # Look for nodes that are not referenced by any other node's edges
        referenced_nodes = set()
        for node in nodes.values():
            for edge_targets in node.edges.values():
                if isinstance(edge_targets, str):
                    referenced_nodes.add(edge_targets)
                elif isinstance(edge_targets, list):
                    referenced_nodes.update(edge_targets)

        # Entry point is a node that exists but is not referenced
        # these are not ordered like they are in the original nodes.
        entry_candidates = set(nodes.keys()) - referenced_nodes

        if len(entry_candidates) == 1:
            entry_point = list(entry_candidates)[0]
            self.logger.debug(f"Identified entry point: {entry_point}")
            return entry_point
        elif len(entry_candidates) == 0:
            self.logger.warning("No entry point found - all nodes are referenced")
            # Fallback: use the first node alphabetically
            return list(nodes.keys())[0]
        else:
            self.logger.warning(
                f"Multiple entry point candidates found: {entry_candidates}. Using first."
            )
            return list(entry_candidates)[0]

    def extract_protocol_mappings(self) -> Dict[str, str]:
        """Extract protocol to implementation mappings from DI container.

        Returns:
            Dictionary mapping protocol names to implementation class names
        """
        try:
            mappings = self.declaration_registry.get_protocol_implementations()

            self.logger.debug(f"Extracted {len(mappings)} protocol mappings")
            return mappings

        except Exception as e:
            self.logger.warning(
                f"Failed to extract protocol mappings: {e}. Using empty mappings."
            )
            return {}
