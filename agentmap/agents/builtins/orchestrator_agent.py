# agentmap/agents/builtins/orchestrator_agent.py
from typing import Any, Dict

from agentmap.agents import get_agent_class
from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.
    Uses existing LLM agents to perform intent matching.
    """

    def __init__(self, name: str, prompt: str, context: dict = None):
        super().__init__(name, prompt, context)
        context = context or {}

        # Configuration options
        self.node_type_filter = context.get("node_type", None)  # Filter by node type
        self.default_target = context.get("default_target", None)  # Default node if no match found
        self.llm_type = context.get("llm_type", "openai")  # LLM type to use for matching

    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and select the best matching node.

        Args:
            inputs: Dictionary containing input and available nodes

        Returns:
            Name of the selected next node
        """
        # Get input text and available nodes
        input_text = self._get_input_text(inputs)
        available_nodes = self._get_available_nodes(inputs)

        # Filter nodes by type if specified
        if self.node_type_filter:
            available_nodes = {
                name: info for name, info in available_nodes.items()
                if info.get("type", "") == self.node_type_filter
            }

        # If no nodes are available, return default target
        if not available_nodes:
            logger.warning(f"[OrchestratorAgent] No available nodes for matching. Using default: {self.default_target}")
            return self.default_target

        # Use LLM to select the best node
        selected_node = self._llm_match(input_text, available_nodes)

        logger.info(f"[OrchestratorAgent] Selected node: '{selected_node}'")
        return selected_node

    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        if not self.input_fields:
            return inputs.get("input", "")

        for field in self.input_fields:
            if field in inputs:
                return str(inputs[field])

        # Fallback: try common input fields
        for field in ["input", "query", "text", "message"]:
            if field in inputs:
                return str(inputs[field])

        return ""

    def _get_available_nodes(self, inputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get available nodes from inputs."""
        # Check for explicitly provided nodes
        if "available_nodes" in inputs:
            return inputs["available_nodes"]

        # Check for node registry in the state
        if "__node_registry" in inputs:
            return inputs["__node_registry"]

        # Assume valid destination nodes are provided as dictionary keys
        nodes = {}
        for key, value in inputs.items():
            if key.startswith("node_") and isinstance(value, dict):
                node_name = key[5:]  # Remove "node_" prefix
                nodes[node_name] = value

        return nodes

    def _llm_match(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """
        Use an LLM to match input to the best node.

        Args:
            input_text: User input text
            available_nodes: Dictionary of nodes with their intents

        Returns:
            Best matching node name
        """
        # Create a formatted description of available nodes
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
        llm_agent_class = get_agent_class(self.llm_type)
        if not llm_agent_class:
            logger.error(f"[OrchestratorAgent] LLM type '{self.llm_type}' not found in registry.")
            return next(iter(available_nodes.keys()))

        llm_agent = llm_agent_class(
            name=f"{self.name}_llm",
            prompt=llm_prompt,
            context={"temperature": 0.2}  # Low temperature for more consistent results
        )

        # Process the prompt
        llm_response = llm_agent.process({})

        # Extract the selected node from the response
        if isinstance(llm_response, str) and "Selected: " in llm_response:
            for line in llm_response.split("\n"):
                if line.strip().startswith("Selected: "):
                    selected = line.split("Selected: ", 1)[1].strip()
                    # Verify this is a valid node
                    if selected in available_nodes:
                        return selected

        # Fallback: look for an exact node name in the response
        llm_response_str = str(llm_response)
        for node_name in available_nodes.keys():
            if node_name in llm_response_str:
                return node_name

        # Last resort: if no node found, return the first available
        logger.warning(f"[OrchestratorAgent] Couldn't extract node from LLM response. Using first available.")
        return next(iter(available_nodes.keys()))