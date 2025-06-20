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

# Core Graph Services
from .graph_builder_service import GraphBuilderService
from .compilation_service import CompilationService
from .graph_runner_service import GraphRunnerService, RunOptions
from .graph_assembly_service import GraphAssemblyService
from .graph_output_service import GraphOutputService
from .graph_scaffold_service import GraphScaffoldService
from agentmap.models.scaffold_types import ScaffoldOptions, ScaffoldResult, ServiceRequirements, ServiceAttribute
from .graph_bundle_service import GraphBundleService

# Utility Services
from .function_resolution_service import FunctionResolutionService
from .prompt_manager_service import PromptManagerService
from .execution_policy_service import ExecutionPolicyService
from .state_adapter_service import StateAdapterService
from .execution_tracking_service import ExecutionTrackingService, ExecutionTracker

# Validation Services
from .validation.validation_service import ValidationService
from .validation.csv_validation_service import CSVValidationService
from .validation.config_validation_service import ConfigValidationService
from .validation.validation_cache_service import ValidationCacheService

# Agent and Registry Services
from .features_registry_service import FeaturesRegistryService
from .agent_registry_service import AgentRegistryService
from .dependency_checker_service import DependencyCheckerService
from .agent_factory_service import AgentFactoryService

# Configuration Services
from .config import ConfigService, AppConfigService, StorageConfigService
from .config.llm_routing_config_service import LLMRoutingConfigService

# Routing Services  
from .routing import LLMRoutingService, PromptComplexityAnalyzer, RoutingCache

# Storage Services
from .storage import StorageServiceManager

# Application Services
from .application_bootstrap_service import ApplicationBootstrapService

# Service Protocols
from .protocols import (
    LLMServiceProtocol,
    StorageServiceProtocol,
    StateAdapterServiceProtocol,
    ExecutionTrackingServiceProtocol,
    LLMCapableAgent,
    StorageCapableAgent,
)

__all__ = [
    # Core Graph Services
    "GraphBuilderService",
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