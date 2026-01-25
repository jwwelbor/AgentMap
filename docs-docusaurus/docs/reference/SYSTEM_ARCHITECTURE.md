# AgentMap System Architecture

**Document Version**: 1.0
**Last Updated**: 2025-10-28
**Maintainer**: Architecture Team

---

## Executive Summary

AgentMap is a sophisticated **CSV-driven workflow orchestration framework** built on LangGraph that transforms declarative CSV definitions into autonomous multi-agent systems. The architecture employs **clean architecture principles**, **protocol-based dependency injection**, and **high-performance bundle caching** to deliver 10x performance improvements over traditional approaches.

### Key Architectural Achievements

- **Clean Separation**: Models (data-only) → Services (business logic) → Agents (execution)
- **Protocol-Based DI**: 40+ runtime-checkable protocols enable loose coupling and testability
- **Bundle System**: Static analysis and caching provide 10x faster workflow execution
- **Zero Circular Dependencies**: Declaration-based analysis eliminates dependency cycles
- **Multi-Deployment**: Single codebase supports CLI, HTTP/FastAPI, and serverless (AWS/Azure/GCP)

### Architecture Statistics

| Metric | Value | Impact |
|--------|-------|--------|
| **Total Python Files** | 257 | Modular, maintainable codebase |
| **Service Classes** | 55+ | Fine-grained service responsibilities |
| **Protocol Interfaces** | 40+ | Clean service contracts |
| **Deployment Modes** | 4 | CLI, HTTP, Lambda, Azure, GCP |
| **Bundle Performance** | 10x | Static analysis vs dynamic loading |
| **Max File Size** | 350 lines | Enforced code quality limits |
| **Max Method Size** | 50 lines | Single responsibility enforcement |

---

## 1. Architectural Principles

### 1.1 Clean Architecture

AgentMap strictly follows clean architecture with explicit layer boundaries:

```
┌─────────────────────────────────────────────┐
│          DEPLOYMENT ADAPTERS                │
│  (CLI, HTTP, Serverless - Entry Points)    │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│          ORCHESTRATION LAYER                │
│  (WorkflowOrchestrationService,             │
│   GraphRunnerService, ServiceAdapter)       │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│           SERVICES LAYER                    │
│  (Business Logic, Graph Execution,          │
│   Agent Factory, Storage, LLM)              │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│            AGENTS LAYER                     │
│  (Agent Implementations, Built-ins,         │
│   Custom Agents, LLM Agents)                │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│           MODELS LAYER                      │
│  (Data Classes, ExecutionResult,            │
│   GraphBundle, Node, GraphSpec)             │
└─────────────────────────────────────────────┘
```

**Layer Rules:**
- **Models**: Pure data classes, no business logic, no dependencies
- **Agents**: Execute business logic, depend on services via protocols
- **Services**: Implement business logic, depend only on other services/protocols
- **Orchestration**: Coordinate services, handle workflow lifecycle
- **Deployment**: Adapt to runtime environments, minimal business logic

### 1.2 Dependency Inversion

All service dependencies use protocol interfaces:

```python
# Protocol definition (contracts)
@runtime_checkable
class LLMServiceProtocol(Protocol):
    def call_llm(self, provider: str, messages: List[Dict], **kwargs) -> str: ...

# Agent capability protocol
@runtime_checkable
class LLMCapableAgent(Protocol):
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None: ...

# Service injection via protocol detection
if isinstance(agent, LLMCapableAgent):
    agent.configure_llm_service(self.llm_service)
```

**Benefits:**
- Loose coupling between layers
- Easy mocking for unit tests
- Service implementations can be swapped
- Clear contracts between components

### 1.3 Simplicity First

AgentMap enforces **radical simplicity** to prevent over-engineering:

**Anti-Patterns Prohibited:**
- No wrapper classes around your own code
- No adapters for new integrations (implement interfaces directly)
- No abstract base classes with single implementations
- No "flexible" frameworks for single use cases
- No backwards compatibility for unreleased code

**Enforced Patterns:**
- Direct implementation of external interfaces
- Single responsibility per service
- Composition over inheritance (except protocol mixins)
- Explicit over implicit
- DRY, SOLID, YAGNI principles

### 1.4 Protocol-Based Service Contracts

Services communicate exclusively through protocols:

```python
# Service protocols in protocols.py
- LLMServiceProtocol: LLM provider abstraction
- StorageServiceProtocol: Unified storage interface
- StateAdapterServiceProtocol: State transformation
- ExecutionTrackingServiceProtocol: Execution monitoring
- PromptManagerServiceProtocol: Prompt resolution
- MessagingServiceProtocol: Cloud messaging
- BlobStorageServiceProtocol: Cloud blob storage

# Agent capability protocols
- LLMCapableAgent: Requires LLM services
- StorageCapableAgent: Requires storage services
- MessagingCapableAgent: Requires messaging services
- BlobStorageCapableAgent: Requires blob storage
- PromptCapableAgent: Requires prompt management
```

---

## 2. Core Layers

### 2.1 Models Layer

**Purpose**: Pure data structures with no business logic.

**Key Models:**
```python
# Execution models
ExecutionResult         # Final workflow result with success/error state
ExecutionTracker        # Tracks node execution with performance metrics
ExecutionSummary        # Aggregated execution statistics
ExecutionThread         # Checkpoint and resume thread metadata

# Graph structure models
GraphBundle             # Pre-compiled graph metadata (bundle system)
GraphSpec               # Graph definition parsed from CSV
Node                    # Individual node definition with routing
GraphState              # LangGraph state container

# Declaration models
AgentDeclaration        # Agent type and service requirements
ServiceDeclaration      # Service configuration and dependencies
FunctionDeclaration     # Custom function metadata

# Validation models
ValidationResult        # CSV/config validation result
CSVRowModel             # Validated CSV row structure

# Storage models
StorageResult           # Storage operation result
EmbeddingInput/Output   # Vector embedding data structures

# Configuration models
ConfigModel             # YAML configuration structure
StorageConfig           # Storage provider configuration
AuthConfig              # Authentication configuration
```

