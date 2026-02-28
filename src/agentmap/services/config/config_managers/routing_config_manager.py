"""Routing configuration manager."""

from typing import Any, Dict

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class RoutingConfigManager(BaseConfigManager):
    """
    Configuration manager for LLM routing settings.

    Handles routing configuration with comprehensive defaults for task types,
    complexity analysis, cost optimization, fallback, and performance settings.
    """

    def get_routing_config(self) -> Dict[str, Any]:
        """Get the routing configuration with default values."""
        routing_config = self.get_section("routing", {})

        # Default routing configuration matching LLMRoutingConfigService expectations
        defaults = {
            "enabled": True,
            "routing_matrix": {},
            "task_types": {
                "general": {
                    "description": "General purpose tasks",
                    "provider_preference": ["anthropic", "openai", "google"],
                    "default_complexity": "medium",
                    "complexity_keywords": {
                        "low": ["simple", "basic", "quick"],
                        "medium": ["analyze", "process", "standard"],
                        "high": ["complex", "detailed", "comprehensive", "advanced"],
                        "critical": ["urgent", "critical", "important", "emergency"],
                    },
                }
            },
            "complexity_analysis": {
                "enabled": True,
                "prompt_length_thresholds": {"low": 500, "medium": 2000, "high": 8000},
                "content_analysis": {
                    "enabled": True,
                    "keyword_weights": {
                        "complexity_indicators": 2.0,
                        "technical_terms": 1.5,
                        "urgency_indicators": 1.8,
                    },
                },
            },
            "cost_optimization": {
                "enabled": True,
                "max_cost_tier": "high",
                "cost_aware_routing": True,
            },
            "fallback": {
                "enabled": True,
                "default_provider": "anthropic",
                # Note: default_model is loaded from routing.fallback.default_model
                # If not specified in config, LLMModelsConfigService provides the default
            },
            "performance": {
                "enable_routing_cache": True,
                "cache_ttl": 300,
                "async_routing": True,
            },
        }

        # Merge with defaults
        return self._merge_with_defaults(routing_config, defaults)
