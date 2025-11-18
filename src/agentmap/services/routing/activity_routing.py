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

    def _get_config_dict(self) -> Dict[str, Any]:
        """
        Get the configuration dictionary from the config service.

        Returns:
            Configuration dictionary
        """
        if hasattr(self._config_service, "get_config"):
            return self._config_service.get_config()  # type: ignore[return-value]
        if hasattr(self._config_service, "config_dict"):
            return getattr(self._config_service, "config_dict")
        return {}

    def _get_activities(self) -> Dict[str, Any]:
        """
        Get activities configuration from the config.

        Returns:
            Activities configuration dictionary
        """
        config = self._get_config_dict() or {}
        if "routing" in config and isinstance(config["routing"], dict):
            return config["routing"].get("activities", {})
        return config.get("activities", {})

    def plan(
        self, activity: Optional[str], complexity_key: str
    ) -> List[Dict[str, str]]:
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

        activities = self._get_activities()
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

        ordered: List[Dict[str, str]] = []

        primary = plan.get("primary")
        if isinstance(primary, dict):
            provider = primary.get("provider")
            model = primary.get("model")
            if provider and model:
                ordered.append({"provider": provider, "model": model})

        for fallback in plan.get("fallbacks", []):
            if not isinstance(fallback, dict):
                continue
            provider = fallback.get("provider")
            model = fallback.get("model")
            if provider and model:
                ordered.append({"provider": provider, "model": model})

        return ordered
