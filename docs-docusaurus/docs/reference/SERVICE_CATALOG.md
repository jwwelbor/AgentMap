# AgentMap Service Catalog

**Document Version**: 1.0
**Last Updated**: 2025-10-28
**Maintainer**: Architecture Team

---

## Executive Summary

AgentMap comprises **55+ service classes** organized into **6 container modules** with **40+ protocol interfaces**. This catalog provides a comprehensive inventory of all services, their responsibilities, dependencies, and protocols for development and architectural reference.

### Service Statistics

| Category | Count | Purpose |
|----------|-------|---------|
| **Total Services** | 55+ | Core business logic |
| **Protocol Interfaces** | 40+ | Service contracts |
| **Container Modules** | 6 | DI organization |
| **Core Services** | 12 | Foundation services |
| **Graph Services** | 15 | Workflow orchestration |
| **Agent Services** | 4 | Agent management |
| **Storage Services** | 8+ | Data persistence |
| **LLM Services** | 4 | AI integration |
| **Validation Services** | 5 | Quality assurance |

---

## 1. Service Organization

### 1.1 Container Structure

```
ApplicationContainer (Root)
├── CoreContainer: Foundation services
├── StorageContainer: Data persistence
├── BootstrapContainer: Initialization & parsing
├── LLMContainer: AI/LLM integration
├── HostRegistryContainer: Custom service injection
├── GraphCoreContainer: Graph orchestration core
└── GraphAgentContainer: Agent management
```

### 1.2 Service Naming Conventions

**Patterns:**
- Service classes: `{Domain}Service` (e.g., `GraphRunnerService`)
- Protocol interfaces: `{Service}Protocol` (e.g., `LLMServiceProtocol`)
- Capability protocols: `{Feature}CapableAgent` (e.g., `LLMCapableAgent`)
- Config services: `{Domain}ConfigService` (e.g., `AppConfigService`)

**File Locations:**
```
Services: src/agentmap/services/{service_name}.py
Protocols: src/agentmap/services/protocols.py
DI Registration: src/agentmap/di/containers.py
Service Tests: tests/services/test_{service_name}.py
```

---

## 2. Core Services (CoreContainer)

### 2.1 ConfigService

**Responsibility**: Load and parse YAML configuration files.

**File**: `services/config/config_service.py`

**Key Methods:**
```python
def load_yaml(file_path: Path) -> Dict[str, Any]:
    """Load YAML configuration file."""

def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value by key."""
```

**Dependencies**: None (foundational service)

**Protocol**: N/A (concrete implementation only)

**Usage:**
```python
config_service = container.config_service()
config_data = config_service.load_yaml(Path("config.yaml"))
value = config_service.get_config_value("execution.timeout", 300)
```

---

### 2.2 AppConfigService

**Responsibility**: Domain-specific configuration access and validation.

**File**: `services/config/app_config_service.py`

**Key Methods:**
```python
def get_execution_config() -> Dict:
    """Get execution configuration."""

def get_storage_config() -> Dict:
    """Get storage configuration."""

def get_csv_repository_path() -> Path:
    """Get CSV repository path."""

def use_direct_import_agents() -> bool:
    """Check if direct import mode enabled."""
```

**Dependencies**:
- `ConfigService` (YAML loading)
- `LoggingService` (error logging)

**DI Registration:**
```python
app_config_service = providers.Singleton(
    AppConfigService,
    config_service,
    logging_service
)
```

**Usage:**
```python
app_config = container.app_config_service()
exec_config = app_config.get_execution_config()
use_direct = app_config.use_direct_import_agents()
```

---

### 2.3 LoggingService

**Responsibility**: Structured logging with class-specific loggers.

**File**: `services/logging_service.py`

**Key Methods:**
```python
def get_class_logger(instance: Any) -> logging.Logger:
    """Get logger for class instance."""

def get_logger(name: str) -> logging.Logger:
    """Get logger by name."""

def set_level(level: str) -> None:
    """Set global log level."""
```

**Dependencies**: None (foundational service)

**Usage:**
```python
class MyService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_class_logger(self)

    def my_method(self):
        self.logger.info("Method called", extra={"key": "value"})
```

---

### 2.4 FilePathService

**Responsibility**: Path resolution, validation, and normalization.

**File**: `services/file_path_service.py`

**Key Methods:**
```python
def resolve_path(path: Union[str, Path]) -> Path:
    """Resolve path with home directory expansion."""

def validate_file_exists(path: Path) -> bool:
    """Validate file exists."""

def get_cache_folder() -> Path:
    """Get cache folder path."""

def get_csv_repository_path() -> Path:
    """Get CSV repository path."""
```

**Dependencies**:
- `AppConfigService` (configuration)
- `LoggingService` (logging)

**Usage:**
```python
file_path_service = container.file_path_service()
cache_folder = file_path_service.get_cache_folder()
resolved = file_path_service.resolve_path("~/workflows/file.csv")
```

---

### 2.5 PromptManagerService

**Responsibility**: Prompt resolution and template formatting.

**File**: `services/prompt_manager_service.py`

**Protocol**: `PromptManagerServiceProtocol`

