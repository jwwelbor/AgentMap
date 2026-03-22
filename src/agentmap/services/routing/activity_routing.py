"""
Activity-based routing for LLM requests.

This module provides the ActivityRoutingTable class for resolving
ordered provider/model candidates based on activity configuration.
"""

from typing import Any, Dict, List, Optional

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.logging_service import LoggingService


class ActivityRoutingTable:
    """Resolve ordered provider/model candidates for a given activity."""

    def __init__(
        self,
        routing_config: LLMRoutingConfigService,
        logger: LoggingService,
    ) -> None:
        """
        Initialize the activity routing table.

        Args:
            routing_config: Routing configuration service
            logger: Logger instance for logging
        """
        self._config_service = routing_config
        self._logger = logger

    def plan(
        self, activity: Optional[str], complexity_key: str
    ) -> List[Dict[str, Any]]:
        """
        Return ordered candidates for a given activity/complexity tier.

        Falls back to an empty list when the activity is undefined or
        no configuration exists, allowing matrix-based routing to continue.

        Args:
            activity: Activity name to route for
            complexity_key: Complexity level key (e.g., 'low', 'medium', 'high')

        Returns:
            Ordered list of candidate provider/model pairs
        """
        if not activity:
            return []

        activities = self._config_service.get_activities_config()
        if not activities:
            return []

        tier_map = activities.get(activity)
        if tier_map is None:
            normalized = str(activity).strip().lower()
            tier_map = activities.get(normalized)

        if not isinstance(tier_map, dict):
            return []

        plan = tier_map.get(complexity_key) or tier_map.get("any")
        if not isinstance(plan, dict):
            return []

        ordered: List[Dict[str, Any]] = []

        # Resolution chain: candidate > tier
        tier_max_tokens = plan.get("max_tokens")
        primary = plan.get("primary")

        # Combine primary and fallbacks into a single list for processing
        all_candidates = []
        if primary:
            all_candidates.append(primary)
        all_candidates.extend(plan.get("fallbacks", []))

        for candidate in all_candidates:
            if not isinstance(candidate, dict):
                continue
            provider = candidate.get("provider")
            model = candidate.get("model")
            if provider and model:
                entry: Dict[str, Any] = {"provider": provider, "model": model}
                candidate_max_tokens = candidate.get("max_tokens")
                if candidate_max_tokens is not None:
                    resolved_max_tokens = candidate_max_tokens
                else:
                    resolved_max_tokens = tier_max_tokens
                if resolved_max_tokens is not None:
                    entry["max_tokens"] = resolved_max_tokens
                ordered.append(entry)

        return ordered
