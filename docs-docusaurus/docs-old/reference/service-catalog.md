---
---

---
sidebar_position: 2
title: Service Catalog
description: Comprehensive catalog of all AgentMap services and their interfaces
---

# Service Catalog

This document provides a comprehensive catalog of all services in the AgentMap clean architecture, their responsibilities, interfaces, and usage examples.

## Service Categories

1. **Core Services** - Essential business logic services
2. **Infrastructure Services** - Technical and external integration services  
3. **Configuration Services** - Configuration management services
4. **Storage Services** - Data persistence services
5. **Validation Services** - Data validation services
6. **Execution Services** - Workflow execution services

## Core Services

### GraphBuilderService

**Purpose**: Builds graph models from CSV files

**Dependencies**:
- CSVGraphParserService
- LoggingService

**Key Methods**:
```python
def build_from_csv(self, csv_path: Path, graph_name: str = None) -> Graph:
    """Build a graph model from CSV file"""
    
def build_from_dataframe(self, df: pd.DataFrame, graph_name: str) -> Graph:
    """Build a graph model from pandas DataFrame"""
```

**Usage Example**:
```python
graph_builder = container.graph_builder_service()
graph = graph_builder.build_from_csv(Path("workflow.csv"))
```

---

### CompilationService

**Purpose**: Compiles graph models into executable LangGraph StateGraphs

**Dependencies**:
- GraphAssemblyService
- GraphBuilderService  
- GraphBundleService
- LoggingService

**Key Methods**:
```python
def compile_graph(self, graph_name: str, csv_path: Path = None, 
                  state_schema: Type = None) -> CompiledGraph:
    """Compile a graph from CSV or cache"""
    
def compile_from_model(self, graph: Graph, state_schema: Type = None) -> CompiledGraph:
    """Compile a graph model directly"""
```

**Usage Example**:
```python
compilation = container.compilation_service()
compiled = compilation.compile_graph("MyWorkflow", Path("workflow.csv"))
```

---

### GraphRunnerService

**Purpose**: Orchestrates graph execution with tracking and policies

**Dependencies**:
- CompilationService
- ExecutionTrackingService
- ExecutionPolicyService
- StateAdapterService
- LoggingService

**Key Methods**:
```python
def run_graph(self, graph_name: str, initial_state: Dict[str, Any], 
              csv_path: Path = None) -> ExecutionResult:
    """Execute a graph with full tracking"""
    
def run_compiled_graph(self, compiled_graph: CompiledGraph, 
                       initial_state: Dict[str, Any]) -> ExecutionResult:
    """Execute a pre-compiled graph"""
```

**Usage Example**:
```python
runner = container.graph_runner_service()
result = runner.run_graph("MyWorkflow", {"input": "data"})
print(f"Success: {result.success}")
print(f"Duration: {result.duration}s")
```

---

### OrchestratorService

**Purpose**: Provides node selection and orchestration business logic for routing workflows

**Dependencies**:
- PromptManagerService
- LoggingService
- LLMServiceProtocol (optional)

**Key Methods**:
```python
def select_best_node(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]],
                     strategy: str = "tiered", confidence_threshold: float = 0.8,
                     node_filter: str = "all", llm_config: Optional[Dict[str, Any]] = None,
                     context: Optional[Dict[str, Any]] = None) -> str:
    """Select the best matching node using specified strategy"""

def parse_node_keywords(self, node_info: Dict[str, Any]) -> List[str]:
    """Parse keywords from node information for efficient matching"""
```

**Usage Example**:
```python
orchestrator = container.orchestrator_service()
selected_node = orchestrator.select_best_node(
    input_text="I need to process a payment",
    available_nodes=nodes_dict,
    strategy="tiered",
    confidence_threshold=0.8
)
print(f"Selected: {selected_node}")
```

**Key Features**:
- **Multiple Matching Strategies**: Algorithm-based, LLM-based, or tiered approach
- **CSV Keyword Integration**: Parses keywords from node context for efficient matching
- **PromptManagerService Integration**: Uses existing template system for LLM prompts
- **Confidence Thresholds**: Configurable fallback between algorithmic and LLM matching
- **Node Filtering**: Support for type-based or name-based node filtering

**CSV Keyword Support**:
Nodes can define keywords in their context for improved algorithmic matching:

```csv
name,description,type,context
auth_node,Handle user authentication,security,"{""keywords"": ""login,authentication,signin""}"
payment_node,Process payments,financial,"{""keywords"": [""payment"", ""billing"", ""transaction""]}"
email_node,Send notifications,communication,"{""keywords"": ""email,notification,message,send""}"
```

The service intelligently parses keywords from:
- `context.keywords` field (string or array format)
- `description`, `prompt`, `intent` fields
- Automatic filtering of short/common words
- Support for phrase matching with confidence boosting

---

### AgentFactoryService

**Purpose**: Creates and configures agent instances with dependency injection