**Key Methods:**
```python
def resolve_prompt(prompt_ref: str) -> str:
    """Resolve prompt reference to text."""

def format_prompt(prompt_ref_or_text: str, values: Dict) -> str:
    """Format prompt with variable substitution."""
```

**Prompt Reference Formats:**
```python
"prompt:name"              # From prompts directory
"file:/path/to/prompt.txt" # From file
"yaml:path#key"            # From YAML key
"Plain text prompt"        # Direct text
```

**Dependencies**:
- `AppConfigService` (prompt paths)
- `FilePathService` (file resolution)
- `LoggingService` (logging)

**Usage:**
```python
prompt_service = container.prompt_manager_service()
prompt = prompt_service.resolve_prompt("prompt:classification")
formatted = prompt_service.format_prompt(prompt, {"text": user_input})
```

---

### 2.6 AuthService

**Responsibility**: API authentication (API keys, bearer tokens).

**File**: `services/auth_service.py`

**Key Methods:**
```python
def generate_api_key(name: str) -> str:
    """Generate new API key."""

def verify_api_key(key: str) -> bool:
    """Verify API key validity."""

def verify_bearer_token(token: str) -> bool:
    """Verify bearer token."""

def list_api_keys() -> List[Dict]:
    """List all API keys."""

def revoke_api_key(key: str) -> bool:
    """Revoke API key."""
```

**Dependencies**:
- `AppConfigService` (auth configuration)
- `LoggingService` (audit logging)

**Usage:**
```python
auth_service = container.auth_service()
api_key = auth_service.generate_api_key("production-key")
valid = auth_service.verify_api_key(request_key)
```

---

## 3. Storage Services (StorageContainer)

### 3.1 StorageServiceManager

**Responsibility**: Unified storage interface across all storage types.

**File**: `services/storage/manager.py`

**Protocol**: `StorageServiceProtocol`

**Key Methods:**
```python
def read(collection: str, **kwargs) -> Any:
    """Read from storage collection."""

def write(collection: str, data: Any, **kwargs) -> Any:
    """Write to storage collection."""
```

**Supported Collections:**
- CSV files: `"filename.csv"`
- JSON files: `"data.json"`
- Files: `"file:path/to/file"`
- Memory: `"memory:key"`
- Vector: `"vector:collection"`

**Dependencies**:
- `CSVStorageService`
- `JSONStorageService`
- `MemoryStorageService`
- `FileStorageService`
- `VectorService`
- `LoggingService`

**Usage:**
```python
storage = container.storage_service_manager()
data = storage.read("data.csv", filters={"status": "active"})
storage.write("results.json", {"result": "success"})
```

---

### 3.2 BlobStorageService

**Responsibility**: Cloud blob storage (S3, Azure Blob, GCS).

**File**: `services/storage/blob_storage_service.py`

**Protocol**: `BlobStorageServiceProtocol`

**Key Methods:**
```python
def read_blob(uri: str, **kwargs) -> bytes:
    """Read blob from cloud storage."""

def write_blob(uri: str, data: bytes, **kwargs) -> Dict:
    """Write blob to cloud storage."""

def blob_exists(uri: str) -> bool:
    """Check if blob exists."""

def list_blobs(prefix: str) -> List[str]:
    """List blobs with prefix."""

def delete_blob(uri: str) -> Dict:
    """Delete blob."""

def get_available_providers() -> List[str]:
    """Get available storage providers."""
```

**URI Formats:**
```python
"s3://bucket/path/file"        # AWS S3
"azure://container/path/file"   # Azure Blob
"gs://bucket/path/file"         # Google Cloud Storage
"file:///local/path/file"       # Local filesystem
```

**Storage Connectors:**
```python
AWS_S3_Connector        # services/storage/aws_s3_connector.py
AzureBlobConnector      # services/storage/azure_blob_connector.py
GCPStorageConnector     # services/storage/gcp_storage_connector.py
LocalFileConnector      # services/storage/local_file_connector.py
```

**Dependencies**:
- `StorageConfigService` (provider configuration)
- `LoggingService` (logging)
- Cloud SDK libraries (boto3, azure-storage-blob, google-cloud-storage)

**Usage:**
```python
blob_service = container.blob_storage_service()
data = blob_service.read_blob("s3://bucket/data.txt")
blob_service.write_blob("azure://container/output.txt", data)
available = blob_service.get_available_providers()  # ["s3", "azure", "local"]
```

---

### 3.3 CSVStorageService

**Responsibility**: CSV file operations with filtering and querying.

**File**: `services/storage/csv_service.py`

**Key Methods:**
```python
def read_csv(path: str, filters: Dict = None) -> List[Dict]:
    """Read CSV with optional filtering."""

def write_csv(path: str, rows: List[Dict]) -> None:
    """Write CSV file."""

def append_csv(path: str, rows: List[Dict]) -> None:
    """Append to CSV file."""
```

**Dependencies**:
- `FilePathService` (path resolution)
- `LoggingService` (logging)

---

### 3.4 JSONStorageService

**Responsibility**: JSON file operations.

**File**: `services/storage/json_service.py`

**Key Methods:**
```python
def read_json(path: str) -> Dict:
    """Read JSON file."""

def write_json(path: str, data: Dict) -> None:
    """Write JSON file."""
```

