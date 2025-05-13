/**
 * Data for the workflow steps.
 * Each step contains title, description, details, code, and visual representation.
 */
const stepsData = [
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
        title: "2. Graph Building",
        description: "The CSV is parsed and transformed into a directed graph structure.",
        details: "The GraphBuilder class reads the CSV and constructs a dictionary representation of the workflow, with nodes, edges, and execution paths.",
        code: `# Inside GraphBuilder.build()
graph_definition = {
    "GetInput": {
        "name": "GetInput",
        "agent_type": "input",
        "prompt": "Please enter your question:",
        "input_fields": ["user_query"],
        "output_field": "input",
        "edges": {"success": "ProcessInput"}
    },
    "ProcessInput": {
        "name": "ProcessInput",
        "agent_type": "openai",
        "prompt": "",
        "input_fields": ["input"],
        "output_field": "answer",
        "edges": {"success": "GenerateResponse", "failure": "HandleError"}
    },
    # ...more nodes
}`,
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
        title: "3. Agent Initialization",
        description: "For each node in the graph, AgentMap creates and initializes the appropriate agent instance.",
        details: "The agent registry maps agent types (like 'openai', 'input', 'echo') to concrete Python classes. Each agent is instantiated with its configuration.",
        code: `# From agentmap/agents/registry.py
AGENT_MAP = {
    "echo": EchoAgent,
    "default": DefaultAgent,
    "input": InputAgent,
    "success": SuccessAgent,
    "failure": FailureAgent,
    "branching": BranchingAgent,
    "openai": OpenAIAgent,
    # ... more agent types
}

# During graph building
agent_cls = get_agent_class(node.agent_type)
agent_instance = agent_cls(
    name=node.name, 
    prompt=node.prompt,
    context={"input_fields": node.inputs, "output_field": node.output}
)`,
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
        title: "4. Graph Compilation",
        description: "The graph is compiled into an executable LangGraph StateGraph.",
        details: "AgentMap creates a LangGraph StateGraph where each node is an agent's run/invoke method. Edges define state transitions between nodes.",
        code: `# From agentmap/compiler.py
def compile_graph(graph_name, ...):
    # Get the graph definition
    graph_def = get_graph_definition(graph_name)
    
    # Create StateGraph builder with schema
    builder = StateGraph(schema_obj)
    
    # Add nodes to the builder
    for node in graph_def.values():
        agent_class = get_agent_class(node.agent_type)
        agent_instance = agent_class(name=node.name, prompt=node.prompt)
        builder.add_node(node.name, agent_instance)
    
    # Set entry point
    entry = next(iter(graph_def))
    builder.set_entry_point(entry)
    
    # Add edges for routing between nodes
    for node in graph_def.values():
        if "success" in node.edges and "failure" in node.edges:
            builder.add_conditional_edges(
                node.name,
                lambda state, s=node.edges["success"], f=node.edges["failure"]: 
                    s if state.get("last_action_success", True) else f
            )
    
    # Compile the graph
    return builder.compile()`,
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
        title: "5. Workflow Execution",
        description: "The compiled graph is executed with an initial state.",
        details: "The state is passed between agents, with each agent updating the state and returning it to the runner.",
        code: `# From agentmap/runner.py
def run_graph(graph_name, initial_state, csv_path=None, ...):
    # Load or build the graph
    graph = load_compiled_graph(graph_name) or build_graph_in_memory(graph_name, csv_path)
    
    # Execute the graph with initial state
    start_time = time.time()
    try:
        result = graph.invoke(initial_state)
        logger.info(f"✅ COMPLETED GRAPH: '{graph_name}' in {time.time() - start_time:.2f}s")
        return result
    except Exception as e:
        logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}'")
        raise`,
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
    {
        title: "The Complete AgentMap Workflow",
        description: "A comprehensive overview of how all parts work together.",
        details: "AgentMap combines CSV parsing, agent creation, graph building, and state management to create flexible workflows.",
        code: null,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    csv[CSV Definition] -->|Parse| graphBuilder[Graph Builder]
                    graphBuilder -->|Build| graphDef[Graph Definition]
                    registry[Agent Registry] -->|Lookup| graphDef
                    graphDef -->|Create| agents[Agent Instances]
                    graphDef -->|Build| stateGraph[StateGraph]
                    stateGraph -->|Compile| compiledGraph[Compiled Graph]
                    agents -->|Add| compiledGraph
                    initialState[Initial State] -->|State Flow| resultState[Result State]
                    resultState -->|Return| runner[Runner]
                    compiledGraph -->|Execute| runner
                    runner -->|Update| resultState
                    
                    classDef csv fill:#F3F4F6,stroke:#9CA3AF,color:#4B5563
                    classDef graphBuilder fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef graphDef fill:#E0F2FE,stroke:#0EA5E9,color:#0C4A6E
                    classDef registry fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef agents fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef stateGraph fill:#D1FAE5,stroke:#10B981,color:#065F46
                    classDef compiled fill:#A7F3D0,stroke:#059669,color:#064E3B
                    classDef initialState fill:#FEF3C7,stroke:#F59E0B,color:#92400E
                    classDef resultState fill:#FFE4E6,stroke:#F43F5E,color:#9F1239
                    classDef runner fill:#FEE2E2,stroke:#EF4444,color:#991B1B
                    
                    class csv csv
                    class graphBuilder graphBuilder
                    class graphDef graphDef
                    class registry registry
                    class agents agents
                    class stateGraph stateGraph
                    class compiledGraph compiled
                    class initialState initialState
                    class resultState resultState
                    class runner runner
                </pre>
            </div>
        `
    }
];

/**
 * Documentation files available in the project
 */
const documentationFiles = [
    { path: 'README.md', title: 'Main README' },
    { path: 'README_usage_details.md', title: 'Usage Details' },
    { path: 'README_cloud_storage.md', title: 'Cloud Storage' }
];