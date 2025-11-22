# services/graph/bundle_serializer.py

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.logging_service import LoggingService


class BundleSerializer:
    """Handles serialization and deserialization of graph bundles.

    This class is responsible for converting GraphBundle objects to/from
    dictionary format for storage and retrieval.
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize the bundle serializer.

        Args:
            logging_service: Service for logging operations
        """
        self.logger = logging_service.get_class_logger(self)

    def serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
        """Serialize enhanced metadata bundle to dictionary format.

        Handles both single-target (str) and multi-target (list[str]) edges
        for parallel execution support. JSON naturally preserves both types.

        Args:
            bundle: GraphBundle to serialize

        Returns:
            Dictionary representation of the bundle
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

    def deserialize_metadata_bundle(
        self, data: Dict[str, Any]
    ) -> Optional[GraphBundle]:
        """Deserialize enhanced metadata bundle from dictionary format.

        Handles both legacy bundles (single-target edges) and new bundles
        (parallel-target edges) with backward compatibility. JSON deserialization
        preserves types (str or list[str]) automatically.

        Args:
            data: Dictionary representation of the bundle

        Returns:
            GraphBundle object or None if deserialization fails
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
