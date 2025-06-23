# Dependency Injection Guide

This guide explains how dependency injection (DI) works in AgentMap's clean architecture and how to use it effectively.

## Overview

AgentMap uses a custom dependency injection container that provides:
- Automatic dependency resolution
- Lazy service instantiation
- Singleton pattern for services
- Graceful degradation for optional services
- Clean testing patterns

## The DI Container

### Basic Structure

```python
class Container:
    """Main dependency injection container for AgentMap"""
    
    def _get_or_create(self, attr_name: str, factory: Callable):
        """Helper to implement singleton pattern"""
        if not hasattr(self, attr_name):
            setattr(self, attr_name, factory())
        return getattr(self, attr_name)
```

### Service Registration Pattern

Services are registered as methods in the container:

```python
class Container:
    # Simple service (no dependencies)
    def logging_service(self) -> LoggingService:
        return self._get_or_create('_logging_service', LoggingService)
    
    # Service with dependencies
    def graph_builder_service(self) -> GraphBuilderService:
        return self._get_or_create('_graph_builder_service',
            lambda: GraphBuilderService(
                csv_parser_service=self.csv_graph_parser_service(),
                logging_service=self.logging_service()
            )
        )
    
    # Optional service with graceful degradation
    def llm_service(self) -> Optional[LLMService]:
        try:
            return self._get_or_create('_llm_service',
                lambda: LLMService(
                    config=self.app_config_service(),
                    logger=self.logging_service()
                )
            )
        except Exception as e:
            self.logging_service().get_logger("Container").warning(
                f"LLM service not available: {e}"
            )
            return None
```

## Using the Container

### Basic Usage

```python
# Create container instance
container = Container()

# Get services (automatically created and wired)
graph_builder = container.graph_builder_service()
runner = container.graph_runner_service()

# Services are singletons
assert container.logging_service() is container.logging_service()
```

### In Application Code

```python
# In CLI commands
def run_command(graph_name: str, initial_state: Dict):
    container = Container()
    runner = container.graph_runner_service()
    result = runner.run_graph(graph_name, initial_state)
    return result

# In API endpoints
@app.post("/run/{graph_name}")
async def run_graph_endpoint(graph_name: str, state: Dict):
    container = Container()  # Could be injected via FastAPI dependency
    runner = container.graph_runner_service()
    result = runner.run_graph(graph_name, state)
    return result
```

## Service Dependencies

### Dependency Types

1. **Required Dependencies**: Must be available
```python
def __init__(self, logging_service: LoggingService):
    self.logger = logging_service.get_class_logger(self)
```

2. **Optional Dependencies**: May be None
```python
def __init__(self, llm_service: Optional[LLMService]):
    self.llm_service = llm_service  # Handle None case
```

3. **Protocol-Based Dependencies**: Injected based on interface
```python
if isinstance(agent, LLMServiceUser):
    agent.configure_llm_service(self.llm_service)
```

### Dependency Graph

```
LoggingService (no deps)
    ↓
ConfigService → AppConfigService
    ↓              ↓
CSVParser ←────────┘
    ↓
GraphBuilderService
    ↓
CompilationService → GraphRunnerService
    ↓                      ↓
AgentFactoryService ←──────┘
```

## Protocol-Based Injection

### Defining Protocols

```python
from typing import Protocol

class LLMServiceUser(Protocol):
    """Protocol for components that use LLM services"""
    def configure_llm_service(self, llm_service: LLMService) -> None: ...

class StorageCapableAgent(Protocol):
    """Protocol for agents that use storage services"""
    def configure_storage_service(self, storage_service: StorageService) -> None: ...

class NodeRegistryUser(Protocol):
    """Protocol for components that need node registry"""
    def configure_node_registry(self, registry: NodeRegistryService) -> None: ...
```

### Implementing Protocols

