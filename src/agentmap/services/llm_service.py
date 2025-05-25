"""
LLM Service for centralized LLM calling in AgentMap.

Provides a unified interface for calling different LLM providers while
handling configuration, error handling, and provider abstraction.
"""
import os
from typing import Any, Dict, List, Optional

from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService
from agentmap.exceptions import (
    LLMServiceError, 
    LLMProviderError, 
    LLMConfigurationError,
    LLMDependencyError
)


from typing import Protocol, runtime_checkable, Any, Dict, List, Optional

@runtime_checkable
class LLMServiceUser(Protocol):
    """
    Protocol for agents that use LLM services.
    
    To use LLM services in your agent, add this to your __init__:
        self.llm_service = None
    
    Then use it in your methods:
        response = self.llm_service.call_llm(provider="openai", messages=[...])
    
    The service will be automatically injected during graph building.
    """
    llm_service: 'LLMService'


class LLMService:
    """
    Centralized service for making LLM calls across different providers.
    
    Handles provider abstraction, configuration loading, and error handling
    while maintaining a simple interface for callers.
    """
    
    def __init__(
        self,
        configuration: Configuration,
        logging_service: LoggingService
    ):
        self.configuration = configuration
        self._clients = {}  # Cache for LangChain clients
        self._logger = logging_service.get_class_logger("agentmap.llm")
                
    def call_llm(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Make an LLM call with standardized interface.
        
        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.)
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Override model name
            temperature: Override temperature
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Response text string
            
        Raises:
            LLMServiceError: On various error conditions
        """
        try:
            self._logger.debug(f"[LLMService] Calling {provider} with {len(messages)} messages")
            
            # Validate inputs
            if not provider:
                raise LLMConfigurationError("Provider cannot be empty")
            if not messages:
                raise LLMConfigurationError("Messages cannot be empty")
                
            # Normalize provider name and handle aliases
            normalized_provider = self._normalize_provider(provider)
            
            # Get provider configuration
            config = self._get_provider_config(normalized_provider)
            
            # Override config with provided parameters
            if model:
                config["model"] = model
            if temperature is not None:
                config["temperature"] = temperature
                
            # Create or get cached client
            client = self._get_or_create_client(normalized_provider, config)
            
            # Make the LLM call
            response = client.invoke(messages)
            
            # Extract content from response
            result = response.content if hasattr(response, 'content') else str(response)
            
            self._logger.debug(f"[LLMService] {provider} call successful, response length: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = f"Error calling {provider} LLM: {str(e)}"
            self._logger.error(f"[LLMService] {error_msg}")
            
            # Re-raise as appropriate service exception
            if isinstance(e, LLMServiceError):
                raise
            else:
                raise LLMProviderError(error_msg) from e
                
    def _normalize_provider(self, provider: str) -> str:
        """Normalize provider name and handle aliases."""
        provider_lower = provider.lower()
        
        # Handle aliases
        aliases = {
            "gpt": "openai",
            "claude": "anthropic", 
            "gemini": "google"
        }
        
        return aliases.get(provider_lower, provider_lower)
        
    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for the specified provider."""
        config = self.configuration.get_llm_config(provider)
        
        if not config:
            raise LLMConfigurationError(f"No configuration found for provider: {provider}")
            
        # Ensure required fields have defaults
        defaults = self._get_provider_defaults(provider)
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
                
        return config
        
    def _get_provider_defaults(self, provider: str) -> Dict[str, Any]:
        """Get default configuration values for a provider."""
        defaults = {
            "openai": {
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "api_key": os.environ.get("OPENAI_API_KEY", "")
            },
            "anthropic": {
                "model": "claude-3-sonnet-20240229", 
                "temperature": 0.7,
                "api_key": os.environ.get("ANTHROPIC_API_KEY", "")
            },
            "google": {
                "model": "gemini-1.0-pro",
                "temperature": 0.7,
                "api_key": os.environ.get("GOOGLE_API_KEY", "")
            }
        }
        
        return defaults.get(provider, {})
        
    def _get_or_create_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Get or create a LangChain client for the provider."""
        # Create cache key based on provider and critical config
        cache_key = f"{provider}_{config.get('model')}_{config.get('api_key', '')[:8]}"
        
        if cache_key in self._clients:
            return self._clients[cache_key]
            
        # Create new client
        client = self._create_langchain_client(provider, config)
        
        # Cache the client
        self._clients[cache_key] = client
        
        return client
        
    def _create_langchain_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Create a LangChain client for the specified provider."""
        api_key = config.get("api_key")
        if not api_key:
            raise LLMConfigurationError(f"No API key found for provider: {provider}")
            
        model = config.get("model")
        temperature = config.get("temperature", 0.7)
        
        try:
            if provider == "openai":
                return self._create_openai_client(api_key, model, temperature)
            elif provider == "anthropic":
                return self._create_anthropic_client(api_key, model, temperature)
            elif provider == "google":
                return self._create_google_client(api_key, model, temperature)
            else:
                raise LLMConfigurationError(f"Unsupported provider: {provider}")
                
        except ImportError as e:
            raise LLMDependencyError(
                f"Missing dependencies for {provider}. "
                f"Install with: pip install agentmap[{provider}]"
            ) from e
            
    def _create_openai_client(self, api_key: str, model: str, temperature: float) -> Any:
        """Create OpenAI LangChain client."""
        try:
            # Try the new langchain-openai package first
            from langchain_openai import ChatOpenAI
        except ImportError:
            # Fall back to legacy import
            try:
                from langchain.chat_models import ChatOpenAI
                self._logger.warning("Using deprecated LangChain import. Consider upgrading to langchain-openai.")
            except ImportError:
                raise LLMDependencyError("OpenAI dependencies not found. Install with: pip install langchain-openai")
                
        return ChatOpenAI(
            model_name=model,
            temperature=temperature,
            openai_api_key=api_key
        )
        
    def _create_anthropic_client(self, api_key: str, model: str, temperature: float) -> Any:
        """Create Anthropic LangChain client."""
        try:
            # Try langchain-anthropic first
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            try:
                # Fall back to community package
                from langchain_community.chat_models import ChatAnthropic
                self._logger.warning("Using community LangChain import. Consider upgrading to langchain-anthropic.")
            except ImportError:
                try:
                    # Legacy fallback
                    from langchain.chat_models import ChatAnthropic
                    self._logger.warning("Using legacy LangChain import. Please upgrade your dependencies.")
                except ImportError:
                    raise LLMDependencyError("Anthropic dependencies not found. Install with: pip install langchain-anthropic")
                    
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            anthropic_api_key=api_key
        )
        
    def _create_google_client(self, api_key: str, model: str, temperature: float) -> Any:
        """Create Google LangChain client."""
        try:
            # Try langchain-google-genai first
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            try:
                # Fall back to community package
                from langchain_community.chat_models import ChatGoogleGenerativeAI
                self._logger.warning("Using community LangChain import. Consider upgrading to langchain-google-genai.")
            except ImportError:
                raise LLMDependencyError("Google dependencies not found. Install with: pip install langchain-google-genai")
                
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key
        )
        
    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._clients.clear()
        self._logger.debug("[LLMService] Client cache cleared")