# agentmap/agents/builtins/orchestrator_agent.py
from typing import Any, Dict, Tuple

from agentmap.agents import get_agent_class
from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter
from agentmap.agents.features import is_llm_enabled

logger = get_logger(__name__, False)


class OrchestratorAgent(BaseAgent):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.
    Uses LLM Service to perform intent matching.

    The OrchestratorAgent has built-in routing capabilities - it will automatically
    navigate to the selected node without requiring an explicit routing function.
    """

    def __init__(self, name: str, prompt: str, context: dict = None):
        """Initialize the orchestrator agent with configuration."""
        super().__init__(name, prompt, context)
        context = context or {}
        
        # NEW: Initialize node_registry - will be set by GraphAssembler during pre-compilation injection
        self.node_registry = None  
        
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

        if not is_llm_enabled() and (self.matching_strategy == "llm" or self.matching_strategy == "tiered"):
            self.log_warning(f"OrchestratorAgent '{name}' requires LLM dependencies for optimal operation.")
            self.log_warning("Will use simple keyword matching only. Install with: pip install agentmap[llm]")
            # Force algorithm matching if LLMs not available
            self.matching_strategy = "algorithm"

        self.log_debug(f"Initialized with: matching_strategy={self.matching_strategy}, "
                     f"node_filter={self.node_filter}, llm_type={self.llm_type}")
                     
        # LLM Service (will be injected or created)
        self.llm_service = None

    def _get_llm_service(self):
        """Get LLM service via DI or direct creation."""
        if self.llm_service is None:
            try:
                from agentmap.di import application
                self.llm_service = application.llm_service()
            except Exception:
                # Fallback for non-DI usage
                from agentmap.services.llm_service import LLMService
                self.llm_service = LLMService()
        return self.llm_service

        # def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
    #     """
    #     Override the post-processing hook to add routing directives.
        
    #     Args:
    #         state: Current state
    #         output: The output value from the process method (selected node name)
            
    #     Returns:
    #         Tuple of (state, output) with routing directives
    #     """
    #     # If we have a valid node name, set the routing directive
    #     if output:
    #         self.log_info(f"Setting __next_node to '{output}'")
    #         state = StateAdapter.set_value(state, "__next_node", output)
            
    #     return state, output
    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Post-process the output to ensure consistent format.
        Extracts selectedNode from JSON responses and returns just the node name.
        Also adds routing directives to the state.
        
        Args:
            state: Current state
            output: The output value, which could be a dict, string, or other format
            
        Returns:
            Tuple of (state, output) with output normalized to node name
        """
        # If output is a dict with selectedNode, extract it
        if isinstance(output, dict) and "selectedNode" in output:
            selected_node = output["selectedNode"]
            self.log_info(f"[OrchestratorAgent] Extracted selected node '{selected_node}' from result dict")
            # Update output to be just the node name
            output = selected_node
        
        # Add routing directive if we have a valid node name
        if output and isinstance(output, str):
            self.log_info(f"[OrchestratorAgent] Setting __next_node to '{output}'")
            state = StateAdapter.set_value(state, "__next_node", output)
        
        return state, output


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
        self.log_debug(f"Input text: '{input_text}'")

        # NEW: Use the injected node registry as the primary source
        available_nodes = self.node_registry
        
        # Log registry status for debugging
        if available_nodes:
            self.log_debug(f"Using injected registry with {len(available_nodes)} nodes: {list(available_nodes.keys())}")
        else:
            self.log_warning("No node registry available - orchestrator may not work correctly")
            # Fallback: try to get nodes from inputs (legacy behavior)
            available_nodes = self._get_nodes_from_inputs(inputs)
            if available_nodes:
                self.log_warning(f"Using fallback registry from inputs with {len(available_nodes)} nodes")
            else:
                self.log_error("No available nodes found - cannot perform orchestration")
                return self.default_target or ""

        # Apply filtering based on context options
        filtered_nodes = self._apply_node_filter(available_nodes)

        self.log_debug(f"Available nodes after filtering: {list(filtered_nodes.keys())}")

        # If no nodes are available, return default target
        if not filtered_nodes:
            self.log_warning(
                f"No nodes available for matching after filtering. Using default: {self.default_target}")
            return self.default_target or ""

        # Handle case with a single node - no need for matching
        if len(filtered_nodes) == 1:
            node_name = next(iter(filtered_nodes.keys()))
            self.log_debug(f"Only one node available, selecting '{node_name}' without matching")
            return node_name

        # Select node based on matching strategy
        selected_node = self._match_intent(input_text, filtered_nodes)
        self.log_info(f"Selected node: '{selected_node}'")
        return selected_node

    def _get_nodes_from_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        LEGACY: Get node dictionary from inputs (fallback when registry injection fails).
        
        Args:
            inputs: Input dictionary
            
        Returns:
            Node registry dictionary or empty dict
        """
        if self.input_fields and self.input_fields[0] in inputs:
            nodes = inputs[self.input_fields[0]]
            if isinstance(nodes, dict):
                return nodes
            self.log_warning(f"Input field '{self.input_fields[0]}' does not contain a dictionary")

        # Fallback to looking for standard names
        for field_name in ["available_nodes", "nodes", "__node_registry"]:
            if field_name in inputs and isinstance(inputs[field_name], dict):
                return inputs[field_name]

        # No nodes found
        self.log_warning("No node dictionary found in inputs")
        return {}

    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        # Check specified input fields (skip the first one if it's used for nodes)
        input_fields_to_check = self.input_fields
        
        # If we have input fields and the first one might be for nodes, skip it
        if input_fields_to_check and len(input_fields_to_check) > 1:
            input_fields_to_check = input_fields_to_check[1:]
        
        # Check specified input fields
        for field in input_fields_to_check:
            if field in inputs:
                return str(inputs[field])

        # Fallback: try common input fields
        for field in ["input", "query", "text", "message", "user_input"]:
            if field in inputs:
                return str(inputs[field])

        # Last resort: use the first available input that's not the node registry
        for field, value in inputs.items():
            if field not in ["available_nodes", "nodes", "__node_registry"] and isinstance(value, str):
                self.log_debug(f"Using fallback input field '{field}' for input text")
                return str(value)

        # Last resort: empty string
        self.log_warning("No input text found in inputs")
        return ""

    def _apply_node_filter(self, nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on context options."""
        if not nodes:
            return {}
            
        # Handle specific node list option
        if self.node_filter.count("|") > 0:
            node_names = [n.strip() for n in self.node_filter.split("|")]
            filtered = {name: info for name, info in nodes.items() if name in node_names}
            self.log_debug(f"Filtered to specific nodes: {list(filtered.keys())}")
            return filtered

        # Handle nodeType option
        elif self.node_filter.startswith("nodeType:"):
            type_filter = self.node_filter.split(":", 1)[1].strip()
            filtered = {
                name: info for name, info in nodes.items()
                if info.get("type", "").lower() == type_filter.lower()
            }
            self.log_debug(f"Filtered to node type '{type_filter}': {list(filtered.keys())}")
            return filtered

        # Handle "all" option (default)
        self.log_debug(f"Using all available nodes: {list(nodes.keys())}")
        return nodes

    def _match_intent(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Match input to the best node using the configured strategy."""
        if self.matching_strategy == "algorithm":
            # Skip LLM entirely, use only algorithmic matching
            node, confidence = self._simple_match(input_text, available_nodes)
            self.log_debug(
                f"Using algorithm matching, selected '{node}' with confidence {confidence:.2f}")
            return node

        elif self.matching_strategy == "llm":
            # Skip algorithmic matching entirely, use only LLM
            return self._llm_match(input_text, available_nodes)

        else:  # "tiered" - default approach
            # Try algorithmic matching first
            node, confidence = self._simple_match(input_text, available_nodes)

            # If confidence is high enough, skip the LLM call
            if confidence >= self.confidence_threshold:
                self.log_info(
                    f"Algorithmic match confidence {confidence:.2f} exceeds threshold. Using '{node}'")
                return node

            # Otherwise, use LLM for better matching
            self.log_info(
                f"Algorithmic match confidence {confidence:.2f} below threshold. Using LLM.")
            return self._llm_match(input_text, available_nodes)

    def _llm_match(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Use LLM Service to match input to the best node."""
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
            "You are an intent router that selects the most appropriate node to handle a user request."
            "Available nodes:\n\n"
            "{nodes_text}\n\n"
            "User input: '{input_text}'\n\n"

            "Consider the semantics and intent of the user request then \n"
            "select the SINGLE BEST node to handle this request from the list of available nodes. \n\n"
            "Output a JSON object with a 'selectedNode' field containing your selection, your confidence level, and the reasoning in the format below:\n\n"

            "Output format:"
            "{\n"
            "\"selectedNode\": \"node_name\",\n"
            "\"confidence\": 0, / a number between 0 and 1 indicating confidence level\n"
            "\"reasoning\": \"your reasoning goes here\" / put your reasoning here\n"
            "}"
        )
        
        # Get formatted prompt with all fallbacks handled internally
        llm_prompt = get_formatted_prompt(
            primary_prompt=self.prompt,
            template_file="file:orchestrator/intent_matching_v1.txt",
            default_template=default_template,
            values=template_values,
            logger=self._logger,
            context_name="OrchestratorAgent",
        )

        try:
            # Build messages for LLM call
            messages = [{"role": "user", "content": llm_prompt}]
            
            # Use LLM Service
            llm_service = self._get_llm_service()
            llm_response = llm_service.call_llm(
                provider=self.llm_type,
                messages=messages,
                temperature=self.temperature
            )
            
        except Exception as e:
            self.log_error(f"Error from LLM: {e}")
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
        self.log_warning("Couldn't extract node from LLM response. Using first available.")
        return next(iter(available_nodes.keys()))

    @staticmethod
    def _simple_match(input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        """Fast algorithmic matching for obvious cases.
        
        Returns:
            Tuple of (matching_result_dict, confidence_score)
        """
        input_lower = input_text.lower()
        result = {}

        # 1. Check for exact node name in input
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                result = {
                    "selectedNode": node_name,
                    "confidence": 1.0,
                    "reasoning": f"Exact match found for node name '{node_name}' in input."
                }
                return result, 1.0  # Perfect confidence for exact match

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

        if best_match:
            result = {
                "selectedNode": best_match,
                "confidence": best_score,
                "reasoning": f"Keyword matching with confidence {best_score:.2f}"
            }
        else:
            default_node = next(iter(available_nodes))
            result = {
                "selectedNode": default_node,
                "confidence": 0.0,
                "reasoning": "No match found. Using default node."
            }
            best_score = 0.0

        return result, best_score