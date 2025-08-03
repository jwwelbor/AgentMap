# Complete Task Breakdown: AgentMap Migration

## Task Summary Table

| Task | Status | Priority | Time | Complexity | Dependencies |
|------|--------|----------|------|------------|--------------|
| 1. Architecture & Tracking | ✅ DONE | - | - | - | - |
| 2. Structure & Validation | ✅ DONE | - | - | - | - |
| 3. Node Domain Model | ✅ DONE | - | - | - | - |
| 4. Graph & ExecutionSummary | ✅ DONE | - | - | - | - |
| 5. GraphBuilderService | ✅ DONE | - | - | - | - |
| 6. CompilationService | ✅ DONE | - | - | - | - |
| 7.1-7.7. GraphRunnerService | ✅ DONE | - | - | - | - |
| 8. Service Migration | ✅ DONE | - | - | - | - |
| 9. DI Container Updates | ✅ DONE | - | - | - | - |
| 10. CLI Implementation | ✅ DONE | - | - | - | - |
| 11. GraphScaffoldService | 🎯 NEXT | HIGH | 3-4h | Medium | None |
| 12. CLI Scaffold Integration | 🔜 READY | HIGH | 30m | Low | 11 |
| 13. DI Scaffold Registration | 🔜 READY | HIGH | 30m | Low | 11 |
| 14. Scaffold Testing | 🔜 READY | MEDIUM | 2h | Medium | 11 |
| 15. FastAPI Router Integration | ⏳ LOW | LOW | 3-4h | Medium | 10 |
| 16. Serverless Handlers | ⏳ PENDING | MEDIUM | 3-4h | Medium | 10 |
| 17. Entry Point Scripts | ⏳ PENDING | MEDIUM | 1-2h | Low | 15,16 |
| 18. Core Integration Tests | ⏳ PENDING | HIGH | 3-4h | Medium | 17 |
| 19. Final Validation | ⏳ PENDING | CRITICAL | 3-4h | Medium | 18 |

## Current Migration Status: 73% Complete

### ✅ Completed Work (10/14 core tasks)
- **Models Layer**: 100% complete - all domain models implemented and tested
- **Core Services**: 80% complete - GraphBuilder, Compilation, Runner services done
- **Service Migration**: 100% complete - core services moved to src_new
- **DI Integration**: 100% complete - container updated with new service locations  
- **CLI Implementation**: 100% complete - all commands using new service architecture

### 🎯 Immediate Next Priority: Scaffold Service Migration
- **GraphScaffoldService**: Missing from core service migration
- **Current State**: CLI scaffold command uses old direct imports
- **Required**: Migrate scaffold functionality to service architecture

### ⏳ Remaining Work: Library Integration Focus
- **FastAPI Integration**: Router pattern for host application integration (LOW PRIORITY)
- **Serverless Handlers**: Function handlers for AWS/GCP/Azure (MEDIUM PRIORITY)
- **Final Integration**: Testing and validation (HIGH PRIORITY)

---

## Detailed Task Implementations

### ✅ COMPLETED TASKS (Tasks 1-10)

**Models Layer** (Tasks 1-4): ✅ COMPLETE
- Pure domain models (Node, Graph, ExecutionSummary, ExecutionResult)
- Comprehensive unit tests
- Clean separation of data and business logic

**Services Layer** (Tasks 5-7): ✅ CORE SERVICES COMPLETE
- GraphBuilderService: CSV parsing with domain model conversion
- CompilationService: Graph compilation with auto-compile capabilities
- GraphRunnerService: Complete orchestration with 8-service dependency injection
- Service migration: Core services moved to src_new architecture

**Integration Layer** (Tasks 8-10): ✅ COMPLETE
- DI container updated to bridge old/new service locations
- CLI handlers fully migrated with service integration
- All commands preserve backward compatibility

---

