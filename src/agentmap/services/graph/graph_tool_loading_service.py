"""
GraphToolLoadingService for AgentMap.

Service responsible for loading and resolving tools from modules for agent nodes.
Extracted from GraphAgentInstantiationService for better separation of concerns.
"""

from typing import Any

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.logging_service import LoggingService
from agentmap.services.tool_loader import load_tools_from_module


class GraphToolLoadingService:
    """
    Service for loading tools from modules for agent nodes.

    This service handles the tool resolution phase where tool_source fields
    in node definitions are resolved to actual tool instances.
    """

    def __init__(self, logging_service: LoggingService):
        """
        Initialize with logging service.

        Args:
            logging_service: Service for logging
        """
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[GraphToolLoadingService] Initialized")

    def load_tools_for_nodes(self, bundle: GraphBundle) -> None:
        """
        Load tools from modules for all nodes that specify tool sources.

        This method processes each node's tool_source field and loads the specified
        tools into bundle.tools[node_name] for later binding during agent instantiation.

        Args:
            bundle: GraphBundle with nodes that may require tools

        Raises:
            ImportError: If a tool module cannot be imported
            ValueError: If specified tools are not found in the module
        """
        if not bundle.nodes:
            return

        loaded_count = 0
        for node_name, node in bundle.nodes.items():
            # Skip nodes without tool_source or with "toolnode" (special case)
            tool_source = getattr(node, "tool_source", None)
            if not tool_source or tool_source.lower() == "toolnode":
                continue

            try:
                tools = self._load_tools_for_single_node(node_name, node, tool_source)

                # Store in bundle
                bundle.tools[node_name] = tools
                loaded_count += 1

            except (ImportError, ValueError):
                # Re-raise these specific exceptions as they have good context
                raise
            except Exception as e:
                error_msg = (
                    f"Unexpected error loading tools for node {node_name}: {str(e)}\n"
                    f"Tool source: {tool_source}"
                )
                self.logger.error(f"[GraphToolLoadingService] {error_msg}")
                raise RuntimeError(error_msg) from e

        if loaded_count > 0:
            self.logger.info(
                f"[GraphToolLoadingService] Tool loading complete: {loaded_count} nodes configured with tools"
            )

    def _load_tools_for_single_node(
        self, node_name: str, node: Any, tool_source: str
    ) -> list:
        """
        Load tools for a single node from its tool source.

        Args:
            node_name: Name of the node
            node: Node object with tool configuration
            tool_source: Module path to load tools from

        Returns:
            List of loaded tool instances

        Raises:
            ImportError: If tool module cannot be imported
            ValueError: If specified tools not found in module
        """
        try:
            # Load all tools from the module
            self.logger.debug(
                f"[GraphToolLoadingService] Loading tools from: {tool_source}"
            )
            all_tools = load_tools_from_module(tool_source)

            # Filter to available_tools if specified
            available_tools = getattr(node, "available_tools", None)
            if available_tools:
                tools = self._filter_tools_by_availability(
                    all_tools, available_tools, tool_source, node_name
                )
            else:
                # Use all tools from module
                tools = all_tools

            tool_names = [t.name for t in tools]
            self.logger.info(
                f"[GraphToolLoadingService] Loaded {len(tools)} tools for {node_name}: {', '.join(tool_names)}"
            )

            return tools

        except ImportError as e:
            error_msg = (
                f"Failed to load tools for node {node_name}: {str(e)}\n"
                f"Tool source: {tool_source}\n"
                f"Suggestions:\n"
                f"  - Check ToolSource column in CSV\n"
                f"  - Verify the file path is correct\n"
                f"  - Ensure the module exists and is accessible"
            )
            self.logger.error(f"[GraphToolLoadingService] {error_msg}")
            raise ImportError(error_msg) from e

    def _filter_tools_by_availability(
        self, all_tools: list, available_tools: list, tool_source: str, node_name: str
    ) -> list:
        """
        Filter tools by the available_tools specification.

        Args:
            all_tools: All tools loaded from module
            available_tools: List of tool names to include
            tool_source: Source module path for error messages
            node_name: Node name for error messages

        Returns:
            Filtered list of tools

        Raises:
            ValueError: If requested tools not found in module
        """
        # Filter tools by name
        tools = [t for t in all_tools if t.name in available_tools]

        # Validate all requested tools were found
        found_names = {t.name for t in tools}
        requested_names = set(available_tools)
        missing = requested_names - found_names

        if missing:
            available_names = [t.name for t in all_tools]
            error_msg = (
                f"Tools not found in {tool_source}: {sorted(missing)}\n"
                f"Available tools: {sorted(available_names)}\n"
                f"Suggestions:\n"
                f"  - Check spelling in AvailableTools column\n"
                f"  - Verify @tool decorated functions exist in module"
            )
            self.logger.error(
                f"[GraphToolLoadingService] Tool validation failed for {node_name}: {error_msg}"
            )
            raise ValueError(error_msg)

        return tools
