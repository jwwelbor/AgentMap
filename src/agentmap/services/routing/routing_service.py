"""
Core LLM routing service for AgentMap.

This module provides the main routing service that orchestrates complexity analysis,
matrix lookups, provider selection, and fallback strategies for optimal LLM routing.
"""

import time
from typing import Any, Dict, List, Optional

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.cache import RoutingCache
from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer
from agentmap.services.routing.types import (
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
)

# if TYPE_CHECKING:
#     from agentmap.config.sections.routing import RoutingConfigSection


class LLMRoutingService:
    """
    Core LLM routing service that orchestrates all routing components.

    Provides intelligent model selection based on task complexity, provider
    preferences, cost optimization, and availability constraints.
    """

    def __init__(
        self,
        llm_routing_config_service: LLMRoutingConfigService,
        logging_service: LoggingService,
        routing_cache: RoutingCache,
        prompt_complexity_analyzer: PromptComplexityAnalyzer,
    ):
        """
        Initialize the LLM routing service.

        Args:
            routing_config: Routing configuration section
            logging_service: Logging service for structured logging
        """
        self.routing_config = llm_routing_config_service
        self._logger = logging_service.get_class_logger(self)
        self.cache = routing_cache

        # Initialize components
        self.complexity_analyzer = prompt_complexity_analyzer

        # Initialize cache if enabled
        if self.routing_config.is_routing_cache_enabled():
            cache_size = self.routing_config.performance.get("max_cache_size", 1000)
            cache_ttl = self.routing_config.get_cache_ttl()
            self.cache.update_cache_parameters(
                max_size=cache_size, default_ttl=cache_ttl
            )
        else:
            self.cache = None

        # Performance tracking
        self._routing_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "complexity_overrides": 0,
        }

        self._logger.info("LLM Routing Service initialized")

    def route_request(
        self,
        prompt: str,
        task_type: str,
        available_providers: List[str],
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        """
        Perform end-to-end routing for an LLM request.

        Args:
            prompt: The prompt text
            task_type: Type of task being performed
            available_providers: List of available providers
            routing_context: Routing context and preferences

        Returns:
            Complete routing decision
        """
        start_time = time.time()
        self._routing_stats["total_requests"] += 1

        try:
            self._logger.debug(
                f"Routing request for task_type='{task_type}', providers={available_providers}"
            )

            # 1. Determine complexity
            complexity = self.determine_complexity(task_type, prompt, routing_context)

            # 2. Check cache if enabled
            if self.cache:
                cached_decision = self._check_cache(
                    task_type, complexity, prompt, available_providers, routing_context
                )
                if cached_decision:
                    self._routing_stats["cache_hits"] += 1
                    self._logger.debug(f"Cache hit for {task_type}({complexity})")
                    return cached_decision

            # 3. Select optimal model
            decision = self.select_optimal_model(
                task_type, complexity, available_providers, routing_context
            )

            # 4. Cache the decision if caching is enabled
            if self.cache and not decision.fallback_used:
                self._cache_decision(
                    task_type,
                    complexity,
                    prompt,
                    available_providers,
                    routing_context,
                    decision,
                )

            # 5. Update statistics
            if decision.fallback_used:
                self._routing_stats["fallback_used"] += 1

            if routing_context.complexity_override:
                self._routing_stats["complexity_overrides"] += 1

            # 6. Log the decision
            elapsed_time = time.time() - start_time
            self._logger.info(
                f"Routed {task_type}({complexity}) to {decision.provider}:{decision.model} "
                f"(confidence: {decision.confidence:.2f}, time: {elapsed_time:.3f}s)"
            )

            return decision

        except Exception as e:
            self._logger.error(f"Error in route_request: {e}")
            # Return emergency fallback
            return self._create_emergency_fallback(available_providers, str(e))

    def determine_complexity(
        self, task_type: str, prompt: str, routing_context: RoutingContext
    ) -> TaskComplexity:
        """
        Determine the complexity level for a routing request.

        Args:
            task_type: Type of task being performed
            prompt: The prompt text
            routing_context: Additional routing context

        Returns:
            Determined complexity level
        """
        return self.complexity_analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

    def select_optimal_model(
        self,
        task_type: str,
        complexity: TaskComplexity,
        available_providers: List[str],
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        """
        Select the optimal provider and model for a request.

        Args:
            task_type: Type of task being performed
            complexity: Determined complexity level
            available_providers: List of available providers
            routing_context: Additional routing context and preferences

        Returns:
            Routing decision with selected provider and model
        """
        self._logger.debug(
            f"Selecting model for {task_type}({complexity}) from {available_providers}"
        )

        # 1. Check for model override first
        if routing_context.model_override:
            return self._handle_model_override(
                routing_context.model_override, complexity, available_providers
            )

        # 2. Get provider preferences for this task type
        task_preferences = self.routing_config.get_provider_preference(task_type)
        context_preferences = routing_context.provider_preference

        # Combine preferences (context overrides task type)
        if context_preferences:
            preferred_providers = context_preferences
        else:
            preferred_providers = task_preferences

        # 3. Filter by available providers and exclusions
        available_preferred = self._filter_available_providers(
            preferred_providers, available_providers, routing_context.excluded_providers
        )

        # 4. Apply cost optimization if enabled
        if (
            routing_context.cost_optimization
            and self.routing_config.is_cost_optimization_enabled()
        ):
            available_preferred = self._apply_cost_optimization(
                available_preferred, complexity, routing_context.max_cost_tier
            )

        # 5. Try to select from preferred providers
        decision = self._select_from_preferred_providers(
            available_preferred, task_type, complexity
        )

        if decision:
            decision.reasoning = f"Selected from preferred providers for {task_type}"
            decision.confidence = 0.9
            return decision

        # 6. Fallback to any available provider
        self._logger.warning(f"No preferred providers available, using fallback")
        return self._apply_fallback_strategy(
            available_providers, task_type, complexity, routing_context
        )

    def _check_cache(
        self,
        task_type: str,
        complexity: TaskComplexity,
        prompt: str,
        available_providers: List[str],
        routing_context: RoutingContext,
    ) -> Optional[RoutingDecision]:
        """Check if a routing decision is cached."""
        if not self.cache:
            return None

        return self.cache.get(
            task_type=task_type,
            complexity=complexity,
            prompt=prompt,
            available_providers=available_providers,
            provider_preference=routing_context.provider_preference,
            cost_optimization=routing_context.cost_optimization,
        )

    def _cache_decision(
        self,
        task_type: str,
        complexity: TaskComplexity,
        prompt: str,
        available_providers: List[str],
        routing_context: RoutingContext,
        decision: RoutingDecision,
    ) -> None:
        """Cache a routing decision."""
        if not self.cache:
            return

        self.cache.put(
            task_type=task_type,
            complexity=complexity,
            prompt=prompt,
            available_providers=available_providers,
            decision=decision,
            provider_preference=routing_context.provider_preference,
            cost_optimization=routing_context.cost_optimization,
        )

    def _handle_model_override(
        self,
        model_override: str,
        complexity: TaskComplexity,
        available_providers: List[str],
    ) -> RoutingDecision:
        """Handle explicit model override."""
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
        return self._create_emergency_fallback(
            available_providers, f"Model override '{model_override}' not available"
        )

    def _filter_available_providers(
        self,
        preferred_providers: List[str],
        available_providers: List[str],
        excluded_providers: List[str],
    ) -> List[str]:
        """Filter providers by availability and exclusions."""
        available_set = set(p.lower() for p in available_providers)
        excluded_set = set(p.lower() for p in excluded_providers)

        filtered = []
        for provider in preferred_providers:
            provider_lower = provider.lower()
            if provider_lower in available_set and provider_lower not in excluded_set:
                filtered.append(provider_lower)

        return filtered

    def _apply_cost_optimization(
        self,
        providers: List[str],
        complexity: TaskComplexity,
        max_cost_tier: Optional[str],
    ) -> List[str]:
        """Apply cost optimization constraints."""
        if not max_cost_tier:
            max_cost_tier = self.routing_config.get_max_cost_tier()

        # Define cost tiers (low to high cost)
        cost_hierarchy = {
            TaskComplexity.LOW: ["low"],
            TaskComplexity.MEDIUM: ["low", "medium"],
            TaskComplexity.HIGH: ["low", "medium", "high"],
            TaskComplexity.CRITICAL: ["low", "medium", "high", "critical"],
        }

        allowed_tiers = cost_hierarchy.get(complexity, ["medium"])

        # Filter to only include allowed cost tiers
        if max_cost_tier in ["low", "medium", "high", "critical"]:
            tier_index = ["low", "medium", "high", "critical"].index(max_cost_tier)
            allowed_tiers = allowed_tiers[: tier_index + 1]

        # For now, return all providers (cost optimization logic can be enhanced)
        return providers

    def _select_from_preferred_providers(
        self, preferred_providers: List[str], task_type: str, complexity: TaskComplexity
    ) -> Optional[RoutingDecision]:
        """Select a model from preferred providers."""
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

    def _apply_fallback_strategy(
        self,
        available_providers: List[str],
        task_type: str,
        complexity: TaskComplexity,
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        """Apply fallback strategy when preferred providers unavailable."""
        self._logger.warning(
            f"Applying fallback strategy for {task_type}({complexity})"
        )

        # Strategy 1: Try lower complexity if enabled
        if (
            routing_context.retry_with_lower_complexity
            and complexity != TaskComplexity.LOW
        ):
            lower_complexity = self._get_lower_complexity(complexity)
            decision = self._select_from_preferred_providers(
                [p.lower() for p in available_providers], task_type, lower_complexity
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

        if fallback_provider.lower() in [p.lower() for p in available_providers]:
            return RoutingDecision(
                provider=fallback_provider,
                model=fallback_model,
                complexity=complexity,
                confidence=0.5,
                reasoning=f"Configured fallback: {fallback_provider}:{fallback_model}",
                fallback_used=True,
            )

        # Strategy 3: Emergency fallback to first available provider
        return self._create_emergency_fallback(
            available_providers, "All fallback strategies exhausted"
        )

    def _get_lower_complexity(self, complexity: TaskComplexity) -> TaskComplexity:
        """Get the next lower complexity level."""
        complexity_order = [
            TaskComplexity.LOW,
            TaskComplexity.MEDIUM,
            TaskComplexity.HIGH,
            TaskComplexity.CRITICAL,
        ]
        current_index = complexity_order.index(complexity)
        if current_index > 0:
            return complexity_order[current_index - 1]
        return complexity

    def _create_emergency_fallback(
        self, available_providers: List[str], reason: str
    ) -> RoutingDecision:
        """Create an emergency fallback decision."""
        if not available_providers:
            raise ValueError("No providers available for emergency fallback")

        # Use first available provider with its lowest complexity model
        provider = available_providers[0]
        provider_matrix = self.routing_config.routing_matrix.get(provider.lower(), {})

        # Try to get the lowest complexity model
        for complexity_level in ["low", "medium", "high", "critical"]:
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

        # Last resort: use a hardcoded fallback
        return RoutingDecision(
            provider=provider,
            model="default-model",
            complexity=TaskComplexity.LOW,
            confidence=0.1,
            reasoning=f"Last resort fallback: {reason}",
            fallback_used=True,
        )

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing service statistics."""
        stats = self._routing_stats.copy()

        if self.cache:
            stats["cache_stats"] = self.cache.get_stats()

        # Calculate additional metrics
        total_requests = stats["total_requests"]
        if total_requests > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / total_requests
            stats["fallback_rate"] = stats["fallback_used"] / total_requests
            stats["override_rate"] = stats["complexity_overrides"] / total_requests

        return stats

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self._routing_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "complexity_overrides": 0,
        }

        if self.cache:
            self.cache.reset_stats()

    def clear_cache(self) -> None:
        """Clear the routing cache."""
        if self.cache:
            self.cache.clear()
            self._logger.info("Routing cache cleared")

    def cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        if self.cache:
            expired_count = self.cache.cleanup_expired()
            if expired_count > 0:
                self._logger.info(f"Cleaned up {expired_count} expired cache entries")
