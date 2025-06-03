# Service Refactoring Mapping - AgentMap Clean Architecture Migration

**Generated:** Task 2 - Audit Models and Services Directory for Refactored Functionality  
**Date:** Monday, June 02, 2025  
**Status:** ✅ COMPLETE - Comprehensive architectural mapping documented

## Executive Summary

**Architectural Pattern:** Clean Architecture with Domain-Driven Design  
**Key Insight:** Business logic extracted to services, data models separated from behavior  
**Dependency Injection:** Comprehensive DI container with string-based providers  
**Service Count:** 25+ services identified with clear contracts

## 🏗️ Architectural Transformation Overview

### OLD Architecture (src_old/):
- **Monolithic Classes**: Business logic mixed with data and infrastructure
- **Direct Imports**: Tight coupling between modules
- **Ad-hoc Dependencies**: Services created without injection

### NEW Architecture (src/):
- **Domain Models**: Pure data containers (dataclasses/Pydantic)
- **Service Layer**: Business logic in dedicated service classes
- **Dependency Injection**: Container-managed service dependencies
- **Clean Contracts**: Protocol-based interfaces for testability

## 📊 Domain Models Mapping

### Core Domain Models (NEW)

| Domain Model | Original Location | Purpose | Architecture Notes |
|-------------|------------------|---------|-------------------|
| `models.graph.Graph` | `src_old/agentmap/graph/node.py` (partial) | Graph structure container | Pure dataclass, no business logic |
| `models.node.Node` | `src_old/agentmap/graph/node.py` | Node properties and edges | Data container with simple methods |
| `models.execution_tracker.ExecutionTracker` | `src_old/agentmap/logging/tracking/execution_tracker.py` | Execution data tracking | **FIXED**: Now pure dataclass |
| `models.execution_result.ExecutionResult` | **NEW** | Execution outcome data | Domain model for results |
| `models.features_registry.FeaturesRegistry` | `src_old/agentmap/features_registry.py` | Feature availability data | State container |
| `models.agent_registry.AgentRegistry` | `src_old/agentmap/agents/registry.py` | Agent type registration | State container |

### Configuration Models

| Domain Model | Original Location | Purpose | Architecture Notes |
|-------------|------------------|---------|-------------------|
| `models.config.config_models.py` | `src_old/agentmap/config/base.py` | Configuration schemas | Pydantic models |
| `models.validation.validation_models.py` | `src_old/agentmap/validation/models.py` | Validation result schemas | Domain-driven validation |

### Validation Models

| Domain Model | Original Location | Purpose | Architecture Notes |
|-------------|------------------|---------|-------------------|
| `models.validation.validation_models.ValidationResult` | `src_old/agentmap/validation/models.py` | Validation outcomes | Pydantic model with methods |
| `models.validation.errors.ValidationError` | `src_old/agentmap/validation/errors.py` | Error representation | Domain model |

## ⚙️ Service Layer Mapping

### 🔄 Core Graph Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **GraphBuilderService** | `src_old/agentmap/graph/builder.py` | CSV parsing → Graph domain models | `AppConfigService`, `LoggingService` |
| **CompilationService** | `src_old/agentmap/compiler.py` + `src_old/agentmap/graph/assembler.py` | Graph compilation + code generation | `GraphBuilderService`, `AppConfigService`, `LoggingService` |
| **GraphBundleService** | `src_old/agentmap/graph/bundle.py` | Bundle creation and serialization | `LoggingService` |
| **GraphRunnerService** | `src_old/agentmap/runner.py` | Complete graph execution orchestration | 12+ injected services |
| **GraphScaffoldService** | `src_old/agentmap/graph/scaffold.py` | Graph scaffolding with service awareness | `AppConfigService`, `LoggingService`, `PromptManagerService` |

