# agentmap/utils/node_registry.py
"""
Utilities for building and managing node registries for orchestration.

The node registry provides metadata about nodes for use by OrchestratorAgent
and other components that need to work with the graph structure.
"""
from typing import Any, Dict, Optional

from agentmap.logging import get_logger

logger = get_logger(__name__)


def build_node_registry(graph_def: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build a registry of node metadata for orchestration from a graph definition.

    Args:
        graph_def: Graph definition dictionary from GraphBuilder

    Returns:
        Dictionary mapping node names to metadata
    """
    registry = {}

    for node_name, node in graph_def.items():
        # Parse node context
        context_dict = _parse_node_context(node.context)

        # Extract metadata from node definition
        registry[node_name] = {
            "description": context_dict.get("description", ""),
            "prompt": node.prompt or "",
            "type": node.agent_type or ""
        }

        # Add a default description if none provided and we have a prompt
        if not registry[node_name]["description"] and node.prompt:
            # Use the prompt trimmed to a reasonable length
            prompt = node.prompt
            max_desc_len = 100
            if len(prompt) > max_desc_len:
                prompt = prompt[:max_desc_len] + "..."
            registry[node_name]["description"] = prompt

    return registry


def _parse_node_context(context: Any) -> Dict[str, Any]:
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
                import json
                return json.loads(context)
            except:
                pass

        # Try parsing as key:value pairs
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
        except:
            pass

        # If parsing failed, use whole string as description
        return {"description": context}

    # Other types - just return empty dict
    return {}


def populate_orchestrator_inputs(initial_state: Dict[str, Any], graph_def: Dict[str, Any],
                                 node_registry: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Populate input fields for orchestrator nodes in the initial state.

    Args:
        initial_state: Initial state dictionary
        graph_def: Graph definition
        node_registry: Node registry from build_node_registry

    Returns:
        Updated initial state
    """
    # Clone the state to avoid modifying the original
    state = dict(initial_state)

    # Add node registry to state for universal access
    state["__node_registry"] = node_registry

    # Find all orchestrator nodes
    for node_name, node in graph_def.items():
        if node.agent_type and node.agent_type.lower() == "orchestrator":
            # Get the first input field for this node
            if node.inputs and len(node.inputs) > 0 and node.inputs[0]:
                input_field = node.inputs[0]
                # Only set if not already present
                if input_field not in state:
                    state[input_field] = node_registry
                    logger.debug(f"Populated orchestrator input field '{input_field}' for node '{node_name}'")

    return state