---

### 3.5 MemoryStorageService

**Responsibility**: In-memory key-value storage.

**File**: `services/storage/memory_service.py`

**Key Methods:**
```python
def get(key: str) -> Any:
    """Get value from memory."""

def set(key: str, value: Any) -> None:
    """Set value in memory."""

def delete(key: str) -> None:
    """Delete key from memory."""
```

---

### 3.6 VectorService

**Responsibility**: Vector embeddings and semantic search.

**File**: `services/storage/vector_service.py`

**Protocols**:
- `EmbeddingServiceProtocol`
- `VectorStorageServiceProtocol`

**Key Methods:**
```python
def embed_and_store(collection: str, texts: List[str]) -> None:
    """Embed texts and store vectors."""

def query(query_text: str, k: int = 5) -> List[Tuple]:
    """Query vectors by similarity."""

def embed_batch(items: List[EmbeddingInput]) -> List[EmbeddingOutput]:
    """Batch embed texts."""
```

**Dependencies**:
- LLM providers (for embeddings)
- ChromaDB (vector database)
- `LoggingService`

---

## 4. Bootstrap Services (BootstrapContainer)

### 4.1 FeaturesRegistryService

**Responsibility**: Track optional feature availability.

**File**: `services/features_registry_service.py`

**Key Methods:**
```python
def is_feature_available(feature: str) -> bool:
    """Check if feature is available."""

def register_feature(feature: str, available: bool) -> None:
    """Register feature availability."""

def get_available_features() -> List[str]:
    """Get list of available features."""
```

**Tracked Features:**
```python
- "llm_openai": OpenAI API available
- "llm_anthropic": Anthropic API available
- "llm_google": Google AI API available
- "storage_s3": AWS S3 available
- "storage_azure": Azure Blob available
- "storage_gcs": Google Cloud Storage available
- "vector_search": ChromaDB available
```

---

### 4.2 AgentRegistryService

**Responsibility**: Register and manage agent types.

**File**: `services/agent/agent_registry_service.py`

**Key Methods:**
```python
def register_agent(name: str, agent_class: Type) -> None:
    """Register agent type."""

def get_agent_class(name: str) -> Type:
    """Get agent class by name."""

def list_agents() -> List[str]:
    """List all registered agents."""
```

---

### 4.3 CSVGraphParserService

**Responsibility**: Parse CSV files to GraphSpec models.

**File**: `services/csv_graph_parser_service.py`

**Key Methods:**
```python
def parse_csv(csv_path: Path) -> List[GraphSpec]:
    """Parse CSV to GraphSpec objects."""

def extract_graph_names(csv_path: Path) -> List[str]:
    """Extract graph names from CSV."""
```

**CSV Parsing Logic:**
```python
1. Read CSV rows
2. Validate required columns
3. Group rows by Graph column
4. Create Node objects for each row
5. Build GraphSpec with nodes and edges
6. Validate graph structure
```

**Dependencies**:
- `ValidationService` (CSV validation)
- `DeclarationParser` (agent declarations)
- `LoggingService`

---

### 4.4 DeclarationParser

**Responsibility**: Parse agent and service declarations.

**File**: `services/declaration_parser.py`

**Key Methods:**
```python
def parse_agent_declaration(agent_type: str) -> AgentDeclaration:
    """Parse agent type declaration."""

def parse_service_declaration(service_name: str) -> ServiceDeclaration:
    """Parse service declaration."""
```

**Declaration Format:**
```python
# Agent declaration from CSV
"AnthropicAgent"           # Built-in agent
"custom.MyAgent"           # Custom agent module path
"CustomAgent[llm,storage]" # With explicit service requirements
```

---

### 4.5 DeclarationRegistryService

**Responsibility**: Service dependency analysis and load ordering.

**File**: `services/declaration_registry_service.py`

**Key Methods:**
```python
def register_declaration(name: str, declaration: ServiceDeclaration) -> None:
    """Register service declaration."""

def get_dependencies(service_name: str) -> List[str]:
    """Get service dependencies."""

def get_load_order() -> List[str]:
    """Calculate optimal service load order."""
```

**Dependency Analysis:**
```python
1. Extract service dependencies from declarations
2. Build dependency graph
3. Detect circular dependencies
4. Topological sort for load order
5. Return ordered service list
```

---

### 4.6 StaticBundleAnalyzer

**Responsibility**: Static analysis for bundle creation (no imports).

**File**: `services/static_bundle_analyzer.py`

**Key Methods:**
```python
def analyze_csv(csv_path: Path) -> GraphBundle:
    """Analyze CSV via static analysis."""

def extract_service_requirements(nodes: List[Node]) -> Set[str]:
    """Extract service requirements from nodes."""
```

**Static Analysis Process:**
```python
1. Parse CSV to GraphSpec (no agent imports)
2. Parse agent declarations
3. Analyze protocol requirements from declarations
4. Determine service dependencies
5. Create GraphBundle with metadata only
6. Cache bundle for fast loading
```

**Performance:**
- Dynamic bundle: ~100ms (full imports)
- Static bundle: ~10ms (declaration analysis only)
- **10x performance improvement**

---

