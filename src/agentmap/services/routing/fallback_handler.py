"""
Fallback handling for LLM routing.

This module provides fallback strategy management for when preferred
providers are unavailable or routing fails.
"""

from typing import List

from agentmap.exceptions.service_exceptions import LLMConfigurationError
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.llm.provider_names import canonicalize_provider
from agentmap.services.routing.types import (
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
    get_complexity_order,
    get_valid_complexity_levels,
)

# Module-level constants
COMPLEXITY_ORDER = get_complexity_order()
VALID_COMPLEXITY_LEVELS = get_valid_complexity_levels()


class FallbackHandler:
    """
    Handles fallback strategies for the routing service.

    Provides methods for applying fallback strategies when preferred
    providers are unavailable, including complexity downgrade and
    emergency fallback handling.
    """

    def __init__(
        self,
        routing_config: LLMRoutingConfigService,
        logger,
    ):
        """
        Initialize the fallback handler.

        Args:
            routing_config: Routing configuration service
            logger: Logger instance for logging
        """
        self.routing_config = routing_config
        self._logger = logger

    def apply_fallback_strategy(
        self,
        available_providers: List[str],
        task_type: str,
        complexity: TaskComplexity,
        routing_context: RoutingContext,
        select_from_preferred_providers,
    ) -> RoutingDecision:
        """
        Apply fallback strategy when preferred providers unavailable.

        Args:
            available_providers: Available providers after applying request exclusions
            task_type: Type of task being performed
            complexity: Task complexity level
            routing_context: Routing context and preferences
            select_from_preferred_providers: Callback for selecting from providers

        Returns:
            Routing decision from fallback strategy
        """
        self._logger.warning(
            f"Applying fallback strategy for {task_type}({complexity})"
        )

        # Strategy 1: Try lower complexity if enabled
        if (
            routing_context.retry_with_lower_complexity
            and complexity != TaskComplexity.LOW
        ):
            lower_complexity = self.get_lower_complexity(complexity)
            decision = select_from_preferred_providers(
                available_providers, task_type, lower_complexity
            )
            if decision:
                decision.fallback_used = True
                decision.reasoning = f"Fallback: lowered complexity from {complexity} to {lower_complexity}"
                decision.confidence = 0.6
                return decision

        return self.select_fallback(
            available_providers,
            complexity,
            routing_context,
            "All fallback strategies exhausted",
        )

    def select_fallback(
        self,
        available_providers: List[str],
        complexity: TaskComplexity,
        routing_context: RoutingContext,
        reason: str,
    ) -> RoutingDecision:
        """Select the configured fallback if eligible, otherwise recover in order."""
        default_provider = canonicalize_provider(
            self.routing_config.get_fallback_provider()
        )
        provider = canonicalize_provider(
            routing_context.fallback_provider or default_provider
        )
        if provider not in set(map(canonicalize_provider, available_providers)):
            return self.create_emergency_fallback(available_providers, reason)

        model = routing_context.fallback_model
        if not model and provider == default_provider:
            model = self.routing_config.fallback.get("default_model")
        if not model:
            try:
                model = self._require_provider_default(provider)
            except LLMConfigurationError:
                return self.create_emergency_fallback(available_providers, reason)
        return RoutingDecision(
            provider=provider,
            model=model,
            complexity=complexity,
            confidence=0.5,
            reasoning=f"Configured fallback: {provider}:{model}",
            fallback_used=True,
        )

    def _require_provider_default(self, provider: str) -> str:
        model = self.routing_config.get_provider_default_model(provider)
        if not model:
            raise LLMConfigurationError(
                f"No fallback model configured for provider '{provider}'"
            )
        return model

    def get_lower_complexity(self, complexity: TaskComplexity) -> TaskComplexity:
        """
        Get the next lower complexity level.

        Args:
            complexity: Current complexity level

        Returns:
            Next lower complexity level
        """
        current_index = COMPLEXITY_ORDER.index(complexity)
        if current_index > 0:
            return COMPLEXITY_ORDER[current_index - 1]
        return complexity

    def create_emergency_fallback(
        self, available_providers: List[str], reason: str
    ) -> RoutingDecision:
        """
        Create an emergency fallback decision.

        Args:
            available_providers: List of available providers
            reason: Reason for emergency fallback

        Returns:
            Emergency routing decision

        Raises:
            ValueError: If no providers are available
        """
        if not available_providers:
            raise ValueError("No providers available for emergency fallback")

        last_model_error = None
        for provider in available_providers:
            provider_key = canonicalize_provider(provider)
            provider_matrix = self.routing_config.routing_matrix.get(provider_key, {})

            for complexity_level in VALID_COMPLEXITY_LEVELS:
                model = provider_matrix.get(complexity_level)
                if model:
                    return RoutingDecision(
                        provider=provider,
                        model=model,
                        complexity=TaskComplexity.LOW,
                        confidence=0.3,
                        reasoning=f"Emergency fallback: {reason}",
                        fallback_used=True,
                    )

            try:
                model = self._require_provider_default(provider_key)
            except LLMConfigurationError as error:
                last_model_error = error
                continue

            return RoutingDecision(
                provider=provider,
                model=model,
                complexity=TaskComplexity.LOW,
                confidence=0.1,
                reasoning=f"Last resort fallback: {reason}",
                fallback_used=True,
            )

        if last_model_error:
            raise last_model_error
        raise LLMConfigurationError(
            "No fallback model configured for any eligible provider"
        )