**Characteristics:**
- Dataclasses or Pydantic models only
- No methods except property accessors
- Immutable where possible
- Serializable (JSON, pickle)
- Type-annotated

### 2.2 Agents Layer

**Purpose**: Execute workflow nodes, implement agent logic.

**Agent Hierarchy:**
```
BaseAgent (abstract)
├── Built-in Agents (src/agentmap/agents/builtins/)
│   ├── LLM Agents
│   │   ├── AnthropicAgent (Claude integration)
│   │   ├── OpenAIAgent (GPT integration)
│   │   └── GoogleAgent (Gemini integration)
│   ├── Control Flow
│   │   ├── InputAgent (workflow entry point)
│   │   ├── SuccessAgent (workflow success terminus)
│   │   ├── FailureAgent (workflow failure terminus)
│   │   ├── BranchingAgent (conditional routing)
│   │   └── OrchestratorAgent (AI-driven routing)
│   ├── Storage Agents
│   │   ├── CSV: reader/writer
│   │   ├── JSON: reader/writer
│   │   ├── File: reader/writer
│   │   ├── Document: reader/writer
│   │   ├── Vector: reader/writer
│   │   └── Blob: blob_reader/blob_writer (cloud storage)
│   └── Human Interaction
│       ├── HumanAgent (pause for human input)
│       └── SuspendAgent (checkpoint without interaction)
└── Custom Agents (user-defined)
    └── Loaded via CustomAgentLoader
```

**Agent Capabilities via Protocols:**
```python
# Agents inherit capability protocols based on services they need
class MyCustomAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    def __init__(self):
        super().__init__()
        self.llm_service = None      # Injected via configure_llm_service()
        self.storage_service = None  # Injected via configure_storage_service()

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Business logic using injected services
        response = self.llm_service.call_llm("openai", messages)
        self.storage_service.write("results", response)
        return {"result": response}
```

**Agent Lifecycle:**
1. Declaration analysis determines service requirements
2. AgentFactoryService instantiates agent
3. AgentServiceInjectionService injects required services via protocols
4. GraphAssemblyService configures agent in executable graph
5. GraphExecutionService invokes agent.execute() during workflow

### 2.3 Services Layer

**Purpose**: Implement all business logic with single responsibilities.

**Service Categories:**

#### Core Services
```python
LoggingService              # Structured logging with class loggers
ConfigService               # YAML configuration loading only
AppConfigService            # Domain-specific configuration
AuthService                 # API authentication
FilePathService             # Path resolution and validation
```

#### Graph Orchestration Services
```python
GraphRunnerService          # High-level workflow orchestration (5-phase pipeline)
GraphExecutionService       # Low-level LangGraph execution
GraphAssemblyService        # Transform Node objects to executable graph
GraphBundleService          # Bundle creation, caching, loading
GraphRegistryService        # Bundle metadata registry
GraphCheckpointService      # LangGraph checkpoint persistence
StateAdapterService         # State transformation and validation
ExecutionTrackingService    # Node execution tracking
ExecutionPolicyService      # Success/failure policy evaluation
```

#### Agent Services
```python
AgentFactoryService                 # Agent instantiation
AgentServiceInjectionService        # Service injection via protocols
AgentRegistryService                # Agent type registration
GraphAgentInstantiationService      # Agent creation for graphs
CustomAgentLoader                   # Load user-defined agents
```

#### Declaration & Parsing Services
```python
CSVGraphParserService               # Parse CSV to GraphSpec
DeclarationParser                   # Parse agent/service declarations
DeclarationRegistryService          # Service dependency resolution
StaticBundleAnalyzer                # Static analysis for bundle creation
ProtocolRequirementsAnalyzer        # Determine service requirements
```

#### Storage Services
```python
StorageServiceManager               # Unified storage interface
SystemStorageManager                # System storage operations
BlobStorageService                  # Cloud blob storage (S3, Azure, GCS)
CSVStorageService                   # CSV storage operations
JSONStorageService                  # JSON storage operations
MemoryStorageService                # In-memory storage
VectorService                       # Vector embeddings and storage
```

#### LLM Services
```python
LLMService                          # Unified LLM interface
LLMRoutingService                   # Intelligent model routing
PromptComplexityAnalyzer            # Analyze prompt complexity
RoutingCache                        # Cache routing decisions
```

#### Validation Services
```python
ValidationService                   # High-level validation orchestration
CSVValidationService                # CSV structure validation
ConfigValidationService             # Config file validation
DependencyCheckerService            # Service dependency validation
```

#### Prompt & Template Services
```python
PromptManagerService                # Prompt resolution and formatting
IndentedTemplateComposer            # Code template generation
FunctionResolutionService           # Resolve custom functions
```

#### Interaction Services
```python
InteractionHandlerService           # Human-in-the-loop coordination
MessagingService                    # Cloud messaging (SQS, EventGrid, PubSub)
```

**Service Patterns:**

**Constructor Injection:**
```python
class MyService:
    def __init__(
        self,
        dependency1: Dep1Protocol,
        dependency2: Dep2Protocol,
        logging_service: LoggingService
    ):
        self.dependency1 = dependency1
        self.dependency2 = dependency2
        self.logger = logging_service.get_class_logger(self)
```

**Service Registration in DI:**
```python
# In di/containers.py
container.register(
    MyService,
    MyService,
    dependencies=['dependency1', 'dependency2', 'logging_service']
)
```

### 2.4 Orchestration Layer

**Purpose**: Coordinate services for workflow execution.

**Key Components:**

#### WorkflowOrchestrationService
**Responsibilities:**
- Workflow parameter validation
- CSV path resolution (file, workflow name, repository)
- Bundle creation/retrieval
- State normalization
- Delegation to GraphRunnerService

