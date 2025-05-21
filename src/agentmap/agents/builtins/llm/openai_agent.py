"""
OpenAI LLM agent implementation using the latest OpenAI Python client (v1.0+).
"""
from typing import Any, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent

class OpenAIAgent(LLMAgent):
    """
    OpenAI agent implementation.
    
    Uses OpenAI's API to generate text completions, with provider-specific
    functionality while inheriting common LLM behaviors from the base class.
    """
    
    def __init__(self, name: str, prompt: str, context: dict = None):
        """Initialize the OpenAI agent with configuration."""
        super().__init__(name, prompt, context or {})
        self._client = None
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "openai"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "OPENAI_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "gpt-3.5-turbo"
    
    def _get_client(self) -> Any:
        """
        Get or create the OpenAI client instance.
        
        Returns:
            OpenAI client instance
        """
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                self.log_debug(f"Created new OpenAI client instance for {self.name}")
            except ImportError:
                raise ImportError("OpenAI package not installed. Install with 'pip install openai>=1.0.0'")
        
        return self._client
    
    def _call_api(self, formatted_prompt: str) -> str:
        """
        Call the OpenAI API and return the result text.
        
        Args:
            formatted_prompt: Formatted prompt text
            
        Returns:
            Response text from OpenAI
            
        Raises:
            ValueError: If API key is missing
            ImportError: If OpenAI package is not installed
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not found in config or environment")
        
        try:
            # Get the client
            client = self._get_client()
            
            self.log_debug(f"Calling OpenAI API with model: {self.model}, temperature: {self.temperature}")
            
            # Make the API call with the new format
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=self.temperature
            )
            
            # Extract the response content
            result = response.choices[0].message.content.strip()
            self.log_debug(f"Received response of {len(result)} characters from OpenAI")
            
            return result
            
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with 'pip install openai>=1.0.0'")
        except Exception as e:
            self.log_error(f"OpenAI API error: {str(e)}")
            raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    def _create_langchain_client(self) -> Optional[Any]:
        """
        Create a LangChain ChatOpenAI client.
        
        Returns:
            LangChain ChatOpenAI client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try to use the new langchain-openai package
            try:
                from langchain_openai import ChatOpenAI
                
                return ChatOpenAI(
                    model_name=self.model,
                    temperature=self.temperature,
                    openai_api_key=self.api_key
                )
            except ImportError:
                # Fall back to community package
                try:
                    from langchain_community.chat_models import ChatOpenAI
                    self.log_warning("Using community LangChain import. Consider upgrading to langchain-openai.")
                    
                    return ChatOpenAI(
                        model_name=self.model,
                        temperature=self.temperature,
                        openai_api_key=self.api_key
                    )
                except ImportError:
                    # Try the oldest import path
                    from langchain.chat_models import ChatOpenAI
                    self.log_warning("Using legacy LangChain import. Please upgrade your dependencies.")
                    
                    return ChatOpenAI(
                        model_name=self.model,
                        temperature=self.temperature,
                        openai_api_key=self.api_key
                    )
        except Exception as e:
            self.log_debug(f"Could not create LangChain ChatOpenAI client: {e}")
            return None