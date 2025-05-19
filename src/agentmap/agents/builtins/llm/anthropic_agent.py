"""
Anthropic Claude LLM agent implementation.

This module provides an agent for interacting with Anthropic's Claude language models.
"""


"""
Anthropic Claude LLM agent implementation.

This module provides an agent for interacting with Anthropic's Claude language models.
"""

from typing import Any, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent

class AnthropicAgent(LLMAgent):
    """
    Anthropic Claude agent implementation.
    
    Uses Anthropic's API to generate text completions, with provider-specific
    functionality while inheriting common LLM behaviors from the base class.
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
    
    def _call_api(self, formatted_prompt: str) -> str:
        """
        Call the Anthropic API and return the result text.
        
        Args:
            formatted_prompt: Formatted prompt text
            
        Returns:
            Response text from Claude
            
        Raises:
            ValueError: If API key is missing
            ImportError: If Anthropic package is not installed
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise ValueError("Anthropic API key not found in config or environment")
        
        # Try newer Anthropic client first
        try:
            from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
            
            client = Anthropic(api_key=self.api_key)
            
            try:
                # Try new messages API first
                completion = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": formatted_prompt}]
                )
                
                return completion.content[0].text.strip()
            except (AttributeError, TypeError):
                # Fall back to older completions API
                completion = client.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=self.temperature,
                    prompt=f"{HUMAN_PROMPT} {formatted_prompt} {AI_PROMPT}",
                )
                
                return completion.completion.strip()
                
        except ImportError:
            # Fallback to older API version if necessary
            try:
                from anthropic import Client as AnthropicClient
                
                client = AnthropicClient(api_key=self.api_key)
                result = client.completion(
                    prompt=f"\n\nHuman: {formatted_prompt}\n\nAssistant:",
                    model=self.model,
                    max_tokens_to_sample=1024,
                    temperature=self.temperature
                ).completion.strip()
                
                return result
                
            except ImportError:
                raise ImportError("Anthropic package not installed. Install with 'pip install anthropic'")
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")
    
    def _create_langchain_client(self) -> Optional[Any]:
        """
        Create a LangChain ChatAnthropic client.
        
        Returns:
            LangChain ChatAnthropic client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try to use the new langchain-anthropic package
            try:
                from langchain_anthropic import ChatAnthropic
                
                return ChatAnthropic(
                    model=self.model,
                    temperature=self.temperature,
                    anthropic_api_key=self.api_key
                )
            except ImportError:
                # Fall back to legacy imports with warning
                try:
                    from langchain_community.chat_models import ChatAnthropic
                    self.log_warning("Using deprecated LangChain import. Consider upgrading to langchain-anthropic.")
                    
                    return ChatAnthropic(
                        model=self.model,
                        temperature=self.temperature,
                        anthropic_api_key=self.api_key
                    )
                except ImportError:
                    # Last resort, try the oldest import path
                    from langchain.chat_models import ChatAnthropic
                    self.log_warning("Using legacy LangChain import. Please upgrade your dependencies.")
                    
                    return ChatAnthropic(
                        model=self.model,
                        temperature=self.temperature,
                        anthropic_api_key=self.api_key
                    )
        except Exception as e:
            self.log_debug(f"Could not create LangChain ChatAnthropic client: {e}")
            return None