### 🏭 Agent Management Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **AgentFactoryService** | `src_old/agentmap/agents/loader.py` | Agent creation with dependency validation | `AgentRegistryService`, `FeaturesRegistryService`, `LoggingService` |
| **AgentRegistryService** | `src_old/agentmap/agents/registry.py` | Agent type registration and lookup | `AgentRegistry` (model), `LoggingService` |
| **FeaturesRegistryService** | `src_old/agentmap/features_registry.py` | Feature availability management | `FeaturesRegistry` (model), `LoggingService` |
| **DependencyCheckerService** | `src_old/agentmap/agents/dependency_checker.py` | Agent dependency validation | `LoggingService`, `FeaturesRegistryService` |

### 📊 State and Execution Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **StateAdapterService** | `src_old/agentmap/state/adapter.py` | State format abstraction | None (static methods) |
| **ExecutionTrackingService** | Part of old ExecutionTracker | Factory for ExecutionTracker instances | `AppConfigService`, `LoggingService` |
| **ExecutionPolicyService** | **NEW** | Policy evaluation for execution results | `AppConfigService`, `LoggingService` |
| **NodeRegistryService** | `src_old/agentmap/utils/node_registry.py` | Node registration for graph assembly | `AppConfigService`, `LoggingService` |

### ⚙️ Configuration Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **ConfigService** | `src_old/agentmap/config/base.py` | Low-level configuration management | None |
| **AppConfigService** | `src_old/agentmap/config/base.py` | Application configuration | `ConfigService` |
| **StorageConfigService** | **NEW** | Storage configuration (optional) | `ConfigService` |
| **LLMRoutingConfigService** | **NEW** | LLM routing configuration | `AppConfigService`, `LoggingService` |

### 🔍 Validation Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **CSVValidationService** | `src_old/agentmap/validation/csv_validator.py` | CSV file validation | `LoggingService` |
| **ConfigValidationService** | `src_old/agentmap/validation/config_validator.py` | Configuration validation | `LoggingService` |
| **ValidationService** | **NEW** | General validation orchestration | `LoggingService` |
| **ValidationCacheService** | **NEW** | Validation result caching | `LoggingService` |

### 🚀 Infrastructure Services

| Service | Original Functionality | Service Contract | DI Dependencies |
|---------|----------------------|------------------|-----------------|
| **LoggingService** | `src_old/agentmap/logging/` | Centralized logging management | Configuration |
| **LLMService** | `src_old/agentmap/services/llm_service.py` | LLM provider management | `AppConfigService`, `LoggingService`, `LLMRoutingService` |
| **PromptManagerService** | `src_old/agentmap/prompts/manager.py` | External template management | `AppConfigService`, `LoggingService` |
| **StorageServiceManager** | `src_old/agentmap/services/storage/manager.py` | Storage service coordination | `StorageConfigService`, `LoggingService` |

## 🔧 Dependency Injection Patterns

### DI Container Architecture (`di/containers.py`)
```python
# STRING-BASED PROVIDERS (avoid circular imports)
service = providers.Singleton(
    "agentmap.services.module.ServiceClass",
    dependency1,
    dependency2
)

# GRACEFUL FAILURE HANDLING
@staticmethod
def _create_optional_service(dependencies):
    try:
        return ServiceClass(dependencies)
    except SpecificException:
        return None  # Graceful degradation
```

### Service Constructor Patterns
```python
# STANDARD SERVICE PATTERN
class ExampleService:
    def __init__(
        self,
        dependency1: Dependency1Protocol,
        dependency2: Dependency2Protocol,
        logging_service: LoggingService
    ):
        self.dep1 = dependency1
        self.dep2 = dependency2
        self.logger = logging_service.get_class_logger(self)
```

## 🔀 Import Migration Patterns

### OLD Direct Import Patterns (BROKEN)
```python
# OLD - Direct business logic imports
from agentmap.graph.builder import GraphBuilder
from agentmap.compiler import Compiler
from agentmap.logging.tracking.execution_tracker import ExecutionTracker
from agentmap.state.adapter import StateAdapter
```

