# File Movement Mapping - AgentMap Import Resolution

**Generated:** Task 1 - Analyze Import Errors and Map File Movements  
**Purpose:** Map old import paths to new locations to understand architectural changes

## Summary of Architectural Migration

**OLD Structure (`src_old/agentmap/`):**
- Flat file structure with modules at root level
- Traditional monolithic organization
- Direct imports between modules

**NEW Structure (`src/agentmap/`):**
- Clean architecture with domain models and services
- Separation of concerns into layers
- Dependency injection patterns

## File Movement Analysis

### 1. Major Architectural Changes

| Old Location | New Location | Status | Notes |
|-------------|-------------|--------|-------|
| `src_old/agentmap/cli.py` | `src/agentmap/core/cli/main_cli.py` | ✅ MOVED | CLI split into multiple modules |
| `src_old/agentmap/compiler.py` | `src/agentmap/services/compilation_service.py` | 🔄 REFACTORED | Business logic extracted to service |
| `src_old/agentmap/runner.py` | `src/agentmap/services/graph_runner_service.py` | 🔄 REFACTORED | Business logic extracted to service |
| `src_old/agentmap/fastapi_server.py` | `src/agentmap/core/api/fastapi_server.py` | ✅ MOVED | Moved to API layer |
| `src_old/agentmap/handler.py` | `src/agentmap/core/handlers/base_handler.py` | 🔄 REFACTORED | Split into multiple handlers |

### 2. Graph Module Changes

| Old Location | New Location | Status | Notes |
|-------------|-------------|--------|-------|
| `src_old/agentmap/graph/builder.py` | `src/agentmap/services/graph_builder_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/graph/assembler.py` | `src/agentmap/services/compilation_service.py` | 🔄 REFACTORED | Merged into compilation service |
| `src_old/agentmap/graph/bundle.py` | `src/agentmap/services/graph_bundle_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/graph/node.py` | `src/agentmap/models/node.py` | ✅ MOVED | Now a domain model |
| `src_old/agentmap/graph/scaffold.py` | `src/agentmap/services/graph_scaffold_service.py` | 🔄 REFACTORED | Business logic moved to service |

### 3. Configuration Changes

| Old Location | New Location | Status | Notes |
|-------------|-------------|--------|-------|
| `src_old/agentmap/config/base.py` | `src/agentmap/services/config/config_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/config/defaults.py` | `src/agentmap/models/config/config_models.py` | 🔄 REFACTORED | Now domain models |

### 4. Validation Changes

| Old Location | New Location | Status | Notes |
|-------------|-------------|--------|-------|
| `src_old/agentmap/validation/models.py` | `src/agentmap/models/validation/validation_models.py` | ✅ MOVED | Now domain models |
| `src_old/agentmap/validation/csv_validator.py` | `src/agentmap/services/validation/csv_validation_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/validation/errors.py` | `src/agentmap/models/validation/errors.py` | ✅ MOVED | Error models moved |

### 5. Agent Module Changes

| Old Location | New Location | Status | Notes |
|-------------|-------------|--------|-------|
| `src_old/agentmap/agents/features.py` | `src/agentmap/models/features_registry.py` | ✅ MOVED | Now domain model |
| `src_old/agentmap/agents/loader.py` | `src/agentmap/services/agent_factory_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/agents/registry.py` | `src/agentmap/services/agent_registry_service.py` | 🔄 REFACTORED | Business logic moved to service |
| `src_old/agentmap/agents/dependency_checker.py` | `src/agentmap/services/dependency_checker_service.py` | 🔄 REFACTORED | Business logic moved to service |

## Legend

- ✅ **MOVED**: File moved to new location with minimal changes
- 🔄 **REFACTORED**: Functionality moved to service layer with architectural changes
- ❌ **DEPRECATED**: Old file no longer needed
- ⚠️ **NEEDS_REVIEW**: Requires manual analysis

## Next Steps

1. **Task 2**: Audit `models/` and `services/` directories for refactored functionality
2. **Task 3**: Update imports for moved files  
3. **Task 4**: Refactor imports to use new service architecture
4. **Task 5**: Add missing standard library imports
5. **Task 6**: Validate fixes and flag unresolved issues

## Import Pattern Changes

### OLD Import Patterns:
```python
from agentmap.compiler import Compiler
from agentmap.graph.builder import GraphBuilder  
from agentmap.validation.csv_validator import CSVValidator
```

### NEW Import Patterns:
```python
from agentmap.services.compilation_service import CompilationService
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.validation.csv_validation_service import CSVValidationService
```

This architectural change requires dependency injection patterns and service-oriented imports.