### 4.7 CustomAgentLoader

**Responsibility**: Load user-defined agent classes.

**File**: `services/custom_agent_loader.py`

**Key Methods:**
```python
def load_custom_agent(module_path: str, class_name: str) -> Type:
    """Load custom agent class."""

def discover_agents(module_paths: List[str]) -> Dict[str, Type]:
    """Discover agents in modules."""
```

**Configuration:**
```yaml
# agentmap_config.yaml
custom_agents:
  modules:
    - path: "my_agents.agents"
    - path: "another_package.agents"
```

---

### 4.8 ValidationService

**Responsibility**: High-level validation orchestration.

**File**: `services/validation/validation_service.py`

**Key Methods:**
```python
def validate_csv_for_bundling(csv_path: Path) -> ValidationResult:
    """Validate CSV before bundling."""

def validate_config(config_path: Path) -> ValidationResult:
    """Validate configuration file."""

def validate_all(csv_path: Path, config_path: Path) -> ValidationResult:
    """Validate CSV and config together."""
```

**Validation Checks:**
```python
- CSV structure (required columns)
- Graph names (unique, non-empty)
- Node names (unique within graph)
- Agent types (valid, available)
- Routing (valid targets, functions exist)
- Service dependencies (available)
```

---

### 4.9 CSVValidationService

**Responsibility**: Detailed CSV structure validation.

**File**: `services/validation/csv_validation_service.py`

**Key Methods:**
```python
def validate_structure(csv_path: Path) -> ValidationResult:
    """Validate CSV structure."""

def validate_row(row: Dict) -> List[str]:
    """Validate single CSV row."""
```

---

### 4.10 DependencyCheckerService

**Responsibility**: Check service dependencies availability.

**File**: `services/dependency_checker_service.py`

**Key Methods:**
```python
def check_dependencies(service_requirements: Set[str]) -> Dict[str, bool]:
    """Check if required services are available."""

def get_missing_dependencies() -> List[str]:
    """Get list of missing dependencies."""
```

---

## 5. LLM Services (LLMContainer)

### 5.1 LLMService

**Responsibility**: Unified LLM interface with intelligent routing.

**File**: `services/llm_service.py`

**Protocol**: `LLMServiceProtocol`

**Key Methods:**
```python
def call_llm(
    provider: str,
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    routing_context: Dict = None,
    **kwargs
) -> str:
    """Call LLM with intelligent routing."""
```

**Supported Providers:**
```python
- "openai": GPT-4, GPT-3.5-turbo, GPT-4-turbo
- "anthropic": Claude 3 (Opus, Sonnet, Haiku)
- "google": Gemini Pro, Gemini Ultra
```

**Dependencies**:
- `LLMRoutingService` (intelligent routing)
- `AppConfigService` (LLM configuration)
- `LoggingService` (logging)
- Provider SDKs (openai, anthropic, google-generativeai)

**Usage:**
```python
llm_service = container.llm_service()
response = llm_service.call_llm(
    provider="openai",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    model="gpt-4",
    temperature=0.7
)
```

---

### 5.2 LLMRoutingService

**Responsibility**: Intelligent LLM model routing based on complexity.

**File**: `services/routing/llm_routing_service.py`

**Key Methods:**
```python
def route_request(
    provider: str,
    messages: List[Dict],
    routing_context: Dict
) -> str:
    """Route to optimal model based on complexity."""
```

**Routing Strategy:**
```python
1. Analyze prompt complexity (token count, task type)
2. Check routing context (cost budget, latency requirements)
3. Consult routing cache
4. Select optimal model:
   - Simple tasks → GPT-3.5-turbo
   - Complex reasoning → Claude Opus
   - Code generation → GPT-4
   - Cost-optimized → Cached model
5. Return model name
```

**Dependencies**:
- `PromptComplexityAnalyzer` (complexity analysis)
- `RoutingCache` (decision caching)
- `LLMRoutingConfigService` (routing rules)

---

### 5.3 PromptComplexityAnalyzer

**Responsibility**: Analyze prompt complexity for routing.

**File**: `services/routing/complexity_analyzer.py`

**Key Methods:**
```python
def analyze_complexity(messages: List[Dict]) -> Dict:
    """Analyze prompt complexity."""
```

**Complexity Factors:**
```python
- Token count
- Task type (classification, generation, reasoning)
- Context length
- Required capabilities (vision, code, math)
```

---

### 5.4 RoutingCache

**Responsibility**: Cache LLM routing decisions.

**File**: `services/routing/cache.py`

**Key Methods:**
```python
def get_cached_route(cache_key: str) -> Optional[str]:
    """Get cached routing decision."""

def cache_route(cache_key: str, model: str) -> None:
    """Cache routing decision."""
```

---

## 6. Graph Orchestration Services (GraphCoreContainer)

### 6.1 GraphRunnerService

**Responsibility**: High-level workflow orchestration (5-phase pipeline).

**File**: `services/graph/graph_runner_service.py`

**Key Methods:**
```python
def run(bundle: GraphBundle, initial_state: Dict) -> ExecutionResult:
    """Execute workflow through 5-phase pipeline."""

def resume_from_checkpoint(
    bundle: GraphBundle,
    thread_id: str,
    checkpoint_state: Dict,
    resume_node: str
) -> ExecutionResult:
    """Resume workflow from checkpoint."""
```

