# agentmap/agents/builtins/orchestrator_agent.py
from typing import Any, Dict, Tuple

from agentmap.agents import get_agent_class
from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter
from agentmap.agents import HAS_LLM_AGENTS

logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.
    Uses existing LLM agents to perform intent matching.

    The OrchestratorAgent has built-in routing capabilities - it will automatically
    navigate to the selected node without requiring an explicit routing function.
    """

    def __init__(self, name: str, prompt: str, context: dict = None):
        """Initialize the orchestrator agent with configuration."""
        super().__init__(name, prompt, context)
        context = context or {}

        # Core configuration options
        self.llm_type = context.get("llm_type", "openai")
        self.temperature = float(context.get("temperature", 0.2))
        self.default_target = context.get("default_target", None)
        self.intent_prompt = context.get("intent_prompt", "file:orchestrator/intent_matching_v1.txt")

        # Matching strategy configuration
        self.matching_strategy = context.get("matching_strategy", "tiered")  # "tiered", "algorithm", or "llm"
        self.confidence_threshold = float(context.get("confidence_threshold", 0.8))  # When to skip LLM

        # Node filtering configuration
        # Parse node filter information from various formats
        if "nodes" in context:
            self.node_filter = context["nodes"]
        elif "node_type" in context:
            self.node_filter = f"nodeType:{context['node_type']}"
        elif "nodeType" in context:
            self.node_filter = f"nodeType:{context['nodeType']}"
        else:
            self.node_filter = "all"  # Default to all nodes

        if not HAS_LLM_AGENTS and self.matching_strategy == "llm" or self.matching_strategy == "tiered":
            logger.warning(f"OrchestratorAgent '{name}' requires LLM dependencies for optimal operation.")
            logger.warning("Will use simple keyword matching only. Install with: pip install agentmap[llm]")
            # Force algorithm matching if LLMs not available
            self.matching_strategy = "algorithm"

        logger.debug(f"[OrchestratorAgent] Initialized with: matching_strategy={self.matching_strategy}, "
                     f"node_filter={self.node_filter}, llm_type={self.llm_type}")

    def run(self, state: Any) -> Any:
        """
        Override the standard run method to provide built-in routing.

        Args:
            state: Current state object

        Returns:
            Updated state with output field and routing metadata
        """
        # First, run the normal agent process to select a node
        updated_state = super().run(state)

        # Get the selected node from the output
        selected_node = StateAdapter.get_value(updated_state, self.output_field)

        # Add a special routing directive to the state
        if selected_node:
            logger.info(f"[OrchestratorAgent] Setting __next_node to '{selected_node}'")
            updated_state = StateAdapter.set_value(
                updated_state,
                "__next_node",
                selected_node
            )

        return updated_state

    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and select the best matching node.

        Args:
            inputs: Dictionary containing input text and available nodes

        Returns:
            Name of the selected next node
        """
        # Get input text for intent matching
        input_text = self._get_input_text(inputs)
        logger.debug(f"[OrchestratorAgent] Input text: '{input_text}'")

        # Get available nodes from input field
        available_nodes = self._get_nodes(inputs)

        # Apply filtering based on context options
        filtered_nodes = self._apply_node_filter(available_nodes)

        logger.debug(f"[OrchestratorAgent] Available nodes after filtering: {list(filtered_nodes.keys())}")

        # If no nodes are available, return default target
        if not filtered_nodes:
            logger.warning(
                f"[OrchestratorAgent] No nodes available for matching after filtering. Using default: {self.default_target}")
            return self.default_target or ""

        # Handle case with a single node - no need for matching
        if len(filtered_nodes) == 1:
            node_name = next(iter(filtered_nodes.keys()))
            logger.debug(f"[OrchestratorAgent] Only one node available, selecting '{node_name}' without matching")
            return node_name

        # Select node based on matching strategy
        selected_node = self._match_intent(input_text, filtered_nodes)
        logger.info(f"[OrchestratorAgent] Selected node: '{selected_node}'")
        return selected_node

    def _get_nodes(self, inputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get node dictionary from the specified input field."""
        if self.input_fields and self.input_fields[0] in inputs:
            nodes = inputs[self.input_fields[0]]
            if isinstance(nodes, dict):
                return nodes
            logger.warning(f"[OrchestratorAgent] Input field '{self.input_fields[0]}' does not contain a dictionary")

        # Fallback to looking for standard names
        for field_name in ["available_nodes", "nodes", "__node_registry"]:
            if field_name in inputs and isinstance(inputs[field_name], dict):
                return inputs[field_name]

        # No nodes found
        logger.warning(f"[OrchestratorAgent] No node dictionary found in inputs")
        return {}

    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        # Check input fields except the first one (which should be nodes)
        input_fields = self.input_fields[1:] if len(self.input_fields) > 1 else []

        # Check specified input fields
        for field in input_fields:
            if field in inputs:
                return str(inputs[field])

        # Fallback: try common input fields
        for field in ["input", "query", "text", "message", "user_input"]:
            if field in inputs:
                return str(inputs[field])

        # Last resort: empty string
        logger.warning(f"[OrchestratorAgent] No input text found in inputs")
        return ""

    def _apply_node_filter(self, nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on context options."""
        # Handle specific node list option
        if self.node_filter.count("|") > 0:
            node_names = [n.strip() for n in self.node_filter.split("|")]
            filtered = {name: info for name, info in nodes.items() if name in node_names}
            logger.debug(f"[OrchestratorAgent] Filtered to specific nodes: {list(filtered.keys())}")
            return filtered

        # Handle nodeType option
        elif self.node_filter.startswith("nodeType:"):
            type_filter = self.node_filter.split(":", 1)[1].strip()
            filtered = {
                name: info for name, info in nodes.items()
                if info.get("type", "").lower() == type_filter.lower()
            }
            logger.debug(f"[OrchestratorAgent] Filtered to node type '{type_filter}': {list(filtered.keys())}")
            return filtered

        # Handle "all" option (default)
        logger.debug(f"[OrchestratorAgent] Using all available nodes: {list(nodes.keys())}")
        return nodes

    def _match_intent(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Match input to the best node using the configured strategy."""
        if self.matching_strategy == "algorithm":
            # Skip LLM entirely, use only algorithmic matching
            node, confidence = self._simple_match(input_text, available_nodes)
            logger.debug(
                f"[OrchestratorAgent] Using algorithm matching, selected '{node}' with confidence {confidence:.2f}")
            return node

        elif self.matching_strategy == "llm":
            # Skip algorithmic matching entirely, use only LLM
            return self._llm_match(input_text, available_nodes)

        else:  # "tiered" - default approach
            # Try algorithmic matching first
            node, confidence = self._simple_match(input_text, available_nodes)

            # If confidence is high enough, skip the LLM call
            if confidence >= self.confidence_threshold:
                logger.info(
                    f"[OrchestratorAgent] Algorithmic match confidence {confidence:.2f} exceeds threshold. Using '{node}'")
                return node

            # Otherwise, use LLM for better matching
            logger.info(
                f"[OrchestratorAgent] Algorithmic match confidence {confidence:.2f} below threshold. Using LLM.")
            return self._llm_match(input_text, available_nodes)

    def _llm_match(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Use an LLM to match input to the best node."""
        # Create a formatted description of available nodes
        node_descriptions = []
        for node_name, node_info in available_nodes.items():
            description = node_info.get("description", "")
            prompt = node_info.get("prompt", "")
            node_type = node_info.get("type", "")

            node_descriptions.append(
                f"- Node: {node_name}\n"
                f"  Description: {description}\n"
                f"  Prompt: {prompt}\n"
                f"  Type: {node_type}"
            )

        nodes_text = "\n".join(node_descriptions)
        template_values = {"nodes_text": nodes_text, "input_text": input_text}

        # Import our comprehensive function
        from agentmap.prompts import get_formatted_prompt
        
        # Default template as fallback
        default_template = (
            "You are an intent router that selects the most appropriate node to handle a user request.\n\n"
            "Available nodes:\n{nodes_text}\n\n"
            "User input: \"{input_text}\"\n\n"
            "Select the SINGLE BEST node to handle this request. "
            "Consider the semantics and intent of the user request. "
            "First explain your reasoning, then on a new line write just the selected node name prefixed with 'Selected: '."
        )
        
        # Get formatted prompt with all fallbacks handled internally
        llm_prompt = get_formatted_prompt(
            primary_prompt=self.prompt,
            template_file="file:orchestrator/intent_matching_v1.txt",
            default_template=default_template,
            values=template_values,
            context_name="OrchestratorAgent"
        )

        # Use appropriate LLM agent
        llm_agent_class = get_agent_class(self.llm_type)
        if not llm_agent_class:
            logger.error(f"[OrchestratorAgent] LLM type '{self.llm_type}' not found in registry.")
            return next(iter(available_nodes.keys()))

        # Create LLM agent with configured temperature
        llm_agent = llm_agent_class(
            name=f"{self.name}_llm",
            prompt=llm_prompt,
            context={"temperature": self.temperature}
        )

        # Process the prompt
        try:
            llm_response = llm_agent.process({})
        except Exception as e:
            logger.error(f"[OrchestratorAgent] Error from LLM: {e}")
            return next(iter(available_nodes.keys()))
        
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

    @staticmethod
    def _simple_match(input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> Tuple[str, float]:
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