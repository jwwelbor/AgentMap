# AgentMap Clean Architecture Guidelines

## Overview

This document defines the architectural principles and guidelines for the AgentMap project refactoring. AgentMap is migrating from a mixed-responsibility structure to a clean architecture with clear separation of concerns, improved testability, and enhanced maintainability.

## Architectural Principles

### 1. **Separation of Concerns**
Each layer has a single, well-defined responsibility:
- **Models**: Pure data containers (NO business logic)
- **Services**: Business logic and orchestration
- **Agents**: Execution units for business logic processing
- **Core**: Application entry points (CLI, API, handlers)
- **Infrastructure**: External integrations and technical utilities
- **DI**: Dependency injection and service wiring

### 2. **Dependency Inversion**
- Higher-level modules should not depend on lower-level modules
- Both should depend on abstractions (interfaces/protocols)
- Use dependency injection for all service dependencies

### 3. **Single Responsibility Principle**
- Each class/module has one reason to change
- Services focus on a single business capability
- Clear boundaries between concerns

### 4. **Interface Segregation**
- Use protocols for service contracts
- Clients should not depend on interfaces they don't use
- Keep interfaces focused and cohesive

### 5. **Don't Repeat Yourself (DRY)**
- Reuse existing proven implementations
- Extract common patterns into shared utilities
- Avoid code duplication across layers

## Layer Definitions

### Models Layer (`/models/`)
**Purpose**: Pure data containers that represent core business entities

**🚨 CRITICAL: Models are data containers ONLY - no business logic!**

**Responsibilities**:
- Hold data for business entities (Node, Graph, ExecutionSummary)
- Simple data access and storage methods only
- Type safety with validation

**Guidelines**:
- **Pure data containers** - no business logic whatsoever
- No dependencies on other layers (except validation utilities)
- All business logic belongs in services
- Follow existing simple patterns like Node model
- Use @dataclass for simple data containers

**Examples**:
```python
# Pure data container (CORRECT)
@dataclass
class Graph:
    name: str
    entry_point: Optional[str] = None
    nodes: Dict[str, Node] = field(default_factory=dict)

# Business logic goes in services (CORRECT)
class GraphService:
    def validate_graph(self, graph: Graph) -> List[str]:
        """Business logic belongs in services"""
        errors = []
        # Validation logic here
        return errors
    
    def get_reachable_nodes(self, graph: Graph) -> Set[str]:
        """Business logic belongs in services"""
        # Traversal logic here
        pass
```

### Services Layer (`/services/`)
**Purpose**: Business logic and orchestration services

**Responsibilities**:
- Implement business use cases
- Coordinate between models and external systems
- Provide clean interfaces for business operations

**Guidelines**:
- Use dependency injection for all dependencies
- Follow existing service patterns (like NodeRegistryService)
- Wrap existing implementations rather than rebuilding
- Maintain backward compatibility during migration

**Service Types**:
- **GraphBuilderService**: CSV parsing → Domain models
- **GraphRunnerService**: Graph execution orchestration
- **CompilationService**: Graph compilation and caching
- **ValidationService**: Validation operations (future)

**Example Service Pattern**:
```python
class GraphBuilderService:
    def __init__(self, config_service: AppConfigService, logging_service: LoggingService):
        self.config = config_service
        self.logger = logging_service.get_class_logger(self)
    
    def build_from_csv(self, csv_path: Path, graph_name: str = None) -> Graph:
        # Wrap existing GraphBuilder implementation
        builder = GraphBuilder(csv_path)  # Reuse existing
        graphs_dict = builder.build()
        return self._convert_to_domain_model(graphs_dict, graph_name)
```

### Agents Layer (`/agents/`)
**Purpose**: Execution units for business logic processing

**Responsibilities**:
- Process state and return updates
- Execute specific business operations within graph execution
- Provide pluggable business logic components

**Guidelines**:
- Keep at top level (NOT in infrastructure)
- Maintain existing agent patterns and protocols
- Agents are execution units, not pure domain models
- Support protocol-based injection (LLMServiceUser, NodeRegistryUser)

**Agent Contract**:
```python
class BaseAgent:
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process state and return updates"""
        pass

# Examples:
# - LLMAgent: AI processing
# - DataTransformAgent: Data transformation
# - ValidationAgent: Business rule validation
```

### Core Layer (`/core/`)
**Purpose**: Application entry points and external interfaces

