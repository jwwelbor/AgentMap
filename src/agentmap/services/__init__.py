# src/agentmap/services/__init__.py
"""
Business logic services for AgentMap.

This module contains services that implement business use cases:
- GraphBuilderService: CSV parsing to domain models
- GraphRunnerService: Graph execution orchestration
- GraphAssemblyService: StateGraph assembly from domain models
- FunctionResolutionService: Dynamic function loading and reference extraction
- ValidationService: Comprehensive validation orchestration
- Configuration services: Existing config management
- Routing services: LLM routing and optimization
- Storage services: Data persistence and retrieval
- Application services: Bootstrap and lifecycle management

Services are loaded lazily via __getattr__ to improve startup performance.
Direct imports from submodules bypass this lazy loading.
"""

# Lazy loading mapping: name -> (module_path, attribute_name)
# Module paths are relative to agentmap.services
_LAZY_IMPORTS = {
    # Models (from agentmap.models.scaffold_types)
    "ScaffoldOptions": ("agentmap.models.scaffold_types", "ScaffoldOptions"),
    "ScaffoldResult": ("agentmap.models.scaffold_types", "ScaffoldResult"),
    "ServiceAttribute": ("agentmap.models.scaffold_types", "ServiceAttribute"),
    "ServiceRequirements": ("agentmap.models.scaffold_types", "ServiceRequirements"),
    # Core Graph Services
    "GraphScaffoldService": (
        "agentmap.services.graph.graph_scaffold_service",
        "GraphScaffoldService",
    ),
    "GraphRunnerService": (
        "agentmap.services.graph.graph_runner_service",
        "GraphRunnerService",
    ),
    "GraphAssemblyService": (
        "agentmap.services.graph.graph_assembly_service",
        "GraphAssemblyService",
    ),
    "GraphBundleService": (
        "agentmap.services.graph.graph_bundle_service",
        "GraphBundleService",
    ),
    # Agent Services
    "AgentFactoryService": (
        "agentmap.services.agent.agent_factory_service",
        "AgentFactoryService",
    ),
    "AgentRegistryService": (
        "agentmap.services.agent.agent_registry_service",
        "AgentRegistryService",
    ),
    # Configuration Services
    "ConfigService": ("agentmap.services.config.config_service", "ConfigService"),
    "AppConfigService": (
        "agentmap.services.config.app_config_service",
        "AppConfigService",
    ),
    "StorageConfigService": (
        "agentmap.services.config.storage_config_service",
        "StorageConfigService",
    ),
    "LLMRoutingConfigService": (
        "agentmap.services.config.llm_routing_config_service",
        "LLMRoutingConfigService",
    ),
    # Execution Services
    "ExecutionPolicyService": (
        "agentmap.services.execution_policy_service",
        "ExecutionPolicyService",
    ),
    "ExecutionTrackingService": (
        "agentmap.services.execution_tracking_service",
        "ExecutionTrackingService",
    ),
    "ExecutionTracker": (
        "agentmap.services.execution_tracking_service",
        "ExecutionTracker",
    ),
    # Registry Services
    "FeaturesRegistryService": (
        "agentmap.services.features_registry_service",
        "FeaturesRegistryService",
    ),
    # Utility Services
    "FilePathService": ("agentmap.services.file_path_service", "FilePathService"),
    "FunctionResolutionService": (
        "agentmap.services.function_resolution_service",
        "FunctionResolutionService",
    ),
    "PromptManagerService": (
        "agentmap.services.prompt_manager_service",
        "PromptManagerService",
    ),
    "StateAdapterService": (
        "agentmap.services.state_adapter_service",
        "StateAdapterService",
    ),
    # Validation Services
    "ValidationService": (
        "agentmap.services.validation.validation_service",
        "ValidationService",
    ),
    "CSVValidationService": (
        "agentmap.services.validation.csv_validation_service",
        "CSVValidationService",
    ),
    "ConfigValidationService": (
        "agentmap.services.validation.config_validation_service",
        "ConfigValidationService",
    ),
    "ValidationCacheService": (
        "agentmap.services.validation.validation_cache_service",
        "ValidationCacheService",
    ),
    # Routing Services
    "LLMRoutingService": (
        "agentmap.services.routing.routing_service",
        "LLMRoutingService",
    ),
    "PromptComplexityAnalyzer": (
        "agentmap.services.routing.prompt_complexity_analyzer",
        "PromptComplexityAnalyzer",
    ),
    "RoutingCache": ("agentmap.services.routing.routing_cache", "RoutingCache"),
    # Storage Services
    "StorageServiceManager": (
        "agentmap.services.storage.manager",
        "StorageServiceManager",
    ),
    # Service Protocols
    "LLMServiceProtocol": ("agentmap.services.protocols", "LLMServiceProtocol"),
    "StorageServiceProtocol": ("agentmap.services.protocols", "StorageServiceProtocol"),
    "StateAdapterServiceProtocol": (
        "agentmap.services.protocols",
        "StateAdapterServiceProtocol",
    ),
    "ExecutionTrackingServiceProtocol": (
        "agentmap.services.protocols",
        "ExecutionTrackingServiceProtocol",
    ),
    "LLMCapableAgent": ("agentmap.services.protocols", "LLMCapableAgent"),
    "StorageCapableAgent": ("agentmap.services.protocols", "StorageCapableAgent"),
}

# Cache for loaded items
_loaded_items = {}


def __getattr__(name: str):
    """Lazy load services and protocols on demand."""
    if name in _LAZY_IMPORTS:
        if name not in _loaded_items:
            module_path, attr_name = _LAZY_IMPORTS[name]
            import importlib

            module = importlib.import_module(module_path)
            _loaded_items[name] = getattr(module, attr_name)
        return _loaded_items[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Support dir() for discoverability."""
    return list(_LAZY_IMPORTS.keys())


__all__ = [
    # Core Graph Services
    "GraphRunnerService",
    "GraphAssemblyService",
    "GraphBundleService",
    "GraphScaffoldService",
    "ScaffoldOptions",
    "ScaffoldResult",
    "ServiceRequirements",
    "ServiceAttribute",
    # Utility Services
    "FilePathService",
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
    # Service Protocols
    "LLMServiceProtocol",
    "StorageServiceProtocol",
    "StateAdapterServiceProtocol",
    "ExecutionTrackingServiceProtocol",
    "LLMCapableAgent",
    "StorageCapableAgent",
]