### 🎯 Task 11: Create GraphScaffoldService to migrate scaffold functionality
**ID**: `2b8942cc-9c12-4589-84ef-0c46491f35b9`  
**Status**: NEXT (HIGH PRIORITY)  
**Dependencies**: None  
**Time Estimate**: 3-4 hours  
**Complexity**: Medium  

#### Problem Statement
The scaffold functionality in `src_old/agentmap/graph/scaffold.py` is sophisticated but not yet migrated to the service architecture. The CLI currently imports scaffold functions directly instead of using service patterns.

#### Implementation Strategy
**WRAP existing scaffold logic, FOLLOW established service patterns, MAINTAIN all features**

```python
class GraphScaffoldService:
    """Service for scaffolding graphs, agents, and edge functions."""
    
    def __init__(
        self, 
        app_config_service: AppConfigService,
        logging_service: LoggingService
    ):
        """Initialize with dependency injection."""
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        
    def scaffold_graph_csv(self, name: str) -> Path:
        """Create a starter CSV for a new graph."""
        
    def scaffold_agent_class(self, agent_type: str, info: Dict) -> Path:
        """Create a starter agent class."""
        # Wrap existing scaffold_agent function
        
    def scaffold_edge_function(self, func_name: str, info: Dict) -> Path:
        """Scaffold a Python function for dynamic edge routing."""
        # Wrap existing scaffold_function function
        
    def scaffold_agents_from_csv(
        self, 
        csv_path: Path, 
        output_path: Path,
        func_path: Path,
        graph_name: Optional[str] = None
    ) -> int:
        """Scaffold agents and functions from CSV with service awareness."""
        # Wrap existing scaffold_agents function

@dataclass
class ScaffoldOptions:
    """Options for scaffolding operations."""
    output_dir: Optional[Path] = None
    function_dir: Optional[Path] = None
    graph_name: Optional[str] = None
    force_overwrite: bool = False

@dataclass
class ScaffoldResult:
    """Result of scaffolding operations."""
    scaffolded_count: int
    created_files: List[Path]
    success: bool
    error: Optional[str] = None
```

#### Key Implementation Details
1. **Reuse Existing Logic**: Import and wrap functions from `src_old/agentmap/graph/scaffold.py`
2. **Service Pattern**: Follow CompilationService and GraphBuilderService patterns
3. **Path Resolution**: Use app_config_service for custom_agents_path and functions_path
4. **Error Handling**: Service-level error handling with informative messages
5. **Logging**: Comprehensive logging following established patterns

#### Files to Create
- **CREATE**: `src_new/agentmap/services/graph_scaffold_service.py`
- **UPDATE**: `src_new/agentmap/services/__init__.py`

#### Success Criteria
- [ ] Service wraps all existing scaffold functionality
- [ ] Uses dependency injection (app_config_service, logging_service)
- [ ] Follows established service patterns
- [ ] Comprehensive error handling and logging
- [ ] Service info method for debugging

---

### 🔜 Task 12: Update CLI scaffold command to use GraphScaffoldService
**ID**: `f8e35447-5c19-4dfb-8b60-7837e55ab6e9`  
**Status**: READY TO START  
**Dependencies**: Task 11  
**Time Estimate**: 30 minutes  
**Complexity**: Low  

#### Implementation Strategy
**REPLACE direct imports with service usage, MAINTAIN identical CLI behavior**

```python
# Before (in src_new/agentmap/core/cli/run_commands.py):
from agentmap.graph.scaffold import scaffold_agents

# After:
def scaffold_command(...):
    container = initialize_di(config_file)
    graph_scaffold_service = container.graph_scaffold_service()
    
    scaffolded = graph_scaffold_service.scaffold_agents_from_csv(
        csv_path=csv_path,
        output_path=output_path,
        func_path=functions_path,
        graph_name=graph,
        logger=logger
    )
```

#### Files to Modify
- **UPDATE**: `src_new/agentmap/core/cli/run_commands.py`

