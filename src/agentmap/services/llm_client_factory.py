"""
LLM Client Factory for creating and caching LangChain clients.

Handles the creation of provider-specific LangChain clients (OpenAI, Anthropic, Google)
with proper dependency management and client caching.
"""

from threading import RLock
from typing import Any, Callable, Dict

from agentmap.exceptions import LLMConfigurationError, LLMDependencyError
from agentmap.services.llm.client_lifecycle import GovernedClientLifecycleMixin
from agentmap.services.llm.observed_clients import (
    ObservedResources,
    governed_google_kwargs,
    governed_openai_kwargs,
    observed_anthropic_client,
)
from agentmap.services.logging_service import LoggingService


class LLMClientFactory(GovernedClientLifecycleMixin):
    """Factory for creating and caching LangChain LLM clients."""

    def __init__(self, logging_service: LoggingService):
        """
        Initialize the client factory.

        Args:
            logging_service: Service for logging
        """
        self._clients = {}  # Cache for LangChain clients
        self._cache_lock = RLock()
        self._initialize_governed_lifecycle()
        self._logger = logging_service.get_class_logger("agentmap.llm.factory")

    @staticmethod
    def _validate_streaming_flag(streaming: Any) -> bool:
        """Reject non-bool ``streaming`` values (TD-024).

        ``streaming`` selects the cache-key suffix AND (via truthiness) the
        provider construction branch.  A non-bool value that is also
        string-truthy — e.g. the literal string ``"False"`` — renders
        identically to ``streaming=False`` in the cache key (``f"..._{streaming}"``
        stringifies both to ``"...False"``) while taking the truthy
        construction branch, aliasing a streaming-aware client and a
        non-streaming client under the same cache key. Reject explicitly
        rather than silently misbehaving.

        ``bool`` is a subclass of ``int`` but ``isinstance(streaming, bool)``
        still correctly excludes plain ``int``/``str``/``None`` values.
        """
        if not isinstance(streaming, bool):
            raise TypeError(
                "streaming must be a bool, got "
                f"{type(streaming).__name__}: {streaming!r}"
            )
        return streaming

    def get_or_create_client(
        self,
        provider: str,
        config: Dict[str, Any],
        streaming: bool = False,
        *,
        governed: bool = False,
    ) -> Any:
        """Cache separate ordinary, streaming, and governed clients."""
        streaming = self._validate_streaming_flag(streaming)
        if not isinstance(governed, bool):
            raise TypeError("governed must be a bool")
        if governed and streaming:
            raise LLMConfigurationError(
                "Governed response observation supports only non-streaming calls"
            )

        cache_key = self._cache_key(provider, config, streaming, governed)
        with self._cache_lock:
            self._ensure_open()
            if cache_key in self._clients:
                return self._clients[cache_key]
            if governed:
                raise LLMConfigurationError(
                    "Governed clients require awaited async construction"
                )
            client = self._create_langchain_client(provider, config, streaming)
            self._clients[cache_key] = client
            return client

    def _create_langchain_client(
        self,
        provider: str,
        config: Dict[str, Any],
        streaming: bool = False,
        *,
        governed: bool = False,
        owner: ObservedResources | None = None,
    ) -> Any:
        """Build the selected wrapper without mutating any cached client.

        Governed calls use verified modern wrappers with SDK retries disabled.
        Streaming and ungoverned calls retain their existing wrapper defaults.
        """
        streaming = self._validate_streaming_flag(streaming)
        if not isinstance(governed, bool):
            raise TypeError("governed must be a bool")

        api_key = config.get("api_key")
        if not api_key:
            raise LLMConfigurationError(f"No API key found for provider: {provider}")

        model = config.get("model")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens")

        try:
            builder = self._client_builder(provider)
            builder_kwargs: Dict[str, Any] = (
                {"governed": True, "owner": owner} if governed else {}
            )
            return builder(
                api_key,
                model,
                temperature,
                max_tokens,
                streaming,
                **builder_kwargs,
            )

        except ImportError as e:
            raise LLMDependencyError(
                f"Missing dependencies for {provider}. "
                f"Install with: pip install agentmap[{provider}]"
            ) from e

    def _client_builder(self, provider: str) -> Callable[..., Any]:
        """Select the supported provider constructor."""
        builders = {
            "openai": self._create_openai_client,
            "anthropic": self._create_anthropic_client,
            "google": self._create_google_client,
        }
        try:
            return builders[provider]
        except KeyError as error:
            raise LLMConfigurationError(f"Unsupported provider: {provider}") from error

    def _create_openai_client(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        streaming: bool = False,
        *,
        governed: bool = False,
        owner: ObservedResources | None = None,
    ) -> Any:
        """Build OpenAI client, with streaming usage or governed observation."""
        try:
            # Try the new langchain-openai package first
            from langchain_openai import ChatOpenAI
        except ImportError:
            if governed:
                raise LLMDependencyError(
                    "Governed calls require the verified langchain-openai wrapper"
                )
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
        if governed:
            kwargs.update(governed_openai_kwargs(owner))
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
        *,
        governed: bool = False,
        owner: ObservedResources | None = None,
    ) -> Any:
        """Build Anthropic client, with streaming usage or governed observation."""
        try:
            # Try langchain-anthropic first
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            if governed:
                raise LLMDependencyError(
                    "Governed calls require the verified langchain-anthropic wrapper"
                )
            try:
                from langchain_community.chat_models import ChatAnthropic

                self._logger.warning(
                    "Using community LangChain import. Consider upgrading to langchain-anthropic."
                )
            except ImportError:
                try:
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
        if governed:
            return observed_anthropic_client(kwargs, owner)
        return ChatAnthropic(**kwargs)

    def _create_google_client(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        streaming: bool = False,
        *,
        governed: bool = False,
        owner: ObservedResources | None = None,
    ) -> Any:
        """Build Google client; streaming has no verified usage opt-in."""
        try:
            # Try langchain-google-genai first
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            if governed:
                raise LLMDependencyError(
                    "Governed calls require the verified langchain-google-genai wrapper"
                )
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
        if governed:
            kwargs.update(governed_google_kwargs(owner))
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    def clear_cache(self) -> None:
        """Clear the client cache."""
        with self._cache_lock:
            self._ensure_open()
            if self._owners or self._active_governed:
                raise LLMConfigurationError(
                    "Governed clients require awaited shutdown before cache clearing"
                )
            self._clients.clear()
            self._api_key_tokens.clear()
        self._logger.debug("Client cache cleared")
