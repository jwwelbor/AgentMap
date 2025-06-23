# AgentMap Clean Architecture Overview

AgentMap has migrated to a clean architecture pattern that separates concerns, improves testability, and enhances maintainability. This document provides a comprehensive overview of the new architecture.

## Architecture Principles

### 1. Separation of Concerns

The architecture strictly separates different aspects of the system:

- **Models**: Pure data containers with NO business logic
- **Services**: All business logic and orchestration
- **Agents**: Execution units that process workflows
- **Core**: Application entry points (CLI, API)
- **Infrastructure**: External integrations
- **DI Container**: Dependency injection and service wiring

### 2. Dependency Inversion

All dependencies flow inward:
- Core depends on Services
- Services depend on Models
- No layer depends on layers above it
- All dependencies are injected, not created

### 3. Clean Models

Models are pure data containers:

```python
# CORRECT: Pure data model
class Node:
    def __init__(self, name, agent_type=None, prompt=None):
        self.name = name
        self.agent_type = agent_type
        self.prompt = prompt
        self.edges = {}
    
    def add_edge(self, condition, target):
        """Simple data storage only"""
        self.edges[condition] = target

# INCORRECT: Business logic in model
class Node:
    def validate(self):  # ❌ Business logic doesn't belong here!
        if not self.name:
            raise ValueError("Node must have name")
    
    def get_next_node(self, state):  # ❌ This is business logic!
        if state.get("success"):
            return self.edges.get("success")
```

## Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Core Layer                          │
│  (CLI Commands, API Endpoints, Serverless Handlers)    │
└─────────────────────┬───────────────────────────────────┘
                      │ uses
┌─────────────────────▼───────────────────────────────────┐
│                   Services Layer                        │
│  (Business Logic, Orchestration, Domain Services)      │
└─────────────────────┬───────────────────────────────────┘
                      │ uses
┌─────────────────────▼───────────────────────────────────┐
│                    Models Layer                         │
│      (Pure Data Containers, Domain Entities)           │
└─────────────────────────────────────────────────────────┘
                      ▲
┌─────────────────────┴───────────────────────────────────┐
│                Infrastructure Layer                     │
│    (File I/O, External APIs, Technical Utilities)      │
└─────────────────────────────────────────────────────────┘
                      ▲
┌─────────────────────┴───────────────────────────────────┐
│              Dependency Injection Layer                 │
│        (Service Registry, Dependency Wiring)           │
└─────────────────────────────────────────────────────────┘
```

## Service Architecture

### Core Services

**GraphBuilderService**
- Builds graph models from CSV files
- Creates Node and Graph data models
- Handles CSV parsing and validation

**CompilationService**
- Compiles graph models into executable LangGraph
- Manages compilation cache
- Coordinates with GraphAssemblyService

**GraphRunnerService**
- Orchestrates graph execution
- Manages execution tracking
- Handles state adaptation

**AgentFactoryService**
- Creates agent instances
- Injects required services
- Manages agent configuration

### Infrastructure Services

**LoggingService**
- Provides structured logging
- Creates class-specific loggers
- Manages log levels and formatting

**ConfigService**
- Loads YAML configuration
- Provides configuration access
- Handles environment variables

**StorageServices**
- CSV, JSON, File storage operations
- Unified storage interface
- Cloud storage integration

### Business Services

**LLMService**
- Manages LLM provider integration
- Handles model selection
- Provides conversation memory

**PromptManagerService**
- Manages prompt templates
- Resolves prompt references
- Handles prompt versioning

## Dependency Injection

The DI container manages all service dependencies:

```python
class Container:
    """Main DI container for AgentMap"""
    
    # Infrastructure Services (always available)
    def logging_service(self) -> LoggingService:
        if not hasattr(self, '_logging_service'):
            self._logging_service = LoggingService()
        return self._logging_service
    
    # Core Services (with dependencies)
    def graph_builder_service(self) -> GraphBuilderService:
        if not hasattr(self, '_graph_builder_service'):
            self._graph_builder_service = GraphBuilderService(
                csv_parser_service=self.csv_graph_parser_service(),
                logging_service=self.logging_service()
            )
        return self._graph_builder_service
    
    # Business Services (graceful degradation)
    def llm_service(self) -> Optional[LLMService]:
        try:
            if not hasattr(self, '_llm_service'):
                self._llm_service = LLMService(
                    config=self.app_config_service(),
                    logger=self.logging_service()
                )
            return self._llm_service
        except Exception:
            return None  # Graceful degradation
