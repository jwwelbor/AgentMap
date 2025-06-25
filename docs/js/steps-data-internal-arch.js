/**
 * Data for the workflow steps.
 * Each step contains title, description, details, code, and visual representation.
 */
const stepsData = [
    {
        title: "What is AgentMap?",
        description: "Build AI workflows using simple CSV files - no complex coding required!",
        details: "AgentMap is a declarative orchestration framework that lets you create sophisticated AI workflows by defining agents and their connections in CSV files. Perfect for rapid prototyping, production workflows, and everything in between.",
        code: null,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TD
                    csv[CSV Definition] -->|Parse| csvParser[CSV Parser Service]
                    csvParser -->|Creates| nodeModels[Node Models]
                    nodeModels -->|Used by| graphBuilder[Graph Builder Service]
                    graphBuilder -->|Creates| graphModel[Graph Model]
                    
                    di[DI Container] -->|Provides| services[Services Layer]
                    services -->|Contains| csvParser
                    services -->|Contains| graphBuilder
                    services -->|Contains| agentFactory[Agent Factory Service]
                    services -->|Contains| compiler[Compilation Service]
                    services -->|Contains| runner[Graph Runner Service]
                    
                    agentFactory -->|Creates| agents[Agent Instances]
                    graphModel -->|Processed by| compiler
                    compiler -->|Produces| compiledGraph[Compiled Graph]
                    
                    initialState[Initial State] -->|Passed to| runner
                    runner -->|Executes| compiledGraph
                    compiledGraph -->|Updates| executionState[Execution State]
                    executionState -->|Returns| resultState[Result State]
                    
                    classDef csv fill:#F3F4F6,stroke:#9CA3AF,color:#4B5563
                    classDef services fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef models fill:#E0F2FE,stroke:#0EA5E9,color:#0C4A6E
                    classDef di fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef agents fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef compiled fill:#A7F3D0,stroke:#059669,color:#064E3B
                    classDef state fill:#FEF3C7,stroke:#F59E0B,color:#92400E
                    classDef result fill:#FFE4E6,stroke:#F43F5E,color:#9F1239
                    
                    class csv csv
                    class csvParser,graphBuilder,agentFactory,compiler,runner,services services
                    class nodeModels,graphModel models
                    class di di
                    class agents agents
                    class compiledGraph compiled
                    class initialState,executionState state
                    class resultState result
                </pre>
            </div>
        `
    },
    {
        title: "1. CSV Workflow Definition",
        description: "AgentMap begins with a CSV file that defines the workflow structure.",
        details: "The CSV file contains rows defining each node in the workflow graph, including agents, edges, prompts, and routing logic.",
        code: null,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart LR
                        subgraph SimpleQA
                            GetInput[GetInput] --> ProcessInput[ProcessInput]
                            ProcessInput -->|success| GenerateResponse[GenerateResponse]
                            ProcessInput -->|failure| HandleError[HandleError]
                            GenerateResponse --> END
                            HandleError --> END
                        end

                        classDef default fill:#1F2937,stroke:#4B5563,color:#E5E7EB
                        classDef input fill:#164E63,stroke:#22D3EE,color:#A5F3FC
                        classDef process fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                        classDef success fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                        classDef error fill:#7F1D1D,stroke:#FCA5A5,color:#FCA5A5
                        classDef endNode fill:#374151,stroke:#6B7280,color:#9CA3AF

                        class GetInput input
                        class ProcessInput process
                        class GenerateResponse success
                        class HandleError error
                        class END endNode
                </pre>
            </div>

            <h3 class="section-title">CSV Definition</h3>
            <div class="csv-table">
                <table>
                    <thead>
                        <tr>
                            <th>GraphName</th>
                            <th>Node</th>
                            <th>Edge</th>
                            <th>Context</th>
                            <th>AgentType</th>
                            <th>Success_Next</th>
                            <th>Failure_Next</th>
                            <th>Input_Fields</th>
                            <th>Output_Field</th>
                            <th>Prompt</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>SimpleQA</td>
                            <td>GetInput</td>
                            <td></td>
                            <td>User input</td>
                            <td>input</td>
                            <td>ProcessInput</td>
                            <td></td>
                            <td>user_query</td>
                            <td>input</td>
                            <td>"Please enter your question:"</td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td>ProcessInput</td>
                            <td></td>
                            <td>Process with LLM</td>
                            <td>openai</td>
                            <td>GenerateResponse</td>
                            <td>HandleError</td>
                            <td>input</td>
                            <td>answer</td>
                            <td>""</td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td>GenerateResponse</td>
                            <td></td>
                            <td>Format response</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
                            <td>answer</td>
                            <td>formatted_answer</td>
                            <td>"Your answer is: {answer}"</td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td>HandleError</td>
                            <td></td>
                            <td>Handle error</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
                            <td>error</td>
                            <td>error_message</td>
                            <td>"Sorry, an error occurred: {error}"</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `
    },
    {
        title: "2. Graph Building with Services",
        description: "The CSV is parsed and transformed into a clean graph model using services.",
        details: "The GraphBuilderService works with CSVGraphParserService to create pure data models. Services contain all business logic while models are simple data containers.",
        code: `# Clean Architecture Pattern
# Models: Pure data containers
class Node:
    def __init__(self, name, agent_type=None, prompt=None, ...):
        self.name = name
        self.agent_type = agent_type
        self.prompt = prompt
        self.edges = {}  # Simple data storage
    
    def add_edge(self, condition, target):
        """Simple data storage method"""
        self.edges[condition] = target

class Graph:
    def __init__(self, name, nodes=None):
        self.name = name
        self.nodes = nodes or {}

# Services: Business logic and orchestration
class GraphBuilderService:
    def __init__(self, csv_parser_service, logging_service):
        self.csv_parser = csv_parser_service
        self.logger = logging_service.get_class_logger(self)
    
    def build_from_csv(self, csv_path: Path) -> Graph:
        """Business logic for building graphs"""
        # Parse CSV using service
        rows = self.csv_parser.parse_csv(csv_path)
        
        # Create node models (pure data)
        nodes = {}
        for row in rows:
            node = Node(name=row['Node'], 
                       agent_type=row['AgentType'],
                       prompt=row['Prompt'])
            # Add edges
            if row.get('Success_Next'):
                node.add_edge('success', row['Success_Next'])
            if row.get('Failure_Next'):
                node.add_edge('failure', row['Failure_Next'])
            nodes[node.name] = node
        
        return Graph(name=row['GraphName'], nodes=nodes)`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart LR
                    GetInput[GetInput] -->|success| ProcessInput[ProcessInput]
                    ProcessInput -->|success| GenerateResponse[GenerateResponse]
                    ProcessInput -->|failure| HandleError[HandleError]
                    
                    classDef input fill:#164E63,stroke:#22D3EE,color:#A5F3FC
                    classDef process fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                    classDef success fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                    classDef error fill:#7F1D1D,stroke:#FCA5A5,color:#FCA5A5
                    
                    class GetInput input
                    class ProcessInput process
                    class GenerateResponse success
                    class HandleError error
                </pre>
            </div>
        `
    },
    {
        title: "3. Agent Initialization with Dependency Injection",
        description: "AgentMap uses services to create and configure agents with proper dependency injection.",
        details: "The AgentFactoryService and AgentRegistryService work together to create agents with injected services. Agents receive infrastructure services (logging, state) and business services (LLM, storage) through protocols.",
        code: `# Service-based agent creation
class AgentFactoryService:
    def __init__(self, agent_registry_service, logging_service, 
                 llm_service, storage_manager, node_registry_service):
        self.agent_registry = agent_registry_service
        self.logging = logging_service
        self.llm_service = llm_service
        self.storage_manager = storage_manager
        self.node_registry = node_registry_service
    
    def create_agent(self, node: Node) -> BaseAgent:
        """Create agent with proper service injection"""
        # Get agent class from registry
        agent_class = self.agent_registry.get_agent_class(node.agent_type)
        
        # Create agent with infrastructure services
        agent = agent_class(
            name=node.name,
            prompt=node.prompt,
            agent_type=node.agent_type,
            context=node.context,
            logger=self.logging.get_agent_logger(node.name)
        )
        
        # Inject business services based on protocols
        if isinstance(agent, LLMServiceUser):
            agent.configure_llm_service(self.llm_service)
        
        if isinstance(agent, StorageCapableAgent):
            storage_service = self.storage_manager.get_service(agent.storage_type)
            agent.configure_storage_service(storage_service)
        
        if isinstance(agent, NodeRegistryUser):
            agent.configure_node_registry(self.node_registry)
        
        return agent

# Protocol-based service injection
class LLMServiceUser(Protocol):
    def configure_llm_service(self, llm_service: LLMService) -> None: ...

class StorageCapableAgent(Protocol):
    def configure_storage_service(self, storage_service: StorageService) -> None: ...`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    registry[Agent Registry] -->|Lookup| agent1[InputAgent]
                    registry -->|Lookup| agent2[OpenAIAgent]
                    registry -->|Lookup| agent3[EchoAgent]

                    agent1 -->|Instantiate| node1[GetInput]
                    agent2 -->|Instantiate| node2[ProcessInput]
                    agent3 -->|Instantiate| node3[GenerateResponse]
                    agent3 -->|Instantiate| node4[HandleError]
                    
                    classDef registry fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef agent fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef node fill:#1F2937,stroke:#4B5563,color:#E5E7EB
                    
                    class registry registry
                    class agent1,agent2,agent3 agent
                    class node1,node2,node3,node4 node
                </pre>
            </div>
        `
    },
    {
        title: "4. Graph Compilation with Services",
        description: "The CompilationService transforms graph models into executable LangGraph StateGraphs.",
        details: "The service layer handles all compilation logic, working with GraphAssemblyService to create LangGraph components. The compiled graph is cached for performance.",
        code: `# Service-based graph compilation
class CompilationService:
    def __init__(self, graph_assembly_service, graph_builder_service, 
                 graph_bundle_service, logging_service):
        self.graph_assembly = graph_assembly_service
        self.graph_builder = graph_builder_service
        self.graph_bundle = graph_bundle_service
        self.logger = logging_service.get_class_logger(self)
    
    def compile_graph(self, graph_name: str, csv_path: Path = None) -> CompiledGraph:
        """Compile graph using clean architecture services"""
        # Check cache first
        cached = self.graph_bundle.load_compiled_graph(graph_name)
        if cached:
            self.logger.info(f"Loaded compiled graph from cache: {graph_name}")
            return cached
        
        # Build graph model from CSV
        graph_model = self.graph_builder.build_from_csv(csv_path)
        
        # Assemble into LangGraph using service
        state_graph = self.graph_assembly.assemble_graph(
            graph_model,
            StateSchema  # Pydantic model for state
        )
        
        # Compile the LangGraph
        compiled = state_graph.compile()
        
        # Cache the result
        self.graph_bundle.save_compiled_graph(graph_name, compiled)
        
        return compiled

class GraphAssemblyService:
    def __init__(self, agent_factory_service, function_resolution_service):
        self.agent_factory = agent_factory_service
        self.function_resolver = function_resolution_service
    
    def assemble_graph(self, graph_model: Graph, state_schema) -> StateGraph:
        """Assemble graph model into LangGraph"""
        builder = StateGraph(state_schema)
        
        # Create and add agents for each node
        for node_name, node in graph_model.nodes.items():
            agent = self.agent_factory.create_agent(node)
            builder.add_node(node_name, agent.run)
        
        # Set entry point
        builder.set_entry_point(graph_model.entry_point)
        
        # Add edges with proper routing
        for node_name, node in graph_model.nodes.items():
            self._add_node_edges(builder, node)
        
        return builder`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    graphDef[Graph Definition] -->|Create| stateGraph[StateGraph Builder]
                    stateGraph -->|AddNode| node1[GetInput]
                    stateGraph -->|AddNode| node2[ProcessInput]
                    stateGraph -->|AddNode| node3[GenerateResponse]
                    stateGraph -->|AddNode| node4[HandleError]
                    stateGraph -->|SetEntryPoint| node1
                    stateGraph -->|AddEdge| edge1{Conditional Edge}
                    stateGraph -->|Compile| compiledGraph[Compiled Graph]
                    
                    classDef graphDef fill:#E0F2FE,stroke:#0EA5E9,color:#0C4A6E
                    classDef builder fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef node fill:#1F2937,stroke:#4B5563,color:#E5E7EB
                    classDef edge fill:#818CF8,stroke:#4F46E5,color:#C7D2FE
                    classDef compiled fill:#D1FAE5,stroke:#10B981,color:#065F46
                    
                    class graphDef graphDef
                    class stateGraph builder
                    class node1,node2,node3,node4 node
                    class edge1 edge
                    class compiledGraph compiled
                </pre>
            </div>
        `
    },
    {
        title: "5. Workflow Execution with Services",
        description: "The GraphRunnerService orchestrates workflow execution with comprehensive tracking.",
        details: "Services handle execution, state management, and tracking. The ExecutionTrackingService monitors performance and the ExecutionPolicyService determines success criteria.",
        code: `# Service-based graph execution
class GraphRunnerService:
    def __init__(self, compilation_service, execution_tracking_service,
                 execution_policy_service, state_adapter_service, logging_service):
        self.compilation = compilation_service
        self.tracking = execution_tracking_service
        self.policy = execution_policy_service
        self.state_adapter = state_adapter_service
        self.logger = logging_service.get_class_logger(self)
    
    def run_graph(self, graph_name: str, initial_state: Dict[str, Any], 
                  csv_path: Path = None) -> ExecutionResult:
        """Execute graph with full service orchestration"""
        # Initialize tracking
        tracker = self.tracking.create_tracker(graph_name)
        tracker.start()
        
        try:
            # Compile or load graph
            compiled_graph = self.compilation.compile_graph(graph_name, csv_path)
            
            # Adapt state if needed
            adapted_state = self.state_adapter.adapt_initial_state(
                initial_state, 
                compiled_graph.state_schema
            )
            
            # Execute with tracking
            self.logger.info(f"Starting execution of graph: {graph_name}")
            result_state = compiled_graph.invoke(adapted_state)
            
            # Track completion
            tracker.complete(result_state)
            
            # Determine success based on policy
            success = self.policy.evaluate_success(
                tracker.get_summary(),
                graph_name
            )
            
            # Build execution result
            return ExecutionResult(
                state=result_state,
                success=success,
                execution_summary=tracker.get_summary(),
                duration=tracker.duration
            )
            
        except Exception as e:
            tracker.fail(str(e))
            self.logger.error(f"Graph execution failed: {graph_name}", exc_info=True)
            raise

# Execution tracking for monitoring
class ExecutionTrackingService:
    def create_tracker(self, graph_name: str) -> ExecutionTracker:
        """Create tracker for execution monitoring"""
        return ExecutionTracker(
            graph_name=graph_name,
            track_outputs=self.config.track_outputs,
            track_inputs=self.config.track_inputs
        )`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    initialState[Initial State] --> getInput[GetInput]
                    getInput -->|Update State| processInput[ProcessInput]
                    processInput -->|Update State| generateResponse[GenerateResponse]
                    generateResponse -->|Update State| finalState[Final State]
                    
                    classDef state fill:#FEF3C7,stroke:#F59E0B,color:#92400E
                    classDef node fill:#1F2937,stroke:#4B5563,color:#E5E7EB
                    classDef final fill:#FFE4E6,stroke:#F43F5E,color:#9F1239
                    
                    class initialState state
                    class getInput,processInput,generateResponse node
                    class finalState final
                </pre>
            </div>
        `
    },
    // {
    //     title: "6. State Management",
    //     description: "AgentMap manages state transitions and updates between agents.",
    //     details: "The runner handles state updates, ensuring that each agent receives the correct context and data.",
    //     code: null,
    //     visual: `<div></div>`
    // },
    // {
    //     title: "7. Result Handling",
    //     description: "The final state is returned after the workflow execution.",
    //     details: "The runner returns the final state, which contains all outputs from the agents.",
    //     code: null,
    //     visual: `<div></div>`
    // },
    // {
    //     title: "8. Error Handling",
    //     description: "AgentMap provides mechanisms for error handling and recovery.",
    //     details: "Errors are logged, and the workflow can be retried or redirected based on the error type.",
    //     code: null,
    //     visual: `<div></div>`
    // }    
];


