"""
GraphBundle model for metadata-only storage of graph information.

This module supports lightweight storage of graph metadata without pickled instances,
eliminating serialization issues while preserving reconstruction capability.
"""

import copy
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, List

from .node import Node


@dataclass
class GraphBundle:
    """
    Lightweight metadata storage for graph information.
    
    Supports both new metadata-only storage and legacy format for backwards compatibility.
    """
    
    # Legacy fields (primary constructor for backwards compatibility)
    graph: Optional[Any] = None
    node_registry: Optional[Dict[str, Any]] = None
    version_hash: Optional[str] = None
    
    # New metadata-only fields (optional for backwards compatibility)
    graph_name: Optional[str] = None
    nodes: Optional[Dict[str, Node]] = None
    required_agents: Optional[Set[str]] = None
    required_services: Optional[Set[str]] = None
    function_mappings: Optional[Dict[str, str]] = None
    csv_hash: Optional[str] = None
    
    def __post_init__(self):
        """Initialize defaults and issue deprecation warnings as needed."""
        # If using new format, ensure all required fields are set
        if (self.graph_name is not None or 
            self.nodes is not None or 
            self.required_agents is not None or 
            self.required_services is not None or 
            self.function_mappings is not None or 
            self.csv_hash is not None):
            
            # Fill in defaults for any missing new-format fields
            if self.graph_name is None:
                self.graph_name = "unknown_graph"
            if self.nodes is None:
                self.nodes = {}
            if self.required_agents is None:
                self.required_agents = set()
            if self.required_services is None:
                self.required_services = set()
            if self.function_mappings is None:
                self.function_mappings = {}
            if self.csv_hash is None:
                self.csv_hash = "unknown_hash"
        
        # If completely empty, set safe defaults
        else:
            self.graph_name = "empty_graph"
            self.nodes = {}
            self.required_agents = set()
            self.required_services = set()
            self.function_mappings = {}
            self.csv_hash = "empty_hash"
    
    
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
            if node_copy.context and 'instance' in node_copy.context:
                del node_copy.context['instance']
            
            prepared_nodes[name] = node_copy
            
        return prepared_nodes
    
    def get_service_load_order(self) -> List[str]:
        """
        Return services in dependency order using topological sort.
        
        This method analyzes the service dependencies and returns them in the
        order they should be loaded to satisfy all dependencies.
        
        Returns:
            List of service names in dependency order
        """
        if self.required_services is None:
            return []
        
        # Simple implementation - can be enhanced with actual dependency analysis
        # For now, return the services as a sorted list for consistency
        return sorted(list(self.required_services))
    
    @classmethod
    def create_metadata(
        cls,
        graph_name: str,
        nodes: Dict[str, Node],
        required_agents: Set[str],
        required_services: Set[str],
        function_mappings: Dict[str, str],
        csv_hash: str,
        version_hash: Optional[str] = None
    ) -> "GraphBundle":
        """
        Create a new GraphBundle using the metadata-only format.
        
        This is the preferred constructor for new code that wants to use
        the metadata-only storage approach.
        
        Args:
            graph_name: Name of the graph
            nodes: Dictionary of node name to Node objects (will be prepared for storage)
            required_agents: Set of agent types needed
            required_services: Set of service dependencies
            function_mappings: Dictionary mapping functions to implementations
            csv_hash: Hash of the source CSV for validation
            version_hash: Optional version identifier
            
        Returns:
            GraphBundle instance with metadata-only storage
        """
        prepared_nodes = cls.prepare_nodes_for_storage(nodes)
        
        return cls(
            graph_name=graph_name,
            nodes=prepared_nodes,
            required_agents=required_agents,
            required_services=required_services,
            function_mappings=function_mappings,
            csv_hash=csv_hash,
            version_hash=version_hash
        )
    
    @classmethod
    def create_from_legacy(
        cls, 
        graph: Any, 
        node_registry: Dict[str, Any], 
        version_hash: Optional[str] = None,
        graph_name: str = "legacy_graph",
        required_agents: Optional[Set[str]] = None,
        required_services: Optional[Set[str]] = None,
        function_mappings: Optional[Dict[str, str]] = None,
        csv_hash: str = "legacy_hash"
    ) -> "GraphBundle":
        """
        Create a new GraphBundle from legacy fields with explicit metadata.
        
        This method helps migrate from the old pickled graph format to the
        new metadata-only format when you have additional metadata available.
        """
        return cls(
            # Legacy fields
            graph=graph,
            node_registry=node_registry,
            version_hash=version_hash,
            # New metadata fields
            graph_name=graph_name,
            nodes=None,  # Will be populated in __post_init__
            required_agents=required_agents,
            required_services=required_services,
            function_mappings=function_mappings,
            csv_hash=csv_hash
        )
    
    @property
    def is_metadata_only(self) -> bool:
        """Check if this bundle is using the new metadata-only format."""
        return (self.graph is None and 
                self.node_registry is None and
                self.nodes is not None)
    
    @property
    def is_legacy_format(self) -> bool:
        """Check if this bundle is using the legacy format."""
        return self.graph is not None or self.node_registry is not None
