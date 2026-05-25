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
        invoke_async_fn: Optional[Callable[..., Awaitable[str]]] = None,
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

        # Tier 1: same provider, low-complexity fallback model
        if self.features_registry and self.features_registry.is_provider_available(
            "llm", original_provider
        ):
            tier1_model = self.get_fallback_model(original_provider, "low")
            if tier1_model and tier1_model != original_model:
                _add(original_provider, tier1_model)

        # Tier 2: configured fallback provider
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
                tier2_model = self.get_fallback_model(fallback_provider, "low")
                if tier2_model:
                    _add(fallback_provider, tier2_model)

        # Tier 3: emergency — first available provider not already in the plan
        if self.features_registry:
            configured_fallback = (
                self.routing_config.fallback.get("default_provider")
                if self.routing_config
                else None
            )
            available = self.features_registry.get_available_providers("llm")
            if not isinstance(available, (list, tuple)):
                available = []
            for provider in available:
                if provider in [original_provider, configured_fallback]:
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
        # One-element mutable cell: [provider, model] of the last tier actually invoked.
        # Updated immediately before _invoke_client_async so it only reflects providers
        # where an actual network call was attempted (MEDIUM-2 fix).
        last_attempted = [original_provider, original_model]
        # Mutable cell holding the last tier's typed exception for use as the
        # cause in LLMResolvedCallError on exhaustion (MEDIUM-1 fix: preserve
        # the typed error discriminator, not a synthetic LLMServiceError wrapper).
        last_error = [error]

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
                # Update last_attempted immediately before the invocation so it
                # reflects a provider that was actually called (MEDIUM-2 fix).
                last_attempted[0] = fallback_provider
                last_attempted[1] = fallback_model
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
                last_error[0] = tier_error

        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {error}"
        )
        self._logger.error(error_msg)
        # Raise with the last-attempted tier identity and the last tier's typed
        # error as cause. Using last_error[0] (the actual typed exception from the
        # last invocation) rather than a synthetic LLMServiceError wrapper preserves
        # the error discriminator (LLMTimeoutError, LLMRateLimitError, etc.) for
        # callers that filter on LLMExecutionError.error_type (MEDIUM-1 fix).
        raise LLMResolvedCallError(
            resolved_provider=last_attempted[0],
            resolved_model=last_attempted[1],
            cause=last_error[0],
        )

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
                config = dict(
                    config
                )  # defensive copy — avoid mutating shared provider config
                config["model"] = fallback_model
                client = get_or_create_client_fn(original_provider, config)
                langchain_msgs = convert_messages_fn(messages)
                result = self._invoke_client(
                    client, langchain_msgs, original_provider, fallback_model
                )

                self._logger.info("Tier 1 fallback successful")
                return result
        except Exception as e:
            self._logger.warning(f"Tier 1 fallback failed: {e}")

        return None

    async def _try_tier1_fallback_async(
        self,
        original_provider: str,
        original_model: str,
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        last_attempted: Optional[List[str]] = None,
        last_error: Optional[List[Exception]] = None,
    ) -> Optional[LLMResponse]:
        """Async Tier 1 fallback using the async resilience layer."""
        try:
            fallback_model = self.get_fallback_model(original_provider, "low")
            if fallback_model and fallback_model != original_model:
                self._logger.warning(
                    f"Tier 1: Retrying with fallback model '{fallback_model}' "
                    f"for provider '{original_provider}'"
                )
                attempted_fallbacks.append(f"{original_provider}:{fallback_model}")

                config = get_provider_config_fn(original_provider)
                config = dict(
                    config
                )  # defensive copy — avoid mutating shared provider config
                config["model"] = fallback_model
                client = get_or_create_client_fn(original_provider, config)
                langchain_msgs = convert_messages_fn(messages)
                # Update last_attempted immediately before the invocation so it
                # reflects a provider that was actually called (MEDIUM-2 fix).
                if last_attempted is not None:
                    last_attempted[0] = original_provider
                    last_attempted[1] = fallback_model
                result = await self._invoke_client_async(
                    client, langchain_msgs, original_provider, fallback_model
                )

                self._logger.info("Tier 1 fallback successful")
                return result
        except Exception as e:
            self._logger.warning(f"Tier 1 fallback failed: {e}")
            if last_error is not None:
                last_error[0] = e

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
                config = dict(
                    config
                )  # defensive copy — avoid mutating shared provider config
                config["model"] = fallback_model
                client = get_or_create_client_fn(fallback_provider, config)
                langchain_msgs = convert_messages_fn(messages)
                result = self._invoke_client(
                    client, langchain_msgs, fallback_provider, fallback_model
                )

                self._logger.info("Tier 2 fallback successful")
                return result
        except Exception as e:
            self._logger.warning(f"Tier 2 fallback failed: {e}")

        return None

    async def _try_tier2_fallback_async(
        self,
        fallback_provider: str,
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        last_attempted: Optional[List[str]] = None,
        last_error: Optional[List[Exception]] = None,
    ) -> Optional[LLMResponse]:
        """Async Tier 2 fallback using the async resilience layer."""
        try:
            fallback_model = self.get_fallback_model(fallback_provider, "low")
            if fallback_model:
                self._logger.warning(
                    f"Tier 2: Retrying with configured fallback provider "
                    f"'{fallback_provider}' and model '{fallback_model}'"
                )
                attempted_fallbacks.append(f"{fallback_provider}:{fallback_model}")

                config = get_provider_config_fn(fallback_provider)
                config = dict(
                    config
                )  # defensive copy — avoid mutating shared provider config
                config["model"] = fallback_model
                client = get_or_create_client_fn(fallback_provider, config)
                langchain_msgs = convert_messages_fn(messages)
                # Update last_attempted immediately before the invocation so it
                # reflects a provider that was actually called (MEDIUM-2 fix).
                if last_attempted is not None:
                    last_attempted[0] = fallback_provider
                    last_attempted[1] = fallback_model
                result = await self._invoke_client_async(
                    client, langchain_msgs, fallback_provider, fallback_model
                )

                self._logger.info("Tier 2 fallback successful")
                return result
        except Exception as e:
            self._logger.warning(f"Tier 2 fallback failed: {e}")
            if last_error is not None:
                last_error[0] = e

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
                    config = dict(
                        config
                    )  # defensive copy — avoid mutating shared provider config
                    config["model"] = fallback_model
                    client = get_or_create_client_fn(provider, config)
                    langchain_msgs = convert_messages_fn(messages)
                    result = self._invoke_client(
                        client, langchain_msgs, provider, fallback_model
                    )

                    self._logger.info("Tier 3 emergency fallback successful")
                    return result
            except Exception as e:
                self._logger.warning(f"Tier 3 fallback failed for {provider}: {e}")

        return None

    async def _try_tier3_fallback_async(
        self,
        original_provider: str,
        configured_fallback_provider: Optional[str],
        messages: List[Dict[str, str]],
        attempted_fallbacks: List[str],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        last_attempted: Optional[List[str]] = None,
        last_error: Optional[List[Exception]] = None,
    ) -> Optional[LLMResponse]:
        """Async Tier 3 fallback using the async resilience layer."""
        available_providers = self.features_registry.get_available_providers("llm")
        for provider in available_providers:
            if provider in [original_provider, configured_fallback_provider]:
                continue

            try:
                fallback_model = self.get_fallback_model(provider, "low")
                if fallback_model:
                    self._logger.warning(
                        f"Tier 3: Emergency fallback to provider '{provider}' "
                        f"with model '{fallback_model}'"
                    )
                    attempted_fallbacks.append(f"{provider}:{fallback_model}")

                    config = get_provider_config_fn(provider)
                    config = dict(
                        config
                    )  # defensive copy — avoid mutating shared provider config
                    config["model"] = fallback_model
                    client = get_or_create_client_fn(provider, config)
                    langchain_msgs = convert_messages_fn(messages)
                    # Update last_attempted immediately before the invocation so it
                    # reflects a provider that was actually called (MEDIUM-2 fix).
                    if last_attempted is not None:
                        last_attempted[0] = provider
                        last_attempted[1] = fallback_model
                    result = await self._invoke_client_async(
                        client, langchain_msgs, provider, fallback_model
                    )

                    self._logger.info("Tier 3 fallback successful")
                    return result
            except Exception as e:
                self._logger.warning(f"Tier 3 fallback failed for {provider}: {e}")
                if last_error is not None:
                    last_error[0] = e

        return None
