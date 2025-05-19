"""
Base LLM Agent with unified configuration and handling for all providers.
"""
import os
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.config import get_llm_config

from agentmap.state.adapter import StateAdapter

class LLMAgent(BaseAgent):
    """
    Base class for LLM agents with consistent configuration and error handling.
    
    This class provides a unified interface for working with different LLM providers
    (OpenAI, Anthropic, Google, etc.) with consistent configuration loading,
    error handling, and state management. Subclasses need only implement
    provider-specific methods.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM agent with provider-specific configuration.
        
        Args:
            name: Name of the agent
            prompt: Prompt text or template
            context: Optional context configuration including:
                - model: Override model name
                - temperature: Override temperature value
                - memory: Memory configuration
                - memory_key: Key to store memory in state
        """
        # First, resolve prompt reference if applicable
        from agentmap.prompts import resolve_prompt
        resolved_prompt = resolve_prompt(prompt)
        
        # Then initialize with the resolved prompt
        super().__init__(name, resolved_prompt, context or {})
        
        # Provider-specific configuration (to be set by subclasses)
        self.provider_name = self._get_provider_name()
        self.api_key_env_var = self._get_api_key_env_var()
        
        # Load configuration with consistent fallbacks
        config = get_llm_config(self.provider_name)
        self.model = self._get_model_name(config)
        self.temperature = self._get_temperature(config)
        self.api_key = self._get_api_key(config)
        
        # Memory management
        self.memory = None
        self.memory_key = self.context.get("memory_key", "conversation_memory")
        
        # Initialize memory if configuration exists
        if "memory" in self.context:
            self.memory = self._create_memory(self.context["memory"])
    
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
        
    def _call_api(self, formatted_prompt: str) -> str:
        """
        Call the provider-specific API and return the result text.
        
        Args:
            formatted_prompt: Formatted prompt text
            
        Returns:
            Response text from the LLM
            
        Raises:
            ValueError: If API key is missing
            ImportError: If provider package is not installed
            RuntimeError: If API call fails
        """
        raise NotImplementedError("Subclasses must implement _call_api()")
        
    def _create_langchain_client(self) -> Any:
        """
        Create a LangChain client for this provider if LangChain is available.
        
        Returns:
            LangChain client or None if unavailable
        """
        raise NotImplementedError("Subclasses must implement _create_langchain_client()")

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

    def _create_memory(self, memory_config: Dict[str, Any]) -> Optional[Any]:
        """
        Create a LangChain memory object based on configuration.
        
        Args:
            memory_config: Memory configuration
            
        Returns:
            Memory object or None if error
        """
        if not memory_config:
            return None
            
        try:
            # Try the newer imports first
            try:
                from langchain_community.memory import (
                    ConversationBufferMemory,
                    ConversationBufferWindowMemory,
                    ConversationSummaryMemory,
                    ConversationTokenBufferMemory
                )
            except ImportError:
                # Fallback to legacy imports
                from langchain.memory import (
                    ConversationBufferMemory,
                    ConversationBufferWindowMemory,
                    ConversationSummaryMemory,
                    ConversationTokenBufferMemory
                )
                self.log_warning("Using deprecated LangChain memory imports. Consider upgrading to langchain-community.")
            
            # Get memory type with fallback to buffer
            memory_type = memory_config.get("type", "buffer")
            
            if memory_type == "buffer" or not memory_type:
                return ConversationBufferMemory(
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "buffer_window":
                k = memory_config.get("k", 5)
                return ConversationBufferWindowMemory(
                    k=k,
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "summary":
                return ConversationSummaryMemory(
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "token_buffer":
                max_token_limit = memory_config.get("max_token_limit", 2000)
                return ConversationTokenBufferMemory(
                    max_token_limit=max_token_limit,
                    return_messages=True,
                    memory_key="history"
                )
            else:
                self.log_warning(f"Unsupported memory type: {memory_type}. Using buffer memory.")
                return ConversationBufferMemory(
                    return_messages=True, 
                    memory_key="history"
                )
        except ImportError:
            self.log_warning("LangChain not installed, memory features unavailable")
            return None
        except Exception as e:
            self.log_error(f"Error creating memory: {e}")
            return None

    def _format_prompt(self, inputs: Dict[str, Any]) -> str:
        """
        Format the prompt with input values.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Formatted prompt text
        """
        try:
            # Filter inputs to only include those in input_fields
            formatted_inputs = {k: v for k, v in inputs.items() if k in self.input_fields}
            return self.prompt.format(**formatted_inputs)
        except KeyError as e:
            self.log_warning(f"Missing key in prompt format: {e}")
            return self.prompt
        except Exception as e:
            self.log_error(f"Error formatting prompt: {e}")
            return self.prompt

    def _process_with_langchain(self, client: Any, formatted_prompt: str, inputs: Dict[str, Any]) -> Any:
        """
        Process the request using LangChain.
        
        Args:
            client: LangChain client
            formatted_prompt: Formatted prompt text
            inputs: Original input dictionary
            
        Returns:
            LLM response or error dictionary
        """
        try:
            # Get or restore memory from inputs
            if self.memory_key in inputs and self.memory is not None:
                from agentmap.agents.builtins.llm.utils import deserialize_memory
                memory_data = inputs[self.memory_key]
                if isinstance(memory_data, dict) and memory_data.get("_type") == "langchain_memory":
                    self.memory = deserialize_memory(memory_data)
                else:
                    self.memory = memory_data  # Handle case when it's already a memory object
            
            # Prepare memory variables if available
            memory_variables = {}
            if self.memory:
                try:
                    memory_variables = self.memory.load_memory_variables({})
                except Exception as e:
                    self.log_warning(f"Error loading memory variables: {e}")
            
            # Run the LLM
            response = None
            result = None
            
            if isinstance(formatted_prompt, list):
                # Chat messages format
                from langchain_core.messages import HumanMessage
                messages = formatted_prompt
                if not messages:
                    messages = [HumanMessage(content=self.prompt)]
                try:
                    # Use the invoke method instead of the deprecated __call__
                    response = client.invoke(messages)
                    result = response.content
                except AttributeError:
                    # Fall back to legacy method if needed
                    response = client.generate([messages])
                    result = response.generations[0][0].text
            else:
                # String prompt format
                if memory_variables:
                    # Combine prompt with memory
                    from langchain_core.prompts import PromptTemplate
                    history = memory_variables.get("history", "")
                    template = f"{{history}}\n\n{formatted_prompt}" if history else formatted_prompt
                    prompt = PromptTemplate(template=template, input_variables=["history"])
                    try:
                        # Use invoke method for newer LangChain versions
                        result = client.invoke(prompt.format(history=history))
                        # Check if result is a message with content attribute
                        if hasattr(result, 'content'):
                            result = result.content
                    except AttributeError:
                        # Fall back to legacy method if needed
                        result = client(prompt.format(history=history))
                else:
                    # Just the prompt
                    try:
                        # Use invoke method for newer LangChain versions
                        result = client.invoke(formatted_prompt)
                        # Check if result is a message with content attribute
                        if hasattr(result, 'content'):
                            result = result.content
                    except AttributeError:
                        # Fall back to legacy method if needed
                        result = client(formatted_prompt)
            
            # Save to memory if available
            if self.memory:
                # Get user input for memory
                user_input = inputs.get(self.input_fields[0]) if self.input_fields else formatted_prompt
                
                # Add to memory
                self.memory.save_context(
                    {"input": user_input},
                    {"output": result}
                )
                
                # Create response with memory
                from agentmap.agents.builtins.llm.utils import serialize_memory
                
                if self.output_field:
                    return {
                        self.output_field: result,
                        self.memory_key: serialize_memory(self.memory)
                    }
                else:
                    return {
                        "output": result,
                        self.memory_key: serialize_memory(self.memory)
                    }
            else:
                # Return just the result
                return result
                
        except Exception as e:
            self.log_error(f"Error in LangChain processing: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs with LangChain or direct API calls.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Response from LLM or error dictionary
        """
        try:
            # Format the prompt with inputs
            formatted_prompt = self._format_prompt(inputs)
            
            # Try LangChain if available
            try:
                langchain_client = self._create_langchain_client()
                if langchain_client:
                    return self._process_with_langchain(langchain_client, formatted_prompt, inputs)
            except Exception as e:
                self.log_debug(f"LangChain processing failed, falling back to direct API: {e}")
            
            # Fall back to direct API call
            result = self._call_api(formatted_prompt)
            return result
            
        except Exception as e:
            self.log_error(f"Error in {self.provider_name} processing: {e}")
            return {
                "error": str(e),
                "last_action_success": False
            }

    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Post-processing hook to handle memory in output.
        
        Args:
            state: Current state
            output: Output from process method
            
        Returns:
            Tuple of (updated_state, updated_output)
        """
        
        # Handle case where output includes memory
        if isinstance(output, dict) and self.memory_key in output:
            memory = output.pop(self.memory_key, None)
            
            # Set memory in state if present
            if memory:
                state = StateAdapter.set_value(state, self.memory_key, memory)
            
            # Get the actual output value
            if self.output_field and self.output_field in output:
                output = output[self.output_field]
        
        # Set output in state if output field is specified
        if self.output_field:
            state = StateAdapter.set_value(state, self.output_field, output)
        
        return state, output