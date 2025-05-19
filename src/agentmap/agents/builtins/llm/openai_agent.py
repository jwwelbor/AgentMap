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
            # Set up the API client
            import openai
            openai.api_key = self.api_key
            
            # Make the API call
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=self.temperature
            )
            
            return response['choices'][0]['message']['content'].strip()
            
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with 'pip install openai'")
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    def _create_langchain_client(self) -> Any:
        """Create a LangChain ChatOpenAI client."""
        if not self.api_key:
            return None
            
        try:
            from langchain.chat_models import ChatOpenAI
            
            return ChatOpenAI(
                model_name=self.model,
                temperature=self.temperature,
                openai_api_key=self.api_key
            )
        except (ImportError, Exception):
            return None