**Dependencies**:
- AgentRegistryService
- LoggingService
- LLMService (optional)
- StorageManager
- NodeRegistryService

**Key Methods**:
```python
def create_agent(self, node: Node) -> BaseAgent:
    """Create an agent with all required services injected"""
    
def create_agent_by_type(self, agent_type: str, name: str, 
                         context: Dict = None) -> BaseAgent:
    """Create an agent by type with services"""
```

**Usage Example**:
```python
factory = container.agent_factory_service()
agent = factory.create_agent(node)
# Agent has all services injected based on protocols
```

---

### GraphAssemblyService

**Purpose**: Assembles graph models into LangGraph StateGraphs

**Dependencies**:
- AgentFactoryService
- FunctionResolutionService
- StateAdapterService
- LoggingService

**Key Methods**:
```python
def assemble_graph(self, graph: Graph, state_schema: Type = None) -> StateGraph:
    """Assemble a graph model into LangGraph"""
    
def assemble_with_agents(self, graph: Graph, agents: Dict[str, BaseAgent], 
                         state_schema: Type = None) -> StateGraph:
    """Assemble with pre-created agents"""
```

**Usage Example**:
```python
assembly = container.graph_assembly_service()
state_graph = assembly.assemble_graph(graph_model, StateSchema)
compiled = state_graph.compile()
```

## Infrastructure Services

### LoggingService

**Purpose**: Provides structured logging throughout the application

**Dependencies**: None (base infrastructure service)

**Key Methods**:
```python
def get_class_logger(self, obj: Any) -> Logger:
    """Get a logger for a class instance"""
    
def get_agent_logger(self, agent_name: str) -> Logger:
    """Get a logger specifically for an agent"""
    
def set_level(self, level: str):
    """Set global logging level"""
```

**Usage Example**:
```python
class MyService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_class_logger(self)
        self.logger.info("Service initialized")
```

---

### StateAdapterService

**Purpose**: Adapts state between different formats (dict, Pydantic, etc.)

**Dependencies**:
- LoggingService

**Key Methods**:
```python
def adapt_initial_state(self, state: Any, schema: Type = None) -> Dict[str, Any]:
    """Adapt initial state to required format"""
    
def extract_value(self, state: Any, key: str, default: Any = None) -> Any:
    """Extract value from state regardless of format"""
```

**Usage Example**:
```python
adapter = container.state_adapter_service()
adapted = adapter.adapt_initial_state({"input": "data"}, StateSchema)
```

---

### FunctionResolutionService

**Purpose**: Resolves function references for dynamic routing

**Dependencies**:
- LoggingService

**Key Methods**:
```python
def resolve_function(self, func_ref: str) -> Optional[Callable]:
    """Resolve a function reference like 'func:my_router'"""
    
def register_function(self, name: str, func: Callable):
    """Register a function for resolution"""
```

**Usage Example**:
```python
resolver = container.function_resolution_service()
router_func = resolver.resolve_function("func:custom_router")
```

## Configuration Services

### AppConfigService

**Purpose**: Manages application configuration with defaults

**Dependencies**:
- ConfigService

**Key Methods**:
```python
def get_csv_path(self) -> Optional[Path]:
    """Get configured CSV path"""
    
def get_llm_config(self, provider: str) -> Dict[str, Any]:
    """Get LLM provider configuration"""
    
def get_prompts_config(self) -> Dict[str, Any]:
    """Get prompts configuration"""
```

**Usage Example**:
```python
config = container.app_config_service()
csv_path = config.get_csv_path()
openai_config = config.get_llm_config("openai")
```

---

### StorageConfigService

**Purpose**: Manages storage service configuration

**Dependencies**:
- ConfigService

**Key Methods**:
```python
def get_provider_config(self, storage_type: str, provider: str) -> Dict[str, Any]:
    """Get configuration for a storage provider"""
    
def get_default_provider(self, storage_type: str) -> str:
    """Get default provider for storage type"""
```

**Usage Example**:
```python
storage_config = container.storage_config_service()
csv_config = storage_config.get_provider_config("csv", "local")
```

## Storage Services

### StorageManager

**Purpose**: Manages and provides access to all storage services

**Dependencies**:
- StorageConfigService
- Various storage service implementations

**Key Methods**:
```python
def get_service(self, storage_type: str, provider: str = None) -> StorageService:
    """Get a storage service by type and provider"""
    
def register_service(self, storage_type: str, provider: str, service: StorageService):
    """Register a custom storage service"""
```

**Usage Example**:
```python
storage_manager = container.storage_manager()
csv_service = storage_manager.get_service("csv")
json_service = storage_manager.get_service("json", "cloud")
```

---

### CSVStorageService

**Purpose**: Handles CSV file operations with pandas

**Key Methods**:
```python
def read(self, collection: str, document_id: Any = None, 
         format: str = "dict", id_field: str = None) -> Any:
    """Read CSV data in various formats"""
    
def write(self, collection: str, data: Any, document_id: Any = None,
          mode: WriteMode = WriteMode.WRITE) -> StorageResult:
    """Write data to CSV"""
```

