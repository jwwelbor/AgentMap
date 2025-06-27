# src/agentmap/services/__init__.py
"""
Business logic services for AgentMap.

This module contains services that implement business use cases:
- GraphBuilderService: CSV parsing to domain models
- GraphRunnerService: Graph execution orchestration
- CompilationService: Graph compilation and caching
- GraphAssemblyService: StateGraph assembly from domain models
- GraphOutputService: Graph export in various formats
- FunctionResolutionService: Dynamic function loading and reference extraction
- ValidationService: Comprehensive validation orchestration
- Configuration services: Existing config management
- Routing services: LLM routing and optimization
- Storage services: Data persistence and retrieval
- Application services: Bootstrap and lifecycle management
"""

from agentmap.models.scaffold_types import (
    ScaffoldOptions,
    ScaffoldResult,
    ServiceAttribute,
    ServiceRequirements,
)

from .agent_factory_service import AgentFactoryService
from .agent_registry_service import AgentRegistryService

# Application Services
from .application_bootstrap_service import ApplicationBootstrapService
from .compilation_service import CompilationService

# Configuration Services
from .config import AppConfigService, ConfigService, StorageConfigService
from .config.llm_routing_config_service import LLMRoutingConfigService
from .dependency_checker_service import DependencyCheckerService
from .execution_policy_service import ExecutionPolicyService
from .execution_tracking_service import ExecutionTracker, ExecutionTrackingService

# Agent and Registry Services
from .features_registry_service import FeaturesRegistryService

# Utility Services
from .function_resolution_service import FunctionResolutionService
from .graph_assembly_service import GraphAssemblyService
from .graph_bundle_service import GraphBundleService

# Core Graph Services
from .graph_definition_service import GraphDefinitionService
from .graph_output_service import GraphOutputService
from .graph_runner_service import GraphRunnerService, RunOptions
from .graph_scaffold_service import GraphScaffoldService
from .prompt_manager_service import PromptManagerService

# Service Protocols
from .protocols import (
    ExecutionTrackingServiceProtocol,
    LLMCapableAgent,
    LLMServiceProtocol,
    StateAdapterServiceProtocol,
    StorageCapableAgent,
    StorageServiceProtocol,
)
from .routing import PromptComplexityAnalyzer, RoutingCache

# Routing Services
# Import LLMRoutingService directly to avoid circular import
from .routing.routing_service import LLMRoutingService
from .state_adapter_service import StateAdapterService

# Storage Services
from .storage import StorageServiceManager
from .validation.config_validation_service import ConfigValidationService
from .validation.csv_validation_service import CSVValidationService
from .validation.validation_cache_service import ValidationCacheService

# Validation Services
from .validation.validation_service import ValidationService

__all__ = [
    # Core Graph Services
    "GraphDefinitionService",
    "CompilationService",
    "GraphRunnerService",
    "GraphAssemblyService",
    "GraphOutputService",
    "GraphBundleService",
    "GraphScaffoldService",
    "RunOptions",
    "ScaffoldOptions",
    "ScaffoldResult",
    "ServiceRequirements",
    "ServiceAttribute",
    # Utility Services
    "FunctionResolutionService",
    "PromptManagerService",
    "ExecutionPolicyService",
    "StateAdapterService",
    "ExecutionTrackingService",
    "ExecutionTracker",
    # Validation Services
    "ValidationService",
    "CSVValidationService",
    "ConfigValidationService",
    "ValidationCacheService",
    # Agent and Registry Services
    "FeaturesRegistryService",
    "AgentRegistryService",
    "DependencyCheckerService",
    "AgentFactoryService",
    # Configuration Services
    "ConfigService",
    "AppConfigService",
    "StorageConfigService",
    "LLMRoutingConfigService",
    # Routing Services
    "LLMRoutingService",
    "PromptComplexityAnalyzer",
    "RoutingCache",
    # Storage Services
    "StorageServiceManager",
    # Application Services
    "ApplicationBootstrapService",
    # Service Protocols
    "LLMServiceProtocol",
    "StorageServiceProtocol",
    "StateAdapterServiceProtocol",
    "ExecutionTrackingServiceProtocol",
    "LLMCapableAgent",
    "StorageCapableAgent",
]