**Responsibilities**:
- Handle user interactions (CLI, HTTP, serverless)
- Route requests to appropriate services
- Manage application lifecycle

**Guidelines**:
- Thin layer - no business logic
- Use services for all business operations
- Handle serialization/deserialization
- Manage authentication and authorization

**Entry Points**:
- **CLI**: Command-line interface
- **API**: FastAPI web server
- **Handlers**: Serverless functions

### Infrastructure Layer (`/infrastructure/`)
**Purpose**: External integrations and technical utilities

**Responsibilities**:
- File I/O and serialization
- External API integrations
- Technical utility functions

**Guidelines**:
- Minimal infrastructure layer for AgentMap
- Only truly external/technical concerns
- Keep existing /logging/ and proven patterns

**Infrastructure Components**:
- `/persistence/`: File serialization (bundle.py)
- Keep existing `/logging/` patterns

### Dependency Injection (`/di/`)
**Purpose**: Service wiring and dependency management

**Responsibilities**:
- Configure service dependencies
- Manage service lifecycle
- Enable testability through mocking

**Guidelines**:
- Extend existing DI container patterns
- Preserve existing graceful degradation
- Use string-based providers to avoid circular dependencies

## Migration Strategy

### Dependency Hierarchy and Migration Order

**🚨 CRITICAL: Migrations must follow dependency hierarchy to prevent test failures and integration issues.**

#### 1. **Dependency Hierarchy Levels**

**Level 1: Models (No Dependencies)**
- Pure data containers with no external dependencies
- Can be migrated first as foundation
- Examples: Node, Graph, ExecutionSummary, Validation models

**Level 2: Services (Depend on Models + Infrastructure)**
- Business logic services that use models
- Depend on Level 1 models and infrastructure utilities
- Examples: GraphBuilderService, CompilationService, ValidationService

**Level 3: Core (Depend on Services)**
- Application entry points that orchestrate services
- Depend on Level 2 services and Level 1 models
- Examples: CLI handlers, API endpoints, serverless functions

**Level 4: Integration (Depend on All Layers)**
- End-to-end functionality that uses complete application stack
- Depend on all previous levels
- Examples: Full workflow tests, deployment scripts

#### 2. **Migration Order Rules**

1. **Never migrate a component before its dependencies**
2. **Models first, then Services, then Core, then Integration**
3. **Within each level, start with components that have fewer dependencies**
4. **Validate each level completely before proceeding to the next**

#### 3. **Dependency Verification Checklist**

Before migrating any component, verify:

- [ ] All dependencies are already migrated
- [ ] All imports resolve correctly
- [ ] Unit tests pass with proper mock patterns
- [ ] Integration tests work with real dependencies
- [ ] No circular dependencies introduced

#### 4. **Service Dependency Graph**

```
Models (Level 1)
  ├── Node ✅
  ├── Graph ✅ 
  ├── ExecutionSummary ✅
  └── Validation Models ✅

Services (Level 2)
  ├── GraphBuilderService ✅ (depends on: Graph, Node)
  ├── CompilationService ✅ (depends on: Graph, GraphBuilderService)
  ├── GraphRunnerService (depends on: Graph, ExecutionSummary, CompilationService)
  └── ValidationService (depends on: Validation Models)

Core (Level 3)
  ├── CLI Handlers (depends on: All Services)
  ├── API Endpoints (depends on: All Services)
  └── Serverless Handlers (depends on: All Services)

Integration (Level 4)
  ├── End-to-End Tests (depends on: All Levels)
  └── Deployment Scripts (depends on: All Levels)
```

#### 5. **Test Dependency Requirements**

**Unit Tests:**
- Must use proper mock service patterns
- Follow established MockLoggingService → MockLogger → .calls pattern
- No direct dependencies on other layers

**Integration Tests:**
- Use real services where possible
- Mock only external dependencies
- Test cross-layer interactions

**End-to-End Tests:**
- Use complete application stack
- Minimal mocking
- Verify full functionality

#### 6. **Common Dependency Violations to Avoid**

❌ **Circular Dependencies**: Service A depends on Service B which depends on Service A
❌ **Layer Skipping**: Core directly importing Models without going through Services
❌ **Reverse Dependencies**: Models importing from Services
❌ **Mock Inconsistencies**: Different mock patterns across similar tests
❌ **Premature Migration**: Migrating services before their model dependencies

#### 7. **Dependency Validation Tools**

