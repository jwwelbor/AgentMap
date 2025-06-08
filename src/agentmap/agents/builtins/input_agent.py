"""
Input agent for prompting user input during execution.
"""
import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class InputAgent(BaseAgent):
    """Agent that prompts the user for input during execution."""
    
    def __init__(
        self, 
        name: str, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None
    ):
        """Initialize the input agent with new protocol-based pattern."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service
        )
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Prompt the user for input and return their response.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            The user's input as a string
        """
        # Log the execution
        self.log_info(f"[InputAgent] {self.name} prompting for user input")
        
        # Use the prompt from initialization or a default
        prompt_text = self.prompt or "Please provide input: "
        
        # Get input from the user
        user_input = input(prompt_text)
        
        return user_input