**5-Phase Pipeline:**
```python
Phase 1: Bootstrap (conditional)
Phase 2: Execution Tracking Setup
Phase 3: Agent Instantiation
Phase 4: Graph Assembly
Phase 5: Graph Execution
```

**Dependencies**:
- `GraphBootstrapService` (Phase 1)
- `ExecutionTrackingService` (Phase 2)
- `GraphAgentInstantiationService` (Phase 3)
- `GraphAssemblyService` (Phase 4)
- `GraphExecutionService` (Phase 5)
- `InteractionHandlerService` (checkpoint coordination)
- `GraphCheckpointService` (checkpoint persistence)
- `AppConfigService` (configuration)
- `LoggingService` (logging)

**Usage:**
```python
runner = container.graph_runner_service()
result = runner.run(bundle, initial_state={"input": "data"})
```

---

### 6.2 GraphExecutionService

**Responsibility**: Low-level LangGraph execution.

**File**: `services/graph/graph_execution_service.py`

**Key Methods:**
```python
def execute(
    compiled_graph: CompiledStateGraph,
    initial_state: Dict,
    config: Dict = None
) -> ExecutionResult:
    """Execute LangGraph."""
```

**Execution Logic:**
```python
1. Initialize LangGraph with initial state
2. Invoke graph execution
3. Handle interrupts (suspend/resume)
4. Collect execution results
5. Create ExecutionResult
```

**Dependencies**:
- `ExecutionPolicyService` (success evaluation)
- `LoggingService` (logging)

---

### 6.3 GraphAssemblyService

**Responsibility**: Transform Node objects to executable LangGraph.

**File**: `services/graph/graph_assembly_service.py`

**Key Methods:**
```python
def assemble_graph(
    graph_spec: GraphSpec,
    agent_instances: Dict[str, BaseAgent],
    tracker: ExecutionTracker
) -> CompiledStateGraph:
    """Assemble executable graph."""
```

**Assembly Process:**
```python
1. Create StateGraph from graph_spec
2. Add nodes with wrapper functions
3. Add edges (normal, conditional, function-based)
4. Set entry point
5. Set finish points (success/failure agents)
6. Compile to executable graph
7. Return compiled graph
```

**Edge Types:**
```python
- Normal: Direct edge to single target
- Conditional: Success/failure routing
- Function-based: Custom routing function
- Orchestrator: AI-driven semantic routing
- Multi-target: Parallel execution
```

**Dependencies**:
- `StateAdapterService` (state transformation)
- `FunctionResolutionService` (routing functions)
- `LoggingService` (logging)

---

### 6.4 GraphBundleService

**Responsibility**: Bundle creation, caching, and loading.

**File**: `services/graph/graph_bundle_service.py`

**Key Methods:**
```python
def get_or_create_bundle(
    csv_path: Path,
    graph_name: str,
    config_path: str = None
) -> Tuple[GraphBundle, bool]:
    """Get cached bundle or create new one."""

def load_bundle(bundle_path: Path) -> GraphBundle:
    """Load bundle from disk."""

def lookup_bundle(csv_hash: str, graph_name: str) -> Optional[GraphBundle]:
    """Lookup bundle in registry."""
```

**Caching Strategy:**
```python
Composite Key: (csv_hash, graph_name)
Cache Location: ~/.agentmap/cache/bundles/
Cache Format: {csv_hash}_{graph_name}.pkl
Registry: bundle_registry.json
```

**Dependencies**:
- `StaticBundleAnalyzer` (static analysis)
- `GraphRegistryService` (bundle registry)
- `CSVGraphParserService` (CSV parsing)
- `AppConfigService` (cache configuration)
- `LoggingService` (logging)

---

### 6.5 GraphRegistryService

**Responsibility**: Bundle metadata registry and lookup.

**File**: `services/graph/graph_registry_service.py`

**Key Methods:**
```python
def register_bundle(bundle: GraphBundle) -> None:
    """Register bundle in registry."""

def lookup_bundle(csv_hash: str, graph_name: str) -> Optional[str]:
    """Lookup bundle path in registry."""

def invalidate_bundle(csv_hash: str, graph_name: str) -> None:
    """Invalidate bundle cache."""
```

**Registry Format:**
```json
{
  "bundles": [
    {
      "csv_hash": "sha256...",
      "graph_name": "MyGraph",
      "bundle_path": "/path/to/bundle.pkl",
      "csv_path": "/path/to/workflow.csv",
      "created_at": "2025-10-28T12:00:00",
      "last_accessed": "2025-10-28T14:30:00"
    }
  ]
}
```

---

### 6.6 ExecutionTrackingService

**Responsibility**: Track node execution with performance metrics.

**File**: `services/execution_tracking_service.py`

**Protocol**: `ExecutionTrackingServiceProtocol`

**Key Methods:**
```python
def create_tracker(graph_name: str, policy: str) -> ExecutionTracker:
    """Create execution tracker."""

def record_node_start(node_name: str, inputs: Dict) -> None:
    """Record node start."""

def record_node_result(node_name: str, success: bool, result: Any, error: str) -> None:
    """Record node result."""

def update_graph_success() -> bool:
    """Update graph success status."""

def get_execution_summary() -> ExecutionSummary:
    """Get execution summary."""
```