### NEW Service Injection Patterns (CORRECT)
```python
# NEW - Service dependency injection
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.compilation_service import CompilationService
from agentmap.models.execution_tracker import ExecutionTracker
from agentmap.services.state_adapter_service import StateAdapterService

# NEW - DI container usage
from agentmap.di.containers import ApplicationContainer

container = ApplicationContainer()
graph_builder = container.graph_builder_service()
```

### Agent Constructor Migration
```python
# OLD - Direct instantiation
class MyAgent(BaseAgent):
    def __init__(self, name, prompt):
        super().__init__(name, prompt)
        self.tracker = ExecutionTracker()  # BROKEN

# NEW - Dependency injection
class MyAgent(BaseAgent):
    def __init__(self, name, prompt, logger, execution_tracker):
        super().__init__(name, prompt, 
                        logger=logger, 
                        execution_tracker=execution_tracker)
```

## 📋 Service Contracts and Protocols

### Key Service Interfaces

**LoggingService Protocol:**
```python
def get_class_logger(self, instance: object)
def get_logger(self, name: str) 
def get_module_logger(self, module_name: str)
```

**AppConfigService Protocol:**
```python
def get_compiled_graphs_path(self) -> Path
def get_csv_path(self) -> Path
def get_execution_config(self) -> Dict[str, Any]
def get_tracking_config(self) -> Dict[str, Any]
```

**GraphBuilderService Contract:**
```python
def build_from_csv(self, csv_path: Path, graph_name: Optional[str] = None) -> Graph
def build_all_from_csv(self, csv_path: Path) -> Dict[str, Graph]
def validate_csv_before_building(self, csv_path: Path) -> List[str]
```

## 🎯 Critical Import Fixes Required

### 1. **ExecutionTracker Migration** ✅ FIXED
```python
# OLD (BROKEN)
from agentmap.logging.tracking.execution_tracker import ExecutionTracker

# NEW (CORRECT)
from agentmap.models.execution_tracker import ExecutionTracker
```

### 2. **StateAdapter Migration** 
```python
# OLD (BROKEN)  
from agentmap.state.adapter import StateAdapter

# NEW (CORRECT)
from agentmap.services.state_adapter_service import StateAdapterService
```

### 3. **Graph Services Migration**
```python
# OLD (BROKEN)
from agentmap.graph.builder import GraphBuilder
from agentmap.compiler import Compiler

# NEW (CORRECT)  
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.compilation_service import CompilationService
```

### 4. **Agent Services Migration**
```python
# OLD (BROKEN)
from agentmap.agents.loader import AgentLoader
from agentmap.agents.registry import Registry

# NEW (CORRECT)
from agentmap.services.agent_factory_service import AgentFactoryService  
from agentmap.services.agent_registry_service import AgentRegistryService
```

## 🏆 Architectural Benefits Achieved

✅ **Separation of Concerns**: Business logic in services, data in models  
✅ **Testability**: Clean DI allows easy mocking and testing  
✅ **Maintainability**: Services have single responsibilities  
✅ **Scalability**: Container manages complex dependency graphs  
✅ **Flexibility**: Optional services with graceful degradation  

## 🔄 Service Orchestration Example

**Complex Service Interaction (GraphRunnerService):**
```python
class GraphRunnerService:
    def __init__(
        self,
        graph_builder_service: GraphBuilderService,
        compilation_service: CompilationService, 
        graph_bundle_service: GraphBundleService,
        llm_service: LLMService,
        storage_service_manager: StorageServiceManager,
        # ... 12+ total dependencies
    ):
        # Clean architecture with proper service coordination
```

## 📝 Next Steps for Task 3 & 4

**Task 3** should focus on:
1. **ExecutionTracker imports** - Update all 40+ agent files
2. **StateAdapter imports** - Update to StateAdapterService  
3. **Simple file moves** - Direct path updates

**Task 4** should focus on:
1. **Service architecture adoption** - Convert direct imports to DI
2. **Agent constructor updates** - Add logger and execution_tracker parameters
3. **Service contracts** - Ensure proper interface usage

---

**Architecture Status:** ✅ Clean architecture successfully implemented with comprehensive service layer and domain models.