**Entry Points:**
```python
execute_workflow(
    workflow: str,           # CSV path or workflow name
    graph_name: str,         # Graph to execute
    initial_state: Dict,     # Starting state
    config_file: str         # Config path
) -> ExecutionResult

resume_workflow(
    thread_id: str,          # Thread to resume
    response_action: str,    # User action
    response_data: Any,      # Response payload
    config_file: str         # Config path
) -> ExecutionResult
```

#### GraphRunnerService
**5-Phase Execution Pipeline:**
```
Phase 1: Bootstrap (conditional)
├── Direct import mode (skip registration)
└── Legacy mode (register agent classes)

Phase 2: Execution Tracking Setup
├── Create execution tracker
├── Configure tracking policies
└── Link subgraph trackers

Phase 3: Agent Instantiation
├── Load agent instances from bundle
├── Inject required services (LLM, Storage, etc.)
├── Configure agent contexts
└── Prepare agent registry

Phase 4: Graph Assembly
├── Transform Node objects to executable graph
├── Resolve edge targets and routing
├── Configure conditional branching
└── Prepare orchestrator node registry

Phase 5: Graph Execution
├── Initialize execution state
├── Execute nodes via LangGraph
├── Track execution path and timing
├── Handle errors and recovery
└── Generate execution summary
```

#### ServiceAdapter
**Responsibilities:**
- Result extraction and formatting
- Error handling standardization
- HTTP response formatting
- Trigger parameter extraction (serverless)

**Helper Classes:**
```python
TriggerParameterExtractor    # Extract params from serverless events
ResponseFormatter            # Format responses for CLI/API/serverless
```

### 2.5 Deployment Adapters

**Purpose**: Adapt AgentMap to different runtime environments.

**Adapters:**
```
CLI (deployment/cli/)
├── main_cli.py: Typer application
├── run_command.py: Execute workflows
├── resume_command.py: Resume checkpoints
├── scaffold_command.py: Generate code
├── validate_command.py: Validate workflows
├── diagnose_command.py: System diagnostics
└── serve_command.py: Start HTTP server

HTTP (deployment/http/)
├── server.py: FastAPI application
├── routes/execute.py: Workflow execution endpoints
├── routes/workflows.py: Workflow management
├── routes/admin.py: Admin and diagnostics
├── middleware/auth.py: Authentication
└── dependencies.py: FastAPI DI integration

Serverless (deployment/serverless/)
├── base_handler.py: Base serverless handler
├── aws_lambda.py: AWS Lambda adapter
├── azure_functions.py: Azure Functions adapter
├── gcp_functions.py: GCP Cloud Functions adapter
└── trigger_strategies/: Event parsing strategies
    ├── http_strategy.py
    ├── aws_sqs_strategy.py
    ├── aws_s3_strategy.py
    ├── azure_event_grid_strategy.py
    └── gcp_pubsub_strategy.py
```

---

## 3. Data Flow & Execution

### 3.1 Request Flow

**CLI Execution:**
```
User Command
    ↓
main_cli.py (Typer)
    ↓
run_command.py
    ↓
WorkflowOrchestrationService.execute_workflow()
    ↓ (DI initialization)
ApplicationContainer
    ↓ (CSV resolution, bundle creation)
GraphBundleService
    ↓ (delegation)
GraphRunnerService.run()
    ↓ (5-phase pipeline)
GraphExecutionService.execute()
    ↓ (LangGraph execution)
Compiled LangGraph
    ↓ (node execution)
Agent.execute() methods
    ↓
ExecutionResult
    ↓
CLI output formatting
```

**HTTP Execution:**
```
HTTP POST /execute/{workflow}/{graph}
    ↓
server.py (FastAPI)
    ↓
routes/execute.py
    ↓ (request validation)
Pydantic models
    ↓
WorkflowOrchestrationService.execute_workflow()
    ↓ (same as CLI flow)
ExecutionResult
    ↓
ServiceAdapter.format_http_response()
    ↓
JSON response
```

**Serverless Execution:**
```
Cloud Event (SQS, EventGrid, PubSub, HTTP)
    ↓
Lambda/Azure/GCP handler
    ↓
BaseHandler.handle_request_sync()
    ↓
TriggerParameterExtractor.extract_workflow_parameters()
    ↓
WorkflowOrchestrationService.execute_workflow()
    ↓ (same execution flow)
ExecutionResult
    ↓
ResponseFormatter.for_serverless()
    ↓
Cloud response format
```

### 3.2 Workflow Execution Flow

**Complete Execution Sequence:**

```
1. Entry Point (Deployment Adapter)
   ├── Parse command/request/event
   ├── Extract parameters
   └── Call WorkflowOrchestrationService

2. Workflow Orchestration
   ├── Initialize DI container
   ├── Resolve CSV path (file/workflow name/repository)
   ├── Parse and validate initial state
   ├── Get or create GraphBundle (with caching)
   └── Delegate to GraphRunnerService

3. Graph Runner (5-Phase Pipeline)
   │
   ├── Phase 1: Bootstrap
   │   └── Direct import mode (skip agent registration)
   │
   ├── Phase 2: Execution Tracking Setup
   │   ├── Create ExecutionTracker
   │   ├── Configure tracking policies (all_nodes, final_node, critical_nodes)
   │   └── Link parent-child trackers for subgraphs
   │
   ├── Phase 3: Agent Instantiation
   │   ├── AgentFactoryService.create_agent() for each node
   │   ├── AgentServiceInjectionService.inject_services()
   │   │   ├── LLM service injection (if LLMCapableAgent)
   │   │   ├── Storage service injection (if StorageCapableAgent)
   │   │   ├── Blob storage injection (if BlobStorageCapableAgent)
   │   │   ├── Messaging injection (if MessagingCapableAgent)
   │   │   └── Prompt service injection (if PromptCapableAgent)
   │   └── Build agent_instances dict: {node_name: agent}
   │
   ├── Phase 4: Graph Assembly
   │   ├── GraphAssemblyService.assemble_graph()
   │   ├── Create StateGraph from bundle.graph_spec
   │   ├── Add nodes with wrapper functions
   │   ├── Add edges (normal, conditional, function-based)
   │   ├── Set entry point and finish points
   │   └── Compile to executable graph
   │
   └── Phase 5: Graph Execution
       ├── GraphExecutionService.execute()
       ├── GraphCheckpointService for suspend/resume
       ├── LangGraph invokes nodes
       ├── ExecutionTrackingService records metrics
       └── Return ExecutionResult

4. Node Execution (for each node)
   ├── Wrapper function invoked by LangGraph
   ├── ExecutionTrackingService.record_node_start()
   ├── StateAdapterService.get_inputs() extracts node inputs
   ├── Agent.execute(state) - business logic
   ├── StateAdapterService.set_value() updates state
   ├── ExecutionTrackingService.record_node_result()
   └── Return updated state

5. Edge Routing
   ├── Conditional edges: success/failure routing
   ├── Function-based routing: custom logic
   ├── Orchestrator routing: AI-driven semantic routing
   └── Multi-target routing: parallel execution

6. Result Processing
   ├── ExecutionPolicyService evaluates success
   ├── ExecutionTracker generates summary
   ├── Create ExecutionResult with final_state
   └── Return to deployment adapter

7. Response Formatting
   ├── CLI: Pretty-print with rich formatting
   ├── HTTP: JSON with ServiceAdapter.format_http_response()
   ├── Serverless: Cloud-specific response format
   └── User receives result
```

