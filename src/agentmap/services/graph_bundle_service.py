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
                 logger: Optional[logging.Logger] = None,
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
        # Handle legacy constructor for backwards compatibility
        if logger is not None and logging_service is None:
            self.logger = logger
            self.logging_service = None
        elif logging_service is not None:
            self.logger = logging_service.get_class_logger(self)
            self.logging_service = logging_service
        else:
            raise ValueError("Either logger or logging_service is required for GraphBundleService.")
        
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
        if bundle.is_metadata_only:
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
        else:
            # Legacy bundles are saved as pickle
            self._save_legacy_bundle(bundle, path)
    
    def _serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
        """Serialize metadata bundle to dictionary format."""
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
        
        return {
            "format": "metadata",
            "graph_name": bundle.graph_name,
            "nodes": nodes_data,
            "required_agents": sorted(list(bundle.required_agents)),
            "required_services": sorted(list(bundle.required_services)),
            "function_mappings": bundle.function_mappings,
            "csv_hash": bundle.csv_hash,
            "version_hash": bundle.version_hash
        }
    
    def _save_legacy_bundle(self, bundle: GraphBundle, path: Path) -> None:
        """Save legacy bundle using pickle format."""
        # Ensure path has .pkl extension
        if path.suffix not in ['.pkl', '.pickle']:
            path = path.with_suffix('.pkl')
        
        data = {
            "graph": bundle.graph,
            "node_registry": bundle.node_registry,
            "version_hash": bundle.version_hash,
        }
        
        with path.open("wb") as f:
            pickle.dump(data, f)
        
        self.logger.debug(f"Saved legacy GraphBundle to {path}")
    
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
            if path.suffix == '.json':
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
            else:
                # Assume pickle format for non-JSON files
                return self._load_legacy_bundle(path)
                
        except Exception as e:
            self.logger.error(f"Failed to load GraphBundle from {path}: {e}")
            return None
    
    def _deserialize_metadata_bundle(self, data: Dict[str, Any]) -> Optional[GraphBundle]:
        """Deserialize metadata bundle from dictionary format."""
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
            
            bundle = GraphBundle.create_metadata(
                graph_name=data["graph_name"],
                nodes=nodes,
                required_agents=set(data["required_agents"]),
                required_services=set(data["required_services"]),
                function_mappings=data["function_mappings"],
                csv_hash=data["csv_hash"],
                version_hash=data.get("version_hash")
            )
            
            self.logger.debug(f"Loaded metadata GraphBundle")
            return bundle
            
        except Exception as e:
            self.logger.error(f"Failed to deserialize metadata bundle: {e}")
            return None
    
    def _load_legacy_bundle(self, path: Path) -> Optional[GraphBundle]:
        """Load legacy bundle from pickle."""
        try:
            with path.open("rb") as f:
                data = pickle.load(f)

            bundle = GraphBundle(
                graph=data["graph"],
                node_registry=data["node_registry"],
                version_hash=data["version_hash"],
            )
            
            self.logger.debug(f"Loaded legacy GraphBundle from {path}")
            return bundle
            
        except Exception as e:
            self.logger.error(f"Failed to load legacy bundle from {path}: {e}")
            return None

    def verify_csv(self, bundle: GraphBundle, csv_content: str) -> bool:
        """Check if CSV content hash matches bundle version hash.
        
        Works with both legacy (version_hash) and new (csv_hash) formats.
        """
        if bundle.is_metadata_only:
            # Use csv_hash for metadata-only bundles
            if not bundle.csv_hash:
                return False
            current_hash = self._generate_hash(csv_content)
            return bundle.csv_hash == current_hash
        else:
            # Use version_hash for legacy bundles
            if not bundle.version_hash:
                return False
            current_hash = self._generate_hash(csv_content)
            return bundle.version_hash == current_hash
    
    def validate_bundle(self, bundle: GraphBundle, csv_content: str) -> bool:
        """Validate if bundle is still valid against CSV content.
        
        This method checks if the bundle's hash matches the current CSV content,
        indicating whether the bundle needs to be regenerated.
        
        Args:
            bundle: GraphBundle to validate
            csv_content: Current CSV content to validate against
            
        Returns:
            True if bundle is valid, False if needs regeneration
        """
        if bundle is None:
            return False
        
        return self.verify_csv(bundle, csv_content)

    def create_metadata_bundle_from_spec(self, 
                                        graph_spec: GraphSpec, 
                                        graph_name: str, 
                                        csv_hash: Optional[str] = None) -> GraphBundle:
        """Create a metadata-only bundle from a parsed GraphSpec.
        
        This method creates a lightweight bundle containing only the metadata
        needed to reconstruct the graph at runtime, without any agent instances.
        
        Args:
            graph_spec: Parsed GraphSpec containing graph structure
            graph_name: Name for the graph
            csv_hash: Optional pre-computed hash of CSV content
            
        Returns:
            GraphBundle with metadata-only format
            
        Raises:
            ValueError: If enhanced dependencies are not available or if no graphs found
        """
        if not self._has_enhanced_dependencies:
            raise ValueError(
                "Enhanced dependencies required for metadata bundle creation. "
                "Please provide protocol_requirements_analyzer and agent_factory_service."
            )
        
        self.logger.debug(f"Creating metadata bundle from GraphSpec with name {graph_name}")
        
        # Get graph names from spec
        graph_names = graph_spec.get_graph_names()
        if not graph_names:
            raise ValueError("No graphs found in GraphSpec")
        
        # Use the first graph if multiple graphs exist
        if len(graph_names) > 1:
            self.logger.warning(
                f"Multiple graphs found in GraphSpec: {graph_names}. Using first graph: {graph_names[0]}"
            )
        
        target_graph_name = graph_names[0]
        node_specs = graph_spec.get_nodes_for_graph(target_graph_name)
        
        # Convert NodeSpec to Node objects
        nodes = self._convert_node_specs_to_nodes(node_specs)
        function_mappings = {}  # TODO: Extract function mappings if needed
        
        # Analyze requirements using protocol-based approach
        requirements = self.protocol_requirements_analyzer.analyze_graph_requirements(nodes)
        required_agents = requirements["required_agents"]
        base_services = requirements["required_services"]
        
        # Get full dependency tree using DI container analyzer
        analyzer = self._get_di_container_analyzer()
        all_services = analyzer.build_full_dependency_tree(base_services)
        
        # Create metadata-only bundle
        bundle = GraphBundle.create_metadata(
            graph_name=graph_name,
            nodes=nodes,
            required_agents=required_agents,
            required_services=all_services,
            function_mappings=function_mappings,
            csv_hash=csv_hash
        )
        
        self.logger.debug(
            f"Created metadata bundle with {len(nodes)} nodes, "
            f"{len(required_agents)} agent types, {len(all_services)} services"
        )
        
        return bundle
    
    def create_metadata_bundle_from_nodes(self, 
                                         nodes: Dict[str, Node], 
                                         graph_name: str, 
                                         csv_hash: Optional[str] = None) -> GraphBundle:
        """Create a metadata-only bundle from a dictionary of Node objects.
        
        This method creates a lightweight bundle containing only the metadata
        needed to reconstruct the graph at runtime, without any agent instances.
        
        Args:
            nodes: Dictionary mapping node names to Node objects
            graph_name: Name for the graph
            csv_hash: Optional pre-computed hash of CSV content
            
        Returns:
            GraphBundle with metadata-only format
            
        Raises:
            ValueError: If enhanced dependencies are not available
        """
        if not self._has_enhanced_dependencies:
            raise ValueError(
                "Enhanced dependencies required for metadata bundle creation. "
                "Please provide protocol_requirements_analyzer and agent_factory_service."
            )
        
        self.logger.debug(
            f"Creating metadata bundle from {len(nodes)} nodes with name {graph_name}"
        )
        
        function_mappings = {}  # TODO: Extract function mappings if needed
        
        # Analyze requirements using protocol-based approach
        requirements = self.protocol_requirements_analyzer.analyze_graph_requirements(nodes)
        required_agents = requirements["required_agents"]
        base_services = requirements["required_services"]
        
        # Get full dependency tree using DI container analyzer
        analyzer = self._get_di_container_analyzer()
        all_services = analyzer.build_full_dependency_tree(base_services)
        
        # Create metadata-only bundle
        bundle = GraphBundle.create_metadata(
            graph_name=graph_name,
            nodes=nodes,
            required_agents=required_agents,
            required_services=all_services,
            function_mappings=function_mappings,
            csv_hash=csv_hash
        )
        
        self.logger.debug(
            f"Created metadata bundle with {len(nodes)} nodes, "
            f"{len(required_agents)} agent types, {len(all_services)} services"
        )
        
        return bundle
    
    def _convert_node_specs_to_nodes(self, node_specs: List[NodeSpec]) -> Dict[str, Node]:
        """Convert NodeSpec objects to Node objects.
        
        Based on the pattern from GraphDefinitionService._create_nodes_from_specs
        but simplified for metadata bundle creation.
        
        Args:
            node_specs: List of NodeSpec objects from GraphSpec
            
        Returns:
            Dictionary mapping node names to Node objects
        """
        nodes_dict = {}
        
        for node_spec in node_specs:
            self.logger.debug(f"Converting NodeSpec to Node: {node_spec.name}")
            
            # Only create if not already exists (handle duplicate definitions)
            if node_spec.name not in nodes_dict:
                # Convert context string to dict if needed
                context_dict = (
                    {"context": node_spec.context} if node_spec.context else {}
                )
                
                # Use default agent type if not specified
                agent_type = node_spec.agent_type or "Default"
                
                node = Node(
                    name=node_spec.name,
                    context=context_dict,
                    agent_type=agent_type,
                    inputs=node_spec.input_fields or [],
                    output=node_spec.output_field,
                    prompt=node_spec.prompt,
                    description=node_spec.description,
                )
                
                # Add edge information
                if node_spec.edge:
                    node.add_edge("default", node_spec.edge)
                elif node_spec.success_next or node_spec.failure_next:
                    if node_spec.success_next:
                        node.add_edge("success", node_spec.success_next)
                    if node_spec.failure_next:
                        node.add_edge("failure", node_spec.failure_next)
                
                nodes_dict[node_spec.name] = node
                
                self.logger.debug(
                    f"Created Node: {node_spec.name} with agent_type: {agent_type}, "
                    f"output: {node_spec.output_field}"
                )
            else:
                self.logger.debug(f"Node {node_spec.name} already exists, skipping")
        
        return nodes_dict

    def create_bundle(self, graph: Any, node_registry: Dict[str, Any], csv_content: str) -> GraphBundle:
        """Create a legacy GraphBundle (deprecated).
        
        This method is deprecated and provided only for backward compatibility.
        Use create_metadata_bundle_from_spec() or create_metadata_bundle_from_nodes() for new code.
        
        Args:
            graph: Compiled graph object
            node_registry: Node registry dictionary
            csv_content: CSV content for version hash
            
        Returns:
            GraphBundle in legacy format
        """
        warnings.warn(
            "create_bundle is deprecated. Use create_metadata_bundle_from_spec() or "
            "create_metadata_bundle_from_nodes() for new code.",
            DeprecationWarning,
            stacklevel=2
        )
        
        version_hash = self._generate_hash(csv_content)
        return GraphBundle(
            graph=graph,
            node_registry=node_registry,
            version_hash=version_hash
        )
    
    @staticmethod
    def _generate_hash(content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()
