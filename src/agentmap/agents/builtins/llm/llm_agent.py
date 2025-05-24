"""
Base LLM Agent with unified configuration and memory management.
"""
import os
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

from agentmap.agents.base_agent import BaseAgent
from agentmap.config import get_llm_config
from agentmap.state.adapter import StateAdapter

# Import memory utilities
from agentmap.agents.builtins.llm.memory import (
    get_memory, add_user_message, add_assistant_message, add_system_message,
    truncate_memory
)


class LLMAgent(BaseAgent):
    """
    Base class for LLM agents with consistent configuration and memory management.
    
    This class provides a unified interface for working with different LLM providers
    (OpenAI, Anthropic, Google, etc.) with consistent configuration loading,
    memory management, and state handling. Subclasses need only implement
    provider-specific methods.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        # First, resolve prompt reference if applicable
        from agentmap.prompts import resolve_prompt
        resolved_prompt = resolve_prompt(prompt)
        
        # Then initialize with the resolved prompt
        super().__init__(name, resolved_prompt, context or {})
        
        # Provider-specific configuration (to be set by subclasses)
        self.provider_name = self._get_provider_name()
        self.api_key_env_var = self._get_api_key_env_var()
        
        # Try to use DI container if available
        try:
            from agentmap.di import application
            config = application.configuration()
            config = config.get_section("llm", {}).get(self.provider_name, {})
        except (ImportError, AttributeError):
            # Fall back to direct config loading
            from agentmap.config import get_llm_config
            config = get_llm_config(self.provider_name)
        
        # Use configuration
        self.model = self._get_model_name(config)
        self.temperature = self._get_temperature(config)
        self.api_key = self._get_api_key(config)
        
        # Memory configuration
        self.memory_key = self.context.get("memory_key", "memory")
        self.max_memory_messages = self.context.get("max_memory_messages", None)
        
        # Add memory_key to input_fields if not already present
        if self.memory_key and self.memory_key not in self.input_fields:
            self.input_fields.append(self.memory_key)
            
        # LLM Service (will be injected or created)
        self.llm_service = None
    
    # Required provider-specific methods (to be implemented by subclasses)
    def _get_provider_name(self) -> str:
        """
        Get the provider name for configuration loading.
        
        Returns:
            Provider name string (e.g., "openai", "anthropic", "google")
        """
        raise NotImplementedError("Subclasses must implement _get_provider_name()")
        
    def _get_api_key_env_var(self) -> str:
        """
        Get the environment variable name for the API key.
        
        Returns:
            Environment variable name (e.g., "OPENAI_API_KEY")
        """
        raise NotImplementedError("Subclasses must implement _get_api_key_env_var()")
        
    def _get_default_model_name(self) -> str:
        """
        Get default model name for this provider.
        
        Returns:
            Default model name
        """
        raise NotImplementedError("Subclasses must implement _get_default_model_name()")

    def _get_llm_service(self):
        """Get LLM service via DI or direct creation."""
        if self.llm_service is None:
            try:
                # Try to get LLM service from DI container
                from agentmap.di import application
                self.llm_service = application.llm_service()
            except (ImportError, AttributeError) as e:
                self.log_warning(f"Could not get LLMService from DI container: {e}")
                # try:
                #     # Fall back to creating a new instance
                #     from agentmap.services.llm_service import LLMService
                #     from agentmap.config.configuration import Configuration
                #     from agentmap.logging.service import LoggingService
                    
                #     # Try to load configuration
                #     try:
                #         from agentmap.config import get_config
                #         config = get_config()
                #     except Exception:
                #         config = Configuration({})
                    
                #     # Create logging service
                #     logging_service = LoggingService(config.get_section("logging", {}))
                    
                #     # Create LLM service
                #     self.llm_service = LLMService(config, logging_service)
                # except Exception as e2:
                #     self.log_error(f"Failed to create LLMService: {e2}")
                #     # Last resort minimal implementation
                #     from agentmap.services.llm_service import LLMService
                #     self.llm_service = LLMService()
                    
        return self.llm_service

    # Common configuration methods with sensible defaults
    def _get_model_name(self, config: Dict[str, Any]) -> str:
        """
        Get model name with fallbacks.
        
        Args:
            config: Provider configuration from config system
            
        Returns:
            Model name to use
        """
        return (
            self.context.get("model") or 
            config.get("model") or 
            self._get_default_model_name()
        )
        
    def _get_temperature(self, config: Dict[str, Any]) -> float:
        """
        Get temperature with fallbacks.
        
        Args:
            config: Provider configuration from config system
            
        Returns:
            Temperature value as float
        """
        temp = (
            self.context.get("temperature") or 
            config.get("temperature") or 
            0.7
        )
        return float(temp)
        
    def _get_api_key(self, config: Dict[str, Any]) -> str:
        """
        Get API key with fallbacks.
        
        Args:
            config: Provider configuration from config system
            
        Returns:
            API key string
        """
        return config.get("api_key") or os.environ.get(self.api_key_env_var, "")

    def _pre_process(self, state: Any, inputs: Dict[str, Any]) -> Any:
        """
        Pre-process hook to initialize and prepare memory.
        
        Args:
            state: Current state
            inputs: Input values for this node
            
        Returns:
            Updated state
        """
        # Initialize memory if needed
        if self.memory_key not in inputs:
            inputs[self.memory_key] = []
            
            # Add system message from prompt if available
            if self.prompt:
                add_system_message(inputs, self.prompt, self.memory_key)
        
        return state

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs with LLM, including memory management.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Response from LLM including updated memory
        """
        try:
            # Get the primary input field (typically "input")
            input_parts = []
            for field in self.input_fields:
                if field != self.memory_key and inputs.get(field):
                    input_parts.append(f"{field}: {inputs.get(field)}")

            user_input = "\n".join(input_parts) if input_parts else ""

            if not user_input:
                self.log_warning("No input found in inputs")
            
            # Get memory from inputs
            messages = get_memory(inputs, self.memory_key)
            
            # Add user message to memory
            add_user_message(inputs, user_input, self.memory_key)
            
            # Get updated messages
            messages = get_memory(inputs, self.memory_key)
            
            # Call LLM via service
            llm_service = self._get_llm_service()
            result = llm_service.call_llm(
                provider=self.provider_name,
                messages=messages,
                model=self.model,
                temperature=self.temperature
            )
            
            # Add assistant response to memory
            add_assistant_message(inputs, result, self.memory_key)
            
            # Apply message limit if configured
            if self.max_memory_messages:
                truncate_memory(inputs, self.max_memory_messages, self.memory_key)
            
            # Return result with memory included
            return {
                "output": result,
                self.memory_key: inputs.get(self.memory_key, [])
            }
            
        except Exception as e:
            self.log_error(f"Error in {self.provider_name} processing: {e}")
            return {
                "error": str(e),
                "last_action_success": False
            }

    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Post-processing hook to ensure memory is in the state.
        
        Args:
            state: Current state
            output: Output from process method
            
        Returns:
            Tuple of (updated_state, updated_output)
        """
        # Handle case where output is a dictionary with memory
        if isinstance(output, dict) and self.memory_key in output:
            memory = output.pop(self.memory_key, None)
            
            # Update memory in state
            if memory is not None:
                state = StateAdapter.set_value(state, self.memory_key, memory)
            
            # Extract output value if available
            if self.output_field and self.output_field in output:
                output = output[self.output_field]
            elif "output" in output:
                output = output["output"]
        
        return state, output