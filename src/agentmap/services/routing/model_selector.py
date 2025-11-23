"""
Model selection utilities for LLM routing.

This module provides helper functions for selecting optimal models based on
provider preferences, cost optimization, and availability constraints.
"""

from typing import List, Optional

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.routing.types import (
    RoutingDecision,
    TaskComplexity,
)


class ModelSelector:
    """
    Handles model selection logic for the routing service.

    Provides methods for selecting models from preferred providers,
    applying cost optimization, and handling model overrides.
    """

    def __init__(
        self,
        routing_config: LLMRoutingConfigService,
        logger,
    ):
        """
        Initialize the model selector.

        Args:
            routing_config: Routing configuration service
            logger: Logger instance for logging
        """
        self.routing_config = routing_config
        self._logger = logger

    def handle_model_override(
        self,
        model_override: str,
        complexity: TaskComplexity,
        available_providers: List[str],
        create_emergency_fallback,
    ) -> RoutingDecision:
        """
        Handle explicit model override.

        Args:
            model_override: The model to use as override
            complexity: Task complexity level
            available_providers: List of available providers
            create_emergency_fallback: Callback function for emergency fallback

        Returns:
            Routing decision for the override
        """
        # Try to find the provider for this model
        for provider in available_providers:
            provider_matrix = self.routing_config.routing_matrix.get(
                provider.lower(), {}
            )
            if model_override in provider_matrix.values():
                return RoutingDecision(
                    provider=provider,
                    model=model_override,
                    complexity=complexity,
                    confidence=1.0,
                    reasoning=f"Model override: {model_override}",
                    fallback_used=False,
                )

        # Model not found in available providers
        self._logger.warning(
            f"Model override '{model_override}' not available in providers {available_providers}"
        )
        return create_emergency_fallback(
            available_providers, f"Model override '{model_override}' not available"
        )

    def filter_available_providers(
        self,
        preferred_providers: List[str],
        available_providers: List[str],
        excluded_providers: List[str],
    ) -> List[str]:
        """
        Filter providers by availability and exclusions.

        Args:
            preferred_providers: List of preferred providers
            available_providers: List of available providers
            excluded_providers: List of providers to exclude

        Returns:
            Filtered list of available preferred providers
        """
        available_set = set(p.lower() for p in available_providers)
        excluded_set = set(p.lower() for p in excluded_providers)

        filtered = []
        for provider in preferred_providers:
            provider_lower = provider.lower()
            if provider_lower in available_set and provider_lower not in excluded_set:
                filtered.append(provider_lower)

        return filtered

    def apply_cost_optimization(
        self,
        providers: List[str],
        complexity: TaskComplexity,
        max_cost_tier: Optional[str],
    ) -> List[str]:
        """
        Apply cost optimization constraints.

        Args:
            providers: List of providers to filter
            complexity: Task complexity level
            max_cost_tier: Maximum allowed cost tier

        Returns:
            Filtered list of providers based on cost constraints
        """
        # TODO: Implement cost optimization logic.
        # For now, return all providers (cost optimization logic can be enhanced)
        return providers

    def select_from_preferred_providers(
        self, preferred_providers: List[str], task_type: str, complexity: TaskComplexity
    ) -> Optional[RoutingDecision]:
        """
        Select a model from preferred providers.

        Args:
            preferred_providers: List of preferred providers
            task_type: Type of task being performed
            complexity: Task complexity level

        Returns:
            Routing decision if a model was found, None otherwise
        """
        complexity_str = str(complexity).lower()

        for provider in preferred_providers:
            model = self.routing_config.get_model_for_complexity(
                provider, complexity_str
            )
            if model:
                return RoutingDecision(
                    provider=provider,
                    model=model,
                    complexity=complexity,
                    confidence=0.9,
                    reasoning=f"Selected from routing matrix: {provider}({complexity_str})",
                    fallback_used=False,
                )

        return None