### 3.3 Bundle System Data Flow

**Bundle Creation Flow:**

```
CSV File
    ↓
GraphBundleService.get_or_create_bundle()
    ↓
Check cache: ~/.agentmap/cache/bundles/{csv_hash}_{graph_name}.pkl
    ↓
Cache Hit? → Load Bundle → Return (1ms)
    ↓
Cache Miss
    ↓
StaticBundleAnalyzer.analyze_csv()
    ↓ (parse declarations only, no imports)
CSVGraphParserService.parse_csv()
    ↓
DeclarationParser.parse_declarations()
    ↓ (extract service requirements)
ProtocolRequirementsAnalyzer.analyze_agents()
    ↓
Create GraphBundle
    ├── graph_spec: GraphSpec
    ├── agent_metadata: Dict[node_name, agent_info]
    ├── service_requirements: Set[protocol_names]
    ├── bundle_path: Path to cache file
    ├── csv_hash: SHA-256 of CSV content
    └── csv_path: Original CSV path
    ↓
GraphRegistryService.register_bundle()
    ↓
Cache bundle to disk (pickle)
    ↓
Return bundle (10ms for static, 100ms for dynamic)
```

**Bundle Caching Strategy:**

```
Composite Key: (csv_hash, graph_name)
├── Primary: CSV content hash (SHA-256)
└── Secondary: Graph name

Cache Location: ~/.agentmap/cache/bundles/
├── {csv_hash}_{graph_name}.pkl (bundle)
└── bundle_registry.json (metadata index)

Cache Invalidation:
├── Automatic: CSV content changes → new hash
├── Manual: agentmap refresh --csv path/to/file.csv
└── Manual: agentmap refresh --all
```

**Performance Comparison:**

| Method | Time | Memory | Description |
|--------|------|--------|-------------|
| Dynamic Bundle | ~100ms | ~50MB | Full imports, circular deps possible |
| Static Bundle | ~10ms | ~5MB | Declaration analysis, no imports |
| Cached Bundle | ~1ms | ~1MB | Load from disk |

### 3.4 Service Injection Flow

**Protocol-Based Injection:**

```
Agent Instantiation
    ↓
AgentServiceInjectionService.inject_services(agent)
    ↓
Check agent isinstance(LLMCapableAgent)?
    Yes → agent.configure_llm_service(llm_service)
    No  → Skip
    ↓
Check agent isinstance(StorageCapableAgent)?
    Yes → agent.configure_storage_service(storage_service)
    No  → Skip
    ↓
Check agent isinstance(BlobStorageCapableAgent)?
    Yes → agent.configure_blob_storage_service(blob_service)
    No  → Skip
    ↓
Check agent isinstance(MessagingCapableAgent)?
    Yes → agent.configure_messaging_service(messaging_service)
    No  → Skip
    ↓
Check agent isinstance(PromptCapableAgent)?
    Yes → agent.configure_prompt_service(prompt_service)
    No  → Skip
    ↓
Check agent isinstance(OrchestrationCapableAgent)?
    Yes → agent.configure_orchestrator_service(orchestrator_service)
    No  → Skip
    ↓
Return configured agent
```

**Host Service Registry (Custom Services):**

```
Host Application
    ↓
container.register_host_service("custom_service", service_instance)
    ↓
HostServiceRegistry.register_service()
    ↓
HostProtocolConfigurationService.configure_host_protocols(agent)
    ↓
Check agent has attribute matching service protocol?
    Yes → Set attribute to service instance
    No  → Skip
    ↓
Custom service available to agent during execution
```

---

## 4. Dependency Injection Architecture

### 4.1 Container Structure

**ApplicationContainer (Composable DI):**

```python
ApplicationContainer
├── _core: CoreContainer
│   ├── config_service
│   ├── app_config_service
│   ├── logging_service
│   ├── file_path_service
│   └── prompt_manager_service
│
├── _storage: StorageContainer
│   ├── storage_config_service
│   ├── blob_storage_service
│   ├── json_storage_service
│   ├── storage_service_manager
│   └── system_storage_manager
│
├── _bootstrap: BootstrapContainer
│   ├── features_registry_service
│   ├── agent_registry_service
│   ├── csv_graph_parser_service
│   ├── declaration_parser
│   ├── declaration_registry_service
│   ├── static_bundle_analyzer
│   └── validation_services
│
├── _llm: LLMContainer
│   ├── llm_routing_service
│   ├── llm_service
│   └── prompt_complexity_analyzer
│
├── _host_registry: HostRegistryContainer
│   ├── host_service_registry
│   └── host_protocol_configuration_service
│
├── _graph_core: GraphCoreContainer
│   ├── graph_bundle_service
│   ├── graph_registry_service
│   ├── graph_factory_service
│   ├── graph_assembly_service
│   ├── graph_execution_service
│   ├── graph_checkpoint_service
│   ├── execution_tracking_service
│   └── state_adapter_service
│
├── _graph_agent: GraphAgentContainer
│   ├── agent_factory_service
│   ├── agent_service_injection_service
│   ├── graph_agent_instantiation_service
│   └── orchestrator_service
│
└── graph_runner_service (top-level orchestrator)
```