/**
 * Documentation files available in the project
 */
const documentationFiles = [
    // Getting Started - FIRST!
    {
        "path": "./usage/agentmap_quick_start.md",
        "title": "🚀 Quick Start Guide - Build Your First Workflow!"
    },
    
    // Core Documentation
    {
        "path": "README.md",
        "title": "Main README"
    },
    {
        "path": "./usage/index.md",
        "title": "Usage Documentation Index"
    },
    
    // Architecture Documentation
    {
        "path": "./architecture/clean_architecture_overview.md",
        "title": "Clean Architecture Overview"
    },
    {
        "path": "./architecture/service_catalog.md",
        "title": "Service Catalog"
    },
    {
        "path": "./architecture/dependency_injection_guide.md",
        "title": "Dependency Injection Guide"
    },
    {
        "path": "./architecture/migration_status.md",
        "title": "Migration Status"
    },
    
    // Getting Started
    {
        "path": "./usage/agentmap_csv_schema_documentation.md",
        "title": "CSV Schema Documentation"
    },
    {
        "path": "./usage/agentmap_cli_documentation.md",
        "title": "CLI Documentation"
    },
    {
        "path": "./usage/state_management_and_data_flow.md",
        "title": "State Management and Data Flow (Updated)"
    },
    
    // Agent Development
    {
        "path": "./usage/agentmap_agent_types.md",
        "title": "Basic Agent Types"
    },
    {
        "path": "./usage/advanced_agent_types.md",
        "title": "Advanced Agent Types"
    },
    {
        "path": "./usage/host-service-integration.md",
        "title": "Host Service Integration (Custom Services)"
    },


    {
        "path": "./usage/storage_services.md",
        "title": "Storage Services"
    },
    
    // Workflow Building
    {
        "path": "./usage/prompt_management_in_agentmap.md",
        "title": "Prompt Management"
    },
    {
        "path": "./usage/agentmap_example_workflows.md",
        "title": "Example Workflows"
    },
    {
        "path": "./usage/README_orchestrator.md",
        "title": "Orchestrator Agent"
    },
    
    // Advanced Features
    {
        "path": "./usage/langchain_memory_in_agentmap.md",
        "title": "Memory Management"
    },
    {
        "path": "./usage/README_cloud_storage.md",
        "title": "Cloud Storage Integration"
    },
    {
        "path": "./usage/agentmap_execution_tracking.md",
        "title": "Execution Tracking and Monitoring"
    }
];