**Tracked Metrics:**
```python
- Node execution time
- Node success/failure
- Input/output data
- Error messages
- Total execution time
- Success rate
```

---

### 6.7 StateAdapterService

**Responsibility**: State transformation and validation.

**File**: `services/state_adapter_service.py`

**Protocol**: `StateAdapterServiceProtocol`

**Key Methods:**
```python
def get_inputs(state: Dict, input_fields: List[str]) -> Dict:
    """Extract input values from state."""

def set_value(state: Dict, field: str, value: Any) -> Dict:
    """Set value in state."""

def normalize_state(state: Any) -> Dict:
    """Normalize state to dict format."""
```

**State Transformations:**
```python
- Extract node inputs from state
- Set node outputs in state
- Normalize pydantic models to dicts
- Validate state structure
```

---

### 6.8 ExecutionPolicyService

**Responsibility**: Evaluate workflow success based on policies.

**File**: `services/execution_policy_service.py`

**Key Methods:**
```python
def evaluate_success(tracker: ExecutionTracker, policy: str) -> bool:
    """Evaluate if workflow succeeded."""
```

**Success Policies:**
```python
- "all_nodes": All nodes must succeed
- "final_node": Only final node must succeed
- "critical_nodes": Specified critical nodes must succeed
- "any_node": At least one node must succeed
```

**Dependencies**:
- `ExecutionTracker` (execution metrics)
- `LoggingService` (logging)

---

### 6.9 GraphCheckpointService

**Responsibility**: LangGraph checkpoint persistence (suspend/resume).

**File**: `services/graph/graph_checkpoint_service.py`

**Key Methods:**
```python
def save_checkpoint(thread_id: str, state: Dict) -> None:
    """Save checkpoint state."""

def load_checkpoint(thread_id: str) -> Dict:
    """Load checkpoint state."""

def list_checkpoints(graph_name: str) -> List[str]:
    """List checkpoints for graph."""
```

**Checkpoint Storage:**
```python
Location: ~/.agentmap/checkpoints/{thread_id}/
Format: LangGraph checkpoint format (pickle)
Metadata: Thread metadata in interaction handler
```

**Dependencies**:
- LangGraph checkpointer
- `InteractionHandlerService` (thread coordination)
- `FilePathService` (path resolution)

---

### 6.10 InteractionHandlerService

**Responsibility**: Human-in-the-loop coordination and thread management.

**File**: `services/interaction_handler_service.py`

**Key Methods:**
```python
def save_thread_metadata(thread_id: str, metadata: Dict) -> bool:
    """Save thread metadata."""

def get_thread_metadata(thread_id: str) -> Dict:
    """Get thread metadata."""

def save_interaction_response(response_id: str, thread_id: str, action: str, data: Dict) -> bool:
    """Save human response."""

def mark_thread_resuming(thread_id: str, last_response_id: str = None) -> bool:
    """Mark thread as resuming."""
```

**Thread Metadata:**
```python
{
    "thread_id": "uuid",
    "graph_name": "MyWorkflow",
    "node_name": "HumanApproval",
    "status": "suspended",
    "pending_interaction_id": "uuid",
    "bundle_info": {...},
    "checkpoint_data": {...}
}
```

**Dependencies**:
- `SystemStorageManager` (pickle storage)
- `LoggingService` (logging)

---

## 7. Agent Services (GraphAgentContainer)

### 7.1 AgentFactoryService

**Responsibility**: Agent instantiation from declarations.

**File**: `services/agent/agent_factory_service.py`

**Key Methods:**
```python
def create_agent(agent_type: str, context: Dict = None) -> BaseAgent:
    """Create agent instance."""
```

**Agent Creation Process:**
```python
1. Parse agent declaration
2. Resolve agent class (built-in or custom)
3. Instantiate agent
4. Configure context if provided
5. Return agent instance
```

**Dependencies**:
- `AgentRegistryService` (agent registry)
- `CustomAgentLoader` (custom agents)
- `LoggingService` (logging)

---

### 7.2 AgentServiceInjectionService

**Responsibility**: Inject services into agents via protocols.

**File**: `services/agent/agent_service_injection_service.py`

**Key Methods:**
```python
def inject_services(agent: BaseAgent) -> BaseAgent:
    """Inject required services into agent."""
```

**Protocol-Based Injection:**
```python
if isinstance(agent, LLMCapableAgent):
    agent.configure_llm_service(self.llm_service)

if isinstance(agent, StorageCapableAgent):
    agent.configure_storage_service(self.storage_service)

if isinstance(agent, BlobStorageCapableAgent):
    agent.configure_blob_storage_service(self.blob_service)

if isinstance(agent, MessagingCapableAgent):
    agent.configure_messaging_service(self.messaging_service)

if isinstance(agent, PromptCapableAgent):
    agent.configure_prompt_service(self.prompt_service)
```

**Dependencies**:
- `LLMService`
- `StorageServiceManager`
- `BlobStorageService`
- `MessagingService`
- `PromptManagerService`
- `LoggingService`

