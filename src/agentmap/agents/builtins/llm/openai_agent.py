"""
OpenAI LLM agent implementation.
"""
from typing import Any, Dict, List

from agentmap.agents.builtins.llm.llm_agent import LLMAgent


class OpenAIAgent(LLMAgent):
    """
    OpenAI agent implementation with memory support.
    
    Uses OpenAI's API to generate text completions while managing conversation
    history within the graph state.
    """
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "openai"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "OPENAI_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "gpt-3.5-turbo"
        
    
    def _create_langchain_client(self) -> Any:
        """
        Create a LangChain ChatOpenAI client.
        
        Returns:
            LangChain ChatOpenAI client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try the new langchain-openai package
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                # Fall back to legacy imports with warning
                from langchain.chat_models import ChatOpenAI
                self.log_warning("Using deprecated LangChain import. Consider upgrading to langchain-openai.")
                
            return ChatOpenAI(
                model_name=self.model,
                temperature=self.temperature,
                openai_api_key=self.api_key
            )
        except Exception as e:
            self.log_warning(f"Could not create LangChain ChatOpenAI client: {e}")
            return None
