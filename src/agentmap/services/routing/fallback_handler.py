"""
Fallback handling for LLM routing.

This module provides fallback strategy management for when preferred
providers are unavailable or routing fails.
"""

from typing import List

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
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
            available_providers: List of available providers
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

        # Compute lowercase available providers once for efficiency
        available_providers_lower = [p.lower() for p in available_providers]
        available_providers_set = set(available_providers_lower)

        # Strategy 1: Try lower complexity if enabled
        if (
            routing_context.retry_with_lower_complexity
            and complexity != TaskComplexity.LOW
        ):
            lower_complexity = self.get_lower_complexity(complexity)
            decision = select_from_preferred_providers(
                available_providers_lower, task_type, lower_complexity
            )
            if decision:
                decision.fallback_used = True
                decision.reasoning = f"Fallback: lowered complexity from {complexity} to {lower_complexity}"
                decision.confidence = 0.6
                return decision

        # Strategy 2: Use configured fallback provider/model
        fallback_provider = (
            routing_context.fallback_provider
            or self.routing_config.get_fallback_provider()
        )
        fallback_model = (
            routing_context.fallback_model or self.routing_config.get_fallback_model()
        )

        if fallback_provider.lower() in available_providers_set:
            return RoutingDecision(
                provider=fallback_provider,
                model=fallback_model,
                complexity=complexity,
                confidence=0.5,
                reasoning=f"Configured fallback: {fallback_provider}:{fallback_model}",
                fallback_used=True,
            )

        # Strategy 3: Emergency fallback to first available provider
        return self.create_emergency_fallback(
            available_providers, "All fallback strategies exhausted"
        )

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

        # Use first available provider with its lowest complexity model
        provider = available_providers[0]
        provider_matrix = self.routing_config.routing_matrix.get(provider.lower(), {})

        # Try to get the lowest complexity model using the enum-based list
        for complexity_level in VALID_COMPLEXITY_LEVELS:
            if complexity_level in provider_matrix:
                model = provider_matrix[complexity_level]
                return RoutingDecision(
                    provider=provider,
                    model=model,
                    complexity=TaskComplexity.LOW,
                    confidence=0.3,
                    reasoning=f"Emergency fallback: {reason}",
                    fallback_used=True,
                )

        # Last resort: use system fallback model
        fallback_model = self.routing_config.get_fallback_model()
        return RoutingDecision(
            provider=provider,
            model=fallback_model,
            complexity=TaskComplexity.LOW,
            confidence=0.1,
            reasoning=f"Last resort fallback: {reason}",
            fallback_used=True,
        )
