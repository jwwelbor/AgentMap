# src/agentmap/models/__init__.py
"""
Domain models for AgentMap.

This module contains simple domain entities that represent core business concepts.
All models are data containers with minimal behavior - business logic belongs in services.
"""

# TODO: ARCHITECTURAL FIX NEEDED - Move validation logic to ValidationService
# The validation modules (CSVValidator, ConfigValidator, ValidationCache) contain
# significant business logic that belongs in services, not domain models:
# - CSV parsing and graph analysis logic
# - YAML parsing and configuration validation
# - File-based caching with expiration logic
# These should be moved to services/validation/ during Task 5+

# Import validation models (currently commented out due to business logic)
# from .validation import *

# Import domain models  
from .node import Node
from .graph import Graph
from .graph_bundle import GraphBundle
from .execution_summary import ExecutionSummary, NodeExecution
from .execution_result import ExecutionResult
from .features_registry import FeaturesRegistry
from .agent_registry import AgentRegistry

__all__ = [
    # Domain models
    "Node",
    "Graph", 
    "GraphBundle",
    "ExecutionSummary",
    "NodeExecution",
    "ExecutionResult",
    "FeaturesRegistry",
    "AgentRegistry",
    
    # TODO: Re-enable after moving validation business logic to ValidationService
    # Only keep simple validation error classes/models in domain models
    # "ValidationResult",
    # "ValidationError", 
    # "ValidationSeverity",
    # "NodeValidationError",
    # "GraphValidationError",
    # "ConfigValidationError",
    # "CSVValidationError",
    # "ValidationCache",  # <- This should be ValidationService
    # "CSVValidator",     # <- This should be ValidationService
    # "ConfigValidator",  # <- This should be ValidationService
]
