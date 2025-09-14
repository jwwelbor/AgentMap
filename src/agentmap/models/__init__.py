# src/agentmap/models/__init__.py
"""
Domain models for AgentMap.

This module contains simple domain entities that represent core business concepts.
All models are data containers with minimal behavior - business logic belongs in services.
"""
from .agent_registry import AgentRegistry
from .execution.result import ExecutionResult
from .execution.summary import ExecutionSummary, NodeExecution
from .features_registry import FeaturesRegistry
from .graph import Graph
from .graph_bundle import GraphBundle

# Import domain models
from .node import Node
from .scaffold_types import (
    ScaffoldOptions,
    ScaffoldResult,
    ServiceAttribute,
    ServiceRequirements,
)
from .storage import (
    CollectionPath,
    DocumentID,
    DocumentResult,
    QueryFilter,
    StorageConfig,
    StorageData,
    StorageOperation,
    StorageResult,
    WriteMode,
)
from .validation import *

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
    # Storage models
    "WriteMode",
    "StorageOperation",
    "StorageResult",
    "StorageConfig",
    "CollectionPath",
    "DocumentID",
    "QueryFilter",
    "StorageData",
    "DocumentResult",
    # Scaffolding models
    "ServiceRequirements",
    "ServiceAttribute",
    "ScaffoldOptions",
    "ScaffoldResult",
    "ValidationResult",
    "ValidationError",
    "ValidationSeverity",
    "NodeValidationError",
    "GraphValidationError",
    "ConfigValidationError",
    "CSVValidationError",
]
