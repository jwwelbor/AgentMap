# services/graph_bundle_service.py

import copy
import hashlib
import logging
import pickle
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Set, List

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocol_requirements_analyzer import ProtocolBasedRequirementsAnalyzer
from agentmap.services.di_container_analyzer import DIContainerAnalyzer
from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.services.storage.types import WriteMode


class GraphBundleService:
    def __init__(self, 
                 logging_service: Optional[LoggingService] = None,
                 protocol_requirements_analyzer: Optional[ProtocolBasedRequirementsAnalyzer] = None,
                 di_container_analyzer: Optional[DIContainerAnalyzer] = None, #gets created on-demand here for documentation
                 agent_factory_service: Optional[AgentFactoryService] = None,
                 json_storage_service: Optional[Any] = None):
        """Initialize GraphBundleService with optional enhanced dependencies.
        
        Supports both legacy constructor (logger only) and enhanced constructor
        with dependency injection for metadata-only bundle functionality.
        
        Args:
            logger: Legacy logger parameter for backwards compatibility
            logging_service: LoggingService for proper dependency injection
            protocol_requirements_analyzer: Service for analyzing protocol requirements
            di_container_analyzer: Service for analyzing DI container dependencies (usually None)
            agent_factory_service: Service for agent creation and management
            json_storage_service: JSON storage service for bundle persistence (required for save/load)
        """
        self.logger = logging_service.get_class_logger(self)
        self.logging_service = logging_service
        
        # Store enhanced dependencies (may be None for legacy usage)
        self.protocol_requirements_analyzer = protocol_requirements_analyzer
        self.agent_factory_service = agent_factory_service
        self.json_storage_service = json_storage_service
        
        # DIContainerAnalyzer will be created on-demand to avoid circular dependency
        self.di_container_analyzer = di_container_analyzer  # Usually None
        
        # Check if enhanced functionality is available
        self._has_enhanced_dependencies = all([
            protocol_requirements_analyzer, agent_factory_service
        ])
        
    def _get_di_container_analyzer(self):
        """Get or create DIContainerAnalyzer on demand.
        
        This method creates the DIContainerAnalyzer only when needed,
        avoiding circular dependency issues during container initialization.
        """
        if self.di_container_analyzer is None:
            # Create DIContainerAnalyzer on-demand using the fully initialized container
            from agentmap.di import initialize_application
            
            container = initialize_application()
            self.di_container_analyzer = DIContainerAnalyzer(
                container,
                self.logging_service  # Use stored logging service if available
            )
            
            self.logger.debug(
                "Created DIContainerAnalyzer on-demand for metadata bundle operations"
            )
        
        return self.di_container_analyzer
    
    # ==========================================
    # Phase 1: Critical Metadata Extraction
    # ==========================================
    
    def _filter_actual_services(self, services: Set[str]) -> Set[str]:
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
            'config_path',      # Configuration value, not a service
            'routing_cache',    # Cache object, not a service
        }
        
        actual_services = set()
        
        for service_name in services:
            # Skip known non-services
            if service_name in non_services:
                self.logger.debug(
                    f"Filtering out non-service entry: {service_name}"
                )
                continue
            
            # Services typically follow naming patterns
            if (service_name.endswith('_service') or 
                service_name.endswith('_manager') or
                service_name.endswith('_analyzer') or
                service_name.endswith('_factory')):
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
    
    def _calculate_service_load_order(self, services: Set[str]) -> List[str]:
        """Calculate topological sort order for services.
        
        This method analyzes service dependencies and returns them in the
        order they should be loaded to satisfy all dependencies.
        
        Args:
            services: Set of service names to analyze
            
        Returns:
            List of service names in dependency order
        """
        try:
            analyzer = self._get_di_container_analyzer()
            dependency_tree = analyzer.get_dependency_tree(services)
            load_order = analyzer.topological_sort(dependency_tree)
            
            self.logger.debug(
                f"Calculated service load order for {len(services)} services: {load_order[:5]}..."
            )
            return load_order
            
        except Exception as e:
            self.logger.warning(
                f"Failed to calculate service load order: {e}. Using sorted fallback."
            )
            # Fallback to sorted order for reliability
            return sorted(list(services))
    
    def _extract_agent_mappings(self, agent_types: Set[str]) -> Dict[str, str]:
        """Extract agent type to class path mappings.
        
        Args:
            agent_types: Set of agent types to map
            
        Returns:
            Dictionary mapping agent types to their class import paths
        """
        try:
            if not self.agent_factory_service:
                self.logger.warning("AgentFactoryService not available for agent mappings")
                return {}
            
            mappings = self.agent_factory_service.get_agent_class_mappings(agent_types)
            
            self.logger.debug(
                f"Extracted {len(mappings)} agent mappings: {list(mappings.keys())}"
            )
            return mappings
            
        except Exception as e:
            self.logger.warning(
                f"Failed to extract agent mappings: {e}. Using empty mappings."
            )
            return {}
    
    def _classify_agents(self, agent_types: Set[str]) -> tuple[Set[str], Set[str]]:
        """Classify agents into builtin and custom categories.
        
        Args:
            agent_types: Set of agent types to classify
            
        Returns:
            Tuple of (builtin_agents, custom_agents)
        """
        builtin_agents = set()
        custom_agents = set()
        
        # Standard framework agent types
        framework_agents = {
            "Default", "LLMAgent", "ToolAgent", "ValidationAgent",
            "DataProcessingAgent", "ConditionalAgent"
        }
        
        for agent_type in agent_types:
            if agent_type in framework_agents:
                builtin_agents.add(agent_type)
            else:
                custom_agents.add(agent_type)
        
        self.logger.debug(
            f"Classified agents: {len(builtin_agents)} builtin, {len(custom_agents)} custom"
        )
        return builtin_agents, custom_agents
    
    def _identify_entry_point(self, nodes: Dict[str, Node]) -> Optional[str]:
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
        entry_candidates = set(nodes.keys()) - referenced_nodes
        
        if len(entry_candidates) == 1:
            entry_point = list(entry_candidates)[0]
            self.logger.debug(f"Identified entry point: {entry_point}")
            return entry_point
        elif len(entry_candidates) == 0:
            self.logger.warning("No entry point found - all nodes are referenced")
            # Fallback: use the first node alphabetically
            return sorted(nodes.keys())[0] if nodes else None
        else:
            self.logger.warning(
                f"Multiple entry point candidates found: {entry_candidates}. Using first."
            )
            return sorted(entry_candidates)[0]
    
    # ==========================================
    # Phase 2: Optimization Metadata
    # ==========================================
    
    def _analyze_graph_structure(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Analyze graph structure for optimization hints.
        
        Args:
            nodes: Dictionary of node name to Node objects
            
        Returns:
            Dictionary containing graph structure analysis
        """
        try:
            edge_count = sum(len(node.edges) for node in nodes.values())
            has_conditional = any(
                any(condition in node.edges for condition in ["success", "failure"])
                for node in nodes.values()
            )
            
            structure = {
                "node_count": len(nodes),
                "edge_count": edge_count,
                "has_conditional_routing": has_conditional,
                "max_depth": self._calculate_max_depth(nodes),
                "is_dag": self._check_dag(nodes),
                "parallel_opportunities": self._identify_parallel_nodes(nodes)
            }
            
            self.logger.debug(
                f"Analyzed graph structure: {structure['node_count']} nodes, "
                f"DAG: {structure['is_dag']}, conditional: {structure['has_conditional_routing']}"
            )
            return structure
            
        except Exception as e:
            self.logger.warning(
                f"Failed to analyze graph structure: {e}. Using minimal structure."
            )
            return {
                "node_count": len(nodes),
                "edge_count": 0,
                "has_conditional_routing": False,
                "max_depth": 1,
                "is_dag": True,
                "parallel_opportunities": []
            }
    
    def _calculate_max_depth(self, nodes: Dict[str, Node]) -> int:
        """Calculate maximum depth of the graph."""
        # Simple implementation - could be enhanced with actual graph traversal
        return min(len(nodes), 10)  # Cap at 10 for performance
    
    def _check_dag(self, nodes: Dict[str, Node]) -> bool:
        """Check if graph is a directed acyclic graph."""
        # Simple heuristic - if any node has edges that could create cycles
        # This is a simplified check and could be enhanced
        return True  # Assume DAG for now
    
    def _identify_parallel_nodes(self, nodes: Dict[str, Node]) -> List[Set[str]]:
        """Identify sets of nodes that can run in parallel."""
        # Simple implementation - nodes without dependencies can run in parallel
        # This could be enhanced with actual dependency analysis
        return []  # Return empty for now
    
    def _extract_protocol_mappings(self) -> Dict[str, str]:
        """Extract protocol to implementation mappings from DI container.
        
        Returns:
            Dictionary mapping protocol names to implementation class names
        """
        try:
            analyzer = self._get_di_container_analyzer()
            mappings = analyzer.get_protocol_mappings()
            
            self.logger.debug(
                f"Extracted {len(mappings)} protocol mappings"
            )
            return mappings
            
        except Exception as e:
            self.logger.warning(
                f"Failed to extract protocol mappings: {e}. Using empty mappings."
            )
            return {}
    
    # ==========================================
    # Phase 3: Validation Metadata
    # ==========================================
    
    def _generate_validation_metadata(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Generate validation metadata for integrity checks.
        
        Args:
            nodes: Dictionary of node name to Node objects
            
        Returns:
            Dictionary containing validation metadata
        """
        try:
            import hashlib
            
            # Generate per-node hashes for validation
            node_hashes = {}
            for name, node in nodes.items():
                node_str = f"{node.name}:{node.agent_type}:{len(node.edges)}"
                node_hashes[name] = hashlib.md5(node_str.encode()).hexdigest()[:8]
            
            validation_data = {
                "node_hashes": node_hashes,
                "compatibility_version": "1.0",
                "framework_version": self._get_framework_version(),
                "validation_rules": [
                    "unique_node_names",
                    "valid_edge_targets", 
                    "required_fields_present"
                ]
            }
            
            self.logger.debug(
                f"Generated validation metadata for {len(node_hashes)} nodes"
            )
            return validation_data
            
        except Exception as e:
            self.logger.warning(
                f"Failed to generate validation metadata: {e}. Using minimal validation."
            )
            return {
                "node_hashes": {},
                "compatibility_version": "1.0",
                "framework_version": "unknown",
                "validation_rules": []
            }
    
    def _get_framework_version(self) -> str:
        """Get the AgentMap framework version."""
        try:
            # This would typically read from package metadata
            return "2.0.0"  # Placeholder version
        except Exception:
            return "unknown"

    def save_bundle(self, bundle: GraphBundle, path: Path) -> None:
        """Persist the bundle to disk in appropriate format.
        
        Saves metadata-only bundles as JSON and legacy bundles as pickle.
        The format is determined automatically based on bundle type.
        
        Args:
            bundle: GraphBundle to save
            path: Path to save the bundle to
            
        Raises:
            ValueError: If json_storage_service is not available for metadata bundles
            IOError: If save operation fails
        """
        # Metadata bundles are always saved as JSON
        if not self.json_storage_service:
            raise ValueError(
                "json_storage_service is required to save metadata bundles. "
                "Please ensure GraphBundleService is properly initialized with all dependencies."
            )
        
        # Ensure path has .json extension
        if path.suffix != '.json':
            path = path.with_suffix('.json')
        
        # Serialize bundle to dictionary
        data = self._serialize_metadata_bundle(bundle)
        
        # Use JSONStorageService to write the bundle
        result = self.json_storage_service.write(
            collection=str(path),
            data=data,
            mode=WriteMode.WRITE
        )
        
        if result.success:
            self.logger.debug(
                f"Saved metadata GraphBundle to {path} with csv_hash {bundle.csv_hash}"
            )
        else:
            error_msg = f"Failed to save GraphBundle: {result.error}"
            self.logger.error(error_msg)
            raise IOError(error_msg)

    
    def _serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
        """Serialize enhanced metadata bundle to dictionary format."""
        # Serialize nodes to dictionaries
        nodes_data = {}
        for name, node in bundle.nodes.items():
            nodes_data[name] = {
                "name": node.name,
                "agent_type": node.agent_type,
                "context": node.context,
                "inputs": node.inputs,
                "output": node.output,
                "prompt": node.prompt,
                "description": node.description,
                "edges": node.edges
            }
        
        # Helper function to convert sets to sorted lists for JSON serialization
        def set_to_list(s):
            return sorted(list(s)) if s is not None else []
        
        return {
            "format": "metadata",
            "bundle_format": bundle.bundle_format,
            "created_at": bundle.created_at,
            
            # Core graph data
            "graph_name": bundle.graph_name,
            "entry_point": bundle.entry_point,
            "nodes": nodes_data,
            
            # Requirements and dependencies
            "required_agents": set_to_list(bundle.required_agents),
            "required_services": set_to_list(bundle.required_services),
            "service_load_order": bundle.service_load_order or [],
            
            # Mappings (Phase 1)
            "agent_mappings": bundle.agent_mappings or {},
            "builtin_agents": set_to_list(bundle.builtin_agents),
            "custom_agents": set_to_list(bundle.custom_agents),
            "function_mappings": bundle.function_mappings or {},
            
            # Optimization metadata (Phase 2)
            "graph_structure": bundle.graph_structure or {},
            "protocol_mappings": bundle.protocol_mappings or {},
            
            # Validation metadata (Phase 3)
            "validation_metadata": bundle.validation_metadata or {},
            
            # Legacy fields for backwards compatibility
            "csv_hash": bundle.csv_hash,
            "version_hash": bundle.version_hash
        }
        
    def load_bundle(self, path: Path) -> Optional[GraphBundle]:
        """Load a GraphBundle from a file.
        
        Automatically detects format (JSON for metadata, pickle for legacy)
        and loads appropriately.
        
        Args:
            path: Path to load the bundle from
            
        Returns:
            GraphBundle or None if loading fails
            
        Raises:
            ValueError: If json_storage_service is not available for JSON files
        """
        try:
            if not path.exists():
                self.logger.error(f"Bundle file not found: {path}")
                return None
            
            # Determine format by extension
            if not self.json_storage_service:
                raise ValueError(
                    "json_storage_service is required to load JSON bundles. "
                    "Please ensure GraphBundleService is properly initialized with all dependencies."
                )
            
            # Use JSONStorageService to read the bundle
            data = self.json_storage_service.read(collection=str(path))
            
            if data is None:
                self.logger.error(f"No data found in bundle file: {path}")
                return None
            
            return self._deserialize_metadata_bundle(data)
                
        except Exception as e:
            self.logger.error(f"Failed to load GraphBundle from {path}: {e}")
            return None
    
    def _deserialize_metadata_bundle(self, data: Dict[str, Any]) -> Optional[GraphBundle]:
        """Deserialize enhanced metadata bundle from dictionary format with backwards compatibility."""
        try:
            # Validate format
            if data.get("format") != "metadata":
                raise ValueError("Not a metadata bundle format")
            
            # Reconstruct nodes
            nodes = {}
            for name, node_data in data["nodes"].items():
                node = Node(
                    name=node_data["name"],
                    agent_type=node_data.get("agent_type"),
                    context=node_data.get("context", {}),
                    inputs=node_data.get("inputs", []),
                    output=node_data.get("output"),
                    prompt=node_data.get("prompt"),
                    description=node_data.get("description")
                )
                node.edges = node_data.get("edges", {})
                nodes[name] = node
            
            # Helper function to convert lists to sets, handling None values
            def list_to_set(lst):
                return set(lst) if lst is not None else set()
            
            # Extract all fields with backwards compatibility
            bundle = GraphBundle.create_metadata(
                graph_name=data["graph_name"],
                entry_point=data.get("entry_point"),
                nodes=nodes,
                required_agents=list_to_set(data["required_agents"]),
                required_services=list_to_set(data["required_services"]),
                service_load_order=data.get("service_load_order"),
                function_mappings=data.get("function_mappings", {}),
                csv_hash=data["csv_hash"],
                version_hash=data.get("version_hash"),
                # Phase 1: Agent mappings
                agent_mappings=data.get("agent_mappings"),
                builtin_agents=list_to_set(data.get("builtin_agents")),
                custom_agents=list_to_set(data.get("custom_agents")),
                # Phase 2: Optimization metadata
                graph_structure=data.get("graph_structure"),
                protocol_mappings=data.get("protocol_mappings"),
                # Phase 3: Validation metadata
                validation_metadata=data.get("validation_metadata")
            )
            
            # Set format metadata if available
            if "bundle_format" in data:
                bundle.bundle_format = data["bundle_format"]
            if "created_at" in data:
                bundle.created_at = data["created_at"]
            
            bundle_format = data.get("bundle_format", "legacy")
            self.logger.debug(
                f"Loaded metadata GraphBundle with format: {bundle_format}"
            )
            return bundle
            
        except Exception as e:
            self.logger.error(f"Failed to deserialize metadata bundle: {e}")
            return None
    
    def create_metadata_bundle_from_nodes(self, 
                                         nodes: Dict[str, Node], 
                                         graph_name: str, 
                                         csv_hash: Optional[str] = None,
                                         entry_point: Optional[str] = None) -> GraphBundle:
        """Create an enhanced metadata bundle from a dictionary of Node objects.
        
        This method creates a comprehensive bundle containing all metadata
        needed for fast graph assembly at runtime, including dependency
        analysis, agent mappings, and optimization hints.
        
        Args:
            nodes: Dictionary mapping node names to Node objects
            graph_name: Name for the graph
            csv_hash: Optional pre-computed hash of CSV content
            entry_point: Optional starting node name (auto-detected if None)
            
        Returns:
            GraphBundle with enhanced metadata-only format
            
        Raises:
            ValueError: If enhanced dependencies are not available
        """
        if not self._has_enhanced_dependencies:
            raise ValueError(
                "Enhanced dependencies required for metadata bundle creation. "
                "Please provide protocol_requirements_analyzer and agent_factory_service."
            )
        
        self.logger.debug(
            f"Creating enhanced metadata bundle from {len(nodes)} nodes with name {graph_name}"
        )
        
        # Phase 1: Critical metadata extraction
        # Identify entry point if not provided
        if entry_point is None:
            entry_point = self._identify_entry_point(nodes)
        
        # Analyze requirements using protocol-based approach
        requirements = self.protocol_requirements_analyzer.analyze_graph_requirements(nodes)
        required_agents = requirements["required_agents"]
        base_services = requirements["required_services"]
        
        # Get full dependency tree and filter to actual services
        analyzer = self._get_di_container_analyzer()
        all_dependencies = analyzer.build_full_dependency_tree(base_services)
        all_services = self._filter_actual_services(all_dependencies)
        service_load_order = self._calculate_service_load_order(all_services)
        
        # Extract agent mappings and classify agents
        agent_mappings = self._extract_agent_mappings(required_agents)
        builtin_agents, custom_agents = self._classify_agents(required_agents)
        
        # Phase 2: Optimization metadata
        graph_structure = self._analyze_graph_structure(nodes)
        protocol_mappings = self._extract_protocol_mappings()
        
        # Phase 3: Validation metadata
        validation_metadata = self._generate_validation_metadata(nodes)
        
        function_mappings = {}  # TODO: Extract function mappings if needed
        
        # Create enhanced metadata bundle with all new fields
        bundle = GraphBundle.create_metadata(
            graph_name=graph_name,
            entry_point=entry_point,
            nodes=nodes,
            required_agents=required_agents,
            required_services=all_services,
            service_load_order=service_load_order,
            function_mappings=function_mappings,
            csv_hash=csv_hash,
            # Phase 1: Agent mappings
            agent_mappings=agent_mappings,
            builtin_agents=builtin_agents,
            custom_agents=custom_agents,
            # Phase 2: Optimization metadata
            graph_structure=graph_structure,
            protocol_mappings=protocol_mappings,
            # Phase 3: Validation metadata
            validation_metadata=validation_metadata
        )
        
        self.logger.debug(
            f"Created enhanced metadata bundle with {len(nodes)} nodes, "
            f"{len(required_agents)} agent types, {len(all_services)} services, "
            f"entry_point: {entry_point}"
        )
        
        return bundle


    # def create_metadata_bundle_from_spec(self, 
    #                                     graph_spec: GraphSpec, 
    #                                     graph_name: str, 
    #                                     csv_hash: Optional[str] = None) -> GraphBundle:
    #     """Create a metadata-only bundle from a parsed GraphSpec.
        
    #     This method creates a lightweight bundle containing only the metadata
    #     needed to reconstruct the graph at runtime, without any agent instances.
        
    #     Args:
    #         graph_spec: Parsed GraphSpec containing graph structure
    #         graph_name: Name for the graph
    #         csv_hash: Optional pre-computed hash of CSV content
            
    #     Returns:
    #         GraphBundle with metadata-only format
            
    #     Raises:
    #         ValueError: If enhanced dependencies are not available or if no graphs found
    #     """
    #     if not self._has_enhanced_dependencies:
    #         raise ValueError(
    #             "Enhanced dependencies required for metadata bundle creation. "
    #             "Please provide protocol_requirements_analyzer and agent_factory_service."
    #         )
        
    #     self.logger.debug(f"Creating metadata bundle from GraphSpec with name {graph_name}")
        
    #     # Get graph names from spec
    #     graph_names = graph_spec.get_graph_names()
    #     if not graph_names:
    #         raise ValueError("No graphs found in GraphSpec")
        
    #     # Use the first graph if multiple graphs exist
    #     if len(graph_names) > 1:
    #         self.logger.warning(
    #             f"Multiple graphs found in GraphSpec: {graph_names}. Using first graph: {graph_names[0]}"
    #         )
        
    #     target_graph_name = graph_names[0]
    #     node_specs = graph_spec.get_nodes_for_graph(target_graph_name)
        
    #     # Convert NodeSpec to Node objects
    #     nodes = self._convert_node_specs_to_nodes(node_specs)
    #     function_mappings = {}  # TODO: Extract function mappings if needed
        
    #     # Analyze requirements using protocol-based approach
    #     requirements = self.protocol_requirements_analyzer.analyze_graph_requirements(nodes)
    #     required_agents = requirements["required_agents"]
    #     base_services = requirements["required_services"]
        
    #     # Get full dependency tree using DI container analyzer
    #     analyzer = self._get_di_container_analyzer()
    #     all_services = analyzer.build_full_dependency_tree(base_services)
        
    #     # Create metadata-only bundle
    #     bundle = GraphBundle.create_metadata(
    #         graph_name=graph_name,
    #         nodes=nodes,
    #         required_agents=required_agents,
    #         required_services=all_services,
    #         function_mappings=function_mappings,
    #         csv_hash=csv_hash
    #     )
        
    #     self.logger.debug(
    #         f"Created metadata bundle with {len(nodes)} nodes, "
    #         f"{len(required_agents)} agent types, {len(all_services)} services"
    #     )
        
    #     return bundle
    
    
    # def _convert_node_specs_to_nodes(self, node_specs: List[NodeSpec]) -> Dict[str, Node]:
    #     """Convert NodeSpec objects to Node objects.
        
    #     Based on the pattern from GraphDefinitionService._create_nodes_from_specs
    #     but simplified for metadata bundle creation.
        
    #     Args:
    #         node_specs: List of NodeSpec objects from GraphSpec
            
    #     Returns:
    #         Dictionary mapping node names to Node objects
    #     """
    #     nodes_dict = {}
        
    #     for node_spec in node_specs:
    #         self.logger.debug(f"Converting NodeSpec to Node: {node_spec.name}")
            
    #         # Only create if not already exists (handle duplicate definitions)
    #         if node_spec.name not in nodes_dict:
    #             # Convert context string to dict if needed
    #             context_dict = (
    #                 {"context": node_spec.context} if node_spec.context else {}
    #             )
                
    #             # Use default agent type if not specified
    #             agent_type = node_spec.agent_type or "Default"
                
    #             node = Node(
    #                 name=node_spec.name,
    #                 context=context_dict,
    #                 agent_type=agent_type,
    #                 inputs=node_spec.input_fields or [],
    #                 output=node_spec.output_field,
    #                 prompt=node_spec.prompt,
    #                 description=node_spec.description,
    #             )
                
    #             # Add edge information
    #             if node_spec.edge:
    #                 node.add_edge("default", node_spec.edge)
    #             elif node_spec.success_next or node_spec.failure_next:
    #                 if node_spec.success_next:
    #                     node.add_edge("success", node_spec.success_next)
    #                 if node_spec.failure_next:
    #                     node.add_edge("failure", node_spec.failure_next)
                
    #             nodes_dict[node_spec.name] = node
                
    #             self.logger.debug(
    #                 f"Created Node: {node_spec.name} with agent_type: {agent_type}, "
    #                 f"output: {node_spec.output_field}"
    #             )
    #         else:
    #             self.logger.debug(f"Node {node_spec.name} already exists, skipping")
        
    #     return nodes_dict

    
 