#### Success Criteria
- [ ] CLI command uses GraphScaffoldService through DI
- [ ] Identical interface and behavior preserved
- [ ] All CLI options work correctly
- [ ] Error messages consistent with existing behavior

---

### 🔜 Task 13: Add GraphScaffoldService to DI container configuration
**ID**: `2ca038f3-f450-4951-a7b8-c62fd49fc7ec`  
**Status**: READY TO START  
**Dependencies**: Task 11  
**Time Estimate**: 30 minutes  
**Complexity**: Low  

#### Implementation Strategy
**FOLLOW exact pattern of other services (GraphBuilderService, CompilationService)**

```python
# In src_old/agentmap/di/containers.py:
class ApplicationContainer(containers.DeclarativeContainer):
    # ... existing services ...
    
    # Graph Scaffold Service for scaffold operations
    graph_scaffold_service = providers.Singleton(
        "agentmap.services.graph_scaffold_service.GraphScaffoldService",
        app_config_service,
        logging_service
    )

# In src_old/agentmap/di/__init__.py:
application.wire(modules=[
    # ... existing modules ...
    "agentmap.services.graph_scaffold_service",
])
```

#### Files to Modify
- **UPDATE**: `src_old/agentmap/di/containers.py`
- **UPDATE**: `src_old/agentmap/di/__init__.py`

#### Success Criteria
- [ ] Service registered in DI container
- [ ] Wire configuration includes new service module
- [ ] DI container can create service instance
- [ ] Service dependencies properly injected

---

### 🔜 Task 14: Create unit and integration tests for GraphScaffoldService
**ID**: `aae7f542-2290-4ff9-b229-bf55911c2bdd`  
**Status**: READY TO START  
**Dependencies**: Task 11  
**Time Estimate**: 2 hours  
**Complexity**: Medium  

#### Implementation Strategy
**FOLLOW established testing patterns (CompilationService tests)**

```python
# tests/unit/test_graph_scaffold_service.py
class TestGraphScaffoldService(ServiceUnitTest):
    def test_service_initialization(self):
    def test_scaffold_graph_csv(self):
    def test_scaffold_agent_class(self):
    def test_scaffold_edge_function(self):
    def test_scaffold_agents_from_csv(self):
    def test_service_info(self):
    def test_error_handling(self):

# tests/integration/test_graph_scaffold_service_integration.py  
class TestGraphScaffoldServiceIntegration(ServiceIntegrationTest):
    def test_real_csv_scaffolding(self):
    def test_file_system_operations(self):
    def test_service_coordination(self):
```

#### Files to Create
- **CREATE**: `tests/unit/test_graph_scaffold_service.py`
- **CREATE**: `tests/integration/test_graph_scaffold_service_integration.py`

#### Success Criteria
- [ ] Comprehensive unit tests following established patterns
- [ ] Integration tests with real file system operations
- [ ] Error handling and edge case coverage
- [ ] Mock service patterns properly used

---

### ⏳ Task 15: Create FastAPI Router Integration for Host Applications
**ID**: `3ba12118-fc0a-48e5-b60c-60a77129c849`  
**Status**: LOW PRIORITY  
**Dependencies**: Task 10 (CLI completed)  
**Time Estimate**: 3-4 hours  
**Complexity**: Medium  

#### Problem Statement
AgentMap is primarily used as an imported library, not a standalone application. The FastAPI integration should follow the router pattern to allow host applications to include AgentMap endpoints.

#### Implementation Strategy
**LIBRARY-FIRST approach, ROUTER pattern, HOST application integration**

