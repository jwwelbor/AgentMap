"""
Node specification conversion logic.

Provides functionality to convert NodeSpec domain models to Node objects
for use in graph building and metadata bundle creation.
"""

import ast
import json
from typing import TYPE_CHECKING, Dict, List

from agentmap.models.graph_spec import NodeSpec
from agentmap.models.node import Node

if TYPE_CHECKING:
    from agentmap.services.logging_service import LoggingService


class NodeSpecConverter:
    """
    Converter for NodeSpec to Node transformations.

    Handles conversion of NodeSpec domain models to Node objects,
    managing edge information and context transformation.
    """

    def __init__(self, logger: "LoggingService"):
        """
        Initialize converter with logger.

        Args:
            logger: Logger instance for logging conversion messages
        """
        self.logger = logger

    def convert_node_specs_to_nodes(
        self, node_specs: List[NodeSpec]
    ) -> Dict[str, Node]:
        """
        Convert NodeSpec objects to Node objects.

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
                context_dict = self._parse_context(node_spec.context)

                # Use default agent type if not specified
                agent_type = node_spec.agent_type or "default"

                node = Node(
                    name=node_spec.name,
                    context=context_dict,
                    agent_type=agent_type,
                    inputs=node_spec.input_fields or [],
                    output=node_spec.output_field,
                    prompt=node_spec.prompt,
                    description=node_spec.description,
                    tool_source=node_spec.tool_source,
                    available_tools=node_spec.available_tools,
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

    def _parse_context(self, context: str) -> Dict:
        """
        Parse the raw context string from a CSV cell into a dict.

        Tries formats in order:
          1. JSON  — {"key": value, ...}
          2. Python dict literal — {'key': value, ...}
          3. Plain string fallback — {"context": original_string}
          4. Empty/None — {}

        This ensures that structured keys (e.g. provider, routing_enabled,
        task_type) are accessible at the top level of Node.context, matching
        the way LLMAgent and other agents read them via self.context.get(...).
        """
        if not context:
            return {}
        try:
            parsed = json.loads(context)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            parsed = ast.literal_eval(context)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass
        return {"context": context}
