"""
LLM Service for centralized LLM calling in AgentMap.

Provides a unified interface for calling different LLM providers while
handling configuration, error handling, provider abstraction, and tiered fallback.
"""

import os
from typing import Any, Dict, List, Optional

from agentmap.exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMServiceError,
)
from agentmap.services.config import AppConfigService
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.routing_service import LLMRoutingService

# Import routing types
from agentmap.services.routing.types import RoutingContext

# @runtime_checkable
# class LLMServiceUser(Protocol):
#     """
#     Protocol for agents that use LLM services.

#     To use LLM services in your agent, add this to your __init__:
#         self.llm_service = None

#     Then use it in your methods:
#         response = self.llm_service.call_llm(provider="openai", messages=[...])

#     The service will be automatically injected during graph building.
#     """
#     llm_service: 'LLMService'


class LLMService:
    """
    Centralized service for making LLM calls across different providers.

    Handles provider abstraction, configuration loading, error handling,
    and tiered fallback strategies while maintaining a simple interface for callers.
    """

    def __init__(
        self,
        configuration: AppConfigService,
        logging_service: LoggingService,
        routing_service: LLMRoutingService,
        llm_models_config_service: LLMModelsConfigService,
        features_registry_service: Optional[FeaturesRegistryService] = None,
        routing_config_service: Optional[LLMRoutingConfigService] = None,
    ):
        self.configuration = configuration
        self._clients = {}  # Cache for LangChain clients
        self._logger = logging_service.get_class_logger("agentmap.llm")
        self.routing_service = routing_service
        self.llm_models_config = llm_models_config_service
        self.features_registry = features_registry_service
        self.routing_config = routing_config_service

        # Track whether routing is enabled
        self._routing_enabled = routing_service is not None

    def call_llm(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Make an LLM call with standardized interface.

        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.)
            messages: List of message dictionaries
            model: Optional model override
            temperature: Optional temperature override
            routing_context: Optional routing context for intelligent model selection
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        if (
            routing_context
            and routing_context.get("routing_enabled", False)
            and self.routing_service
        ):
            return self._call_llm_with_routing(messages, routing_context, **kwargs)
        return self._call_llm_direct(
            provider,
            messages,
            model,
            temperature,
            **kwargs,
        )

    def _get_default_model(self, provider: Optional[str] = None) -> str:
        """
        Get default model name for this provider.

        Args:
            provider: Optional provider name (uses self.provider_name if not provided)

        Returns:
            Default model name
        """
        if not provider:
            provider = self.provider_name

        default_model = self.llm_models_config.get_default_model(provider)
        return default_model or self.llm_models_config.get_fallback_model()

    def _normalize_provider(self, provider: str) -> str:
        """Normalize provider name and handle aliases."""
        provider_lower = provider.lower()

        # Handle aliases
        aliases = {"gpt": "openai", "claude": "anthropic", "gemini": "google"}

        return aliases.get(provider_lower, provider_lower)

    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for the specified provider."""
        config = self.configuration.get_llm_config(provider)

        if not config:
            raise LLMConfigurationError(
                f"No configuration found for provider: {provider}"
            )

        # Ensure required fields have defaults
        defaults = self._get_provider_defaults(provider)
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value

        return config

    def _get_provider_defaults(self, provider: str) -> Dict[str, Any]:
        """Get default configuration values for a provider."""
        default_model = self.llm_models_config.get_default_model(provider)

        if not default_model:
            return {}

        # Get API key environment variable name
        api_key_env_var = self._get_api_key_env_var(provider)

        return {
            "model": default_model,
            "temperature": 0.7,
            "api_key": os.environ.get(api_key_env_var, ""),
        }

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

    def _create_openai_client(
        self, api_key: str, model: str, temperature: float
    ) -> Any:
        """Create OpenAI LangChain client."""
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
        """Create Anthropic LangChain client."""
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
        """Create Google LangChain client."""
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

    def _call_llm_with_routing(
        self, messages: List[Dict[str, str]], routing_context: Dict[str, Any], **kwargs
    ) -> str:
        """
        Make an LLM call using intelligent routing to select provider/model.

        Args:
            messages: List of message dictionaries
            routing_context: Dictionary containing routing parameters
            **kwargs: Additional LLM parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: If routing fails or no providers are available
        """
        if not self.routing_service:
            raise LLMServiceError("Routing requested but no routing service available")

        try:
            # Convert routing context dict to RoutingContext object
            context = self._create_routing_context(routing_context, messages)

            # Get available providers from configuration
            available_providers = self._get_available_providers()

            if not available_providers:
                raise LLMServiceError("No providers configured")

            # Extract prompt for routing analysis
            prompt = self._extract_prompt_from_messages(messages)

            # Get routing decision
            decision = self.routing_service.route_request(
                prompt=prompt,
                task_type=context.task_type,
                available_providers=available_providers,
                routing_context=context,
            )

            self._logger.info(
                f"Routing decision: {decision.provider}:{decision.model} "
                f"(complexity: {decision.complexity}, confidence: {decision.confidence:.2f})"
            )

            # Make the actual LLM call with the selected provider/model
            return self._call_llm_direct(
                provider=decision.provider,
                messages=messages,
                model=decision.model,
                temperature=kwargs.get("temperature"),
                **kwargs,
            )

        except Exception as e:
            self._logger.error(f"Routing failed: {e}")
            # Fall back to direct call if routing fails
            fallback_provider = routing_context.get("fallback_provider", "anthropic")
            self._logger.warning(
                f"Falling back to {fallback_provider} due to routing failure"
            )
            return self._call_llm_direct(
                provider=fallback_provider,
                messages=messages,
                model=kwargs.get("model"),
                temperature=kwargs.get("temperature"),
                **kwargs,
            )

    def _get_fallback_model(
        self, provider: str, complexity: str = "low"
    ) -> Optional[str]:
        """
        Get fallback model from routing matrix.

        Args:
            provider: Provider name
            complexity: Complexity level (default: 'low')

        Returns:
            Model name from routing matrix, or None if not found
        """
        if not self.routing_config:
            return None

        provider_matrix = self.routing_config.routing_matrix.get(provider.lower(), {})
        return provider_matrix.get(complexity.lower())

    def _try_with_fallback(
        self,
        original_provider: str,
        original_model: str,
        messages: List[Dict[str, str]],
        error: Exception,
        **kwargs,
    ) -> str:
        """
        Attempt tiered fallback strategy when LLM call fails.

        Tier 1: Same provider, lower complexity model from routing matrix
        Tier 2: Configured fallback provider from routing.fallback.default_provider
        Tier 3: Emergency fallback to first available provider
        Tier 4: Raise error with full context

        Args:
            original_provider: Provider that failed
            original_model: Model that failed
            messages: Messages to send
            error: Original error that triggered fallback
            **kwargs: Additional parameters

        Returns:
            Response string from successful fallback

        Raises:
            LLMServiceError: If all fallback tiers exhausted
        """
        self._logger.error(
            f"Model '{original_model}' failed for provider '{original_provider}': {error}"
        )

        attempted_fallbacks = []

        # Tier 1: Same provider, low complexity model
        if self.features_registry and self.features_registry.is_provider_available(
            "llm", original_provider
        ):
            try:
                fallback_model = self._get_fallback_model(original_provider, "low")
                if fallback_model and fallback_model != original_model:
                    self._logger.warning(
                        f"Tier 1: Retrying with fallback model '{fallback_model}' "
                        f"for provider '{original_provider}'"
                    )
                    attempted_fallbacks.append(f"{original_provider}:{fallback_model}")

                    config = self._get_provider_config(original_provider)
                    config["model"] = fallback_model
                    client = self._get_or_create_client(original_provider, config)
                    response = client.invoke(
                        self._convert_messages_to_langchain(messages)
                    )

                    self._logger.info("Tier 1 fallback successful")
                    return (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
            except Exception as e:
                self._logger.warning(f"Tier 1 fallback failed: {e}")

        # Tier 2: Configured fallback provider
        if self.routing_config:
            fallback_provider = self.routing_config.fallback.get("default_provider")
            if (
                fallback_provider
                and fallback_provider != original_provider
                and self.features_registry
                and self.features_registry.is_provider_available(
                    "llm", fallback_provider
                )
            ):
                try:
                    fallback_model = self._get_fallback_model(fallback_provider, "low")
                    if fallback_model:
                        self._logger.warning(
                            f"Tier 2: Retrying with configured fallback provider "
                            f"'{fallback_provider}' and model '{fallback_model}'"
                        )
                        attempted_fallbacks.append(
                            f"{fallback_provider}:{fallback_model}"
                        )

                        config = self._get_provider_config(fallback_provider)
                        config["model"] = fallback_model
                        client = self._get_or_create_client(fallback_provider, config)
                        response = client.invoke(
                            self._convert_messages_to_langchain(messages)
                        )

                        self._logger.info("Tier 2 fallback successful")
                        return (
                            response.content
                            if hasattr(response, "content")
                            else str(response)
                        )
                except Exception as e:
                    self._logger.warning(f"Tier 2 fallback failed: {e}")

        # Tier 3: Emergency fallback - first available provider
        if self.features_registry:
            available_providers = self.features_registry.get_available_providers("llm")
            for provider in available_providers:
                if provider in [original_provider, fallback_provider]:
                    continue  # Already tried these

                try:
                    fallback_model = self._get_fallback_model(provider, "low")
                    if fallback_model:
                        self._logger.warning(
                            f"Tier 3: Emergency fallback to provider '{provider}' "
                            f"with model '{fallback_model}'"
                        )
                        attempted_fallbacks.append(f"{provider}:{fallback_model}")

                        config = self._get_provider_config(provider)
                        config["model"] = fallback_model
                        client = self._get_or_create_client(provider, config)
                        response = client.invoke(
                            self._convert_messages_to_langchain(messages)
                        )

                        self._logger.info("Tier 3 emergency fallback successful")
                        return (
                            response.content
                            if hasattr(response, "content")
                            else str(response)
                        )
                except Exception as e:
                    self._logger.warning(f"Tier 3 fallback failed for {provider}: {e}")

        # Tier 4: All fallbacks exhausted
        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {error}"
        )
        self._logger.error(error_msg)
        raise LLMServiceError(error_msg)

    def _call_llm_direct(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> str:
        """
        Make a direct LLM call to a specific provider without routing.

        This is the original LLM calling logic that maintains backward compatibility.

        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.)
            messages: List of message dictionaries
            model: Optional model override
            temperature: Optional temperature override
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        try:
            # Normalize provider name
            provider = self._normalize_provider(provider)

            # Get provider configuration
            config = self._get_provider_config(provider)

            # Override model and temperature if provided
            if model:
                config = config.copy()
                config["model"] = model
            if temperature is not None:
                config = config.copy()
                config["temperature"] = temperature

            # Get or create LangChain client
            client = self._get_or_create_client(provider, config)

            # Convert messages to LangChain format
            langchain_messages = self._convert_messages_to_langchain(messages)

            # Make the call
            self._logger.debug(
                f"Making LLM call to {provider} with model {config.get('model')}"
            )
            response = client.invoke(langchain_messages)

            # Extract content from response
            if hasattr(response, "content"):
                result = response.content
            else:
                result = str(response)

            self._logger.debug(f"LLM call successful, response length: {len(result)}")
            return result

        except Exception as e:
            error_msg = f"LLM call failed for provider {provider}: {str(e)}"
            self._logger.error(error_msg)

            # Check for dependency errors - these should NOT trigger fallback
            if (
                isinstance(e, ImportError)
                or "dependencies" in str(e).lower()
                or "install" in str(e).lower()
                or "no module named" in str(e).lower()
            ):
                raise LLMDependencyError(
                    f"Missing dependencies for {provider}: {str(e)}"
                )
            elif (
                "api_key" in str(e).lower()
                or "api key" in str(e).lower()
                or "authentication" in str(e).lower()
            ):
                raise LLMConfigurationError(
                    f"Authentication failed for {provider}: {str(e)}"
                )

            # For model errors or provider errors, try fallback if services available
            if self.features_registry and self.routing_config:
                try:
                    # Get current model from config or parameter
                    current_model = model or config.get("model", "unknown")
                    return self._try_with_fallback(
                        provider, current_model, messages, e, **kwargs
                    )
                except LLMServiceError:
                    # Fallback exhausted, raise original error type
                    pass

            # If it's already one of our custom exception types, preserve it
            if isinstance(
                e,
                (
                    LLMConfigurationError,
                    LLMDependencyError,
                    LLMProviderError,
                    LLMServiceError,
                ),
            ):
                raise e
            elif "model" in str(e).lower():
                raise LLMConfigurationError(
                    f"Model configuration error for {provider}: {str(e)}"
                )
            else:
                raise LLMProviderError(f"Provider {provider} error: {str(e)}")

    def _create_routing_context(
        self, routing_context: Dict[str, Any], messages: List[Dict[str, str]]
    ) -> RoutingContext:
        """
        Convert routing context dictionary to RoutingContext object.

        Args:
            routing_context: Dictionary containing routing parameters
            messages: List of messages for context analysis

        Returns:
            RoutingContext object
        """
        # Extract prompt for complexity analysis
        prompt = self._extract_prompt_from_messages(messages)

        return RoutingContext(
            task_type=routing_context.get("task_type", "general"),
            routing_enabled=routing_context.get("routing_enabled", True),
            activity=routing_context.get("activity"),
            complexity_override=routing_context.get("complexity_override"),
            auto_detect_complexity=routing_context.get("auto_detect_complexity", True),
            provider_preference=routing_context.get("provider_preference", []),
            excluded_providers=routing_context.get("excluded_providers", []),
            model_override=routing_context.get("model_override"),
            max_cost_tier=routing_context.get("max_cost_tier"),
            prompt=prompt,
            input_context=routing_context.get("input_context", {}),
            memory_size=len(messages) - 1 if messages else 0,  # Exclude system message
            input_field_count=routing_context.get("input_field_count", 1),
            cost_optimization=routing_context.get("cost_optimization", True),
            prefer_speed=routing_context.get("prefer_speed", False),
            prefer_quality=routing_context.get("prefer_quality", False),
            fallback_provider=routing_context.get("fallback_provider"),
            fallback_model=routing_context.get("fallback_model"),
            retry_with_lower_complexity=routing_context.get(
                "retry_with_lower_complexity", True
            ),
        )

    def _get_available_providers(self) -> List[str]:
        """
        Get list of providers that are configured and have valid API keys.

        Returns:
            List of available provider names
        """
        available_providers = []

        # Check each provider for configuration and API key
        providers_to_check = ["openai", "anthropic", "google"]

        for provider in providers_to_check:
            try:
                config = self.configuration.get_llm_config(provider)
                if config:
                    # Check if API key is available
                    api_key = config.get("api_key") or os.environ.get(
                        self._get_api_key_env_var(provider)
                    )
                    if api_key:
                        available_providers.append(provider)
                        self._logger.debug(f"Provider {provider} is available")
                    else:
                        self._logger.debug(f"Provider {provider} missing API key")
                else:
                    self._logger.debug(f"Provider {provider} not configured")
            except Exception as e:
                self._logger.debug(f"Provider {provider} check failed: {e}")

        return available_providers

    def _get_api_key_env_var(self, provider: str) -> str:
        """
        Get the environment variable name for a provider's API key.

        Args:
            provider: Provider name

        Returns:
            Environment variable name
        """
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return env_vars.get(provider, f"{provider.upper()}_API_KEY")

    def _extract_prompt_from_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Extract the main prompt content from messages for complexity analysis.

        Args:
            messages: List of message dictionaries

        Returns:
            Combined prompt text
        """
        if not messages:
            return ""

        # Combine all user and system messages
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "system"] and content:
                prompt_parts.append(content)

        return " ".join(prompt_parts)

    def _convert_messages_to_langchain(
        self, messages: List[Dict[str, str]]
    ) -> List[Any]:
        """
        Convert messages to LangChain message format.

        Args:
            messages: List of message dictionaries

        Returns:
            List of LangChain message objects
        """
        try:
            from langchain.schema import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            # Try newer imports
            try:
                from langchain_core.messages import (
                    AIMessage,
                    HumanMessage,
                    SystemMessage,
                )
            except ImportError:
                # Last resort - return as-is and hope the client handles it
                return messages

        langchain_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # default to user
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._clients.clear()
        self._logger.debug("[LLMService] Client cache cleared")

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing service statistics if available.

        Returns:
            Dictionary containing routing statistics or empty dict if no routing service
        """
        if self.routing_service:
            return self.routing_service.get_routing_stats()
        return {}

    def is_routing_enabled(self) -> bool:
        """
        Check if routing is enabled for this service.

        Returns:
            True if routing service is available
        """
        return self._routing_enabled

    def generate(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using LLM with simplified interface.

        Args:
            prompt: The prompt text to generate from
            provider: Optional provider name (defaults to 'anthropic')
            **kwargs: Additional LLM parameters

        Returns:
            Generated text response
        """
        provider = provider or "anthropic"
        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(provider=provider, messages=messages, **kwargs)

    def get_available_providers(self) -> List[str]:
        """
        Public method to get available providers.

        Returns:
            List of available provider names
        """
        return self._get_available_providers()