```python
# src_new/agentmap/integrations/fastapi/router.py
def create_agentmap_router(container=None, prefix="/agentmap") -> APIRouter:
    """
    Create a FastAPI router that can be included in any FastAPI app.
    
    Usage in host application:
    ```python
    from fastapi import FastAPI
    from agentmap.integrations.fastapi import create_agentmap_router
    
    app = FastAPI()
    agentmap_router = create_agentmap_router()
    app.include_router(agentmap_router)
    ```
    """
    router = APIRouter(prefix=prefix)
    
    if container is None:
        container = initialize_di()
    
    adapter = create_service_adapter(container)
    
    @router.post("/run")
    async def run_graph_endpoint(request: GraphRunRequest):
        # Implementation using GraphRunnerService
        pass
    
    return router

# src_new/agentmap/integrations/fastapi/dependencies.py
def get_agentmap_container() -> ApplicationContainer:
    """FastAPI dependency to get AgentMap container."""
    pass

def get_graph_runner_service(container = Depends(get_agentmap_container)):
    """FastAPI dependency to get GraphRunnerService."""
    return container.graph_runner_service()

# src_new/agentmap/integrations/fastapi/factory.py
def create_agentmap_app(config_file=None, **kwargs) -> FastAPI:
    """
    Factory function for creating a complete AgentMap FastAPI app.
    
    Use this when you want AgentMap to BE the application.
    """
    container = initialize_di(config_file)
    app = FastAPI(title="AgentMap API", **kwargs)
    
    router = create_agentmap_router(container)
    app.include_router(router)
    
    return app
```

#### Directory Structure
```
src_new/agentmap/integrations/
├── __init__.py
├── fastapi/
│   ├── __init__.py          # Export main functions
│   ├── router.py            # FastAPI router (main pattern)
│   ├── dependencies.py     # FastAPI dependencies
│   ├── factory.py          # App factory for standalone use
│   └── models.py           # Request/response models
```

#### Files to Create
- **CREATE**: `src_new/agentmap/integrations/fastapi/router.py`
- **CREATE**: `src_new/agentmap/integrations/fastapi/dependencies.py`
- **CREATE**: `src_new/agentmap/integrations/fastapi/factory.py`
- **CREATE**: `src_new/agentmap/integrations/fastapi/models.py`
- **CREATE**: `src_new/agentmap/integrations/fastapi/__init__.py`
- **CREATE**: `src_new/agentmap/integrations/__init__.py`

#### Success Criteria
- [ ] Router can be included in any FastAPI app
- [ ] Standalone app factory available for single-purpose deployments
- [ ] Dependency injection works through FastAPI Depends mechanism
- [ ] Request/response models maintain backward compatibility
- [ ] Documentation includes host application integration examples

---

### ⏳ Task 16: Implement Serverless Handlers with Service Integration
**ID**: `e2179be4-b0b9-489e-bf7d-0ab6a03bb4d9`  
**Status**: PENDING  
**Dependencies**: Task 10 (CLI completed)  
**Time Estimate**: 3-4 hours  
**Complexity**: Medium  

#### Implementation Strategy
**MAINTAIN existing handlers, UPDATE to use services**

The existing serverless handlers are already implemented but need to be verified for service integration.

#### Files to Verify/Update
- **VERIFY**: `src_new/agentmap/core/handlers/base_handler.py`
- **VERIFY**: `src_new/agentmap/core/handlers/aws_lambda.py`
- **VERIFY**: `src_new/agentmap/core/handlers/gcp_functions.py`
- **VERIFY**: `src_new/agentmap/core/handlers/azure_functions.py`

---

### ⏳ Task 17: Update entry point scripts and configuration
**ID**: `35175b1a-6234-4083-92ce-b3486c1108fa`  
**Status**: PENDING  
**Dependencies**: Task 15, 16  
**Time Estimate**: 1-2 hours  
**Complexity**: Low  

#### Implementation Strategy
**UPDATE pyproject.toml to point to new entry points**

```toml
[tool.poetry.scripts]
agentmap = "agentmap.core.cli.main_cli:app"
agentmap-server = "agentmap.integrations.fastapi.factory:main"
```

---

### ⏳ Task 18: Create comprehensive integration tests for Core layer
**ID**: `e17cb24b-e399-4320-881a-5b6f8c1dcf12`  
**Status**: PENDING  
**Dependencies**: Task 17  
**Time Estimate**: 3-4 hours  
**Complexity**: Medium  

