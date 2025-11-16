# services/graph_bundle_service.py

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.csv_graph_parser_service import CSVGraphParserService
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.graph.graph_registry_service import GraphRegistryService
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocol_requirements_analyzer import (
    ProtocolBasedRequirementsAnalyzer,
)
from agentmap.services.static_bundle_analyzer import StaticBundleAnalyzer
from agentmap.services.storage.json_service import JSONStorageService
from agentmap.services.storage.system_manager import SystemStorageManager
from agentmap.services.storage.types import StorageResult, WriteMode


class GraphBundleService:
    def __init__(
        self,
        logging_service: LoggingService,
        protocol_requirements_analyzer: ProtocolBasedRequirementsAnalyzer,
        agent_factory_service: AgentFactoryService,
        json_storage_service: JSONStorageService,
        csv_parser_service: CSVGraphParserService,
        static_bundle_analyzer: StaticBundleAnalyzer,
        app_config_service: AppConfigService,
        declaration_registry_service: DeclarationRegistryService,
        graph_registry_service: GraphRegistryService,
        file_path_service: FilePathService,
        system_storage_manager: SystemStorageManager,
    ):  # Added for bundle caching and registry
        """Initialize GraphBundleService with enhanced dependencies.

        Args:
            logging_service: LoggingService for proper dependency injection
            protocol_requirements_analyzer: Service for analyzing protocol requirements
            agent_factory_service: Service for agent creation and management
            json_storage_service: JSON storage service for bundle persistence (required for save/load)
            csv_parser_service: CSV parser service for parsing CSV files
            static_bundle_analyzer: Static bundle analyzer for fast declaration-based bundle creation
            app_config_service: Application config service for cache path (optional)
            declaration_registry_service: Declaration registry service for service dependencies (optional)
            graph_registry_service: Graph registry service for bundle caching and registry
            file_path_service: File path service for centralized secure path handling
            system_storage_manager: System storage manager for system cache storage (optional)
        """
        self.logger = logging_service.get_class_logger(self)
        self.logging_service = logging_service

        # Store enhanced dependencies (may be None for legacy usage)
        self.protocol_requirements_analyzer = protocol_requirements_analyzer
        self.agent_factory_service = agent_factory_service
        self.json_storage_service = json_storage_service
        self.csv_parser_service = csv_parser_service
        self.static_bundle_analyzer = static_bundle_analyzer
        self.app_config_service = app_config_service
        self.declaration_registry = (
            declaration_registry_service  # Store for service dependency resolution
        )
        self.graph_registry_service = (
            graph_registry_service  # Store for bundle registry and caching
        )
        self.system_storage_manager = (
            system_storage_manager  # Store for system-level bundle storage
        )
        self.file_path_service = (
            file_path_service  # Store for centralized path handling
        )

        # Check if enhanced functionality is available
        self._has_enhanced_dependencies = all(
            [protocol_requirements_analyzer, agent_factory_service]
        )

    def requires_checkpoint_support(self, bundle: GraphBundle) -> bool:
        """Determine if the supplied bundle needs checkpoint support."""

        if bundle is None:
            self.logger.debug(
                "[GraphBundleService] No bundle supplied for checkpoint analysis"
            )
            return False

        interrupt_capable_types = {"human", "suspend"}

        required_agents = getattr(bundle, "required_agents", None)
        if required_agents:
            normalized_agents = {
                str(agent).split(":")[-1].strip().lower()
                for agent in required_agents
                if isinstance(agent, str) and agent.strip()
            }
            intersection = interrupt_capable_types & normalized_agents
            if intersection:
                matched = ", ".join(sorted(intersection))
                self.logger.debug(
                    f"[GraphBundleService] Bundle '{bundle.graph_name}' requires"
                    f" checkpoint support due to agents: {matched}"
                )
                return True

            self.logger.debug(
                f"[GraphBundleService] Bundle '{bundle.graph_name}' does not require"
                " checkpoint support (no interrupt-capable agents declared)"
            )
            return False

        # Fallback behavior removed - bundles without required_agents don't get checkpoint support
        self.logger.debug(
            f"[GraphBundleService] Bundle '{bundle.graph_name}' has no required_agents; "
            "checkpoint support not required"
        )
        return False

    # ==========================================
    # Phase 1: Critical Metadata Extraction
    # ===========================================

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

    def _extract_agent_mappings(self, agent_types: Set[str]) -> Dict[str, str]:
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

    # ==========================================
    # Phase 2: Optimization Metadata
    # ==========================================

    def _analyze_graph_structure(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Analyze graph structure for optimization hints.

        Now includes parallel routing analysis for better metadata.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary containing graph structure analysis including parallel patterns
        """
        try:
            edge_count = sum(len(node.edges) for node in nodes.values())
            has_conditional = any(
                any(condition in node.edges for condition in ["success", "failure"])
                for node in nodes.values()
            )

            # Analyze parallel patterns
            parallel_analysis = self._analyze_parallel_patterns(nodes)

            structure = {
                "node_count": len(nodes),
                "edge_count": edge_count,
                "has_conditional_routing": has_conditional,
                "max_depth": self._calculate_max_depth(nodes),
                "is_dag": self._check_dag(nodes),
                "parallel_opportunities": parallel_analysis["parallel_groups"],
                "has_parallel_routing": parallel_analysis["has_parallel"],
                "max_parallelism": parallel_analysis["max_parallelism"],
                "fan_out_count": len(parallel_analysis["fan_out_nodes"]),
                "fan_in_count": len(parallel_analysis["fan_in_nodes"]),
            }

            self.logger.debug(
                f"Analyzed graph structure: {structure['node_count']} nodes, "
                f"DAG: {structure['is_dag']}, conditional: {structure['has_conditional_routing']}, "
                f"parallel: {structure['has_parallel_routing']} (max={structure['max_parallelism']})"
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
                "parallel_opportunities": [],
                "has_parallel_routing": False,
                "max_parallelism": 1,
                "fan_out_count": 0,
                "fan_in_count": 0,
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

    def _analyze_parallel_patterns(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Analyze parallel routing patterns in the graph.

        Identifies fan-out, fan-in, and parallel opportunities for optimization.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary with parallel pattern analysis:
            - fan_out_nodes: Nodes that route to multiple targets
            - fan_in_nodes: Nodes that receive from multiple sources
            - parallel_groups: Groups of nodes that execute in parallel
            - max_parallelism: Maximum number of parallel branches
            - has_parallel: Whether graph contains any parallel routing
        """
        fan_out_nodes = []
        fan_in_count = {}
        parallel_groups = []
        max_parallelism = 1

        # Find fan-out nodes (nodes with parallel edges)
        for node_name, node in nodes.items():
            for condition, targets in node.edges.items():
                if isinstance(targets, list) and len(targets) > 1:
                    fan_out_nodes.append(
                        {
                            "node": node_name,
                            "condition": condition,
                            "targets": targets,
                            "parallelism": len(targets),
                        }
                    )
                    parallel_groups.append(targets)
                    max_parallelism = max(max_parallelism, len(targets))

                    # Track fan-in (nodes receiving from parallel source)
                    for target in targets:
                        fan_in_count[target] = fan_in_count.get(target, 0) + 1

        # Identify actual fan-in nodes (nodes with multiple incoming edges)
        fan_in_nodes = [
            {"node": node, "incoming_count": count}
            for node, count in fan_in_count.items()
            if count > 1
        ]

        return {
            "fan_out_nodes": fan_out_nodes,
            "fan_in_nodes": fan_in_nodes,
            "parallel_groups": parallel_groups,
            "max_parallelism": max_parallelism,
            "has_parallel": len(fan_out_nodes) > 0,
        }

    def _extract_protocol_mappings(self) -> Dict[str, str]:
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
                    "required_fields_present",
                ],
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
                "validation_rules": [],
            }

    def _get_framework_version(self) -> str:
        """Get the AgentMap framework version."""
        try:
            # This would typically read from package metadata
            return "2.0.0"  # Placeholder version
        except Exception:
            return "unknown"

    def delete_bundle(self, bundle: GraphBundle) -> bool:
        """Delete a cached bundle file from disk.

        Uses the bundle's csv_hash and graph_name to locate and delete the cached bundle file
        using consistent path format from FilePathService.
        This method only handles file deletion - registry cleanup should be
        handled separately by the caller if needed.

        Args:
            bundle: GraphBundle containing the csv_hash to identify the cached file

        Returns:
            True if bundle file was deleted, False if file not found

        Raises:
            ValueError: If bundle has no csv_hash
            PermissionError: If insufficient permissions to delete file
            IOError: If deletion fails for other reasons
        """
        # Check for csv_hash first, before any other operations
        # Note: GraphBundle.__post_init__ converts None to "unknown_hash"
        if (
            bundle.csv_hash is None
            or bundle.csv_hash == ""
            or bundle.csv_hash == "unknown_hash"
        ):
            raise ValueError(
                "Bundle has no csv_hash - cannot identify cached file to delete"
            )

        try:
            # Use FilePathService to get consistent bundle path
            bundle_path = self.file_path_service.get_bundle_path(
                csv_hash=bundle.csv_hash, graph_name=bundle.graph_name
            )

            if not bundle_path.exists():
                self.logger.debug(f"Bundle file not found for deletion: {bundle_path}")
                return False

            # Delete the bundle file
            bundle_path.unlink()
            self.logger.info(
                f"Deleted cached bundle: {bundle_path.name} for graph '{bundle.graph_name}'"
            )
            return True

        except PermissionError as e:
            error_msg = f"Permission denied when deleting bundle file: {e}"
            self.logger.error(error_msg)
            raise PermissionError(error_msg)
        except Exception as e:
            error_msg = f"Failed to delete bundle file: {e}"
            self.logger.error(error_msg)
            raise IOError(error_msg)

    def save_bundle(self, bundle: GraphBundle, path: Path) -> Optional[StorageResult]:
        """Persist the bundle to disk in appropriate format.

        Saves metadata-only bundles as JSON. Uses SystemStorageManager for system bundles
        in cache_folder/bundles and JSONStorageService for user storage.

        Args:
            bundle: GraphBundle to save
            path: Path to save the bundle to (can be Path or str)

        Raises:
            ValueError: If required storage service is not available
            IOError: If save operation fails
        """

        # Ensure path is a Path object
        path = Path(path)

        # Use system storage for cache_folder/bundles
        self.logger.debug(f"Using SystemStorageManager for system bundle: {path}")

        # Serialize bundle to dictionary
        data = self._serialize_metadata_bundle(bundle)

        # Get JSON storage service for "bundles" namespace
        storage_service = self.system_storage_manager.get_json_storage("bundles")

        result = storage_service.write(
            collection=path.name, data=data, mode=WriteMode.WRITE
        )

        if result.success:
            self.logger.debug(
                f"Saved system bundle to cache_folder/bundles/{path.name} with csv_hash {bundle.csv_hash}"
            )
            return result
        else:
            error_msg = f"Failed to save system bundle: {result.error}"
            self.logger.error(error_msg)
            raise IOError(error_msg)

    def _is_cache_path(self, path: Path) -> bool:
        """Check if the given path is within the cache_folder.

        Args:
            path: Path to check

        Returns:
            True if path is within cache_folder, False otherwise
        """
        if not self.app_config_service:
            return False

        try:
            cache_folder = Path(self.app_config_service.get_cache_folder())
            return cache_folder in path.parents or path.parent == cache_folder
        except Exception as e:
            self.logger.debug(f"Could not determine if path is in cache folder: {e}")
            return False

    def _serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
        """Serialize enhanced metadata bundle to dictionary format.

        Handles both single-target (str) and multi-target (list[str]) edges
        for parallel execution support. JSON naturally preserves both types.
        """
        # Serialize nodes to dictionaries
        nodes_data = {}
        for name, node in bundle.nodes.items():
            # Serialize edges with proper type handling
            # Edge values may be str (single target) or list[str] (parallel)
            # JSON serialization preserves both types naturally
            nodes_data[name] = {
                "name": node.name,
                "agent_type": node.agent_type,
                "context": node.context,
                "inputs": node.inputs,
                "output": node.output,
                "prompt": node.prompt,
                "description": node.description,
                "edges": node.edges,  # Preserves Union[str, List[str]] for each edge
                "tool_source": node.tool_source,
                "available_tools": node.available_tools,
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
            "missing_declarations": set_to_list(bundle.missing_declarations),
            # Legacy fields for backwards compatibility
            "csv_hash": bundle.csv_hash,
            "version_hash": bundle.version_hash,
        }

    def load_bundle(self, path: Path) -> Optional[GraphBundle]:
        """Load a GraphBundle from a file.

        Automatically detects format (JSON for metadata)
        and loads appropriately. Uses SystemStorageManager for system bundles
        in cache_folder/bundles and JSONStorageService for user storage.

        Args:
            path: Path to load the bundle from (can be Path or str)

        Returns:
            GraphBundle or None if loading fails

        Raises:
            ValueError: If required storage service is not available
        """
        try:
            # Ensure path is a Path object
            path = Path(path)

            # Use system storage for cache_folder/bundles
            self.logger.debug(f"Using SystemStorageManager for system bundle: {path}")

            # Get JSON storage service for "bundles" namespace
            storage_service = self.system_storage_manager.get_json_storage("bundles")
            data = storage_service.read(
                collection=path.name,
            )

            if data is None:
                self.logger.error(f"No data found in system bundle file: {path}")
                return None

            return self._deserialize_metadata_bundle(data)

        except Exception as e:
            self.logger.error(f"Failed to load GraphBundle from {path}: {e}")
            return None

    def _deserialize_metadata_bundle(
        self, data: Dict[str, Any]
    ) -> Optional[GraphBundle]:
        """Deserialize enhanced metadata bundle from dictionary format.

        Handles both legacy bundles (single-target edges) and new bundles
        (parallel-target edges) with backward compatibility. JSON deserialization
        preserves types (str or list[str]) automatically.
        """
        try:
            # Validate format
            if data.get("format") != "metadata":
                raise ValueError("Not a metadata bundle format")

            # Reconstruct nodes with parallel edge support
            nodes = {}
            for name, node_data in data["nodes"].items():
                node = Node(
                    name=node_data["name"],
                    agent_type=node_data.get("agent_type"),
                    context=node_data.get("context", {}),
                    inputs=node_data.get("inputs", []),
                    output=node_data.get("output"),
                    prompt=node_data.get("prompt"),
                    description=node_data.get("description"),
                    tool_source=node_data.get("tool_source"),
                    available_tools=node_data.get("available_tools"),
                )

                # Restore edges - now supports Union[str, List[str]]
                # JSON deserialization preserves types (str or list)
                edges_data = node_data.get("edges", {})
                for condition, targets in edges_data.items():
                    # Targets may be str or list[str] - both supported by Node.add_edge()
                    node.add_edge(condition, targets)

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
                validation_metadata=data.get("validation_metadata"),
                missing_declarations=list_to_set(
                    data.get("missing_declarations")
                ),  # FIX: Restore missing_declarations
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

    def create_metadata_bundle_from_nodes(
        self,
        nodes: Dict[str, Node],
        graph_name: str,
        config_path: str,
        csv_hash: Optional[str] = None,
        entry_point: Optional[str] = None,
    ) -> GraphBundle:
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
            if not nodes:
                # Handle empty nodes case - set to None, will be handled downstream
                entry_point = None
            else:
                # for now, go with the first node until we need to do otherwise.
                entry_point = list(nodes.keys())[
                    0
                ]  # self._identify_entry_point(nodes) #this isn't really working correctly

        # Analyze requirements using protocol-based approach
        # TODO: FIX this... it doesn't seem to be picking up all the protocols
        requirements = self.protocol_requirements_analyzer.analyze_graph_requirements(
            nodes
        )
        required_agents = requirements["required_agents"]
        base_services = requirements["required_services"]

        # Load service dependencies from declaration registry
        all_dependencies = self.declaration_registry.resolve_service_dependencies(
            base_services
        )
        service_load_order = self.declaration_registry.calculate_load_order(
            all_dependencies
        )

        # TODO: Check if this is still needed
        all_services = self._filter_actual_services(all_dependencies)

        # Extract agent mappings and classify agents
        agent_mappings = self._extract_agent_mappings(required_agents)
        builtin_agents, custom_agents = self._classify_agents(required_agents)

        # Phase 2: Optimization metadata
        # graph_structure = self._analyze_graph_structure(nodes) # this doesn't really do anythign right now... not needed.
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
            # graph_structure=graph_structure,
            protocol_mappings=protocol_mappings,
            # Phase 3: Validation metadata
            validation_metadata=validation_metadata,
        )

        self.logger.debug(
            f"Created enhanced metadata bundle with {len(nodes)} nodes, "
            f"{len(required_agents)} agent types, {len(all_services)} services, "
            f"entry_point: {entry_point}"
        )

        return bundle

    def get_or_create_bundle(
        self,
        csv_path: Path,
        graph_name: Optional[str] = None,
        config_path: Optional[str] = None,
        force_create: bool = False,
    ) -> Tuple[GraphBundle, bool]:
        """
        Get existing bundle from cache or create a new one.

        This method encapsulates the bundle caching logic, checking for
        existing bundles using composite keys (csv_hash, graph_name) and
        creating new ones as needed. Bundles are created per-graph, not per-CSV.

        Args:
            csv_path: Path to CSV file
            graph_name: Optional graph name (used for composite key lookup)
            config_path: Optional path to configuration file

        Returns:
            Tuple containing:
                GraphBundle ready for execution or scaffolding
                Boolean indicating if bundle was created (True) or loaded (False)

        Raises:
            ValueError: If graph_registry_service is not available
            FileNotFoundError: If CSV file doesn't exist
        """
        if not self.graph_registry_service:
            raise ValueError(
                "graph_registry_service is required for bundle caching. "
                "Please ensure GraphBundleService is properly initialized."
            )

        # Ensure csv_path is a Path object
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Compute hash for CSV file using helper method
        csv_hash = GraphRegistryService.compute_hash(csv_path)

        bundle = self.lookup_bundle(csv_hash, graph_name)

        if bundle and not force_create:
            # Bundle contains everything needed - no declaration loading required
            return (bundle, True)

        # load all classes for bundle creation
        bundle = self._create_bundle(csv_path, csv_hash, graph_name)
        return (bundle, False)

    def _create_bundle(self, csv_path, csv_hash, graph_name) -> GraphBundle:
        # Create new bundle for this specific graph
        self.logger.info(
            f"Creating new bundle for {csv_path} with graph '{graph_name or 'auto-detect'}'"
        )
        bundle = None

        try:
            # load all classes for a new bundle
            self.declaration_registry.load_all()

            bundle = self.static_bundle_analyzer.create_static_bundle(
                csv_path, graph_name
            )
            self.logger.info("Created bundle using fast static analysis")
        except FileNotFoundError as e:
            self.logger.warning(f"CSV not found: {csv_path}")
        except Exception as e:
            self.logger.warning("Failed to create bundle using fast static analysis")
            raise e

        bundle_path = self.file_path_service.get_bundle_path(
            csv_hash=csv_hash,
            graph_name=bundle.graph_name,
        )

        save_result: StorageResult = self.save_bundle(bundle, bundle_path)

        if save_result.success:
            # TODO: See if this actually changes from above
            bundle_path = Path(save_result.file_path)
            # Register with composite key for future lookups
            self.graph_registry_service.register(
                csv_hash,
                bundle.graph_name,
                bundle_path,
                csv_path,
                len(bundle.nodes) if bundle.nodes else 0,
            )
            self.logger.info(
                f"Bundle saved and registered with composite key: "
                f"({csv_hash[:8]}..., '{bundle.graph_name}')"
            )
        else:
            self.logger.warning(f"Failed to save bundle: {save_result.error}")

        # Log warnings for missing declarations
        if bundle.missing_declarations:
            self.logger.warning(
                f"Missing declarations for agent types: {', '.join(bundle.missing_declarations)}. "
                f"These agents will need to be defined before graph execution. execute 'scaffold' command"
            )

        return bundle

    def lookup_bundle(self, csv_hash, graph_name):
        # Look up bundle using composite key (csv_hash, graph_name)
        bundle_path = self.graph_registry_service.find_bundle(csv_hash, graph_name)
        bundle = None
        if bundle_path:
            # Load existing bundle from cache
            self.logger.info(
                f"Loading cached bundle for hash {csv_hash[:8]}... "
                f"and graph '{graph_name or 'default'}'"
            )
            bundle = self.load_bundle(bundle_path)

            # Validate the loaded bundle matches requested graph
            if bundle and graph_name and bundle.graph_name != graph_name:
                self.logger.warning(
                    f"Cached bundle has graph '{bundle.graph_name}' but "
                    f"requested '{graph_name}'. Creating new bundle."
                )
                bundle = None  # Force recreation
        return bundle
