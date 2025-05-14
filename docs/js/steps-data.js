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
            <div class="workflow-visual graph-diagram">
                <svg width="500" height="220" viewBox="0 0 500 220">
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#4B5563" />
                        </marker>
                    </defs>
                    <!-- Nodes -->
                    <g>
                        <rect x="20" y="80" width="100" height="40" rx="5" fill="#93C5FD" stroke="#3B82F6" strokeWidth="2" />
                        <text x="70" y="105" fontSize="12" textAnchor="middle" fill="#1E3A8A">GetInput</text>
                        
                        <rect x="200" y="80" width="100" height="40" rx="5" fill="#FDE68A" stroke="#F59E0B" strokeWidth="2" />
                        <text x="250" y="105" fontSize="12" textAnchor="middle" fill="#92400E">ProcessInput</text>
                        
                        <rect x="380" y="40" width="100" height="40" rx="5" fill="#A7F3D0" stroke="#10B981" strokeWidth="2" />
                        <text x="430" y="65" fontSize="12" textAnchor="middle" fill="#065F46">GenerateResponse</text>
                        
                        <rect x="380" y="120" width="100" height="40" rx="5" fill="#FCA5A5" stroke="#EF4444" strokeWidth="2" />
                        <text x="430" y="145" fontSize="12" textAnchor="middle" fill="#7F1D1D">HandleError</text>
                    </g>
                    <!-- Edges -->
                    <g>
                        <line x1="120" y1="100" x2="190" y2="100" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <text x="155" y="95" fontSize="10" textAnchor="middle" fill="#4B5563">success</text>
                        
                        <line x1="300" y1="90" x2="370" y2="60" stroke="#10B981" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <text x="335" y="60" fontSize="10" textAnchor="middle" fill="#10B981">success</text>
                        
                        <line x1="300" y1="110" x2="370" y2="140" stroke="#EF4444" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <text x="335" y="140" fontSize="10" textAnchor="middle" fill="#EF4444">failure</text>
                    </g>
                </svg>
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
            <div class="workflow-visual complete-workflow">
                <svg width="550" height="400" viewBox="0 0 550 400">
                    <!-- Main flow components -->
                    <g>
                        <!-- CSV file -->
                        <rect x="10" y="20" width="120" height="60" rx="5" fill="#F3F4F6" stroke="#9CA3AF" strokeWidth="2" />
                        <text x="70" y="55" fontSize="14" textAnchor="middle" fill="#4B5563">CSV Definition</text>
                        
                        <!-- GraphBuilder -->
                        <rect x="200" y="20" width="120" height="60" rx="5" fill="#DBEAFE" stroke="#3B82F6" strokeWidth="2" />
                        <text x="260" y="55" fontSize="14" textAnchor="middle" fill="#1E40AF">Graph Builder</text>
                        
                        <!-- Graph Definition -->
                        <rect x="200" y="120" width="120" height="60" rx="5" fill="#E0F2FE" stroke="#0EA5E9" strokeWidth="2" />
                        <text x="260" y="155" fontSize="14" textAnchor="middle" fill="#0C4A6E">Graph Definition</text>
                        
                        <!-- Agent Registry -->
                        <rect x="10" y="120" width="120" height="60" rx="5" fill="#F3E8FF" stroke="#A855F7" strokeWidth="2" />
                        <text x="70" y="155" fontSize="14" textAnchor="middle" fill="#6B21A8">Agent Registry</text>
                        
                        <!-- Agent Instances -->
                        <rect x="200" y="220" width="120" height="60" rx="5" fill="#FCE7F3" stroke="#EC4899" strokeWidth="2" />
                        <text x="260" y="255" fontSize="14" textAnchor="middle" fill="#9D174D">Agent Instances</text>
                        
                        <!-- StateGraph -->
                        <rect x="390" y="120" width="120" height="60" rx="5" fill="#D1FAE5" stroke="#10B981" strokeWidth="2" />
                        <text x="450" y="155" fontSize="14" textAnchor="middle" fill="#065F46">StateGraph</text>
                        
                        <!-- Compiled Graph -->
                        <rect x="390" y="220" width="120" height="60" rx="5" fill="#A7F3D0" stroke="#059669" strokeWidth="2" />
                        <text x="450" y="255" fontSize="14" textAnchor="middle" fill="#064E3B">Compiled Graph</text>
                        
                        <!-- Initial State -->
                        <rect x="10" y="320" width="120" height="60" rx="5" fill="#FEF3C7" stroke="#F59E0B" strokeWidth="2" />
                        <text x="70" y="355" fontSize="14" textAnchor="middle" fill="#92400E">Initial State</text>
                        
                        <!-- Runner -->
                        <rect x="390" y="320" width="120" height="60" rx="5" fill="#FEE2E2" stroke="#EF4444" strokeWidth="2" />
                        <text x="450" y="355" fontSize="14" textAnchor="middle" fill="#991B1B">Runner</text>
                        
                        <!-- Result -->
                        <rect x="200" y="320" width="120" height="60" rx="5" fill="#FFE4E6" stroke="#F43F5E" strokeWidth="2" />
                        <text x="260" y="355" fontSize="14" textAnchor="middle" fill="#9F1239">Result State</text>
                    </g>
                    
                    <!-- Connecting arrows -->
                    <g>
                        <line x1="130" y1="50" x2="190" y2="50" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="260" y1="80" x2="260" y2="110" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="130" y1="150" x2="190" y2="150" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="260" y1="180" x2="260" y2="210" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="320" y1="150" x2="380" y2="150" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="450" y1="180" x2="450" y2="210" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="70" y1="180" x2="70" y2="310" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        
                        <line x1="130" y1="350" x2="190" y2="350" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="320" y1="350" x2="380" y2="350" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        
                        <line x1="450" y1="280" x2="450" y2="310" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        <line x1="320" y1="250" x2="380" y2="250" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                        
                        <path d="M 390 320 C 350 300, 320 300, 280 280" fill="none" stroke="#4B5563" strokeWidth="2" markerEnd="url(#arrowhead)" />
                    </g>
                    
                    <!-- Labels for arrows -->
                    <g>
                        <text x="160" y="40" fontSize="10" textAnchor="middle" fill="#4B5563">Parse</text>
                        <text x="270" y="100" fontSize="10" textAnchor="middle" fill="#4B5563">Build</text>
                        <text x="160" y="140" fontSize="10" textAnchor="middle" fill="#4B5563">Lookup</text>
                        <text x="270" y="200" fontSize="10" textAnchor="middle" fill="#4B5563">Create</text>
                        <text x="350" y="140" fontSize="10" textAnchor="middle" fill="#4B5563">Build</text>
                        <text x="460" y="200" fontSize="10" textAnchor="middle" fill="#4B5563">Compile</text>
                        <text x="160" y="340" fontSize="10" textAnchor="middle" fill="#4B5563">State Flow</text>
                        <text x="350" y="340" fontSize="10" textAnchor="middle" fill="#4B5563">Return</text>
                        <text x="350" y="240" fontSize="10" textAnchor="middle" fill="#4B5563">Add</text>
                        <text x="460" y="300" fontSize="10" textAnchor="middle" fill="#4B5563">Execute</text>
                        <text x="340" y="300" fontSize="10" textAnchor="middle" fill="#4B5563">Update</text>
                    </g>
                </svg>
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