```

## Service Patterns

### Protocol-Based Injection

Services can be injected based on protocols:

```python
# Define protocols for service users
class LLMServiceUser(Protocol):
    """Protocol for agents that use LLM services"""
    def configure_llm_service(self, llm_service: LLMService) -> None: ...

class StorageCapableAgent(Protocol):
    """Protocol for agents that use storage services"""
    def configure_storage_service(self, storage_service: StorageService) -> None: ...

# Agent factory checks protocols and injects services
def create_agent(self, node: Node) -> BaseAgent:
    agent = agent_class(name=node.name, ...)
    
    # Inject based on protocols
    if isinstance(agent, LLMServiceUser):
        agent.configure_llm_service(self.llm_service)
    
    if isinstance(agent, StorageCapableAgent):
        storage = self.storage_manager.get_service(agent.storage_type)
        agent.configure_storage_service(storage)
    
    return agent
```

### Service Configuration

Services are configured through the container:

```python
# Get services from container
container = Container()
graph_builder = container.graph_builder_service()
runner = container.graph_runner_service()

# Services automatically get their dependencies
# No manual wiring needed!
```

## Migration from Old Architecture

### Old Pattern (Mixed Responsibilities)
```python
class GraphBuilder:
    def __init__(self):
        self.logger = get_logger()  # Direct creation
        self.config = load_config()  # Direct loading
    
    def build(self, csv_path):
        # Mixed: Business logic + data + I/O
        data = pd.read_csv(csv_path)
        nodes = self.create_nodes(data)
        graph = Graph(nodes)
        graph.validate()  # Business logic in model
        return graph
```

### New Pattern (Clean Architecture)
```python
class GraphBuilderService:
    def __init__(self, csv_parser_service, logging_service):
        # Dependencies injected
        self.csv_parser = csv_parser_service
        self.logger = logging_service.get_class_logger(self)
    
    def build_from_csv(self, csv_path: Path) -> Graph:
        # Clean separation
        rows = self.csv_parser.parse_csv(csv_path)  # I/O in service
        nodes = self._create_nodes(rows)  # Business logic in service
        return Graph(name=..., nodes=nodes)  # Pure data model
```

## Benefits of Clean Architecture

### 1. Testability
- Easy to mock dependencies
- Services can be tested in isolation
- Clear boundaries for unit tests

### 2. Maintainability
- Single responsibility for each component
- Easy to find and fix issues
- Clear dependency flow

### 3. Extensibility
- New services can be added easily
- Existing services can be replaced
- Protocol-based extension points

### 4. Flexibility
- Services can be composed differently
- Alternative implementations possible
- Graceful degradation built-in

## Best Practices

### 1. Keep Models Pure
- Only data and simple data access
- No business logic whatsoever
- No dependencies on services

### 2. Use Dependency Injection
- Never create dependencies directly
- Always inject through constructor
- Use the container for wiring

### 3. Follow the Layers
- Core uses Services
- Services use Models
- Never skip layers

### 4. Test with Real Services
- Use real DI container in tests
- Mock only external dependencies
- Test service interactions

## Common Patterns

### Service Creation Pattern
```python
class MyService:
    def __init__(self, dep1_service, dep2_service, logging_service):
        self.dep1 = dep1_service
        self.dep2 = dep2_service
        self.logger = logging_service.get_class_logger(self)
    
    def do_something(self):
        self.logger.debug("Doing something")
        # Use injected services
```

### Model Creation Pattern
```python
@dataclass
class MyModel:
    id: str
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Only simple data methods
    def add_data(self, key: str, value: Any):
        self.data[key] = value
```

### Testing Pattern
```python
class TestMyService(unittest.TestCase):
    def setUp(self):
        self.container = Container()
        self.service = self.container.my_service()
    
    def test_operation(self):
        # Test with real services
        result = self.service.do_operation()
        self.assertIsNotNone(result)
```

## Next Steps

1. Review the [Service Catalog](./service_catalog.md) for detailed service documentation
2. Read the [Dependency Injection Guide](./dependency_injection_guide.md) for DI patterns
3. See the [Migration Guide](./migration_guide.md) for updating existing code
4. Check [Testing Patterns](../tests/fresh_suite/TESTING_PATTERNS.md) for test guidelines

The clean architecture provides a solid foundation for AgentMap's continued growth and maintainability while preserving all existing functionality.
