# agentmap/services/node_registry_service.py
"""
Service for managing node registries and their injection into graphs.

This service consolidates all node registry operations including building registries
from graph definitions and injecting them into orchestrator agents.
"""
import json
from dataclasses import dataclass
from typing import Any, Dict

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


@dataclass
class NodeMetadata:
    """Metadata for a single node in the registry."""

    description: str
    prompt: str
    type: str
    input_fields: list = None
    output_field: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "description": self.description,
            "prompt": self.prompt,
            "type": self.type,
            "input_fields": self.input_fields or [],
            "output_field": self.output_field,
        }


from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class NodeRegistryUser(Protocol):
    """
    Protocol for agents that need a node registry. NOT the service, but the nodes created by the service

    To use LLM services in your agent, add this to your __init__:
        self.node_regsitry = None

    Then use it in your methods:
        response = self.node_registry

    The service will be automatically injected during graph building.
    """

    node_registry: Dict[str, Dict[str, Any]]


class NodeRegistryService:
    """
    Service for managing node registries and their injection into graphs.

    Handles building registries from graph definitions, caching them for performance,
    and injecting them into orchestrator agents during graph assembly.
    """

    def __init__(
        self, configuration: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize the NodeRegistryService.

        Args:
            configuration: Application configuration service
            logging_service: Logging service for creating loggers
        """
        self.configuration = configuration
        self.logger = logging_service.get_class_logger(self)
        self._registry_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def build_registry(
        self,
        graph_def: Dict[str, Any],
        graph_name: Optional[str] = None,
        force_rebuild: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a registry of node metadata from a graph definition.

        Args:
            graph_def: Graph definition dictionary from GraphBuilder
            graph_name: Optional name for caching purposes
            force_rebuild: Force rebuild even if cached version exists

        Returns:
            Dictionary mapping node names to metadata dictionaries
        """
        # Check cache first
        cache_key = graph_name or "unnamed"
        if not force_rebuild and cache_key in self._registry_cache:
            self.logger.debug(f"[NodeRegistry] Using cached registry for: {cache_key}")
            return self._registry_cache[cache_key]

        self.logger.debug(f"[NodeRegistry] Building registry for graph: {cache_key}")

        if not graph_def:
            self.logger.warning("[NodeRegistry] Empty graph definition provided")
            return {}

        registry = {}

        for node_name, node in graph_def.items():
            try:
                # Parse node context
                context_dict = self._parse_node_context(node.context)

                # Create metadata object
                metadata = NodeMetadata(
                    description=context_dict.get("description", "")
                    or node.description
                    or "",
                    prompt=node.prompt or "",
                    type=node.agent_type or "",
                    input_fields=getattr(node, "inputs", []),
                    output_field=getattr(node, "output", ""),
                )

                # Add a default description if none provided and we have a prompt
                if not metadata.description and metadata.prompt:
                    # Use the prompt trimmed to a reasonable length
                    max_desc_len = self.configuration.get_value(
                        "node_registry.max_description_length", 100
                    )
                    prompt = metadata.prompt
                    if len(prompt) > max_desc_len:
                        prompt = prompt[:max_desc_len] + "..."
                    metadata.description = prompt

                registry[node_name] = metadata.to_dict()

                self.logger.trace(
                    f"[NodeRegistry] Added node '{node_name}' to registry"
                )

            except Exception as e:
                self.logger.error(
                    f"[NodeRegistry] Failed to process node '{node_name}': {e}"
                )
                # Add minimal metadata for failed nodes
                registry[node_name] = {
                    "description": f"Error processing node: {str(e)}",
                    "prompt": "",
                    "type": getattr(node, "agent_type", "") or "",
                }

        # Cache the result
        if graph_name:
            self._registry_cache[cache_key] = registry

        self.logger.info(
            f"[NodeRegistry] Built registry with {len(registry)} nodes for: {cache_key}"
        )
        return registry

    def prepare_for_assembly(
        self, graph_def: Dict[str, Any], graph_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Prepare node registry for use during graph assembly.

        This is the main method for pre-compilation registry preparation.

        Args:
            graph_def: Graph definition from GraphBuilder
            graph_name: Optional graph name for caching

        Returns:
            Node registry ready for injection during assembly
        """
        self.logger.debug(
            f"[NodeRegistry] Preparing registry for assembly: {graph_name}"
        )

        # Build the registry
        registry = self.build_registry(graph_def, graph_name)

        # Log summary for debugging
        summary = self.get_registry_summary(registry)
        self.logger.info(f"[NodeRegistry] Registry prepared for assembly:")
        self.logger.info(f"   Total nodes: {summary['total_nodes']}")
        self.logger.info(f"   Node types: {summary['node_types']}")
        self.logger.info(f"   Nodes with descriptions: {summary['has_descriptions']}")

        return registry

    def verify_pre_compilation_injection(
        self, assembler: Any  # GraphAssembler instance
    ) -> Dict[str, bool]:
        """
        Verify that registry injection worked during assembly.

        Args:
            assembler: GraphAssembler instance

        Returns:
            Dictionary with verification results
        """
        stats = assembler.get_injection_summary()

        success_rate = 0
        if stats["orchestrators_found"] > 0:
            success_rate = (
                stats["orchestrators_injected"] / stats["orchestrators_found"]
            )

        result = {
            "has_orchestrators": stats["orchestrators_found"] > 0,
            "all_injected": stats["injection_failures"] == 0
            and stats["orchestrators_injected"] == stats["orchestrators_found"],
            "success_rate": success_rate,
            "stats": stats,
        }

        if result["has_orchestrators"]:
            if result["all_injected"]:
                self.logger.info(
                    f"[NodeRegistry] ✅ All {stats['orchestrators_found']} orchestrators successfully injected"
                )
            else:
                self.logger.warning(
                    f"[NodeRegistry] ⚠️ Only {stats['orchestrators_injected']}/{stats['orchestrators_found']} orchestrators injected"
                )
        else:
            self.logger.debug("[NodeRegistry] No orchestrators found in graph")

        return result

    # # SIMPLIFIED: Keep post-compilation injection as fallback for edge cases
    # def inject_post_compilation_fallback(
    #     self,
    #     graph: Any,
    #     node_registry: Dict[str, Dict[str, Any]],
    #     graph_name: Optional[str] = None
    # ) -> bool:
    #     """
    #     Fallback method for post-compilation injection.

    #     This is kept as a safety net for edge cases where pre-compilation
    #     injection might not work.

    #     Args:
    #         graph: Compiled LangGraph StateGraph
    #         node_registry: Node registry to inject
    #         graph_name: Optional graph name for logging

    #     Returns:
    #         True if injection was successful, False otherwise
    #     """
    #     self.logger.warning(f"[NodeRegistry] Using fallback post-compilation injection for graph: {graph_name}")
    #     self.logger.warning("[NodeRegistry] This should not normally be needed - consider investigating why pre-compilation injection failed")

    #     if not node_registry:
    #         self.logger.debug("[NodeRegistry] No node registry provided for fallback injection")
    #         return True

    #     if not hasattr(graph, 'nodes'):
    #         self.logger.error("[NodeRegistry] Graph has no 'nodes' attribute, cannot perform fallback injection")
    #         return False

    #     orchestrator_count = 0
    #     injection_errors = []

    #     # Simplified post-compilation injection - just try direct attribute access
    #     for node_name, node_func in graph.nodes.items():
    #         try:
    #             # Try to find agent instance through simple introspection
    #             agent = None

    #             # Check if it's a bound method
    #             if hasattr(node_func, '__self__') and hasattr(node_func.__self__, 'run'):
    #                 agent = node_func.__self__

    #             if agent and agent.__class__.__name__ == "OrchestratorAgent":
    #                 orchestrator_count += 1
    #                 agent.node_registry = node_registry
    #                 self.logger.info(f"[NodeRegistry] ✅ Fallback injection successful for orchestrator '{node_name}'")

    #         except Exception as e:
    #             error_msg = f"Failed fallback injection for node '{node_name}': {e}"
    #             self.logger.error(f"[NodeRegistry] {error_msg}")
    #             injection_errors.append(error_msg)

    #     success = len(injection_errors) == 0

    #     if orchestrator_count == 0:
    #         self.logger.debug("[NodeRegistry] No orchestrators found during fallback injection")
    #         success = True
    #     elif success:
    #         self.logger.info(f"[NodeRegistry] ✅ Fallback injection successful for {orchestrator_count} orchestrator(s)")
    #     else:
    #         self.logger.error(f"[NodeRegistry] ❌ Fallback injection failed with {len(injection_errors)} errors")

    #     return success

    def get_registry_summary(
        self, node_registry: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get a summary of the node registry for logging/debugging.

        Args:
            node_registry: The node registry to summarize

        Returns:
            Summary dictionary with registry statistics
        """
        if not node_registry:
            return {
                "total_nodes": 0,
                "node_types": {},
                "has_descriptions": 0,
                "node_names": [],
            }

        node_types = {}
        has_descriptions = 0

        for node_name, metadata in node_registry.items():
            node_type = metadata.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

            if metadata.get("description"):
                has_descriptions += 1

        return {
            "total_nodes": len(node_registry),
            "node_types": node_types,
            "has_descriptions": has_descriptions,
            "node_names": list(node_registry.keys()),
        }

    def clear_cache(self, graph_name: Optional[str] = None) -> None:
        """
        Clear the registry cache.

        Args:
            graph_name: If provided, only clear cache for this graph. Otherwise clear all.
        """
        if graph_name:
            cache_key = graph_name
            if cache_key in self._registry_cache:
                del self._registry_cache[cache_key]
                self.logger.debug(
                    f"[NodeRegistry] Cleared cache for graph: {graph_name}"
                )
        else:
            self._registry_cache.clear()
            self.logger.debug("[NodeRegistry] Cleared all registry caches")

    def _parse_node_context(self, context: Any) -> Dict[str, Any]:
        """
        Parse node context into a dictionary of metadata.

        Args:
            context: Node context from CSV (might be string, dict, or None)

        Returns:
            Dictionary of metadata from context
        """
        # Handle already parsed context
        if isinstance(context, dict):
            return context

        # Handle empty context
        if not context:
            return {}

        # Parse string context
        if isinstance(context, str):
            # Try parsing as JSON
            if context.strip().startswith("{"):
                try:
                    return json.loads(context)
                except json.JSONDecodeError as e:
                    self.logger.warning(
                        f"[NodeRegistry] Malformed JSON in context: {e}. Using as plain text."
                    )
                    # For malformed JSON, use whole string as description (don't try key-value parsing)
                    return {"description": context}

            # Try parsing as key:value pairs (only for non-JSON-like strings)
            context_dict = {}
            try:
                for part in context.split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        context_dict[k.strip()] = v.strip()
                    # Handle key=value format as well
                    elif "=" in part:
                        k, v = part.split("=", 1)
                        context_dict[k.strip()] = v.strip()

                # If we found any key-value pairs, return them
                if context_dict:
                    return context_dict
            except Exception as e:
                self.logger.debug(
                    f"[NodeRegistry] Failed to parse context as key-value pairs: {e}"
                )

            # If parsing failed, use whole string as description
            return {"description": context}

        # Other types - just return empty dict
        self.logger.debug(f"[NodeRegistry] Unknown context type: {type(context)}")
        return {}