#### Implementation Strategy
**END-TO-END testing of all Core layer components**

```python
class TestCoreLayerIntegration:
    def test_cli_commands_with_services(self):
        """Test all CLI commands work with new service architecture."""
        
    def test_fastapi_router_integration(self):
        """Test FastAPI router works in host applications."""
        
    def test_serverless_handlers_integration(self):
        """Test serverless handlers work with service architecture."""
        
    def test_backward_compatibility(self):
        """Ensure all interfaces maintain backward compatibility."""
```

---

### ⏳ Task 19: Final migration validation and testing
**ID**: `381010e7-eac5-4fcc-b6b5-87a211c84228`  
**Status**: PENDING  
**Dependencies**: Task 18  
**Time Estimate**: 3-4 hours  
**Complexity**: Medium  

#### Validation Strategy
**COMPREHENSIVE comparison, PERFORMANCE validation, FEATURE verification**

```python
class TestMigrationValidation:
    def test_scaffold_functionality_equivalence(self):
        """Ensure GraphScaffoldService produces equivalent results."""
        
    def test_cli_compatibility_complete(self):
        """Comprehensive CLI testing including scaffold commands."""
        
    def test_service_architecture_complete(self):
        """Verify all services are properly integrated."""
        
    def test_performance_regression(self):
        """Ensure no significant performance degradation."""
        
    def test_library_integration_patterns(self):
        """Test FastAPI router and other integration patterns."""
```

---

## Migration Timeline Estimate

### Phase 1: Complete Scaffold Service Migration (Tasks 11-14)
**Duration**: 6-7 hours  
**Priority**: HIGH (missing from core services)  
**Tasks**: GraphScaffoldService + CLI integration + DI registration + testing  

### Phase 2: Library Integration (Tasks 15-17)  
**Duration**: 7-10 hours  
**Priority**: MEDIUM (FastAPI LOW, serverless/entry points MEDIUM)  
**Tasks**: FastAPI router + serverless verification + entry point updates  

### Phase 3: Final Integration and Validation (Tasks 18-19)
**Duration**: 6-8 hours  
**Priority**: HIGH (comprehensive testing)  
**Tasks**: Core layer testing + final migration validation  

### Total Remaining Duration: 19-25 hours
**Current Completion**: 73% (10/14 core tasks complete)  
**Immediate Focus**: Complete scaffold service migration (Tasks 11-14)  

---

## Quality Gates for Remaining Tasks

### Scaffold Service Migration (Tasks 11-14)
- [ ] Service follows established patterns (CompilationService, GraphBuilderService)
- [ ] All existing scaffold functionality preserved
- [ ] CLI integration maintains identical behavior
- [ ] Comprehensive testing with mock service patterns
- [ ] DI container integration working correctly

### Library Integration (Tasks 15-17)
- [ ] FastAPI router pattern supports host application integration
- [ ] Serverless handlers verified with service architecture
- [ ] Entry points properly configured
- [ ] Documentation includes integration examples

### Final Validation (Tasks 18-19)
- [ ] All tests pass (unit, integration, e2e)
- [ ] Behavioral equivalence between old and new implementations
- [ ] Performance benchmarks within acceptable range
- [ ] Complete feature preservation
- [ ] Migration documentation complete

---

## Prioritized Execution Plan

### Immediate (Next Session): Tasks 11-14
1. **Task 11**: GraphScaffoldService implementation (3-4 hours)
2. **Task 12**: CLI integration (30 minutes)
3. **Task 13**: DI registration (30 minutes)  
4. **Task 14**: Testing (2 hours)

**Total**: ~6-7 hours to complete scaffold service migration

### Next Phase: Tasks 15-19
Focus on library integration and final validation based on project priorities and usage patterns.

---

*This updated task breakdown reflects the current migration status with scaffold service migration as the immediate priority and FastAPI integration designed for AgentMap's primary use case as an imported library.*