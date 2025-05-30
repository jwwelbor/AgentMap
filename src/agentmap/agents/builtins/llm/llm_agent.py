"""
Base LLM Agent with unified configuration and memory management.
"""
import os
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

from agentmap.agents.base_agent import BaseAgent
from agentmap.exceptions import ConfigurationException

# from agentmap.config import get_llm_config
from agentmap.state.adapter import StateAdapter

# Import memory utilities
from agentmap.agents.builtins.llm.memory import (
    get_memory, add_user_message, add_assistant_message, add_system_message,
    truncate_memory
)


class LLMAgent(BaseAgent):
    """
    Unified LLM agent with intelligent routing and backward compatibility.
    
    This agent can work in two modes:
    1. Legacy mode: Direct provider specification (backward compatible)
    2. Routing mode: Intelligent provider/model selection based on task complexity
    
    The mode is determined by the 'routing_enabled' context parameter.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        # First, resolve prompt reference if applicable
        from agentmap.prompts import resolve_prompt
        resolved_prompt = resolve_prompt(prompt)
        
        # Then initialize with the resolved prompt
        super().__init__(name, resolved_prompt, context or {})
        
        # Determine operation mode
        self.routing_enabled = self.context.get("routing_enabled", False)
        
        if self.routing_enabled:
            # Routing mode: Provider will be determined dynamically
            self.provider_name = "auto"  # Placeholder for routing
            self.model = None  # Will be determined by routing
            self.temperature = self.context.get("temperature", 0.7)
            self.api_key = None  # Not needed in routing mode
        else:
            # Legacy mode: Use specified provider or default to anthropic
            self.provider_name = self.context.get("provider", "anthropic") 
            
            # Try to use DI container if available
            try:
                from agentmap.di import application
                config = application.configuration()
                config = config.get_section("llm", {}).get(self.provider_name, {})
            except (ImportError, AttributeError):
                raise ConfigurationException( f"Could not get configuration from DI container for provider {self.provider_name}")
                # # Fall back to direct config loading
                # from agentmap.config import get_llm_config
                # config = get_llm_config(self.provider_name)
            
            # Use configuration for legacy mode
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
    
    def _get_provider_name(self) -> str:
        """
        Get the provider name for configuration loading.
        
        Returns:
            Provider name string (e.g., "openai", "anthropic", "google")
        """
        if self.routing_enabled:
            return "auto"  # Will be determined by routing
        return self.context.get("provider", "anthropic")
        
    def _get_api_key_env_var(self, provider: Optional[str] = None) -> str:
        """
        Get the environment variable name for the API key.
        
        Args:
            provider: Optional provider name (uses self.provider_name if not provided)
            
        Returns:
            Environment variable name (e.g., "ANTHROPIC_API_KEY")
        """
        if not provider:
            provider = self.provider_name
            
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY", 
            "google": "GOOGLE_API_KEY"
        }
        return env_vars.get(provider, f"{provider.upper()}_API_KEY")
        
    def _get_default_model_name(self, provider: Optional[str] = None) -> str:
        """
        Get default model name for this provider.
        
        Args:
            provider: Optional provider name (uses self.provider_name if not provided)
            
        Returns:
            Default model name
        """
        if not provider:
            provider = self.provider_name
            
        defaults = {
            "anthropic": "claude-3-sonnet-20240229",
            "openai": "gpt-3.5-turbo",
            "google": "gemini-1.0-pro"
        }
        return defaults.get(provider, "claude-3-sonnet-20240229")

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
    
    def is_routing_enabled(self) -> bool:
        """
        Check if routing is enabled for this agent.
        
        Returns:
            True if routing is enabled
        """
        return self.routing_enabled
    
    def get_effective_provider(self) -> str:
        """
        Get the effective provider name (for logging/debugging).
        
        Returns:
            Provider name or "routing" if routing is enabled
        """
        return "routing" if self.routing_enabled else self.provider_name

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
        provider = self.provider_name
        return config.get("api_key") or os.environ.get(self._get_api_key_env_var(provider), "")
    
    def _prepare_routing_context(self, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Prepare routing context based on agent configuration and inputs.
        
        Args:
            inputs: Input values for this node
            
        Returns:
            Routing context dictionary or None for legacy mode
        """
        if not self.routing_enabled:
            # Legacy mode: return None to use direct calling
            return None
        
        # Extract prompt content for complexity analysis
        input_parts = []
        for field in self.input_fields:
            if field != self.memory_key and inputs.get(field):
                input_parts.append(str(inputs.get(field)))
        
        user_input = " ".join(input_parts) if input_parts else ""
        
        # Build routing context
        routing_context = {
            "routing_enabled": True,
            "task_type": self.context.get("task_type", "general"),
            "complexity_override": self.context.get("complexity_override"),
            "auto_detect_complexity": self.context.get("auto_detect_complexity", True),
            "provider_preference": self.context.get("provider_preference", []),
            "excluded_providers": self.context.get("excluded_providers", []),
            "model_override": self.context.get("model_override"),
            "max_cost_tier": self.context.get("max_cost_tier"),
            "cost_optimization": self.context.get("cost_optimization", True),
            "prefer_speed": self.context.get("prefer_speed", False),
            "prefer_quality": self.context.get("prefer_quality", False),
            "fallback_provider": self.context.get("fallback_provider", "anthropic"),
            "fallback_model": self.context.get("fallback_model"),
            "retry_with_lower_complexity": self.context.get("retry_with_lower_complexity", True),
            "input_context": {
                "user_input": user_input,
                "input_field_count": len([f for f in self.input_fields if f != self.memory_key]),
                "memory_size": len(inputs.get(self.memory_key, [])),
                **self.context.get("input_context", {})
            }
        }
        
        return routing_context

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
        Process inputs with LLM, supporting both routing and legacy modes.
        
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
            
            # Prepare routing context
            routing_context = self._prepare_routing_context(inputs)
            
            # Call LLM via service
            llm_service = self._get_llm_service()
            
            if routing_context:
                # Routing mode: Let the routing service decide provider/model
                self.log_debug(f"Using routing mode for task_type: {routing_context.get('task_type')}")
                result = llm_service.call_llm(
                    provider="auto",  # Will be determined by routing
                    messages=messages,
                    routing_context=routing_context
                )
            else:
                # Legacy mode: Use specified provider and model
                self.log_debug(f"Using legacy mode with provider: {self.provider_name}")
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
            provider_name = self.provider_name if not self.routing_enabled else "routing"
            self.log_error(f"Error in {provider_name} processing: {e}")
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