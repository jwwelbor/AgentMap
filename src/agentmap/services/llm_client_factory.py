"""
LLM Client Factory for creating and caching LangChain clients.

Handles the creation of provider-specific LangChain clients (OpenAI, Anthropic, Google)
with proper dependency management and client caching.
"""

from typing import Any, Dict

from agentmap.exceptions import LLMConfigurationError, LLMDependencyError
from agentmap.services.logging_service import LoggingService


class LLMClientFactory:
    """Factory for creating and caching LangChain LLM clients."""

    def __init__(self, logging_service: LoggingService):
        """
        Initialize the client factory.

        Args:
            logging_service: Service for logging
        """
        self._clients = {}  # Cache for LangChain clients
        self._logger = logging_service.get_class_logger("agentmap.llm.factory")

    def get_or_create_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """
        Get or create a LangChain client for the provider.

        Args:
            provider: Provider name (openai, anthropic, google)
            config: Provider configuration dictionary

        Returns:
            LangChain client instance
        """
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
        """
        Create a LangChain client for the specified provider.

        Args:
            provider: Provider name
            config: Provider configuration

        Returns:
            LangChain client instance

        Raises:
            LLMConfigurationError: If configuration is invalid
            LLMDependencyError: If required dependencies are missing
        """
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

    def _create_openai_client(
        self, api_key: str, model: str, temperature: float
    ) -> Any:
        """
        Create OpenAI LangChain client.

        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Temperature setting

        Returns:
            ChatOpenAI client instance
        """
        try:
            # Try the new langchain-openai package first
            from langchain_openai import ChatOpenAI
        except ImportError:
            # Fall back to legacy import
            try:
                from langchain.chat_models import ChatOpenAI

                self._logger.warning(
                    "Using deprecated LangChain import. Consider upgrading to langchain-openai."
                )
            except ImportError:
                raise LLMDependencyError(
                    "OpenAI dependencies not found. Install with: pip install langchain-openai"
                )

        return ChatOpenAI(
            model_name=model, temperature=temperature, openai_api_key=api_key
        )

    def _create_anthropic_client(
        self, api_key: str, model: str, temperature: float
    ) -> Any:
        """
        Create Anthropic LangChain client.

        Args:
            api_key: Anthropic API key
            model: Model name
            temperature: Temperature setting

        Returns:
            ChatAnthropic client instance
        """
        try:
            # Try langchain-anthropic first
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            try:
                # Fall back to community package
                from langchain_community.chat_models import ChatAnthropic

                self._logger.warning(
                    "Using community LangChain import. Consider upgrading to langchain-anthropic."
                )
            except ImportError:
                try:
                    # Legacy fallback
                    from langchain.chat_models import ChatAnthropic

                    self._logger.warning(
                        "Using legacy LangChain import. Please upgrade your dependencies."
                    )
                except ImportError:
                    raise LLMDependencyError(
                        "Anthropic dependencies not found. Install with: pip install langchain-anthropic"
                    )

        return ChatAnthropic(
            model=model, temperature=temperature, anthropic_api_key=api_key
        )

    def _create_google_client(
        self, api_key: str, model: str, temperature: float
    ) -> Any:
        """
        Create Google LangChain client.

        Args:
            api_key: Google API key
            model: Model name
            temperature: Temperature setting

        Returns:
            ChatGoogleGenerativeAI client instance
        """
        try:
            # Try langchain-google-genai first
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            try:
                # Fall back to community package
                from langchain_community.chat_models import ChatGoogleGenerativeAI

                self._logger.warning(
                    "Using community LangChain import. Consider upgrading to langchain-google-genai."
                )
            except ImportError:
                raise LLMDependencyError(
                    "Google dependencies not found. Install with: pip install langchain-google-genai"
                )

        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, google_api_key=api_key
        )

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._clients.clear()
        self._logger.debug("Client cache cleared")