```python
class MyAgent(BaseAgent, LLMServiceUser, StorageCapableAgent):
    """Agent that uses both LLM and storage services"""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self._llm_service = None
        self._storage_service = None
    
    def configure_llm_service(self, llm_service: LLMService) -> None:
        """Configure LLM service"""
        self._llm_service = llm_service
        self.log_debug("LLM service configured")
    
    def configure_storage_service(self, storage_service: StorageService) -> None:
        """Configure storage service"""
        self._storage_service = storage_service
        self.log_debug("Storage service configured")
```

### Using Protocol Injection

```python
class AgentFactoryService:
    def create_agent(self, node: Node) -> BaseAgent:
        # Create agent
        agent = agent_class(name=node.name, **kwargs)
        
        # Inject services based on protocols
        if isinstance(agent, LLMServiceUser) and self.llm_service:
            agent.configure_llm_service(self.llm_service)
        
        if isinstance(agent, StorageCapableAgent):
            storage = self.storage_manager.get_service(agent.storage_type)
            agent.configure_storage_service(storage)
        
        if isinstance(agent, NodeRegistryUser):
            agent.configure_node_registry(self.node_registry)
        
        return agent
```

## Testing with DI

### Unit Testing Pattern

```python
class TestGraphBuilderService(unittest.TestCase):
    def setUp(self):
        # Use real container for integration
        self.container = Container()
        self.service = self.container.graph_builder_service()
    
    def test_build_from_csv(self):
        # Test with real dependencies
        graph = self.service.build_from_csv(self.test_csv)
        self.assertIsInstance(graph, Graph)
```

### Mocking Dependencies

```python
class TestWithMocks(unittest.TestCase):
    def setUp(self):
        # Create mocks
        self.mock_csv_parser = Mock(spec=CSVGraphParserService)
        self.mock_logger = Mock(spec=LoggingService)
        
        # Create service with mocks
        self.service = GraphBuilderService(
            csv_parser_service=self.mock_csv_parser,
            logging_service=self.mock_logger
        )
    
    def test_parsing_called(self):
        # Setup mock
        self.mock_csv_parser.parse_csv.return_value = []
        
        # Test
        self.service.build_from_csv(Path("test.csv"))
        
        # Verify
        self.mock_csv_parser.parse_csv.assert_called_once()
```

### Testing Optional Dependencies

```python
class TestOptionalDependencies(unittest.TestCase):
    def test_without_llm_service(self):
        # Create container without LLM config
        container = Container()
        
        # LLM service should be None
        llm_service = container.llm_service()
        self.assertIsNone(llm_service)
        
        # But other services should work
        graph_builder = container.graph_builder_service()
        self.assertIsNotNone(graph_builder)
```

## Graceful Degradation

### Pattern for Optional Services

```python
class Container:
    def vector_service(self) -> Optional[VectorService]:
        """Vector service with graceful degradation"""
        try:
            # Check if vector DB dependencies available
            import chromadb  # or other vector DB
            
            return self._get_or_create('_vector_service',
                lambda: VectorService(
                    config=self.storage_config_service(),
                    logger=self.logging_service()
                )
            )
        except ImportError:
            self.logging_service().get_logger("Container").info(
                "Vector service not available - dependencies not installed"
            )
            return None
        except Exception as e:
            self.logging_service().get_logger("Container").warning(
                f"Vector service initialization failed: {e}"
            )
            return None
```

### Handling Missing Services

```python
class MyService:
    def __init__(self, llm_service: Optional[LLMService]):
        self.llm_service = llm_service
    
    def process_with_ai(self, text: str) -> str:
        if self.llm_service is None:
            # Fallback behavior
            return f"AI not available. Original: {text}"
        
        # Normal AI processing
        return self.llm_service.generate(text)
```

## Best Practices

### 1. Constructor Injection

Always inject dependencies through the constructor:

```python
# Good ✅
class MyService:
    def __init__(self, dep_service: DependencyService):
        self.dep = dep_service

# Bad ❌
class MyService:
    def __init__(self):
        self.dep = DependencyService()  # Creates tight coupling
```

### 2. Type Hints

Use proper type hints for all dependencies:

