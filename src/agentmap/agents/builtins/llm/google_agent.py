"""
Google Gemini LLM agent implementation.
"""
from typing import Any, Dict, List, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent


class GoogleAgent(LLMAgent):
    """
    Google Gemini agent implementation with memory support.
    
    Uses Google's Gemini API to generate text completions while managing conversation
    history within the graph state.
    """
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "google"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "GOOGLE_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "gemini-1.0-pro"
    
    def _create_langchain_client(self) -> Optional[Any]:
        """
        Create a LangChain ChatGoogleGenerativeAI client.
        
        Returns:
            LangChain ChatGoogleGenerativeAI client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try langchain-google-genai first
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                return ChatGoogleGenerativeAI(
                    model=self.model,
                    temperature=self.temperature,
                    google_api_key=self.api_key
                )
            except ImportError:
                # Try community package
                try:
                    from langchain_community.chat_models import ChatGoogleGenerativeAI
                    self.log_warning("Using community LangChain import. Consider upgrading to langchain-google-genai.")
                    
                    return ChatGoogleGenerativeAI(
                        model=self.model,
                        temperature=self.temperature,
                        google_api_key=self.api_key
                    )
                except (ImportError, AttributeError):
                    self.log_warning("Could not create LangChain Google client. "
                                "Install with 'pip install langchain-google-genai'")
                    return None
        except Exception as e:
            self.log_warning(f"Could not create LangChain Google client: {e}")
            return None