- **Import Analysis**: Check that imports only go "down" the dependency hierarchy
- **Test Pattern Verification**: Ensure all tests follow established mock patterns
- **Circular Dependency Detection**: Automated checks for circular imports
- **Documentation Updates**: Keep dependency graph documentation current

### Phase-Based Approach
1. **Models**: Move and create pure data models
2. **Services**: Extract service wrappers around existing implementations
3. **Core**: Create clean entry points
4. **Integration**: Wire everything through DI
5. **Validation**: Comprehensive testing and comparison

### Preservation Priorities
**Keep These Excellent Patterns**:
- Dependency injection container with graceful degradation
- Sophisticated testing framework (unit/integration/e2e)
- Protocol-based service injection
- Exception hierarchy
- Configuration management

**Reuse These Implementations**:
- GraphBuilder (wrap, don't rebuild)
- GraphAssembler (keep as service - it's business logic)
- Compiler functions (wrap in service)
- NodeRegistryService (keep unchanged)
- LLMService (keep unchanged)

### Service Extraction Pattern
```python
# Pattern: Wrap existing implementations
class GraphBuilderService:
    def __init__(self, ...):
        # Initialize dependencies
        
    def build_from_csv(self, csv_path: Path) -> Graph:
        # 1. Use existing implementation
        builder = GraphBuilder(csv_path)  # Existing proven code
        raw_graphs = builder.build()
        
        # 2. Convert to domain models
        return self._convert_to_domain_models(raw_graphs)
    
    def _convert_to_domain_models(self, raw_graphs: Dict) -> Graph:
        # New logic for domain model conversion
        pass
```

## Testing Strategy

### Test-Driven Development
- Write tests first for all new components
- Use existing test patterns and fixtures
- Maintain existing mock factory patterns

### Test Types
- **Unit Tests**: Mock all dependencies, test in isolation
- **Integration Tests**: Real DI container, test service interactions
- **End-to-End Tests**: Full application testing

### Testing Patterns to Follow
```python
# Unit Test Pattern
class TestGraphBuilderService(ServiceUnitTest):
    def test_build_from_csv(self):
        service = GraphBuilderService(self.mock_config_service, self.mock_logging_service)
        result = service.build_from_csv(test_csv_path)
        self.assert_service_configured(service, ["config", "logger"])

# Integration Test Pattern  
class TestGraphBuilderServiceIntegration(ServiceIntegrationTest):
    def test_real_csv_parsing(self):
        service = self.container.graph_builder_service()
        result = service.build_from_csv(self.test_csv_path)
        assert isinstance(result, Graph)
```

## Code Quality Standards

### Naming Conventions
- **Classes**: PascalCase (GraphBuilderService)
- **Methods/Variables**: snake_case (build_from_csv)
- **Constants**: UPPER_CASE (DEFAULT_TIMEOUT)
- **Files**: snake_case (graph_builder_service.py)

### Documentation
- Docstrings for all public methods
- Type hints for all parameters and return values
- Clear comments for complex business logic

### Error Handling
- Use existing exception hierarchy
- Provide context in error messages
- Follow existing error handling patterns

## Integration Guidelines

### Service Integration
- All services use dependency injection
- Follow protocol-based injection patterns
- Maintain existing service interfaces during migration

### Backward Compatibility
- Preserve existing API contracts during migration
- Use wrapper pattern to maintain compatibility
- Gradual migration with comparison testing

### Performance Considerations
- No performance degradation from refactoring
- Wrapper pattern should add minimal overhead
- Reuse existing efficient implementations

## Future Extensibility

### Adding New Services
1. Define service interface/protocol
2. Implement service following existing patterns
3. Add to DI container
4. Create comprehensive tests
5. Update documentation

### Adding New Models
1. Follow domain model patterns
2. Add validation using existing patterns
3. Create unit tests with full coverage
4. Update related services as needed

### Adding New Agents
1. Follow existing agent patterns
2. Implement required protocols
3. Add to agent registry
4. Create agent tests

## Success Criteria

### Technical Goals
- ✅ Clean separation of concerns
- ✅ Improved testability
- ✅ Enhanced maintainability
- ✅ Better extensibility

### Migration Goals
- ✅ All existing functionality preserved
- ✅ No performance regressions
- ✅ Backward compatibility maintained
- ✅ Test coverage maintained or improved

### Quality Metrics
- All tests pass
- Code coverage maintained
- No breaking changes to external APIs
- Documentation updated and complete

---

*This architecture serves as the foundation for the AgentMap refactoring. All implementation decisions should align with these principles and guidelines.*