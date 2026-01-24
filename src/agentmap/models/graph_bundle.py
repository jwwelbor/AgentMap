"""
GraphBundle model for metadata-only storage of graph information.

This module supports lightweight storage of graph metadata.
"""

import copy
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from langchain_core.tools import Tool

from .node import Node


@dataclass
class GraphBundle:
    """
    Lightweight metadata storage for graph information.

    Supports both new metadata-only storage and legacy format for backwards compatibility.
    """

    # Legacy fields (primary constructor for backwards compatibility)
    graph: Optional[Any] = None
    node_instances: Optional[Dict[str, Any]] = None
    version_hash: Optional[str] = None

    # New metadata-only fields (optional for backwards compatibility)
    graph_name: Optional[str] = None
    entry_point: Optional[str] = None  # NEW: Starting node name
    nodes: Optional[Dict[str, Node]] = None
    required_agents: Optional[Set[str]] = None
    required_services: Optional[Set[str]] = None
    service_load_order: Optional[List[str]] = None  # NEW: Services in dependency order
    function_mappings: Optional[Dict[str, str]] = None
    csv_hash: Optional[str] = None

    # Phase 1: Agent mappings
    agent_mappings: Optional[Dict[str, str]] = None  # NEW: agent_type -> class path
    builtin_agents: Optional[Set[str]] = None  # NEW: Standard framework agents
    custom_agents: Optional[Set[str]] = None  # NEW: User-defined agents

    # Phase 2: Optimization metadata
    graph_structure: Optional[Dict[str, Any]] = None  # NEW: Structure analysis
    protocol_mappings: Optional[Dict[str, str]] = (
        None  # NEW: Protocol -> implementation
    )

    # Phase 3: Validation metadata
    validation_metadata: Optional[Dict[str, Any]] = None  # NEW: Integrity checks
    bundle_format: str = "metadata-v1"  # NEW: Format version
    created_at: Optional[str] = None  # NEW: Creation timestamp
    missing_declarations: Optional[Set[str]] = (
        None  # NEW: Agent types without declarations
    )

    # AGM-TOOLS-001: Tool caching
    tools: Optional[Dict[str, List[Tool]]] = (
        None  # Cache for loaded tools, keyed by node name
    )

    def __post_init__(self):
        """Initialize defaults and issue deprecation warnings as needed."""
        # If using new format, ensure all required fields are set
        if (
            self.graph_name is not None
            or self.nodes is not None
            or self.required_agents is not None
            or self.required_services is not None
            or self.function_mappings is not None
            or self.csv_hash is not None
        ):

            # Fill in defaults for any missing new-format fields
            if self.graph_name is None:
                self.graph_name = "unknown_graph"
            if self.nodes is None:
                self.nodes = {}
            if self.required_agents is None:
                self.required_agents = set()
            if self.required_services is None:
                self.required_services = set()
            if self.service_load_order is None:
                self.service_load_order = []
            if self.function_mappings is None:
                self.function_mappings = {}
            if self.csv_hash is None:
                self.csv_hash = "unknown_hash"
            if self.agent_mappings is None:
                self.agent_mappings = {}
            if self.builtin_agents is None:
                self.builtin_agents = set()
            if self.custom_agents is None:
                self.custom_agents = set()
            if self.graph_structure is None:
                self.graph_structure = {}
            if self.protocol_mappings is None:
                self.protocol_mappings = {}
            if self.validation_metadata is None:
                self.validation_metadata = {}
            if self.created_at is None:
                from datetime import datetime

                self.created_at = datetime.utcnow().isoformat()
            if self.missing_declarations is None:
                self.missing_declarations = set()
            if self.tools is None:
                self.tools = {}

        # If completely empty, set safe defaults
        else:
            self.graph_name = "empty_graph"
            self.entry_point = None
            self.nodes = {}
            self.required_agents = set()
            self.required_services = set()
            self.service_load_order = []
            self.function_mappings = {}
            self.csv_hash = "empty_hash"
            self.agent_mappings = {}
            self.builtin_agents = set()
            self.custom_agents = set()
            self.graph_structure = {}
            self.protocol_mappings = {}
            self.validation_metadata = {}
            from datetime import datetime

            self.created_at = datetime.utcnow().isoformat()
            self.missing_declarations = set()
            self.tools = {}

    @staticmethod
    def prepare_nodes_for_storage(nodes: Dict[str, Node]) -> Dict[str, Node]:
        """
        Create deep copies of nodes and remove agent instances from context.

        This method strips any 'instance' key from node.context to prevent
        serialization issues with thread locks and other non-serializable objects.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary of node name to Node objects with agent instances removed
        """
        prepared_nodes = {}

        for name, node in nodes.items():
            # Create a deep copy of the node
            node_copy = copy.deepcopy(node)

            # Remove agent instance from context if present
            if node_copy.context and "instance" in node_copy.context:
                del node_copy.context["instance"]

            prepared_nodes[name] = node_copy

        return prepared_nodes

    def get_service_load_order(self) -> List[str]:
        """
        Return services in dependency order using topological sort.

        This method returns the pre-calculated service load order if available,
        or falls back to a simple sorted order for backwards compatibility.

        Returns:
            List of service names in dependency order
        """
        # Use pre-calculated service load order if available
        if self.service_load_order is not None and self.service_load_order:
            return self.service_load_order

        # Fallback for backwards compatibility
        if self.required_services is None:
            return []

        # Simple implementation - can be enhanced with actual dependency analysis
        # For now, return the services
        return list(self.required_services)

    @classmethod
    def create_metadata(
        cls,
        graph_name: str,
        nodes: Dict[str, Node],
        required_agents: Set[str],
        required_services: Set[str],
        function_mappings: Dict[str, str],
        csv_hash: str,
        version_hash: Optional[str] = None,
        # New Phase 1 parameters
        entry_point: Optional[str] = None,
        service_load_order: Optional[List[str]] = None,
        agent_mappings: Optional[Dict[str, str]] = None,
        builtin_agents: Optional[Set[str]] = None,
        custom_agents: Optional[Set[str]] = None,
        # New Phase 2 parameters
        graph_structure: Optional[Dict[str, Any]] = None,
        protocol_mappings: Optional[Dict[str, str]] = None,
        # New Phase 3 parameters
        validation_metadata: Optional[Dict[str, Any]] = None,
        missing_declarations: Optional[Set[str]] = None,
    ) -> "GraphBundle":
        """
        Create a new GraphBundle using the enhanced metadata-only format.

        This is the preferred constructor for new code that wants to use
        the metadata-only storage approach with all enhancement metadata.

        Args:
            graph_name: Name of the graph
            nodes: Dictionary of node name to Node objects (will be prepared for storage)
            required_agents: Set of agent types needed
            required_services: Set of service dependencies
            function_mappings: Dictionary mapping functions to implementations
            csv_hash: Hash of the source CSV for validation
            version_hash: Optional version identifier
            entry_point: Optional starting node name
            service_load_order: Optional pre-calculated service dependency order
            agent_mappings: Optional mapping of agent types to class paths
            builtin_agents: Optional set of standard framework agents
            custom_agents: Optional set of user-defined agents
            graph_structure: Optional graph structure analysis for optimization
            protocol_mappings: Optional protocol to implementation mappings
            validation_metadata: Optional validation and integrity data

        Returns:
            GraphBundle instance with enhanced metadata-only storage
        """
        prepared_nodes = cls.prepare_nodes_for_storage(nodes)

        return cls(
            graph_name=graph_name,
            entry_point=entry_point,
            nodes=prepared_nodes,
            required_agents=required_agents,
            required_services=required_services,
            service_load_order=service_load_order,
            function_mappings=function_mappings,
            csv_hash=csv_hash,
            version_hash=version_hash,
            # Phase 1: Agent mappings
            agent_mappings=agent_mappings,
            builtin_agents=builtin_agents,
            custom_agents=custom_agents,
            # Phase 2: Optimization metadata
            graph_structure=graph_structure,
            protocol_mappings=protocol_mappings,
            # Phase 3: Validation metadata
            validation_metadata=validation_metadata,
            missing_declarations=missing_declarations,
        )
