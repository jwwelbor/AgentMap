"""
LLM Fallback Handler for implementing tiered fallback strategies.

Handles multi-tier fallback logic when LLM calls fail, including:
- Tier 1: Same provider, lower complexity model
- Tier 2: Configured fallback provider
- Tier 3: Emergency fallback to first available provider
- Tier 4: Error with full context
"""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from agentmap.exceptions import LLMServiceError
from agentmap.exceptions.service_exceptions import LLMResolvedCallError
from agentmap.models.llm_execution import LLMResponse
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
        invoke_fn: Optional[Callable[..., str]] = None,
        invoke_async_fn: Optional[Callable[..., Awaitable[LLMResponse]]] = None,
    ):
        """
        Initialize fallback handler.

        Args:
            logging_service: Logging service
            routing_config: Optional routing configuration service
            features_registry: Optional features registry service
            invoke_fn: Optional callable (client, messages, provider, model) -> str
                       that wraps invocation with resilience (retry + circuit breaker).
                       When None, falls back to direct ``client.invoke()``.
        """
        self._logger = logging_service.get_class_logger("agentmap.llm.fallback")
        self.routing_config = routing_config
        self.features_registry = features_registry
        self._invoke_fn = invoke_fn
        self._invoke_async_fn = invoke_async_fn

    def _invoke_client(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
    ) -> str:
        """Invoke client through resilience layer when available, else direct."""
        if self._invoke_fn is not None:
            return self._invoke_fn(client, langchain_messages, provider, model)
        response = client.invoke(langchain_messages)
        return response.content if hasattr(response, "content") else str(response)

    async def _invoke_client_async(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
    ) -> LLMResponse:
        """Invoke client through the async resilience layer.

        When ``_invoke_async_fn`` is set (wired to
        ``LLMService._invoke_with_resilience_async``), returns ``LLMResponse``
        carrying the resolved provider, model, and usage extracted from the raw
        response.  When no async fn is set, falls back to a bare sync invoke and
        wraps the result in a minimal ``LLMResponse`` with no usage.
        """
        if self._invoke_async_fn is not None:
            return await self._invoke_async_fn(
                client, langchain_messages, provider, model
            )
        # Bare fallback: no resilience layer available; wrap sync result.
        text = self._invoke_client(client, langchain_messages, provider, model)
        return LLMResponse(
            text=text,
            resolved_provider=provider,
            resolved_model=model,
            usage=None,
        )

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

    def _build_tier_plan(
        self,
        original_provider: str,
        original_model: str,
    ) -> List[tuple]:
        """Build the ordered list of (provider, model) pairs to attempt as fallbacks.

        Shared by try_with_fallback (sync) and try_with_fallback_async so the
        tier ordering is defined in one place (DRY — claude.md:101).

        Tier 1: Same provider, low-complexity model (skip if same as original model
                or provider unavailable).
        Tier 2: Configured fallback.default_provider (skip if same as original or
                unavailable).
        Tier 3: Any remaining available provider not already in the plan.

        Returns:
            Ordered list of (provider, model) tuples. Entries where no low model
            is found in the routing matrix are omitted.
        """
        plan: List[tuple] = []
        seen: set = set()

        def _add(provider: str, model: str) -> None:
            key = (provider, model)
            if key not in seen:
                seen.add(key)
                plan.append(key)

        configured_fallback_provider = (
            self.routing_config.fallback.get("default_provider")
            if self.routing_config
            else None
        )

        # Tier 1: same provider, low-complexity fallback model
        if self.features_registry and self.features_registry.is_provider_available(
            "llm", original_provider
        ):
            tier1_model = self.get_fallback_model(original_provider, "low")
            if tier1_model and tier1_model != original_model:
                _add(original_provider, tier1_model)

        # Tier 2: configured fallback provider
        if (
            configured_fallback_provider
            and configured_fallback_provider != original_provider
            and self.features_registry
            and self.features_registry.is_provider_available(
                "llm", configured_fallback_provider
            )
        ):
            tier2_model = self.get_fallback_model(configured_fallback_provider, "low")
            if tier2_model:
                _add(configured_fallback_provider, tier2_model)

        # Tier 3: emergency — first available provider not already in the plan
        if self.features_registry:
            available = self.features_registry.get_available_providers("llm")
            if not isinstance(available, (list, tuple)):
                available = []
            for provider in available:
                if provider in [original_provider, configured_fallback_provider]:
                    continue
                tier3_model = self.get_fallback_model(provider, "low")
                if tier3_model:
                    _add(provider, tier3_model)

        return plan

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

        # Use shared tier plan — keeps sync/async ladders in sync (DRY).
        for fallback_provider, fallback_model in self._build_tier_plan(
            original_provider, original_model
        ):
            try:
                self._logger.warning(
                    f"Fallback tier: trying '{fallback_provider}:{fallback_model}'"
                )
                attempted_fallbacks.append(f"{fallback_provider}:{fallback_model}")

                config = get_provider_config_fn(fallback_provider)
                config = dict(config)  # defensive copy — avoid mutating shared config
                config["model"] = fallback_model
                client = get_or_create_client_fn(fallback_provider, config)
                langchain_msgs = convert_messages_fn(messages)
                result = self._invoke_client(
                    client, langchain_msgs, fallback_provider, fallback_model
                )
                self._logger.info(
                    f"Fallback tier '{fallback_provider}:{fallback_model}' successful"
                )
                return result
            except Exception as tier_error:
                self._logger.warning(
                    f"Fallback tier '{fallback_provider}:{fallback_model}' failed: {tier_error}"
                )

        # All fallback tiers exhausted
        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {error}"
        )
        self._logger.error(error_msg)
        raise LLMServiceError(error_msg)

    async def try_with_fallback_async(
        self,
        original_provider: str,
        original_model: str,
        messages: List[Dict[str, str]],
        error: Exception,
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        **kwargs,
    ) -> LLMResponse:
        """Async variant of tiered fallback preserving the sync fallback order.

        Returns ``LLMResponse`` carrying the resolved provider, model, and usage
        from the winning fallback tier.

        On exhaustion, raises ``LLMResolvedCallError`` carrying the last-attempted
        tier's identity (policy: last tier wins — the most recent concrete provider
        invoked is the most relevant for observability and debugging).
        """
        self._logger.error(
            f"Model '{original_model}' failed for provider '{original_provider}': {error}"
        )

        attempted_fallbacks = []
        # Last tier actually invoked.
        # Updated immediately before _invoke_client_async so it only reflects providers
        # where an actual network call was attempted (MEDIUM-2 fix).
        last_attempted_provider = original_provider
        last_attempted_model = original_model
        # Last tier's typed exception for use as the cause in LLMResolvedCallError
        # on exhaustion (MEDIUM-1 fix: preserve the typed error discriminator, not
        # a synthetic LLMServiceError wrapper).
        last_error = error

        # Use shared tier plan — keeps sync/async ladders in sync (DRY).
        for fallback_provider, fallback_model in self._build_tier_plan(
            original_provider, original_model
        ):
            try:
                self._logger.warning(
                    f"Fallback tier: trying '{fallback_provider}:{fallback_model}'"
                )
                attempted_fallbacks.append(f"{fallback_provider}:{fallback_model}")

                config = get_provider_config_fn(fallback_provider)
                config = dict(config)  # defensive copy — avoid mutating shared config
                config["model"] = fallback_model
                client = get_or_create_client_fn(fallback_provider, config)
                last_attempted_provider = fallback_provider
                last_attempted_model = fallback_model
                # Update last_attempted before message conversion so it reflects
                # a provider that was actually called (MEDIUM-2 fix).
                langchain_msgs = convert_messages_fn(messages)
                result = await self._invoke_client_async(
                    client, langchain_msgs, fallback_provider, fallback_model
                )
                self._logger.info(
                    f"Fallback tier '{fallback_provider}:{fallback_model}' successful"
                )
                return result
            except Exception as tier_error:
                self._logger.warning(
                    f"Fallback tier '{fallback_provider}:{fallback_model}' failed: {tier_error}"
                )
                last_error = tier_error

        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {error}"
        )
        self._logger.error(error_msg)
        # Raise with the last-attempted tier identity and the last tier's typed
        # error as cause. Using last_error (the actual typed exception from the
        # last invocation) rather than a synthetic LLMServiceError wrapper preserves
        # the error discriminator (LLMTimeoutError, LLMRateLimitError, etc.) for
        # callers that filter on LLMExecutionError.error_type (MEDIUM-1 fix).
        raise LLMResolvedCallError(
            resolved_provider=last_attempted_provider,
            resolved_model=last_attempted_model,
            cause=last_error,
        )