### 4.2 Service Lifecycle

**Initialization Sequence:**

```
1. Configuration Discovery
   ├── Check for explicit config_file parameter
   ├── Look for agentmap_config.yaml in CWD
   └── Use system defaults

2. Container Initialization
   ├── ApplicationContainer.init()
   ├── Load config into container.config
   └── Set up lazy service providers

3. Service Instantiation (Lazy)
   ├── Service requested: container.some_service()
   ├── Check if already instantiated (Singleton)
   ├── If not: resolve dependencies recursively
   ├── Instantiate service with dependencies
   ├── Cache service instance
   └── Return service

4. Service Dependency Resolution
   ├── DeclarationRegistryService.get_load_order()
   ├── Build dependency graph
   ├── Topological sort for load order
   ├── Detect circular dependencies
   └── Return ordered service list
```

**Service Scopes:**

```python
# Singleton (default) - one instance per container
providers.Singleton(MyService, dependency1, dependency2)

# Factory - new instance per call
providers.Factory(MyService, dependency1, dependency2)

# Callable - dynamic resolution
providers.Callable(lambda: get_service_dynamically())
```

### 4.3 Configuration Management

**Configuration Hierarchy:**

```
System Defaults (lowest priority)
    ↓ (override)
agentmap_config.yaml in current directory
    ↓ (override)
Explicit config_file parameter (highest priority)
    ↓
Merged Configuration
```

**Configuration Structure:**

```yaml
# agentmap_config.yaml
execution:
  use_direct_import_agents: true
  default_success_policy: "all_nodes"
  enable_checkpoints: true

storage:
  cache_folder: "~/.agentmap/cache"
  csv_repository_path: "~/.agentmap/csv_repository"

logging:
  level: "INFO"
  format: "structured"
  log_to_file: false

performance:
  bundle_cache_enabled: true
  static_analysis_enabled: true

llm:
  default_provider: "openai"
  routing_strategy: "complexity"

custom_agents:
  modules:
    - path: "my_agents.agents"
    - path: "another_package.agents"
```

**Domain-Specific Config Services:**

```python
ConfigService              # YAML loading only (no business logic)
AppConfigService           # Domain-specific config access
StorageConfigService       # Storage provider configuration
LLMModelsConfigService     # LLM model configuration
LLMRoutingConfigService    # LLM routing configuration
```

---

## 5. Performance Architecture

### 5.1 Bundle System Performance

**Static Analysis Benefits:**

```
Traditional Approach (Dynamic):
├── Import all agent modules → 50ms
├── Import all service modules → 30ms
├── Execute module-level code → 20ms
├── Resolve circular dependencies → risk
└── Total: ~100ms + circular dep risk

AgentMap Approach (Static):
├── Parse CSV declarations → 5ms
├── Analyze protocol requirements → 3ms
├── Build metadata structure → 2ms
├── No imports, no circular deps → safe
└── Total: ~10ms (10x faster)
```

**Caching Strategy:**

```
First Execution:
├── Parse CSV → 10ms
├── Create bundle → 10ms
├── Cache to disk → 5ms
└── Total: ~25ms

Subsequent Executions:
├── Load cached bundle → 1ms
└── Total: ~1ms (25x faster)
```

### 5.2 Memory Optimization

**Bundle Memory Footprint:**

```
Dynamic Bundle:
├── All agent class imports: ~20MB
├── All service imports: ~15MB
├── Module execution overhead: ~10MB
├── Dependency graph: ~5MB
└── Total: ~50MB

Static Bundle (Metadata Only):
├── GraphSpec structure: ~1MB
├── Agent metadata dicts: ~2MB
├── Service requirements set: ~1MB
├── Routing metadata: ~1MB
└── Total: ~5MB (90% reduction)
```

**Runtime Memory Management:**

```
Agent Instances:
├── Created only during Phase 3 (execution)
├── Service references (not copies)
├── Reused across multiple graph executions
└── Garbage collected after completion

State Management:
├── Immutable state transitions
├── Copy-on-write semantics
├── Large states processed in chunks
└── Streaming for blob data
```

### 5.3 Execution Performance

**Edge Caching:**

```python
# Route decisions cached per execution
cached_routes = {}

def route_function(state):
    route_key = generate_route_key(state)
    if route_key not in cached_routes:
        cached_routes[route_key] = compute_route(state)
    return cached_routes[route_key]
```

**Parallel Opportunities:**

```
Multi-Target Routing:
├── Node A completes
├── Routes to [B, C, D] in parallel
├── LangGraph manages concurrency
└── Collect results before next node
```

**Service Reuse:**

```
Single Service Instances:
├── LLMService: one instance, all agents share
├── StorageService: one instance, all agents share
├── No per-agent service overhead
└── Connection pooling for external services
```

### 5.4 Performance Benchmarks

**Workflow Execution Times:**

| Workflow Type | Nodes | Cold Start | Warm Start | Cached |
|---------------|-------|------------|------------|--------|
| Simple (3 nodes) | 3 | 150ms | 50ms | 25ms |
| Medium (10 nodes) | 10 | 300ms | 100ms | 75ms |
| Complex (25 nodes) | 25 | 600ms | 200ms | 150ms |
| Enterprise (50 nodes) | 50 | 1200ms | 400ms | 300ms |

**Bundle Creation Times:**

