"""
Anthropic Claude LLM agent implementation.
"""
from typing import Any, Dict, List, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent


class AnthropicAgent(LLMAgent):
    """
    Anthropic Claude agent implementation with memory support.
    
    Uses Anthropic's API to generate text completions while managing conversation
    history within the graph state.
    """
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "anthropic"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "ANTHROPIC_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "claude-3-sonnet-20240229"
    
    def _create_langchain_client(self) -> Optional[Any]:
        """
        Create a LangChain ChatAnthropic client.
        
        Returns:
            LangChain ChatAnthropic client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try the dedicated langchain-anthropic package
            try:
                from langchain_anthropic import ChatAnthropic
                
                return ChatAnthropic(
                    model=self.model,
                    temperature=self.temperature,
                    anthropic_api_key=self.api_key
                )
            except ImportError:
                # Fall back to community package
                try:
                    from langchain_community.chat_models import ChatAnthropic
                    self.log_warning("Using community LangChain import. Consider upgrading to langchain-anthropic.")
                    
                    return ChatAnthropic(
                        model=self.model,
                        temperature=self.temperature,
                        anthropic_api_key=self.api_key
                    )
                except (ImportError, AttributeError):
                    # Legacy fallback
                    from langchain.chat_models import ChatAnthropic
                    self.log_warning("Using legacy LangChain import. Please upgrade your dependencies.")
                    
                    return ChatAnthropic(
                        model=self.model,
                        temperature=self.temperature,
                        anthropic_api_key=self.api_key
                    )
        except Exception as e:
            self.log_warning(f"Could not create LangChain ChatAnthropic client: {e}")
            return None
