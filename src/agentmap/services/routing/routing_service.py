"""
Core LLM routing service for AgentMap.

This module provides the main routing service that orchestrates complexity analysis,
matrix lookups, provider selection, and fallback strategies for optimal LLM routing.
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from agentmap.exceptions.service_exceptions import LLMConfigurationError
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.llm.provider_names import canonicalize_provider
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.activity_routing import ActivityRoutingTable
from agentmap.services.routing.cache import RoutingCache
from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer
from agentmap.services.routing.fallback_handler import FallbackHandler
from agentmap.services.routing.model_selector import (
    ModelSelector,
    filter_excluded_providers,
)
from agentmap.services.routing.types import (
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
)

# Re-export for backwards compatibility
__all__ = ["LLMRoutingService", "ActivityRoutingTable"]


# Models known to NOT support vision/multimodal input.
# All current routing-matrix models (Claude 3+, GPT-4o+, Gemini) support vision.
# Populate this set with text-only model identifiers as needed.
_NON_VISION_MODELS: frozenset[str] = frozenset()


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
            llm_routing_config_service: LLM routing configuration service
            logging_service: Logging service for structured logging
            routing_cache: Routing cache service
            prompt_complexity_analyzer: Prompt complexity analyzer
        """
        self.routing_config = llm_routing_config_service
        self._logger = logging_service.get_class_logger(self)
        self.cache: Optional[RoutingCache] = routing_cache

        # Initialize components
        self.complexity_analyzer = prompt_complexity_analyzer
        self.model_selector = ModelSelector(llm_routing_config_service, self._logger)
        self.fallback_handler = FallbackHandler(
            llm_routing_config_service, self._logger
        )

        # Initialize cache if enabled
        if self.routing_config.is_routing_cache_enabled():
            cache_size = self.routing_config.performance.get("max_cache_size", 1000)
            cache_ttl = self.routing_config.get_cache_ttl()
            routing_cache.update_cache_parameters(
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
        eligible_providers = self._eligible_providers(
            available_providers, routing_context
        )

        try:
            self._logger.debug(
                f"Routing request for task_type='{task_type}', providers={available_providers}"
            )

            # 1. Determine complexity
            complexity = self.determine_complexity(task_type, prompt, routing_context)

            # 2. Check cache if enabled
            if self.cache:
                cached_decision = self._check_cache(
                    task_type, complexity, prompt, eligible_providers, routing_context
                )
                if cached_decision:
                    self._routing_stats["cache_hits"] += 1
                    self._logger.debug(f"Cache hit for {task_type}({complexity})")
                    return cached_decision

            # 3. Build candidate list (activity-first) and choose if available
            decision = None
            candidates = self._select_candidates(
                routing_context,
                available_providers=eligible_providers,
                complexity=complexity,
            )

            if candidates:
                decision = self._choose_candidate_decision(
                    candidates,
                    eligible_providers,
                    routing_context,
                    complexity,
                )

            # 4. Fall back to matrix-based selection when needed
            if decision is None:
                decision = self._select_optimal_model(
                    task_type, complexity, eligible_providers, routing_context
                )

            # 5. Cache the decision if caching is enabled
            if self.cache and not decision.fallback_used:
                self._cache_decision(
                    task_type,
                    complexity,
                    prompt,
                    eligible_providers,
                    routing_context,
                    decision,
                )

            # 6. Update statistics
            if decision.fallback_used:
                self._routing_stats["fallback_used"] += 1

            if routing_context.complexity_override:
                self._routing_stats["complexity_overrides"] += 1

            # 7. Log the decision
            elapsed_time = time.time() - start_time
            self._logger.info(
                f"Routed {task_type}({complexity}) to {decision.provider}:{decision.model} "
                f"(confidence: {decision.confidence:.2f}, time: {elapsed_time:.3f}s)"
            )

            return decision

        except LLMConfigurationError:
            raise
        except Exception as e:
            self._logger.error(f"Error in route_request: {e}")
            if routing_context.fallback_provider or routing_context.fallback_model:
                return self.recover_route(eligible_providers, routing_context, str(e))
            return self.create_emergency_fallback(eligible_providers, str(e))

    @staticmethod
    def _eligible_providers(
        available_providers: List[str], routing_context: RoutingContext
    ) -> List[str]:
        """Apply request exclusions before selection or recovery."""
        eligible = filter_excluded_providers(
            available_providers, routing_context.excluded_providers
        )
        if available_providers and not eligible:
            raise LLMConfigurationError(
                "No eligible providers remain after routing exclusions"
            )
        return eligible

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
        eligible_providers = self._eligible_providers(
            available_providers, routing_context
        )
        return self._select_optimal_model(
            task_type, complexity, eligible_providers, routing_context
        )

    def _select_optimal_model(
        self,
        task_type: str,
        complexity: TaskComplexity,
        eligible_providers: List[str],
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        self._logger.debug(
            f"Selecting model for {task_type}({complexity}) from {eligible_providers}"
        )

        # 1. Check for model override first
        if routing_context.model_override:
            return self.model_selector.handle_model_override(
                routing_context.model_override,
                complexity,
                eligible_providers,
                self.create_emergency_fallback,
            )

        # 2. Get provider preferences for this task type
        task_preferences = self.routing_config.get_provider_preference(task_type)
        context_preferences = routing_context.provider_preference

        # Combine preferences (context overrides task type)
        if context_preferences:
            preferred_providers = context_preferences
        else:
            preferred_providers = task_preferences

        # 3. Keep eligible providers in preference order
        available_preferred = self.model_selector.filter_available_providers(
            preferred_providers, eligible_providers
        )

        # 4. Apply cost optimization if enabled
        if (
            routing_context.cost_optimization
            and self.routing_config.is_cost_optimization_enabled()
        ):
            available_preferred = self.model_selector.apply_cost_optimization(
                available_preferred, complexity, routing_context.max_cost_tier
            )

        # 5. Try to select from preferred providers
        decision = self.model_selector.select_from_preferred_providers(
            available_preferred, task_type, complexity
        )

        if decision:
            decision.reasoning = f"Selected from preferred providers for {task_type}"
            decision.confidence = 0.9
            return decision

        # 6. Fallback to any available provider
        self._logger.warning("No preferred providers available, using fallback")
        return self.fallback_handler.apply_fallback_strategy(
            eligible_providers,
            task_type,
            complexity,
            routing_context,
            self.model_selector.select_from_preferred_providers,
        )

    def select_candidates(
        self,
        routing_context: Union[RoutingContext, Dict[str, Any]],
        *,
        available_providers: Optional[List[str]] = None,
        complexity: Optional[TaskComplexity] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build an ordered list of candidate provider/model pairs.

        Activity plans are evaluated first, followed by routing-matrix backstops
        and provider preferences.

        Args:
            routing_context: Routing context or dict
            available_providers: List of available providers
            complexity: Task complexity level

        Returns:
            Ordered list of candidate provider/model pairs (may include max_tokens)
        """
        ctx = (
            routing_context
            if isinstance(routing_context, RoutingContext)
            else RoutingContext.from_dict(routing_context)
        )

        available = (
            list(self.routing_config.routing_matrix)
            if available_providers is None
            else available_providers
        )
        return self._select_candidates(
            ctx,
            available_providers=filter_excluded_providers(
                available, ctx.excluded_providers
            ),
            complexity=complexity,
        )

    def _select_candidates(
        self,
        ctx: RoutingContext,
        *,
        available_providers: List[str],
        complexity: Optional[TaskComplexity],
    ) -> List[Dict[str, Any]]:
        if complexity is None:
            # Analyse prompt from context to infer complexity when not provided
            prompt = ctx.prompt or ctx.input_context.get("user_input", "")
            if ctx.complexity_override:
                try:
                    complexity = TaskComplexity[ctx.complexity_override.upper()]
                except KeyError:
                    complexity = TaskComplexity.MEDIUM
            else:
                complexity = self.complexity_analyzer.analyze_prompt_complexity(prompt)

        complexity_key = str(complexity).lower()
        activity_table = ActivityRoutingTable(self.routing_config, self._logger)
        ordered: List[Dict[str, Any]] = []
        seen_pairs: Set[Tuple[str, str]] = set()
        available_keys = set(map(canonicalize_provider, available_providers))

        # 1) Activity-driven plan (primary + fallbacks)
        for entry in activity_table.plan(ctx.activity, complexity_key):
            provider = entry.get("provider")
            model = entry.get("model")
            if not provider or not model:
                continue
            provider_key = canonicalize_provider(provider)
            if provider_key not in available_keys:
                continue
            pair = (provider_key, model)
            if pair in seen_pairs:
                continue
            candidate: Dict[str, Any] = {"provider": provider, "model": model}
            if "max_tokens" in entry:
                candidate["max_tokens"] = entry["max_tokens"]
            ordered.append(candidate)
            seen_pairs.add(pair)

        # 2) Matrix-based backstops for remaining providers
        for provider in available_providers:
            provider_key = canonicalize_provider(provider)
            model = self.routing_config.get_model_for_complexity(
                provider_key, complexity_key
            )
            if not model:
                continue
            pair = (provider_key, model)
            if pair in seen_pairs:
                continue
            ordered.append({"provider": provider, "model": model})
            seen_pairs.add(pair)

        # 3) Filter out non-vision-capable models when vision is required
        if ctx.requires_vision and _NON_VISION_MODELS:
            ordered = [c for c in ordered if c.get("model") not in _NON_VISION_MODELS]

        # 4) Restrict providers to prompt-cache-capable entries when requested
        if ctx.requires_prompt_caching:
            ordered = [
                candidate
                for candidate in ordered
                if self.routing_config.supports_prompt_caching(
                    canonicalize_provider(candidate["provider"])
                )
            ]

        # 5) Apply provider preference ordering when supplied
        if ctx.provider_preference:
            preference_index: Dict[str, int] = {}
            for index, provider in enumerate(ctx.provider_preference):
                preference_index.setdefault(canonicalize_provider(provider), index)
            ordered.sort(
                key=lambda item: preference_index.get(
                    canonicalize_provider(item["provider"]), 1_000_000
                )
            )

        return ordered

    def _choose_candidate_decision(
        self,
        candidates: List[Dict[str, Any]],
        available_providers: List[str],
        routing_context: RoutingContext,
        complexity: TaskComplexity,
    ) -> Optional[RoutingDecision]:
        """Select the first viable candidate and convert to a decision."""

        available_set = set(map(canonicalize_provider, available_providers))
        activity = routing_context.activity

        for index, candidate in enumerate(candidates):
            provider = candidate.get("provider")
            model = candidate.get("model")
            if not provider or not model:
                continue

            if canonicalize_provider(provider) not in available_set:
                continue

            reasoning = (
                f"Activity routing: {activity}"
                if activity and index == 0
                else "Routing matrix candidate"
            )
            confidence = 0.9 if index == 0 else 0.7

            return RoutingDecision(
                provider=provider,
                model=model,
                complexity=complexity,
                confidence=confidence,
                reasoning=reasoning,
                fallback_used=index > 0,
                max_tokens=candidate.get("max_tokens"),
            )

        return None

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

    def recover_route(
        self, eligible_providers: List[str], context: RoutingContext, reason: str
    ) -> RoutingDecision:
        """Resolve a configured or emergency fallback after a routing error."""
        return self.fallback_handler.select_fallback(
            eligible_providers, TaskComplexity.LOW, context, reason
        )

    def create_emergency_fallback(
        self, available_providers: List[str], reason: str
    ) -> RoutingDecision:
        """Create an emergency decision from the ordered eligible providers."""
        return self.fallback_handler.create_emergency_fallback(
            available_providers, reason
        )

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing service statistics."""
        stats: Dict[str, Any] = self._routing_stats.copy()

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