| Bundle Type | CSV Size | Creation Time | Memory |
|-------------|----------|---------------|--------|
| Static | 10 KB | 8ms | 3MB |
| Static | 100 KB | 15ms | 8MB |
| Static | 1 MB | 50ms | 25MB |
| Dynamic | 10 KB | 80ms | 40MB |
| Dynamic | 100 KB | 200ms | 80MB |

---

## 6. Integration Points

### 6.1 LLM Integration

**Unified LLM Interface:**

```python
class LLMService:
    def call_llm(
        self,
        provider: str,           # "openai", "anthropic", "google"
        messages: List[Dict],    # Chat messages
        model: Optional[str],    # Model override
        temperature: float,      # Sampling temperature
        routing_context: Dict,   # For intelligent routing
        **kwargs                 # Provider-specific params
    ) -> str:
        """Unified LLM call with intelligent routing."""
```

**Intelligent Routing:**

```
User Request
    ↓
LLMService.call_llm()
    ↓
LLMRoutingService.route_request()
    ↓
PromptComplexityAnalyzer.analyze()
    ├── Token count
    ├── Task complexity
    ├── Required capabilities
    └── Performance requirements
    ↓
Select optimal model
    ├── Simple task → GPT-3.5-turbo
    ├── Complex reasoning → Claude Opus
    ├── Code generation → GPT-4
    └── Cost-optimized → Cached model
    ↓
RoutingCache (cache decision)
    ↓
Execute LLM call
    ↓
Return response
```

**Supported Providers:**

```python
Providers:
├── OpenAI: GPT-4, GPT-3.5-turbo, GPT-4-turbo
├── Anthropic: Claude 3 (Opus, Sonnet, Haiku)
└── Google: Gemini Pro, Gemini Ultra

Features:
├── Streaming responses
├── Function calling
├── Vision inputs (GPT-4V, Claude 3)
├── Context caching (Anthropic)
└── Intelligent routing based on complexity
```

### 6.2 Storage Integration

**Unified Storage Interface:**

```python
class StorageServiceManager:
    def read(self, collection: str, **kwargs) -> Any:
        """Read from storage collection."""

    def write(self, collection: str, data: Any, **kwargs) -> Any:
        """Write to storage collection."""
```

**Storage Backends:**

```
Local Storage:
├── CSV: Structured data storage
├── JSON: Semi-structured data
├── File: Raw file operations
├── Memory: In-memory caching
└── Document: Text document storage

Cloud Storage (BlobStorageService):
├── AWS S3: s3://bucket/path
├── Azure Blob: azure://container/path
├── GCP Storage: gs://bucket/path
└── Local files: file:///path

Vector Storage:
├── ChromaDB: Local vector database
├── Embeddings: OpenAI, Anthropic, Google
└── Semantic search operations
```

**Storage Operations:**

```python
# CSV storage
csv_service.read("data.csv", filters={"column": "value"})
csv_service.write("data.csv", rows=[...])

# JSON storage
json_service.read("config.json")
json_service.write("config.json", {"key": "value"})

# Blob storage (cloud)
blob_service.read_blob("s3://bucket/file.txt")
blob_service.write_blob("azure://container/file.txt", data)
blob_service.list_blobs("gs://bucket/prefix/")

# Vector storage
vector_service.embed_and_store(collection="docs", texts=[...])
results = vector_service.query(query_text="search", k=5)
```

### 6.3 Messaging Integration

**Cloud Messaging Support:**

```python
class MessagingService:
    async def publish_message(
        self,
        topic: str,              # Queue/topic name
        message_type: str,       # Message type
        payload: Dict,           # Message payload
        provider: CloudProvider, # AWS/Azure/GCP
        priority: MessagePriority,
        thread_id: str           # Correlation ID
    ) -> StorageResult:
        """Publish message to cloud queue/topic."""
```

**Supported Providers:**

```
AWS:
├── SQS: Queue messages
├── SNS: Pub/sub topics
└── EventBridge: Event bus

Azure:
├── Service Bus: Queues and topics
├── Event Grid: Event routing
└── Event Hubs: High-throughput streaming

GCP:
├── Pub/Sub: Global messaging
└── Cloud Tasks: Task queue
```

**Message Templates:**

```python
# Template-based messaging
messaging_service.apply_template(
    template_name="workflow_trigger",
    variables={
        "workflow_name": "data_pipeline",
        "graph_name": "ETL",
        "inputs": {...}
    }
)
```

### 6.4 Suspend/Resume Architecture

**Checkpoint System:**

```
Workflow Execution
    ↓
Node encounters interrupt() (HumanAgent or SuspendAgent)
    ↓
GraphCheckpointService.save_checkpoint()
    ├── Save current state to LangGraph checkpointer
    ├── Store thread metadata (InteractionHandlerService)
    ├── Store bundle info for rehydration
    └── Return checkpoint_id (thread_id)
    ↓
Execution paused, returns to caller
    ↓
User provides response (HumanAgent) or trigger (SuspendAgent)
    ↓
WorkflowOrchestrationService.resume_workflow()
    ├── Load thread metadata
    ├── Rehydrate GraphBundle
    ├── Create HumanInteractionResponse (if HumanAgent)
    ├── Inject response into checkpoint state
    └── Call GraphRunnerService.resume_from_checkpoint()
    ↓
GraphCheckpointService.load_checkpoint()
    ↓
LangGraph resumes from checkpoint
    ↓
Workflow continues from suspend point
```

**Thread Metadata Storage:**

```python
# Stored in ~/.agentmap/threads/{thread_id}.pkl
{
    "thread_id": "uuid",
    "graph_name": "MyWorkflow",
    "node_name": "HumanApproval",
    "status": "suspended",  # or "resuming", "completed"
    "pending_interaction_id": "uuid",  # HumanAgent only
    "bundle_info": {
        "csv_hash": "sha256",
        "bundle_path": "/path/to/bundle.pkl",
        "csv_path": "/path/to/workflow.csv"
    },
    "checkpoint_data": {...}  # Current state snapshot
}
```

---

## 7. Extension Points

### 7.1 Custom Agents

**Creating Custom Agents:**

