"""
Standardized OrchestratorAgent with consistent prompt resolution.
"""
from typing import Any, Dict, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.mixins import PromptResolutionMixin
from agentmap.state.adapter import StateAdapter
from agentmap.agents.features import is_llm_enabled


class OrchestratorAgent(BaseAgent, PromptResolutionMixin):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.
    Uses LLM Service to perform intent matching with standardized prompt resolution.
    """

    def __init__(self, name: str, prompt: str, context: dict = None):
        """Initialize the orchestrator agent with configuration."""
        super().__init__(name, prompt, context)
        context = context or {}
        
        # LLM Service - implements LLMServiceUser protocol
        self.llm_service = None
        # Node Registry - implements NodeRegistryUser protocol  
        self.node_registry = None

        # Core configuration options
        self.llm_type = context.get("llm_type", "openai")
        self.temperature = float(context.get("temperature", 0.2))
        self.default_target = context.get("default_target", None)

        # Matching strategy configuration
        self.matching_strategy = context.get("matching_strategy", "tiered")
        self.confidence_threshold = float(context.get("confidence_threshold", 0.8))

        # Node filtering configuration
        self.node_filter = self._parse_node_filter(context)

        # Validate LLM availability
        if not is_llm_enabled() and (self.matching_strategy in ["llm", "tiered"]):
            self.log_warning(f"OrchestratorAgent '{name}' requires LLM dependencies for optimal operation.")
            self.log_warning("Will use simple keyword matching only. Install with: pip install agentmap[llm]")
            self.matching_strategy = "algorithm"

        self.log_debug(f"Initialized with: matching_strategy={self.matching_strategy}, "
                     f"node_filter={self.node_filter}, llm_type={self.llm_type}")

    def _parse_node_filter(self, context: dict) -> str:
        """Parse node filter from various context formats."""
        if "nodes" in context:
            return context["nodes"]
        elif "node_type" in context:
            return f"nodeType:{context['node_type']}"
        elif "nodeType" in context:
            return f"nodeType:{context['nodeType']}"
        else:
            return "all"

    # PromptResolutionMixin implementation
    def _get_default_template_file(self) -> str:
        """Get default template file for orchestrator prompts."""
        return "file:orchestrator/intent_matching_v1.txt"
    
    def _get_default_template_text(self) -> str:
        """Get default template text for orchestrator prompts."""
        return (
            "You are an intent router that selects the most appropriate node to handle a user request.\n"
            "Available nodes:\n{nodes_text}\n\n"
            "User input: '{input_text}'\n\n"
            "Consider the semantics and intent of the user request then select the SINGLE BEST node.\n"
            "Output a JSON object with a 'selectedNode' field containing your selection, confidence level, and reasoning:\n\n"
            "Output format:\n"
            "{{\n"
            '  "selectedNode": "node_name",\n'
            '  "confidence": 0.8,\n'
            '  "reasoning": "your reasoning"\n'
            "}}"
        )
    
    def _extract_template_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract template variables specific to orchestrator needs."""
        # Get input text for intent matching
        input_text = self._get_input_text(inputs)
        
        # Get available nodes (from registry or inputs)
        available_nodes = self.node_registry or self._get_nodes_from_inputs(inputs)
        
        # Format node descriptions for template
        nodes_text = self._format_node_descriptions(available_nodes)
        
        return {
            "input_text": input_text,
            "nodes_text": nodes_text
        }

    def _format_node_descriptions(self, nodes: Dict[str, Dict[str, Any]]) -> str:
        """Format node descriptions for template substitution."""
        if not nodes:
            return "No nodes available"
            
        descriptions = []
        for node_name, node_info in nodes.items():
            description = node_info.get("description", "")
            prompt = node_info.get("prompt", "")
            node_type = node_info.get("type", "")
            
            descriptions.append(
                f"- Node: {node_name}\n"
                f"  Description: {description}\n"
                f"  Prompt: {prompt}\n"
                f"  Type: {node_type}"
            )
        
        return "\n".join(descriptions)

    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """Post-process output to extract node name and set routing directive."""
        # Extract selectedNode from JSON responses if needed
        if isinstance(output, dict) and "selectedNode" in output:
            selected_node = output["selectedNode"]
            self.log_info(f"[OrchestratorAgent] Extracted selected node '{selected_node}' from result dict")
            output = selected_node
        
        # Set routing directive if we have a valid node name
        if output and isinstance(output, str):
            self.log_info(f"[OrchestratorAgent] Setting __next_node to '{output}'")
            state = StateAdapter.set_value(state, "__next_node", output)
        
        return state, output

    def process(self, inputs: Dict[str, Any]) -> str:
        """Process inputs and select the best matching node."""
        # Get input text for intent matching
        input_text = self._get_input_text(inputs)
        self.log_debug(f"Input text: '{input_text}'")

        # Use injected node registry as primary source
        available_nodes = self.node_registry
        
        if not available_nodes:
            self.log_warning("No node registry available - orchestrator may not work correctly")
            available_nodes = self._get_nodes_from_inputs(inputs)
            if not available_nodes:
                self.log_error("No available nodes found - cannot perform orchestration")
                return self.default_target or ""

        # Apply filtering based on context options
        filtered_nodes = self._apply_node_filter(available_nodes)
        self.log_debug(f"Available nodes after filtering: {list(filtered_nodes.keys())}")

        if not filtered_nodes:
            self.log_warning(f"No nodes available after filtering. Using default: {self.default_target}")
            return self.default_target or ""

        # Handle single node case
        if len(filtered_nodes) == 1:
            node_name = next(iter(filtered_nodes.keys()))
            self.log_debug(f"Only one node available, selecting '{node_name}' without matching")
            return node_name

        # Select node based on matching strategy
        selected_node = self._match_intent(input_text, filtered_nodes, inputs)
        self.log_info(f"Selected node: '{selected_node}'")
        return selected_node

    def _match_intent(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]], inputs: Dict[str, Any]) -> str:
        """Match input to the best node using the configured strategy."""
        if self.matching_strategy == "algorithm":
            node, confidence = self._simple_match(input_text, available_nodes)
            self.log_debug(f"Using algorithm matching, selected '{node}' with confidence {confidence:.2f}")
            return node
        elif self.matching_strategy == "llm":
            return self._llm_match(inputs, available_nodes)
        else:  # "tiered" - default approach
            node, confidence = self._simple_match(input_text, available_nodes)
            if confidence >= self.confidence_threshold:
                self.log_info(f"Algorithmic match confidence {confidence:.2f} exceeds threshold. Using '{node}'")
                return node
            self.log_info(f"Algorithmic match confidence {confidence:.2f} below threshold. Using LLM.")
            return self._llm_match(inputs, available_nodes)

    def _llm_match(self, inputs: Dict[str, Any], available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Use LLM Service to match input to the best node with standardized prompt resolution."""
        try:
            # Get formatted prompt using standardized method
            llm_prompt = self._get_formatted_prompt(inputs)
            
            # Build messages for LLM call
            messages = [{"role": "user", "content": llm_prompt}]
            
            # Use LLM Service
            llm_response = self.llm_service.call_llm(
                provider=self.llm_type,
                messages=messages,
                temperature=self.temperature
            )
            
            # Extract selected node from response
            return self._extract_node_from_response(llm_response, available_nodes)
            
        except Exception as e:
            self.log_error(f"Error from LLM: {e}")
            return next(iter(available_nodes.keys()))

    def _extract_node_from_response(self, llm_response: str, available_nodes: Dict[str, Dict[str, Any]]) -> str:
        """Extract the selected node from LLM response."""
        # Try to parse JSON response first
        try:
            import json
            if isinstance(llm_response, str) and llm_response.strip().startswith('{'):
                parsed = json.loads(llm_response.strip())
                if "selectedNode" in parsed:
                    selected = parsed["selectedNode"]
                    if selected in available_nodes:
                        return selected
        except json.JSONDecodeError:
            pass
        
        # Fallback: look for exact node name in response
        llm_response_str = str(llm_response)
        for node_name in available_nodes.keys():
            if node_name in llm_response_str:
                return node_name
        
        # Last resort: return first available
        self.log_warning("Couldn't extract node from LLM response. Using first available.")
        return next(iter(available_nodes.keys()))

    # Keep existing helper methods unchanged
    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        input_fields_to_check = self.input_fields[1:] if len(self.input_fields) > 1 else self.input_fields
        
        for field in input_fields_to_check:
            if field in inputs:
                return str(inputs[field])
        
        for field in ["input", "query", "text", "message", "user_input"]:
            if field in inputs:
                return str(inputs[field])
        
        for field, value in inputs.items():
            if field not in ["available_nodes", "nodes", "__node_registry"] and isinstance(value, str):
                self.log_debug(f"Using fallback input field '{field}' for input text")
                return str(value)
        
        self.log_warning("No input text found in inputs")
        return ""

    def _get_nodes_from_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Fallback: Get node dictionary from inputs when registry injection fails."""
        if self.input_fields and self.input_fields[0] in inputs:
            nodes = inputs[self.input_fields[0]]
            if isinstance(nodes, dict):
                return nodes
        
        for field_name in ["available_nodes", "nodes", "__node_registry"]:
            if field_name in inputs and isinstance(inputs[field_name], dict):
                return inputs[field_name]
        
        return {}

    def _apply_node_filter(self, nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on context options."""
        if not nodes:
            return {}
            
        if self.node_filter.count("|") > 0:
            node_names = [n.strip() for n in self.node_filter.split("|")]
            return {name: info for name, info in nodes.items() if name in node_names}
        elif self.node_filter.startswith("nodeType:"):
            type_filter = self.node_filter.split(":", 1)[1].strip()
            return {name: info for name, info in nodes.items() 
                   if info.get("type", "").lower() == type_filter.lower()}
        
        return nodes

    @staticmethod
    def _simple_match(input_text: str, available_nodes: Dict[str, Dict[str, Any]]) -> Tuple[str, float]:
        """Fast algorithmic matching for obvious cases."""
        input_lower = input_text.lower()
        
        # Check for exact node name match
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                return node_name, 1.0
        
        # Keyword matching
        best_match = None
        best_score = 0.0
        
        for node_name, node_info in available_nodes.items():
            intent = node_info.get("intent", "") or node_info.get("prompt", "")
            keywords = intent.lower().split()
            
            if keywords:
                matches = sum(1 for kw in keywords if kw in input_lower)
                score = matches / len(keywords)
                if score > best_score:
                    best_score = score
                    best_match = node_name
        
        return best_match or next(iter(available_nodes)), best_score