---

### 7.3 GraphAgentInstantiationService

**Responsibility**: Create agent instances for graph execution.

**File**: `services/agent/graph_agent_instantiation_service.py`

**Key Methods:**
```python
def instantiate_agents_for_graph(bundle: GraphBundle) -> Dict[str, BaseAgent]:
    """Instantiate all agents for graph."""
```

**Process:**
```python
1. Iterate over nodes in GraphSpec
2. Create agent instance via AgentFactoryService
3. Inject services via AgentServiceInjectionService
4. Configure agent context
5. Build dict: {node_name: agent_instance}
6. Return agent instances dict
```

**Dependencies**:
- `AgentFactoryService` (agent creation)
- `AgentServiceInjectionService` (service injection)
- `LoggingService` (logging)

---

### 7.4 OrchestratorService

**Responsibility**: AI-driven semantic routing between nodes.

**File**: `services/orchestrator_service.py`

**Key Methods:**
```python
def route(state: Dict, available_nodes: List[str]) -> str:
    """Select next node via AI routing."""
```

**Routing Logic:**
```python
1. Extract current state context
2. Build prompt with available nodes and descriptions
3. Call LLM to select next node
4. Parse LLM response
5. Validate selected node exists
6. Return node name
```

**Dependencies**:
- `LLMService` (AI routing)
- `LoggingService` (logging)

---

## 8. Host Registry Services (HostRegistryContainer)

### 8.1 HostServiceRegistry

**Responsibility**: Register external services for agent injection.

**File**: `services/host_service_registry.py`

**Key Methods:**
```python
def register_service(service_name: str, service_instance: Any) -> None:
    """Register external service."""

def get_service(service_name: str) -> Any:
    """Get registered service."""

def has_service(service_name: str) -> bool:
    """Check if service registered."""

def clear_services() -> None:
    """Clear all registered services."""
```

**Usage:**
```python
# In host application
from agentmap.di import initialize_di

container = initialize_di()
container.register_host_service("custom_api", my_api_client)

# Now available to agents implementing CustomAPICapableAgent protocol
```

---

### 8.2 HostProtocolConfigurationService

**Responsibility**: Configure host services on agents via protocols.

**File**: `services/host_protocol_configuration_service.py`

**Key Methods:**
```python
def configure_host_protocols(agent: BaseAgent) -> int:
    """Configure host services on agent."""
```

**Protocol Matching:**
```python
for service_name, service_instance in host_services.items():
    if hasattr(agent, service_name):
        setattr(agent, service_name, service_instance)
        configured_count += 1
```

---

## 9. Service Protocols Reference

### 9.1 Service Protocols

**Core Service Protocols:**
```python
LLMServiceProtocol              # LLM provider abstraction
StorageServiceProtocol          # Unified storage interface
StateAdapterServiceProtocol     # State transformation
ExecutionTrackingServiceProtocol # Execution monitoring
PromptManagerServiceProtocol    # Prompt resolution
BlobStorageServiceProtocol      # Cloud blob storage
MessagingServiceProtocol        # Cloud messaging
GraphBundleServiceProtocol      # Bundle operations
EmbeddingServiceProtocol        # Vector embeddings
VectorStorageServiceProtocol    # Vector storage
```

**Location**: `src/agentmap/services/protocols.py`

---

### 9.2 Agent Capability Protocols

**Capability Protocols:**
```python
LLMCapableAgent                 # Requires LLM services
StorageCapableAgent             # Requires storage services
BlobStorageCapableAgent         # Requires blob storage
MessagingCapableAgent           # Requires messaging services
PromptCapableAgent              # Requires prompt management
OrchestrationCapableAgent       # Requires orchestrator service
EmbeddingCapableAgent           # Requires embedding service
VectorStorageCapableAgent       # Requires vector storage
GraphBundleCapableAgent         # Requires bundle service
CSVCapableAgent                 # Requires CSV storage
JSONCapableAgent                # Requires JSON storage
FileCapableAgent                # Requires file storage
VectorCapableAgent              # Requires vector service
MemoryCapableAgent              # Requires memory storage
```

**Usage Pattern:**
```python
@runtime_checkable
class LLMCapableAgent(Protocol):
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None: ...

# Agent implementation
class MyAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    def configure_llm_service(self, llm_service):
        self.llm_service = llm_service

    def configure_storage_service(self, storage_service):
        self.storage_service = storage_service
```

---

## 10. Service Dependencies

### 10.1 Dependency Graph

**Core Services (No Dependencies):**
```
LoggingService
ConfigService
```

**Level 1 (Core Dependencies):**
```
AppConfigService → ConfigService, LoggingService
FilePathService → AppConfigService, LoggingService
AuthService → AppConfigService, LoggingService
```

**Level 2 (File & Config Dependencies):**
```
PromptManagerService → AppConfigService, FilePathService, LoggingService
StorageConfigService → ConfigService, AppConfigService, LoggingService
```

**Level 3 (Storage Services):**
```
CSVStorageService → FilePathService, LoggingService
JSONStorageService → FilePathService, LoggingService
BlobStorageService → StorageConfigService, LoggingService
StorageServiceManager → All storage services, LoggingService
```

