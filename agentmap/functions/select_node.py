# agentmap/functions/select_node_llm.py
from typing import Any, Dict

from agentmap.agents import get_agent_class
from agentmap.logging import get_logger

logger = get_logger(__name__)


def select_node_llm(state: Any, success_node: str = None, failure_node: str = None) -> str:
    """
    Select the most appropriate node based on LLM analysis of input and intents.

    Args:
        state: Current state object
        success_node: Default success node if no match is found
        failure_node: Default failure node in case of error

    Returns:
        Name of the selected node

    Node Context: LLM-powered node selector that matches user input against node intents

    Available in state:
    - input_text: Text to match against intents
    - available_nodes: Dictionary of nodes with their intents
    - node_type: Optional filter for node types
    - llm_type: LLM type to use for matching (openai, anthropic, google)
    """
    try:
        # Extract configuration from state
        node_type = state.get("node_type", None)  # Filter by node type
        llm_type = state.get("llm_type", "openai")  # LLM type to use

        # Get input text to match against intents
        input_text = _get_input_text(state)

        # Get available nodes from state
        available_nodes = _get_available_nodes(state)

        # Filter nodes by type if specified
        if node_type:
            available_nodes = {
                name: info for name, info in available_nodes.items()
                if info.get("type", "") == node_type
            }

        # If no nodes are available, return default target
        if not available_nodes:
            logger.warning(f"[select_node_llm] No available nodes for matching. Using success_node: {success_node}")
            return success_node

        # Create node descriptions for the LLM
        node_descriptions = []
        for node_name, node_info in available_nodes.items():
            description = node_info.get("description", "")
            intent = node_info.get("intent", "") or node_info.get("prompt", "")
            node_type = node_info.get("type", "")

            node_descriptions.append(
                f"- Node: {node_name}\n"
                f"  Description: {description}\n"
                f"  Intent: {intent}\n"
                f"  Type: {node_type}"
            )

        nodes_text = "\n".join(node_descriptions)

        # Construct prompt for the LLM
        llm_prompt = (
            f"You are an intent router that selects the most appropriate node to handle a user request.\n\n"
            f"Available nodes:\n{nodes_text}\n\n"
            f"User input: \"{input_text}\"\n\n"
            f"Select the SINGLE BEST node to handle this request. "
            f"Consider the semantics and intent of the user request. "
            f"First explain your reasoning, then on a new line write just the selected node name prefixed with 'Selected: '."
        )

        # Use existing LLM agent
        llm_agent_class = get_agent_class(llm_type)
        if not llm_agent_class:
            logger.warning(
                f"[select_node_llm] LLM type '{llm_type}' not found in registry. Using first available node.")
            return next(iter(available_nodes.keys()))

        llm_agent = llm_agent_class(
            name="orchestrator_llm",
            prompt=llm_prompt,
            context={"temperature": 0.2}  # Low temperature for more consistent results
        )

        # Process the prompt
        llm_response = llm_agent.process({})

        # Extract the selected node from the response
        llm_response_str = str(llm_response)

        # Look for the "Selected: " pattern
        if "Selected: " in llm_response_str:
            for line in llm_response_str.split("\n"):
                if line.strip().startswith("Selected: "):
                    selected = line.split("Selected: ", 1)[1].strip()
                    # Verify this is a valid node
                    if selected in available_nodes:
                        return selected

        # Fallback: look for an exact node name in the response
        for node_name in available_nodes.keys():
            if node_name in llm_response_str:
                return node_name

        # Last resort: if no node found, return success_node
        logger.warning(f"[select_node_llm] Couldn't extract node from LLM response. Using success_node.")
        return success_node

    except Exception as e:
        logger.error(f"[select_node_llm] Error selecting node: {e}")
        return failure_node


def _get_input_text(state: Dict[str, Any]) -> str:
    """Extract input text from state."""
    # Check common input field names
    for field in ["input", "input_text", "query", "text", "message", "user_input"]:
        if field in state:
            return str(state[field])

    # If no recognized field, return empty string
    return ""


def _get_available_nodes(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Get available nodes from state."""
    # First check for explicitly provided nodes
    if "available_nodes" in state:
        return state["available_nodes"]

    # Second check for node registry in the state
    if "__node_registry" in state:
        return state["__node_registry"]

    # Final option: assume valid destination nodes are provided as dictionary keys
    nodes = {}
    for key, value in state.items():
        if key.startswith("node_") and isinstance(value, dict):
            node_name = key[5:]  # Remove "node_" prefix
            nodes[node_name] = value

    return nodes


def _simple_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> tuple[str, float]:
    """Fast algorithmic matching for obvious cases."""
    input_lower = input_text.lower()

    # 1. Check for exact node name in input
    for node_name in available_nodes:
        if node_name.lower() in input_lower:
            return node_name, 1.0  # Perfect confidence for exact match

    # 2. Quick keyword matching
    best_match = None
    best_score = 0.0

    for node_name, node_info in available_nodes.items():
        # Extract keywords from intent/prompt
        intent = node_info.get("intent", "") or node_info.get("prompt", "")
        keywords = intent.lower().split()

        # Count matching keywords
        matches = sum(1 for kw in keywords if kw in input_lower)

        if keywords:
            score = matches / len(keywords)
            if score > best_score:
                best_score = score
                best_match = node_name

    return best_match or next(iter(available_nodes)), best_score