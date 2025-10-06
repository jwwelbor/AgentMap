"""
LLM Routing Services for AgentMap.

This package provides intelligent routing capabilities for LLM requests,
including complexity analysis, provider selection, and model optimization.
"""

# Import other modules that don't have circular dependencies
from agentmap.services.routing.cache import CacheEntry, RoutingCache
from agentmap.services.routing.circuit_breaker import CircuitBreaker
from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer

# Import types first to avoid circular dependencies
from agentmap.services.routing.types import (
    ComplexityAnalyzer,
    ComplexitySignal,
    LLMRouter,
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
    TaskType,
    get_valid_complexity_levels,
)

# Note: LLMRoutingService is not imported here to avoid circular dependency
# It should be imported directly when needed: from agentmap.services.routing.routing_service import LLMRoutingService

__all__ = [
    # Types
    "TaskComplexity",
    "TaskType",
    "CircuitBreaker",
    "RoutingContext",
    "RoutingDecision",
    "ComplexitySignal",
    "LLMRouter",
    "ComplexityAnalyzer",
    # Implementations
    "PromptComplexityAnalyzer",
    "RoutingCache",
    "CacheEntry",
    # Utility functions
    "get_valid_complexity_levels",
    # Note: LLMRoutingService removed from __all__ to avoid circular import
]
