"""
LLM Fallback Handler for implementing tiered fallback strategies.

Handles multi-tier fallback logic when LLM calls fail, including:
- Tier 1: Same provider, lower complexity model
- Tier 2: Configured fallback provider
- Tier 3: Emergency fallback to first available provider
- Tier 4: Error with full context
"""

from typing import Any, Awaitable, Callable, List, Optional, Sequence

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import LLMMessage, LLMResponse
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm.fallback_ladder import LLMFallbackAsyncLadderMixin
from agentmap.services.llm.provider_names import canonicalize_provider
from agentmap.services.llm.tool_call_extraction import (
    normalize_response_content,
    normalize_response_content_value,
)
from agentmap.services.llm_message_service import LLMMessageService
from agentmap.services.logging_service import LoggingService


class LLMFallbackHandler(LLMFallbackAsyncLadderMixin):
    """Handler for tiered LLM fallback strategies.

    The async ladder (``try_with_fallback_async`` and its private helpers)
    lives on ``LLMFallbackAsyncLadderMixin`` (``services/llm/fallback_ladder.py``,
    NFR-F-006) -- this class supplies the sync ladder, the shared tier-plan
    builder, and the resilience-layer invocation helpers both ladders use.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        routing_config: Optional[LLMRoutingConfigService] = None,
        features_registry: Optional[FeaturesRegistryService] = None,
        invoke_fn: Optional[Callable[..., Any]] = None,
        invoke_async_fn: Optional[Callable[..., Awaitable[LLMResponse]]] = None,
    ):
        """
        Initialize fallback handler.

        Args:
            logging_service: Logging service
            routing_config: Optional routing configuration service
            features_registry: Optional features registry service
            invoke_fn: Optional callable (client, messages, provider, model) -> raw
                       provider content that wraps invocation with resilience
                       (retry + circuit breaker).
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
            raw_content = self._invoke_fn(client, langchain_messages, provider, model)
            text, _ = normalize_response_content_value(raw_content)
        else:
            response = client.invoke(langchain_messages)
            text, _ = normalize_response_content(response)
        return text

    async def _invoke_client_async(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
        **limits: Any,
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
                client, langchain_messages, provider, model, **limits
            )
        if self._invoke_fn is not None:
            raw_content = self._invoke_fn(client, langchain_messages, provider, model)
            text, text_status = normalize_response_content_value(raw_content)
            return LLMResponse(
                text=text,
                resolved_provider=provider,
                resolved_model=model,
                usage=None,
                text_status=text_status,
            )
        # Bare fallback: no resilience layer available; still construct the
        # same safe receipt shape as the resilience path.
        response = client.invoke(langchain_messages)
        text, text_status = normalize_response_content(response)
        return LLMResponse(
            text=text,
            resolved_provider=provider,
            resolved_model=model,
            usage=None,
            text_status=text_status,
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

        provider_matrix = self.routing_config.routing_matrix.get(
            canonicalize_provider(provider), {}
        )
        return provider_matrix.get(complexity.lower())

    def _build_tier_plan(
        self,
        original_provider: str,
        original_model: str,
        eligible_providers: Optional[Sequence[str]] = None,
    ) -> List[tuple[str, str]]:
        """Build the ordered list of (provider, model) pairs to attempt as fallbacks.

        Shared by try_with_fallback (sync) and try_with_fallback_async so the
        tier ordering is defined in one place (DRY — claude.md:101).

        Tier 1: Same provider, low-complexity model (skip if same as original model
                or provider unavailable).
        Tier 2: Configured fallback.default_provider (skip if same as original or
                unavailable).
        Tier 3: Any remaining available provider not already in the plan.

        Returns:
            Ordered list of (provider, model) tuples for permitted providers
            with a low model in the routing matrix.
        """
        configured_provider = (
            self.routing_config.fallback.get("default_provider")
            if self.routing_config
            else None
        )
        original = canonicalize_provider(original_provider)
        configured = (
            canonicalize_provider(configured_provider) if configured_provider else None
        )
        allowed = (
            {canonicalize_provider(provider) for provider in eligible_providers}
            if eligible_providers is not None
            else None
        )

        # Keep the fallback tiers stable: same provider, configured provider,
        # then the remaining eligible providers in request/registry order.
        if eligible_providers is not None:
            candidates = list(eligible_providers)
        else:
            registered = (
                self.features_registry.get_available_providers("llm")
                if self.features_registry
                else []
            )
            if not isinstance(registered, (list, tuple)):
                registered = (
                    list(self.routing_config.routing_matrix)
                    if self.routing_config
                    else []
                )
            candidates = [original_provider]
            if configured_provider:
                candidates.append(configured_provider)
            candidates.extend(registered)

        # Compute the request/registry intersection once using the registry's
        # availability contract, then reuse canonical identities for tier
        # membership and deduplication.
        available: List[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            provider = canonicalize_provider(candidate)
            if provider in seen or (allowed is not None and provider not in allowed):
                continue
            seen.add(provider)
            if self.features_registry and self.features_registry.is_provider_available(
                "llm", provider
            ):
                available.append(provider)

        preferred = [original]
        if configured:
            preferred.append(configured)
        ordered = list(dict.fromkeys([*preferred, *available]))
        available_set = set(available)

        plan: List[tuple[str, str]] = []
        for provider in ordered:
            if provider not in available_set:
                continue
            model = self.get_fallback_model(provider)
            if model and (provider, model) != (original, original_model):
                plan.append((provider, model))
        return plan

    def try_with_fallback(
        self,
        original_provider: str,
        original_model: str,
        messages: List[LLMMessage],
        error: Exception,
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        *,
        eligible_providers: Optional[Sequence[str]] = None,
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
            eligible_providers: Ordered provider allowlist from the routing request
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
        # Strip Anthropic-only cache_control before failover (see async variant).
        langchain_msgs = convert_messages_fn(
            LLMMessageService.strip_cache_control(messages)
        )

        # Use shared tier plan — keeps sync/async ladders in sync (DRY).
        for fallback_provider, fallback_model in self._build_tier_plan(
            original_provider, original_model, eligible_providers
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