```python
from agentmap.agents import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent

class MyCustomAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    """Custom agent with LLM and storage capabilities."""

    def __init__(self):
        super().__init__()
        self.llm_service = None      # Injected via protocol
        self.storage_service = None  # Injected via protocol

    def configure_llm_service(self, llm_service):
        self.llm_service = llm_service

    def configure_storage_service(self, storage_service):
        self.storage_service = storage_service

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Agent business logic."""
        # Use injected services
        response = self.llm_service.call_llm(
            provider="openai",
            messages=[{"role": "user", "content": "Hello"}]
        )

        # Store result
        self.storage_service.write("results", response)

        return {"result": response}
```

**Registration:**

```yaml
# agentmap_config.yaml
custom_agents:
  modules:
    - path: "my_agents.agents"  # Python module path
```

### 7.2 Custom Services

**Creating Custom Services:**

```python
from typing import Protocol, runtime_checkable

# 1. Define service protocol
@runtime_checkable
class MyServiceProtocol(Protocol):
    def my_method(self, param: str) -> str: ...

# 2. Define capability protocol for agents
@runtime_checkable
class MyServiceCapableAgent(Protocol):
    def configure_my_service(self, service: MyServiceProtocol) -> None: ...

# 3. Implement service
class MyService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_class_logger(self)

    def my_method(self, param: str) -> str:
        self.logger.info(f"Processing: {param}")
        return f"Result: {param}"

# 4. Register in DI container (in di/containers.py)
container.register(
    MyService,
    MyService,
    dependencies=['logging_service']
)

# 5. Use in agents
class MyAgent(BaseAgent, MyServiceCapableAgent):
    def configure_my_service(self, service: MyServiceProtocol):
        self.my_service = service

    def execute(self, state: Dict) -> Dict:
        result = self.my_service.my_method("data")
        return {"result": result}
```

### 7.3 Host Service Registration

**Injecting External Services:**

```python
from agentmap.di import initialize_di

# Initialize container
container = initialize_di()

# Register custom service
container.register_host_service("custom_api", my_api_client)

# Now available to agents via protocol
@runtime_checkable
class CustomAPICapableAgent(Protocol):
    custom_api: Any

class MyAgent(BaseAgent, CustomAPICapableAgent):
    def execute(self, state):
        result = self.custom_api.call_endpoint(...)
        return {"result": result}
```

### 7.4 Custom Routing Functions

**Function-Based Routing:**

```python
# In functions/routing.py
def my_routing_function(state: Dict[str, Any]) -> str:
    """Custom routing logic."""
    if state.get("score", 0) > 0.8:
        return "high_confidence"
    elif state.get("score", 0) > 0.5:
        return "medium_confidence"
    else:
        return "low_confidence"

# In CSV:
# Node,Agent,Routing,RoutingFunction,Outputs
# classifier,ClassifyAgent,function,my_routing_function,"high_confidence,medium_confidence,low_confidence"
```

### 7.5 Custom Success Policies

**Creating Custom Policies:**

```python
from agentmap.services.execution_policy_service import ExecutionPolicyService

class CustomPolicy:
    """Custom success evaluation policy."""

    @staticmethod
    def evaluate(tracker: ExecutionTracker) -> bool:
        """Evaluate if workflow succeeded."""
        # Custom logic
        critical_nodes = ["validation", "processing", "storage"]
        return all(
            tracker.nodes.get(node, {}).get("success", False)
            for node in critical_nodes
        )

# Register policy
ExecutionPolicyService.register_policy("custom", CustomPolicy.evaluate)

# Use in config
execution:
  default_success_policy: "custom"
```

---

## 8. Well-Architected Framework Alignment

### 8.1 Security

**Implementation:**
- **AuthService**: API key and bearer token authentication
- **Protocol Isolation**: Services accessed only via protocols
- **No Direct Container Access**: Agents cannot access DI container directly
- **Secure Storage**: Credentials managed via environment variables
- **Audit Logging**: All execution tracked with LoggingService

**Gaps:**
- No built-in encryption for stored bundles
- No role-based access control (RBAC)
- Limited input sanitization for custom functions
- No secrets management integration

### 8.2 Reliability

**Implementation:**
- **Graceful Degradation**: Optional services fail gracefully
- **Error Recovery**: Try/catch with detailed error messages
- **Checkpoint/Resume**: Built-in suspend/resume via LangGraph
- **Execution Tracking**: Detailed node execution monitoring
- **Validation**: Pre-execution CSV and config validation

**Gaps:**
- No automatic retry mechanisms (user must implement)
- No circuit breakers for external services
- Limited health checks for integrated services
- No distributed tracing for serverless deployments

### 8.3 Performance Efficiency

**Implementation:**
- **Bundle Caching**: 10x performance improvement via static analysis
- **Service Reuse**: Singleton services across executions
- **Lazy Loading**: Services instantiated only when needed
- **Memory Optimization**: Metadata-only bundles, immutable states
- **Edge Caching**: Route decisions cached per execution

**Gaps:**
- No connection pooling for LLM APIs
- No query caching for vector searches
- Limited parallel execution (multi-target routing only)
- No CDN integration for blob storage

### 8.4 Cost Optimization

**Implementation:**
- **Intelligent Routing**: Route to cheapest suitable LLM model
- **Caching**: Reduce redundant LLM API calls
- **Bundle System**: Minimize cold start times in serverless
- **Resource Reuse**: Single service instances reduce memory
- **Storage Tiering**: Support for multiple storage backends

**Gaps:**
- No cost tracking or budget limits
- No automatic model downgrading on budget exhaustion
- Limited cost estimation for workflows
- No storage lifecycle policies

### 8.5 Operational Excellence

**Implementation:**
- **Structured Logging**: Comprehensive logging with LoggingService
- **Execution Tracking**: Detailed metrics per node
- **Diagnostics**: Built-in diagnose command for troubleshooting
- **Validation**: Pre-execution validation prevents runtime errors
- **Documentation**: Comprehensive docs with architecture details

