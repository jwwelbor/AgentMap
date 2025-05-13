"""
Base LLM Agent with LangChain integration.
"""
import os
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent, StateAdapter
from agentmap.logging import get_logger

logger = get_logger(__name__)

# Flag to indicate if LangChain is available
try:
    import langchain
    from langchain.schema import BaseMemory
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not installed. Install with 'pip install langchain'")
    LANGCHAIN_AVAILABLE = False


class LLMAgent(BaseAgent):
    """
    Base class for LLM agents using LangChain.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """Initialize the LLM agent."""
        super().__init__(name, prompt, context)
        
        # Parse context configuration
        self.context = context or {}
        
        # Setup memory if configured
        self.memory = None  
        self.memory_key = self.context.get("memory_key", "conversation_memory")
        
        # Initialize memory if configuration exists
        if LANGCHAIN_AVAILABLE and "memory" in self.context:
            self.memory = self._create_memory(self.context["memory"])
        
        # Set fallback implementation flag
        self.use_langchain = LANGCHAIN_AVAILABLE
        
    def _create_memory(self, memory_config: Dict[str, Any]) -> Optional[Any]:
        """Create a LangChain memory object based on configuration."""
        if not memory_config or not LANGCHAIN_AVAILABLE:
            return None
            
        try:
            from langchain.memory import ConversationBufferMemory
            
            # Get memory type with fallback to buffer
            memory_type = memory_config.get("type", "buffer")
            
            if memory_type == "buffer" or not memory_type:
                return ConversationBufferMemory(
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "buffer_window":
                from langchain.memory import ConversationBufferWindowMemory
                k = memory_config.get("k", 5)
                return ConversationBufferWindowMemory(
                    k=k,
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "summary":
                from langchain.memory import ConversationSummaryMemory
                return ConversationSummaryMemory(
                    return_messages=True,
                    memory_key="history"
                )
            elif memory_type == "token_buffer":
                from langchain.memory import ConversationTokenBufferMemory
                max_token_limit = memory_config.get("max_token_limit", 2000)
                return ConversationTokenBufferMemory(
                    max_token_limit=max_token_limit,
                    return_messages=True,
                    memory_key="history"
                )
            else:
                logger.warning(f"Unsupported memory type: {memory_type}. Using buffer memory.")
                return ConversationBufferMemory(
                    return_messages=True, 
                    memory_key="history"
                )
        except Exception as e:
            logger.error(f"Error creating memory: {e}")
            return None
            
    def _get_llm(self) -> Any:
        """Create and return a LangChain LLM instance - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _get_llm()")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs with LangChain or fallback implementation."""
        # Check for LangChain availability
        if not self.use_langchain:
            return self._fallback_process(inputs)
            
        try:
            # Get or restore memory from inputs
            if self.memory_key in inputs and self.memory is not None:
                from agentmap.agents.builtins.memory.utils import deserialize_memory
                memory_data = inputs[self.memory_key]
                if isinstance(memory_data, dict) and memory_data.get("_type") == "langchain_memory":
                    self.memory = deserialize_memory(memory_data)
                else:
                    self.memory = memory_data  # Handle case when it's already a memory object
            
            # Get LLM from subclass
            llm = self._get_llm()
            if not llm:
                return {
                    "error": "Failed to initialize LLM",
                    "last_action_success": False
                }
            
            # Format the prompt
            formatted_prompt = self._format_prompt(inputs)
            
            # Prepare memory variables if available
            memory_variables = {}
            if self.memory:
                try:
                    memory_variables = self.memory.load_memory_variables({})
                except Exception as e:
                    logger.warning(f"Error loading memory variables: {e}")
            
            # Run the LLM
            response = None
            if isinstance(formatted_prompt, list):
                # Chat messages format
                from langchain.schema import HumanMessage
                messages = formatted_prompt
                if not messages:
                    messages = [HumanMessage(content=self.prompt)]
                response = llm.generate([messages])
                result = response.generations[0][0].text
            else:
                # String prompt format
                if memory_variables:
                    # Combine prompt with memory
                    from langchain.prompts import PromptTemplate
                    history = memory_variables.get("history", "")
                    template = f"{{history}}\n\n{formatted_prompt}" if history else formatted_prompt
                    prompt = PromptTemplate(template=template, input_variables=["history"])
                    result = llm(prompt.format(history=history))
                else:
                    # Just the prompt
                    result = llm(formatted_prompt)
            
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
                if self.output_field:
                    return {
                        self.output_field: result,
                        self.memory_key: self.memory
                    }
                else:
                    return {
                        "output": result,
                        self.memory_key: self.memory
                    }
            else:
                # Return just the result
                return result
                
        except Exception as e:
            logger.error(f"Error in LangChain processing: {e}")
            # Fall back to direct implementation
            return self._fallback_process(inputs)
    
    def _format_prompt(self, inputs: Dict[str, Any]) -> str:
        """Format the prompt with input values."""
        try:
            # Filter inputs to only include those in input_fields
            formatted_inputs = {k: v for k, v in inputs.items() if k in self.input_fields}
            return self.prompt.format(**formatted_inputs)
        except KeyError as e:
            logger.warning(f"Missing key in prompt format: {e}")
            return self.prompt
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            return self.prompt
    
    def _fallback_process(self, inputs: Dict[str, Any]) -> Any:
        """Fallback implementation when LangChain is not available."""
        raise NotImplementedError("Subclasses must implement _fallback_process()")