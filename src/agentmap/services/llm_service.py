"""
LLM Service for centralized LLM calling in AgentMap.

Provides a unified interface for calling different LLM providers while
handling configuration, error handling, provider abstraction, tiered fallback,
and resilience (retry with backoff + circuit breaker).
"""

import random
import time
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
from agentmap.services.llm_client_factory import LLMClientFactory
from agentmap.services.llm_error_utils import classify_llm_error, is_retryable
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_message_utils import LLMMessageUtils
from agentmap.services.llm_provider_utils import LLMProviderUtils
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.circuit_breaker import CircuitBreaker
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import RoutingContext


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
        """
        Initialize the LLM service.

        Args:
            configuration: Application configuration service
            logging_service: Logging service
            routing_service: LLM routing service
            llm_models_config_service: LLM models configuration service
            features_registry_service: Optional features registry service
            routing_config_service: Optional routing configuration service
        """
        self.configuration = configuration
        self._logger = logging_service.get_class_logger("agentmap.llm")
        self.routing_service = routing_service
        self.llm_models_config = llm_models_config_service
        self.features_registry = features_registry_service
        self.routing_config = routing_config_service

        # Initialize helper components
        self._client_factory = LLMClientFactory(logging_service)
        self._provider_utils = LLMProviderUtils(
            configuration, llm_models_config_service, logging_service
        )
        self._fallback_handler = LLMFallbackHandler(
            logging_service,
            routing_config_service,
            features_registry_service,
            invoke_fn=self._invoke_with_resilience,
        )
        self._message_utils = LLMMessageUtils()

        # Resilience: retry + circuit breaker
        self._resilience_config = configuration.get_llm_resilience_config()
        cb_cfg = self._resilience_config.get("circuit_breaker", {})
        self._circuit_breaker = CircuitBreaker(
            failures_threshold=cb_cfg.get("failure_threshold", 5),
            reset_seconds=cb_cfg.get("reset_timeout", 60),
        )

        # Track whether routing is enabled
        self._routing_enabled = routing_service is not None

    @property
    def _clients(self):
        """Backwards compatibility accessor for client cache."""
        return self._client_factory._clients

    def _normalize_provider(self, provider: str) -> str:
        """Backwards compatibility wrapper for normalize_provider."""
        return self._provider_utils.normalize_provider(provider)

    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Backwards compatibility wrapper for get_provider_config."""
        return self._provider_utils.get_provider_config(provider)

    def _get_available_providers(self) -> List[str]:
        """Backwards compatibility wrapper for get_available_providers."""
        return self._provider_utils.get_available_providers()

    def _create_langchain_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Backwards compatibility wrapper for create_langchain_client."""
        return self._client_factory._create_langchain_client(provider, config)

    def _get_or_create_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Backwards compatibility wrapper for get_or_create_client."""
        return self._client_factory.get_or_create_client(provider, config)

    def _convert_messages_to_langchain(
        self, messages: List[Dict[str, str]]
    ) -> List[Any]:
        """Backwards compatibility wrapper for convert_messages_to_langchain."""
        return self._message_utils.convert_messages_to_langchain(messages)

    def _extract_prompt_from_messages(self, messages: List[Dict[str, str]]) -> str:
        """Backwards compatibility wrapper for extract_prompt_from_messages."""
        return self._message_utils.extract_prompt_from_messages(messages)

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Make an LLM call with standardized interface.

        When routing_context is provided, routing owns all provider and model selection.
        The provider and model parameters are ignored in that case — use
        routing_context['provider_preference'] / routing_context['fallback_provider'] and
        routing_context['model_override'] instead. Warnings are logged if provider or model
        are passed alongside routing_context.

        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.).
                      Ignored when routing_context is provided.
            messages: List of message dictionaries
            model: Optional model override. Ignored when routing_context is provided.
            temperature: Optional temperature override
            routing_context: Optional routing context for intelligent model selection.
                             When present, routing owns all provider/model decisions.
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        if routing_context is not None and self.routing_service:
            if model is not None:
                self._logger.warning(
                    "[LLMService] 'model' parameter is ignored when routing_context is provided. "
                    "Use routing_context['model_override'] to force a specific model."
                )
            if provider is not None:
                self._logger.warning(
                    "[LLMService] 'provider' parameter is ignored when routing_context is provided. "
                    "Use routing_context['provider_preference'] to influence provider selection "
                    "or routing_context['fallback_provider'] to set the fallback."
                )
            return self._call_llm_with_routing(messages, routing_context, **kwargs)
        if not provider:
            raise LLMServiceError(
                "provider is required when routing_context is not provided."
            )
        return self._call_llm_direct(
            provider,
            messages,
            model,
            temperature,
            **kwargs,
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
            available_providers = self._provider_utils.get_available_providers()

            if not available_providers:
                raise LLMServiceError("No providers configured")

            # Extract prompt for routing analysis
            prompt = self._message_utils.extract_prompt_from_messages(messages)

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

        Uses ``_invoke_with_resilience`` for retry + circuit breaker, then
        falls back through tiered providers if routing config is available.

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
            provider = self._provider_utils.normalize_provider(provider)

            # Get provider configuration
            config = self._provider_utils.get_provider_config(provider)

            # Override model and temperature if provided
            if model:
                config = config.copy()
                config["model"] = model
            if temperature is not None:
                config = config.copy()
                config["temperature"] = temperature

            # Get or create LangChain client
            client = self._client_factory.get_or_create_client(provider, config)

            # Convert messages to LangChain format
            langchain_messages = self._message_utils.convert_messages_to_langchain(
                messages
            )

            # Make the call with resilience (retry + circuit breaker)
            current_model = config.get("model", "unknown")
            return self._invoke_with_resilience(
                client, langchain_messages, provider, current_model
            )

        except Exception as e:
            # Classify the error
            typed_error = classify_llm_error(e, provider)

            # Dependency and config errors should NOT trigger fallback
            if isinstance(typed_error, (LLMDependencyError, LLMConfigurationError)):
                raise typed_error

            # For provider errors, try fallback if services available
            if self.features_registry and self.routing_config:
                try:
                    current_model = model or config.get("model", "unknown")
                    return self._fallback_handler.try_with_fallback(
                        provider,
                        current_model,
                        messages,
                        typed_error,
                        self._provider_utils.get_provider_config,
                        self._client_factory.get_or_create_client,
                        self._message_utils.convert_messages_to_langchain,
                        **kwargs,
                    )
                except LLMServiceError:
                    # Fallback exhausted, raise original typed error
                    pass

            raise typed_error

    def _invoke_with_resilience(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
    ) -> str:
        """
        Invoke an LLM client with retry + circuit breaker protection.

        Args:
            client: LangChain chat model client.
            langchain_messages: Pre-converted LangChain message list.
            provider: Provider name (for circuit breaker keying).
            model: Model name (for circuit breaker keying).

        Returns:
            Response text string.

        Raises:
            LLMProviderError (or subclass): After retries exhausted or
                circuit open or non-retryable error.
        """
        # Circuit breaker check
        if self._circuit_breaker.is_open(provider, model):
            raise LLMProviderError(
                f"Circuit breaker open for {provider}:{model} — "
                f"skipping call (resets after "
                f"{self._circuit_breaker.reset}s)"
            )

        retry_cfg = self._resilience_config.get("retry", {})
        max_attempts = retry_cfg.get("max_attempts", 3)
        backoff_base = retry_cfg.get("backoff_base", 2.0)
        backoff_max = retry_cfg.get("backoff_max", 30.0)
        jitter = retry_cfg.get("jitter", True)

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                self._logger.debug(
                    f"LLM call to {provider}:{model} (attempt {attempt}/{max_attempts})"
                )
                response = client.invoke(langchain_messages)

                # Extract content
                result = (
                    response.content if hasattr(response, "content") else str(response)
                )

                self._circuit_breaker.record_success(provider, model)
                self._logger.debug(
                    f"LLM call successful, response length: {len(result)}"
                )
                return result

            except Exception as e:
                typed_error = classify_llm_error(e, provider)
                last_error = typed_error

                # Non-retryable → fail immediately
                if not is_retryable(typed_error):
                    self._circuit_breaker.record_failure(provider, model)
                    raise typed_error

                # Last attempt → no more retries
                if attempt == max_attempts:
                    break

                # Exponential backoff with optional jitter
                delay = min(backoff_base ** (attempt - 1), backoff_max)
                if jitter:
                    delay = delay * (0.5 + random.random())

                self._logger.warning(
                    f"Retryable error on {provider}:{model} "
                    f"(attempt {attempt}/{max_attempts}): {typed_error}. "
                    f"Retrying in {delay:.1f}s"
                )
                time.sleep(delay)

        # All retries exhausted
        self._circuit_breaker.record_failure(provider, model)
        raise last_error  # type: ignore[misc]

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
        prompt = self._message_utils.extract_prompt_from_messages(messages)

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

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._client_factory.clear_cache()
        self._logger.debug("[LLMService] Client cache cleared")

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing service statistics if available.

        Returns:
            Dictionary containing routing statistics, circuit breaker state,
            or empty dict if no routing service.
        """
        stats: Dict[str, Any] = {}
        if self.routing_service:
            stats.update(self.routing_service.get_routing_stats())

        # Append circuit breaker state
        cb = self._circuit_breaker
        stats["circuit_breaker"] = {
            "open_circuits": list(cb.opened_at.keys()),
            "failure_counts": dict(cb.failures),
        }
        return stats

    def is_routing_enabled(self) -> bool:
        """
        Check if routing is enabled for this service.

        Returns:
            True if routing service is available
        """
        return self._routing_enabled

    def ask(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Ask the LLM a single plain-string question.

        Convenience wrapper around call_llm() for simple single-turn prompts
        that don't require constructing a messages list.

        Args:
            prompt: The prompt text to send
            provider: Optional provider name (defaults to 'anthropic')
            **kwargs: Additional LLM parameters (e.g. temperature, model)

        Returns:
            Response text string
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
        return self._provider_utils.get_available_providers()