**Gaps:**
- No built-in monitoring/alerting
- No performance dashboards
- Limited telemetry for production deployments
- No automated incident response

---

## 9. Architectural Constraints

### 9.1 Code Quality Constraints

**Enforced Limits:**
```python
MAX_FILE_LINES = 350      # Files must not exceed 350 lines
MAX_METHOD_LINES = 50     # Methods must not exceed 50 lines
MAX_COMPLEXITY = 10       # Cyclomatic complexity limit
```

**Prohibited Patterns:**
- Business logic in models
- Direct DI container access from services
- Wrapper classes around your own code
- Adapters for new integrations (implement directly)
- Abstract base classes with single implementations
- Backwards compatibility for unreleased features

### 9.2 Dependency Constraints

**Rules:**
- Services depend only on protocols, not concrete classes
- Models have no dependencies (except dataclass utilities)
- Agents depend on services via protocols only
- No circular dependencies (enforced via static analysis)
- Container parts compose cleanly without cross-contamination

### 9.3 Testing Constraints

**Test Patterns:**
```python
# Unit tests: MockServiceFactory for dependencies
def test_my_service():
    mock_deps = MockServiceFactory()
    service = MyService(mock_deps.create_dependency())
    assert service.my_method() == expected

# Integration tests: Real DI container
def test_integration():
    container = initialize_di()
    service = container.my_service()
    result = service.execute_workflow(...)
    assert result.success
```

**Prohibited:**
- Business logic in model tests
- DI mocks in container tests
- Test-specific production code

### 9.4 Performance Constraints

**Requirements:**
- Bundle creation must complete <100ms (static analysis)
- Node execution overhead <5ms per node
- Memory footprint <50MB for typical workflows
- Cold start <500ms for serverless deployments
- Cached execution <25ms for simple workflows

---

## 10. Future Architecture Evolution

### 10.1 Planned Improvements

**Near-Term (0-6 months):**
- **Distributed Caching**: Redis backend for bundle cache
- **Connection Pooling**: HTTP connection reuse for LLM APIs
- **Parallel Execution**: True parallel node execution via async
- **Health Checks**: Built-in service health monitoring
- **Cost Tracking**: Automatic cost calculation per workflow

**Mid-Term (6-12 months):**
- **Microservices**: Service isolation for distributed deployment
- **Telemetry**: OpenTelemetry integration for observability
- **Circuit Breakers**: Automatic failover for external services
- **RBAC**: Role-based access control for workflows
- **Query Optimization**: Vector search caching and optimization

**Long-Term (12+ months):**
- **Multi-Region**: Distributed workflow execution across regions
- **Auto-Scaling**: Dynamic resource allocation based on load
- **ML Ops Integration**: Model versioning and A/B testing
- **Real-Time Streaming**: Streaming workflow execution
- **Advanced Security**: Encryption at rest, secrets management

### 10.2 Extensibility Roadmap

**Plugin System:**
```python
# Future: Plugin architecture for extensions
class PluginManager:
    def register_plugin(self, plugin: AgentMapPlugin):
        """Register external plugin."""

    def load_plugins(self, config: Dict):
        """Auto-discover and load plugins."""
```

**Service Mesh Integration:**
```python
# Future: Service mesh support for distributed deployments
class ServiceMeshAdapter:
    def register_service(self, service: Service, mesh: ServiceMesh):
        """Register service with mesh."""
```

---

## 11. Related Documentation

- **[DEPLOYMENT_ARCHITECTURE.md](./DEPLOYMENT_ARCHITECTURE.md)**: CLI, HTTP, and serverless deployment details
- **[SERVICE_CATALOG.md](./SERVICE_CATALOG.md)**: Complete service inventory and protocols
- **[Testing Patterns](../../docs-docusaurus/docs/testing/testing-patterns.md)**: Testing strategies
- **[Configuration Reference](../../docs-docusaurus/docs/configuration/)**: Configuration options

---

## Appendix A: Glossary

**Bundle**: Pre-compiled workflow metadata containing GraphSpec, agent metadata, and service requirements.

**Protocol**: Runtime-checkable interface defining service contract (PEP 544).

**Static Analysis**: Parsing code declarations without importing/executing modules.

**Declaration**: Agent or service type definition from CSV or Python decorators.

**Clean Architecture**: Layered architecture with strict dependency rules (models → services → orchestration → deployment).

**DI Container**: Dependency injection container managing service lifecycle and dependencies.

**GraphSpec**: Parsed representation of workflow graph from CSV definition.

**ExecutionTracker**: Service tracking node execution with performance metrics.

**StateAdapter**: Service transforming state between different representations.

**Checkpoint**: Saved workflow state enabling suspend/resume functionality.

**Host Service**: External service registered by host application for agent use.

---

## Appendix B: Architecture Decision Records (ADRs)

### ADR-001: Protocol-Based Service Contracts
**Decision**: Use runtime-checkable protocols for all service interfaces.
**Rationale**: Loose coupling, easy testing, clear contracts.
**Consequences**: More boilerplate, but better maintainability.

### ADR-002: Bundle System for Performance
**Decision**: Pre-compile workflow metadata via static analysis.
**Rationale**: 10x performance improvement, eliminate circular dependencies.
**Consequences**: Requires declaration-based agent definitions.

### ADR-003: Clean Architecture Layers
**Decision**: Enforce strict layer boundaries with dependency rules.
**Rationale**: Maintainability, testability, clear separation of concerns.
**Consequences**: More files, but better organization.

### ADR-004: Simplicity Over Flexibility
**Decision**: Prohibit over-engineering patterns (wrappers, unnecessary abstractions).
**Rationale**: Codebase clarity, reduced complexity, faster development.
**Consequences**: Less "flexible" but more maintainable.

### ADR-005: LangGraph as Execution Engine
**Decision**: Use LangGraph for workflow execution instead of custom engine.
**Rationale**: Battle-tested, checkpoint/resume, active development.
**Consequences**: Dependency on external library, but significant feature gain.

---

**End of System Architecture Document**