```python
def __init__(self, 
             logging_service: LoggingService,
             config_service: AppConfigService,
             llm_service: Optional[LLMService] = None):
    # Clear types for all dependencies
```

### 3. Single Responsibility

Each service should have one clear responsibility:

```python
# Good ✅
class GraphBuilderService:  # Only builds graphs
class CompilationService:   # Only compiles graphs
class ValidationService:    # Only validates

# Bad ❌  
class GraphService:  # Does everything with graphs
```

### 4. Avoid Service Locator

Don't pass the container around:

```python
# Good ✅
def __init__(self, needed_service: NeededService):
    self.service = needed_service

# Bad ❌
def __init__(self, container: Container):
    self.service = container.needed_service()  # Service locator anti-pattern
```

### 5. Test with Real Container

Prefer integration tests with real dependencies:

```python
# Good ✅
def setUp(self):
    self.container = Container()
    self.service = self.container.my_service()

# Use mocks only when necessary
def test_specific_behavior(self):
    mock_dep = Mock()
    service = MyService(mock_dep)
    # Test specific interaction
```

## Adding New Services

### Step 1: Create Service Class

```python
# services/my_new_service.py
class MyNewService:
    """Service for doing something new"""
    
    def __init__(self, 
                 dependency_service: DependencyService,
                 logging_service: LoggingService):
        self.dependency = dependency_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.info("MyNewService initialized")
    
    def do_something(self, input: str) -> str:
        self.logger.debug(f"Processing: {input}")
        # Implementation
        return result
```

### Step 2: Register in Container

```python
# di/containers.py
class Container:
    def my_new_service(self) -> MyNewService:
        """Provide MyNewService instance"""
        return self._get_or_create('_my_new_service',
            lambda: MyNewService(
                dependency_service=self.dependency_service(),
                logging_service=self.logging_service()
            )
        )
```

### Step 3: Use in Other Services

```python
class OtherService:
    def __init__(self, my_new_service: MyNewService):
        self.new_service = my_new_service
    
    def use_new_service(self):
        result = self.new_service.do_something("input")
        return result
```

### Step 4: Write Tests

```python
class TestMyNewService(unittest.TestCase):
    def setUp(self):
        self.container = Container()
        self.service = self.container.my_new_service()
    
    def test_do_something(self):
        result = self.service.do_something("test")
        self.assertEqual(result, expected)
```

## Container Lifecycle

### Application Lifecycle

1. **Container Creation**: Usually one per application/request
2. **Service Creation**: Lazy, on first request
3. **Service Caching**: Singletons within container instance
4. **Cleanup**: Services cleaned up with container

### Request Scoping

For web applications, consider request-scoped containers:

```python
# FastAPI example
async def get_container():
    """Dependency that provides container per request"""
    container = Container()
    try:
        yield container
    finally:
        # Cleanup if needed
        pass

@app.post("/run")
async def run_endpoint(
    request: RunRequest,
    container: Container = Depends(get_container)
):
    runner = container.graph_runner_service()
    return runner.run_graph(request.graph_name, request.state)
```

## Troubleshooting

### Common Issues

1. **Circular Dependencies**
   - Error: RecursionError in container
   - Solution: Refactor to break circular dependency

2. **Missing Optional Service**
   - Error: None returned from container
   - Solution: Check configuration and dependencies

3. **Service Not Registered**
   - Error: AttributeError on container
   - Solution: Add service method to container

4. **Dependency Not Injected**
   - Error: Service method fails
   - Solution: Check constructor parameters

### Debug Logging

Enable debug logging to trace DI issues:

```python
# Set logging level
container = Container()
container.logging_service().set_level("DEBUG")

# Services will log initialization
graph_builder = container.graph_builder_service()
# Logs: "GraphBuilderService initialized with dependencies"
```

## Summary

The dependency injection system provides:
- Clean separation of concerns
- Easy testing and mocking
- Graceful degradation
- Clear dependency management
- Flexible service composition

Follow the patterns in this guide for consistent, maintainable service development.