**Level 4 (LLM Services):**
```
LLMService → LLMRoutingService, AppConfigService, LoggingService
LLMRoutingService → PromptComplexityAnalyzer, RoutingCache, LLMRoutingConfigService
```

**Level 5 (Graph Services):**
```
GraphBundleService → StaticBundleAnalyzer, GraphRegistryService, CSVGraphParserService
GraphExecutionService → ExecutionPolicyService, LoggingService
GraphAssemblyService → StateAdapterService, FunctionResolutionService, LoggingService
```

**Level 6 (Agent Services):**
```
AgentServiceInjectionService → LLMService, StorageServiceManager, BlobStorageService, etc.
GraphAgentInstantiationService → AgentFactoryService, AgentServiceInjectionService
```

**Level 7 (Orchestration):**
```
GraphRunnerService → All graph services, agent services, tracking services
WorkflowOrchestrationService → GraphRunnerService
```

### 10.2 Service Load Order

**Calculated by DeclarationRegistryService:**
```python
1. LoggingService
2. ConfigService
3. AppConfigService
4. FilePathService
5. AuthService
6. PromptManagerService
7. StorageConfigService
8. BlobStorageService
9. JSONStorageService
10. CSVStorageService
11. StorageServiceManager
12. LLMRoutingService
13. LLMService
14. GraphBundleService
15. GraphExecutionService
16. GraphAssemblyService
17. AgentFactoryService
18. AgentServiceInjectionService
19. GraphAgentInstantiationService
20. GraphRunnerService
```

---

## 11. Service Usage Patterns

### 11.1 Service Access via DI

```python
from agentmap.di import initialize_di

# Initialize container
container = initialize_di(config_file="config.yaml")

# Access services
llm_service = container.llm_service()
storage_service = container.storage_service_manager()
runner = container.graph_runner_service()
```

### 11.2 Service Injection in Agents

```python
class MyAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    def __init__(self):
        super().__init__()
        self.llm_service = None
        self.storage_service = None

    def configure_llm_service(self, llm_service):
        self.llm_service = llm_service

    def configure_storage_service(self, storage_service):
        self.storage_service = storage_service

    def execute(self, state: Dict) -> Dict:
        # Use injected services
        response = self.llm_service.call_llm(...)
        self.storage_service.write(...)
        return {"result": response}
```

### 11.3 Service Testing

**Unit Tests with Mocks:**
```python
from tests.utils.mock_service_factory import MockServiceFactory

def test_my_service():
    mock_factory = MockServiceFactory()
    mock_llm = mock_factory.create_llm_service()

    service = MyService(mock_llm)
    result = service.process()

    assert result.success
```

**Integration Tests with Real DI:**
```python
from agentmap.di import initialize_di

def test_integration():
    container = initialize_di()
    service = container.my_service()

    result = service.execute_workflow(...)
    assert result.success
```

---

## 12. Service Development Guidelines

### 12.1 Creating New Services

**Checklist:**
1. Define service protocol in `services/protocols.py`
2. Implement service in `services/{domain}/{service_name}.py`
3. Register in appropriate DI container
4. Define agent capability protocol if needed
5. Update service injection logic
6. Write unit tests with MockServiceFactory
7. Write integration tests with real DI
8. Document in this catalog

**Template:**
```python
# services/my_service.py
class MyService:
    def __init__(
        self,
        dependency1: Dep1Protocol,
        logging_service: LoggingService
    ):
        self.dependency1 = dependency1
        self.logger = logging_service.get_class_logger(self)

    def my_method(self, param: str) -> str:
        self.logger.info(f"Processing: {param}")
        result = self.dependency1.process(param)
        return result

# services/protocols.py
@runtime_checkable
class MyServiceProtocol(Protocol):
    def my_method(self, param: str) -> str: ...

@runtime_checkable
class MyServiceCapableAgent(Protocol):
    def configure_my_service(self, service: MyServiceProtocol) -> None: ...

# di/containers.py
my_service = providers.Singleton(
    MyService,
    dependency1,
    logging_service
)
```

### 12.2 Service Naming Conventions

**Service Classes:**
- `{Domain}Service` for domain services
- `{Domain}ConfigService` for configuration
- `{Domain}Manager` for coordinating services
- `{Domain}Analyzer` for analysis services
- `{Domain}Parser` for parsing services

**Protocol Names:**
- `{Service}Protocol` for service interfaces
- `{Feature}CapableAgent` for agent capabilities

**File Names:**
- `services/{domain}/{service_name}.py`
- `services/protocols.py` (all protocols)

### 12.3 Service Documentation Requirements

**Required Documentation:**
- Service responsibility (single sentence)
- Key methods with signatures
- Dependencies list
- Protocol definitions
- Usage examples
- Test examples

---

## 13. Related Documentation

- **[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)**: Architecture overview and patterns
- **[DEPLOYMENT_ARCHITECTURE.md](./DEPLOYMENT_ARCHITECTURE.md)**: Deployment modes and patterns
- **[Testing Patterns](../../docs-docusaurus/docs/testing/testing-patterns.md)**: Service testing strategies

---

**End of Service Catalog Document**
