"""
LLM Fallback Handler for implementing tiered fallback strategies.

Handles multi-tier fallback logic when LLM calls fail, including:
- Tier 1: Same provider, lower complexity model
- Tier 2: Configured fallback provider
- Tier 3: Emergency fallback to first available provider
- Tier 4: Error with full context
"""

from typing import Any, Dict, List, Optional

from agentmap.exceptions import LLMServiceError
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService


class LLMFallbackHandler:
    """Handler for tiered LLM fallback strategies."""

    def __init__(
        self,
        logging_service: LoggingService,
        routing_config: Optional[LLMRoutingConfigService] = None,
        features_registry: Optional[FeaturesRegistryService] = None,
    ):
        """
        Initialize fallback handler.

        Args:
            logging_service: Logging service
            routing_config: Optional routing configuration service
            features_registry: Optional features registry service
        """
        self._logger = logging_service.get_class_logger("agentmap.llm.fallback")
        self.routing_config = routing_config
        self.features_registry = features_registry

    def get_fallback_model(
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

    def try_with_fallback(
        self,
        original_provider: str,
        original_model: str,
        messages: List[Dict[str, str]],
        error: Exception,
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
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
            get_provider_config_fn: Function to get provider config
            get_or_create_client_fn: Function to get or create client
            convert_messages_fn: Function to convert messages to LangChain format
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
            result = self._try_tier1_fallback(
                original_provider,
                original_model,
                messages,
                attempted_fallbacks,
                get_provider_config_fn,
                get_or_create_client_fn,
                convert_messages_fn,
            )
            if result:
                return result

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
                result = self._try_tier2_fallback(
                    fallback_provider,
                    messages,
                    attempted_fallbacks,
                    get_provider_config_fn,
                    get_or_create_client_fn,
                    convert_messages_fn,
                )
                if result:
                    return result

        # Tier 3: Emergency fallback - first available provider
        if self.features_registry:
            result = self._try_tier3_fallback(
                original_provider,
                self.routing_config.fallback.get("default_provider")
                if self.routing_config
                else None,
                messages,
                attempted_fallbacks,
                get_provider_config_fn,
                get_or_create_client_fn,
                convert_messages_fn,
            )
            if result:
                return result

        # Tier 4: All fallbacks exhausted
        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {error}"
        )
        self._logger.error(error_msg)
        raise LLMServiceError(error_msg)

    def _try_tier1_fallback(
        self,
        original_provider: str,
        original_model: str,
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
    ) -> Optional[str]:
        """
        Try Tier 1 fallback: Same provider, low complexity model.

        Args:
            original_provider: Original provider
            original_model: Original model
            messages: Messages to send
            attempted_fallbacks: List to track attempted fallbacks
            get_provider_config_fn: Function to get provider config
            get_or_create_client_fn: Function to get or create client
            convert_messages_fn: Function to convert messages

        Returns:
            Response string if successful, None otherwise
        """
        try:
            fallback_model = self.get_fallback_model(original_provider, "low")
            if fallback_model and fallback_model != original_model:
                self._logger.warning(
                    f"Tier 1: Retrying with fallback model '{fallback_model}' "
                    f"for provider '{original_provider}'"
                )
                attempted_fallbacks.append(f"{original_provider}:{fallback_model}")

                config = get_provider_config_fn(original_provider)
                config["model"] = fallback_model
                client = get_or_create_client_fn(original_provider, config)
                response = client.invoke(convert_messages_fn(messages))

                self._logger.info("Tier 1 fallback successful")
                return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            self._logger.warning(f"Tier 1 fallback failed: {e}")

        return None

    def _try_tier2_fallback(
        self,
        fallback_provider: str,
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
    ) -> Optional[str]:
        """
        Try Tier 2 fallback: Configured fallback provider.

        Args:
            fallback_provider: Configured fallback provider
            messages: Messages to send
            attempted_fallbacks: List to track attempted fallbacks
            get_provider_config_fn: Function to get provider config
            get_or_create_client_fn: Function to get or create client
            convert_messages_fn: Function to convert messages

        Returns:
            Response string if successful, None otherwise
        """
        try:
            fallback_model = self.get_fallback_model(fallback_provider, "low")
            if fallback_model:
                self._logger.warning(
                    f"Tier 2: Retrying with configured fallback provider "
                    f"'{fallback_provider}' and model '{fallback_model}'"
                )
                attempted_fallbacks.append(f"{fallback_provider}:{fallback_model}")

                config = get_provider_config_fn(fallback_provider)
                config["model"] = fallback_model
                client = get_or_create_client_fn(fallback_provider, config)
                response = client.invoke(convert_messages_fn(messages))

                self._logger.info("Tier 2 fallback successful")
                return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            self._logger.warning(f"Tier 2 fallback failed: {e}")

        return None

    def _try_tier3_fallback(
        self,
        original_provider: str,
        configured_fallback_provider: Optional[str],
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
    ) -> Optional[str]:
        """
        Try Tier 3 fallback: Emergency fallback to first available provider.

        Args:
            original_provider: Original provider to skip
            configured_fallback_provider: Configured fallback provider to skip
            messages: Messages to send
            attempted_fallbacks: List to track attempted fallbacks
            get_provider_config_fn: Function to get provider config
            get_or_create_client_fn: Function to get or create client
            convert_messages_fn: Function to convert messages

        Returns:
            Response string if successful, None otherwise
        """
        available_providers = self.features_registry.get_available_providers("llm")
        for provider in available_providers:
            if provider in [original_provider, configured_fallback_provider]:
                continue  # Already tried these

            try:
                fallback_model = self.get_fallback_model(provider, "low")
                if fallback_model:
                    self._logger.warning(
                        f"Tier 3: Emergency fallback to provider '{provider}' "
                        f"with model '{fallback_model}'"
                    )
                    attempted_fallbacks.append(f"{provider}:{fallback_model}")

                    config = get_provider_config_fn(provider)
                    config["model"] = fallback_model
                    client = get_or_create_client_fn(provider, config)
                    response = client.invoke(convert_messages_fn(messages))

                    self._logger.info("Tier 3 emergency fallback successful")
                    return response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                self._logger.warning(f"Tier 3 fallback failed for {provider}: {e}")

        return None
