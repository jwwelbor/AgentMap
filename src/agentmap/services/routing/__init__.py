"""
LLM Routing Services for AgentMap.

This package provides intelligent routing capabilities for LLM requests,
including complexity analysis, provider selection, and model optimization.
"""

from agentmap.services.routing.types import (
    TaskComplexity,
    TaskType,
    RoutingContext,
    RoutingDecision,
    ComplexitySignal,
    LLMRouter,
    ComplexityAnalyzer
)

from agentmap.services.routing.complexity_analyzer import (
    PromptComplexityAnalyzer,
    create_complexity_analyzer
)

from agentmap.services.routing.cache import (
    RoutingCache,
    CacheEntry
)

from agentmap.services.routing.routing_service import (
    LLMRoutingService,
    create_routing_service
)

__all__ = [
    'TaskComplexity',
    'TaskType', 
    'RoutingContext',
    'RoutingDecision',
    'ComplexitySignal',
    'LLMRouter',
    'ComplexityAnalyzer',
    'PromptComplexityAnalyzer',
    'create_complexity_analyzer',
    'RoutingCache',
    'CacheEntry',
    'LLMRoutingService',
    'create_routing_service'
]
