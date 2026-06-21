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

    def get_or_create_client(
        self, provider: str, config: Dict[str, Any], streaming: bool = False
    ) -> Any:
        """
        Get or create a LangChain client for the provider.

        Args:
            provider: Provider name (openai, anthropic, google)
            config: Provider configuration dictionary
            streaming: When True, construct a streaming-aware client with
                provider-specific usage opt-in flags (e.g. stream_usage=True
                for Anthropic, stream_options={"include_usage": True} for OpenAI).
                Defaults to False so all existing callers are unaffected.

        Returns:
            LangChain client instance
        """
        # Create cache key based on provider and critical config.
        # The streaming dimension is appended last so streaming and non-streaming
        # clients for the same (provider, config) are cached separately.
        max_tok = config.get("max_tokens")
        temperature = config.get("temperature", 0.7)
        # ``api_key`` may be present-but-None (keys are often optionally loaded);
        # ``or ""`` guards against ``None[:8]`` raising TypeError.
        api_key_prefix = (config.get("api_key") or "")[:8]
        cache_key = (
            f"{provider}_{config.get('model')}_{api_key_prefix}_"
            f"{max_tok}_{temperature!r}_{streaming}"
        )

        if cache_key in self._clients:
            return self._clients[cache_key]

        # Create new client
        client = self._create_langchain_client(provider, config, streaming)

        # Cache the client.
        # Accepted benign race: concurrent fan-out coroutines can arrive here
        # simultaneously for the same cache_key, each creating an equivalent
        # client and storing it.  The last write wins and both clients are
        # identical (same provider, model, temperature, API key prefix, and
        # streaming-ness), so the race produces no incorrect behaviour.
        # An asyncio.Lock would eliminate the redundant work but adds complexity
        # not justified by the low probability of simultaneous first-use of the
        # exact same key.
        self._clients[cache_key] = client

        return client

    def _create_langchain_client(
        self, provider: str, config: Dict[str, Any], streaming: bool = False
    ) -> Any:
        """
        Create a LangChain client for the specified provider.

        Args:
            provider: Provider name
            config: Provider configuration
            streaming: When True, add provider-specific usage opt-in flags
                to the constructed LangChain client (e.g. stream_usage=True
                for Anthropic, stream_options={"include_usage": True} for OpenAI).
                Defaults to False; non-streaming construction is unchanged.

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
        max_tokens = config.get("max_tokens")

        try:
            if provider == "openai":
                return self._create_openai_client(
                    api_key, model, temperature, max_tokens, streaming
                )
            elif provider == "anthropic":
                return self._create_anthropic_client(
                    api_key, model, temperature, max_tokens, streaming
                )
            elif provider == "google":
                return self._create_google_client(
                    api_key, model, temperature, max_tokens, streaming
                )
            else:
                raise LLMConfigurationError(f"Unsupported provider: {provider}")

        except ImportError as e:
            raise LLMDependencyError(
                f"Missing dependencies for {provider}. "
                f"Install with: pip install agentmap[{provider}]"
            ) from e

    def _create_openai_client(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        streaming: bool = False,
    ) -> Any:
        """
        Create OpenAI LangChain client.

        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Temperature setting
            max_tokens: Optional max response tokens
            streaming: When True, adds stream_options={"include_usage": True}
                so the LangChain wrapper forwards end-of-stream usage metadata.

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

        kwargs: Dict[str, Any] = {
            "model_name": model,
            "temperature": temperature,
            "openai_api_key": api_key,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if streaming:
            kwargs["stream_options"] = {"include_usage": True}
        return ChatOpenAI(**kwargs)

    def _create_anthropic_client(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        streaming: bool = False,
    ) -> Any:
        """
        Create Anthropic LangChain client.

        Args:
            api_key: Anthropic API key
            model: Model name
            temperature: Temperature setting
            max_tokens: Optional max response tokens
            streaming: When True, adds stream_usage=True so the LangChain
                wrapper forwards end-of-stream usage metadata.

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

        kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "anthropic_api_key": api_key,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if streaming:
            kwargs["stream_usage"] = True
        return ChatAnthropic(**kwargs)

    def _create_google_client(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        streaming: bool = False,
    ) -> Any:
        """
        Create Google LangChain client.

        Args:
            api_key: Google API key
            model: Model name
            temperature: Temperature setting
            max_tokens: Optional max response tokens
            streaming: Accepted for signature uniformity with other builders;
                no Google streaming usage opt-in is set (Gemini streaming usage
                is unverified and out of epic scope — engineering-context.md:100).

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

        kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "google_api_key": api_key,
        }
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._clients.clear()
        self._logger.debug("Client cache cleared")