**Usage Example**:
```python
csv_service = storage_manager.get_service("csv")
data = csv_service.read("users", format="records")
result = csv_service.write("users", new_data)
```

---

### JSONStorageService

**Purpose**: Handles JSON document storage

**Key Methods**:
```python
def read(self, collection: str, document_id: str = None, 
         path: str = None) -> Any:
    """Read JSON documents or paths"""
    
def write(self, collection: str, data: Any, document_id: str = None,
          mode: WriteMode = WriteMode.WRITE, path: str = None) -> StorageResult:
    """Write JSON documents"""
```

**Usage Example**:
```python
json_service = storage_manager.get_service("json")
doc = json_service.read("configs", "app_config")
result = json_service.write("configs", {"debug": True}, "app_config")
```

## Validation Services

### ValidationService

**Purpose**: Orchestrates all validation operations

**Dependencies**:
- CSVValidationService
- ConfigValidationService
- ValidationCacheService
- LoggingService

**Key Methods**:
```python
def validate_csv(self, csv_path: Path) -> ValidationResult:
    """Validate a CSV file"""
    
def validate_config(self, config_path: Path = None) -> ValidationResult:
    """Validate configuration files"""
```

**Usage Example**:
```python
validator = container.validation_service()
result = validator.validate_csv(Path("workflow.csv"))
if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error.message}")
```

## Execution Services

### ExecutionTrackingService

**Purpose**: Tracks workflow execution metrics and history

**Dependencies**:
- AppConfigService
- LoggingService

**Key Methods**:
```python
def create_tracker(self, graph_name: str) -> ExecutionTracker:
    """Create a new execution tracker"""
    
def get_tracking_enabled(self) -> bool:
    """Check if tracking is enabled"""
```

**Usage Example**:
```python
tracking = container.execution_tracking_service()
tracker = tracking.create_tracker("MyWorkflow")
tracker.start()
# ... execution ...
tracker.complete(final_state)
summary = tracker.get_summary()
```

---

### ExecutionPolicyService

**Purpose**: Evaluates execution success based on configured policies

**Dependencies**:
- AppConfigService
- LoggingService

**Key Methods**:
```python
def evaluate_success(self, execution_summary: ExecutionSummary, 
                     graph_name: str = None) -> bool:
    """Evaluate if execution was successful"""
    
def get_policy_type(self) -> str:
    """Get configured policy type"""
```

**Usage Example**:
```python
policy = container.execution_policy_service()
success = policy.evaluate_success(execution_summary, "MyWorkflow")
```

## Service Registration in DI Container

All services are registered in the DI container with proper dependency injection:

```python
class Container:
    # Infrastructure services (no dependencies)
    def logging_service(self) -> LoggingService:
        return self._get_or_create('_logging_service', LoggingService)
    
    # Services with dependencies
    def graph_builder_service(self) -> GraphBuilderService:
        return self._get_or_create('_graph_builder_service', 
            lambda: GraphBuilderService(
                csv_parser_service=self.csv_graph_parser_service(),
                logging_service=self.logging_service()
            )
        )
    
    # Optional services with graceful degradation
    def llm_service(self) -> Optional[LLMService]:
        try:
            return self._get_or_create('_llm_service',
                lambda: LLMService(
                    config=self.app_config_service(),
                    logger=self.logging_service()
                )
            )
        except Exception:
            return None
```

## Service Lifecycle

1. **Creation**: Services are created lazily when first requested
2. **Caching**: Services are cached in the container (singleton pattern)
3. **Dependency Injection**: Dependencies are automatically injected
4. **Graceful Degradation**: Optional services return None if unavailable
5. **Cleanup**: Services can implement cleanup methods if needed

## Best Practices

1. **Always inject dependencies** - Never create services directly
2. **Use type hints** - Clear interfaces with proper typing
3. **Handle None returns** - Optional services may not be available
4. **Log appropriately** - Use injected loggers for debugging
5. **Test with container** - Use real DI container in tests

## Adding New Services

To add a new service:

1. Create service class with constructor injection
2. Add to appropriate module (services/your_service.py)
3. Register in DI container (di/containers.py)
4. Add to this catalog with documentation
5. Write tests following patterns

Example:
```python
# 1. Create service
class MyNewService:
    def __init__(self, dep_service: DependencyService, logging_service: LoggingService):
        self.dep = dep_service
        self.logger = logging_service.get_class_logger(self)
    
    def do_something(self) -> Result:
        self.logger.debug("Doing something")
        return Result()

# 2. Register in container
class Container:
    def my_new_service(self) -> MyNewService:
        return self._get_or_create('_my_new_service',
            lambda: MyNewService(
                dep_service=self.dependency_service(),
                logging_service=self.logging_service()
            )
        )
```

This catalog will be updated as new services are added to the system.
