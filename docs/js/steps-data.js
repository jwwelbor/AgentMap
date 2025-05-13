/**
 * Data for the workflow steps.
 * Each step contains title, description, details, code, and visual representation.
 */
const stepsData = [
    {
        title: "1. CSV Workflow Definition",
        description: "AgentMap begins with a CSV file that defines the workflow structure.",
        details: "The CSV file contains rows defining each node in the workflow graph, including agents, edges, prompts, and routing logic.",
        code: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
SimpleQA,GetInput,,User input,input,ProcessInput,,user_query,input,"Please enter your question:"
SimpleQA,ProcessInput,,Process with LLM,openai,GenerateResponse,HandleError,input,answer,""
SimpleQA,GenerateResponse,,Format response,echo,END,,answer,formatted_answer,"Your answer is: {answer}"
SimpleQA,HandleError,,Handle error,echo,END,,error,error_message,"Sorry, an error occurred: {error}"`,
        visual: `
            <div class="workflow-visual csv-table">
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
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="node-highlight">GetInput</td>
                            <td></td>
                            <td>User input</td>
                            <td>input</td>
                            <td>ProcessInput</td>
                            <td></td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="node-highlight">ProcessInput</td>
                            <td></td>
                            <td>Process with LLM</td>
                            <td>openai</td>
                            <td>GenerateResponse</td>
                            <td>HandleError</td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="node-highlight">GenerateResponse</td>
                            <td></td>
                            <td>Format response</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="node-highlight">HandleError</td>
                            <td></td>
                            <td>Handle error</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
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
            <div class="mermaid">
            flowchart LR
                GetInput["GetInput"] -->|success| ProcessInput["ProcessInput"]
                ProcessInput -->|success| GenerateResponse["GenerateResponse"]
                ProcessInput -->|failure| HandleError["HandleError"]
                
                classDef input fill:#164E63,stroke:#22D3EE,color:#A5F3FC
                classDef process fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                classDef success fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                classDef error fill:#7F1D1D,stroke:#FCA5A5,color:#FCA5A5
                
                class GetInput input
                class ProcessInput process
                class GenerateResponse success
                class HandleError error
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
            <div class="workflow-visual agent-boxes">
                <div class="agent-box agent-input">
                    <div class="agent-name">GetInput</div>
                    <div class="agent-content">
                        <div class="agent-type">InputAgent</div>
                        <div class="agent-desc">Prompts the user for input</div>
                    </div>
                </div>
                
                <div class="agent-box agent-openai">
                    <div class="agent-name">ProcessInput</div>
                    <div class="agent-content">
                        <div class="agent-type">OpenAIAgent</div>
                        <div class="agent-desc">Uses GPT for processing</div>
                    </div>
                </div>
                
                <div class="agent-box agent-echo">
                    <div class="agent-name">GenerateResponse</div>
                    <div class="agent-content">
                        <div class="agent-type">EchoAgent</div>
                        <div class="agent-desc">Formats the response</div>
                    </div>
                </div>
                
                <div class="agent-box agent-error">
                    <div class="agent-name">HandleError</div>
                    <div class="agent-content">
                        <div class="agent-type">EchoAgent</div>
                        <div class="agent-desc">Formats error messages</div>
                    </div>
                </div>
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
            <div class="workflow-visual compilation-view">
                <div class="compilation-header">
                    <div class="compilation-title">StateGraph Compilation</div>
                    <div class="compilation-subtitle">Internal representation of the workflow as a LangGraph StateGraph</div>
                </div>
                
                <div class="compilation-details">
                    <div class="compilation-row">
                        <div class="compilation-label">Nodes:</div>
                        <div class="compilation-value">GetInput, ProcessInput, GenerateResponse, HandleError</div>
                    </div>
                    <div class="compilation-row">
                        <div class="compilation-label">Entry Point:</div>
                        <div class="compilation-value">GetInput</div>
                    </div>
                    <div class="compilation-row">
                        <div class="compilation-label">Conditional Edges:</div>
                        <div class="compilation-value">
                            <div>ProcessInput → GenerateResponse (if success)</div>
                            <div>ProcessInput → HandleError (if failure)</div>
                        </div>
                    </div>
                    <div class="compilation-row">
                        <div class="compilation-label">Direct Edges:</div>
                        <div class="compilation-value">
                            <div>GetInput → ProcessInput</div>
                            <div>GenerateResponse → END</div>
                            <div>HandleError → END</div>
                        </div>
                    </div>
                </div>
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
            <div class="workflow-visual execution-flow">
                <div class="state-box initial-state">
                    <div class="state-title">Initial State</div>
                    <pre class="state-content">{\n  "user_query": "What is AgentMap?"\n}</pre>
                </div>
                
                <div class="flow-arrow">↓</div>
                
                <div class="state-box input-state">
                    <div class="state-title">GetInput (InputAgent)</div>
                    <pre class="state-content">{\n  "user_query": "What is AgentMap?",\n  "input": "What is AgentMap?",\n  "last_action_success": true\n}</pre>
                </div>
                
                <div class="flow-arrow">↓</div>
                
                <div class="state-box process-state">
                    <div class="state-title">ProcessInput (OpenAIAgent)</div>
                    <pre class="state-content">{\n  "user_query": "What is AgentMap?",\n  "input": "What is AgentMap?",\n  "answer": "AgentMap is a framework for building...",\n  "last_action_success": true\n}</pre>
                </div>
                
                <div class="flow-arrow">↓</div>
                
                <div class="state-box response-state">
                    <div class="state-title">GenerateResponse (EchoAgent)</div>
                    <pre class="state-content">{\n  "user_query": "What is AgentMap?",\n  "input": "What is AgentMap?",\n  "answer": "AgentMap is a framework for building...",\n  "formatted_answer": "Your answer is: AgentMap is a framework for building...",\n  "last_action_success": true\n}</pre>
                </div>
                
                <div class="flow-arrow">↓</div>
                
                <div class="state-box final-state">
                    <div class="state-title">Final State (Result)</div>
                    <pre class="state-content">{\n  "user_query": "What is AgentMap?",\n  "input": "What is AgentMap?",\n  "answer": "AgentMap is a framework for building...",\n  "formatted_answer": "Your answer is: AgentMap is a framework for building...",\n  "last_action_success": true\n}</pre>
                </div>
            </div>
        `
    },
    {
        title: "The Complete AgentMap Workflow",
        description: "A comprehensive overview of how all parts work together.",
        details: "AgentMap combines CSV parsing, agent creation, graph building, and state management to create flexible workflows.",
        code: null,
        visual: `
            <div class="mermaid">
            flowchart TD
                CSV["CSV Definition"] -->|Parse| GraphBuilder["Graph Builder"]
                GraphBuilder -->|Build| GraphDef["Graph Definition"]
                AgentRegistry["Agent Registry"] -->|Lookup| GraphDef
                GraphDef -->|Create| AgentInstances["Agent Instances"]
                GraphDef -->|Build| StateGraph["StateGraph"]
                StateGraph -->|Compile| CompiledGraph["Compiled Graph"]
                AgentInstances -->|Add| CompiledGraph
                InitialState["Initial State"] -->|State Flow| ResultState["Result State"]
                ResultState -->|Return| Runner["Runner"]
                CompiledGraph -->|Execute| Runner
                Runner -->|Update| ResultState
                
                classDef csv fill:#F3F4F6,stroke:#9CA3AF,color:#4B5563
                classDef graph fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                classDef graphDef fill:#E0F2FE,stroke:#0EA5E9,color:#0C4A6E
                classDef agent fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                classDef instances fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                classDef state fill:#D1FAE5,stroke:#10B981,color:#065F46
                classDef compiled fill:#A7F3D0,stroke:#059669,color:#064E3B
                classDef initial fill:#FEF3C7,stroke:#F59E0B,color:#92400E
                classDef runner fill:#FEE2E2,stroke:#EF4444,color:#991B1B
                classDef result fill:#FFE4E6,stroke:#F43F5E,color:#9F1239
                
                class CSV csv
                class GraphBuilder graph
                class GraphDef graphDef
                class AgentRegistry agent
                class AgentInstances instances
                class StateGraph state
                class CompiledGraph compiled
                class InitialState initial
                class ResultState result
                class Runner runner
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