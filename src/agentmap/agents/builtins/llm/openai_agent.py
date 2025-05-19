"""
OpenAI LLM agent implementation using LangChain.
"""
from typing import Any

from agentmap.agents.builtins.llm.llm_agent import LLMAgent

# agentmap/agents/builtins/llm/openai_agent.py
class OpenAIAgent(LLMAgent):
    """OpenAI agent implementation."""
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "openai"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "OPENAI_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "gpt-3.5-turbo"
        
    def _call_api(self, formatted_prompt: str) -> str:
        """Call the OpenAI API and return the result text."""
        if not self.api_key:
            raise ValueError("OpenAI API key not found in config or environment")
        
        try:
            # Set up the API client using the new API format
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            # Make the API call with the new format
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=self.temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with 'pip install openai>=1.0.0'")
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    def _create_langchain_client(self) -> Any:
        """Create a LangChain ChatOpenAI client with the updated imports."""
        if not self.api_key:
            return None
            
        try:
            # Try to use the new langchain-openai package
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                # Fall back to legacy imports with warning
                from langchain.chat_models import ChatOpenAI
                self.log_warning("Using deprecated LangChain import path. Consider upgrading to langchain-openai.")
                
            return ChatOpenAI(
                model_name=self.model,
                temperature=self.temperature,
                openai_api_key=self.api_key
            )
        except (ImportError, Exception) as e:
            self.log_warning(f"Could not create LangChain client: {str(e)}")
            return None