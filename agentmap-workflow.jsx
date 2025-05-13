const AgentMapWorkflow = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [activeTab, setActiveTab] = useState('workflow');
  const [markdownContent, setMarkdownContent] = useState('');
  const [markdownTitle, setMarkdownTitle] = useState('');
  
  const steps = [
    {
      title: "1. CSV Workflow Definition",
      description: "AgentMap begins with a CSV file that defines the workflow structure.",
      details: "The CSV file contains rows defining each node in the workflow graph, including agents, edges, prompts, and routing logic.",
      code: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
SimpleQA,GetInput,,User input,input,ProcessInput,,user_query,input,"Please enter your question:"
SimpleQA,ProcessInput,,Process with LLM,openai,GenerateResponse,HandleError,input,answer,""
SimpleQA,GenerateResponse,,Format response,echo,END,,answer,formatted_answer,"Your answer is: {answer}"
SimpleQA,HandleError,,Handle error,echo,END,,error,error_message,"Sorry, an error occurred: {error}"`,
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <div className="flex flex-col space-y-2">
            <div className="flex text-xs font-bold">
              <div className="w-24 border-r border-gray-300 p-1">GraphName</div>
              <div className="w-24 border-r border-gray-300 p-1">Node</div>
              <div className="w-24 border-r border-gray-300 p-1">Edge</div>
              <div className="w-32 border-r border-gray-300 p-1">Context</div>
              <div className="w-24 border-r border-gray-300 p-1">AgentType</div>
              <div className="w-24 border-r border-gray-300 p-1">Success_Next</div>
              <div className="w-24 border-r border-gray-300 p-1">Failure_Next</div>
            </div>
            <div className="flex text-xs">
              <div className="w-24 border-r border-gray-300 p-1">SimpleQA</div>
              <div className="w-24 border-r border-gray-300 p-1 font-medium">GetInput</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
              <div className="w-32 border-r border-gray-300 p-1">User input</div>
              <div className="w-24 border-r border-gray-300 p-1">input</div>
              <div className="w-24 border-r border-gray-300 p-1">ProcessInput</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
            </div>
            <div className="flex text-xs">
              <div className="w-24 border-r border-gray-300 p-1">SimpleQA</div>
              <div className="w-24 border-r border-gray-300 p-1 font-medium">ProcessInput</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
              <div className="w-32 border-r border-gray-300 p-1">Process with LLM</div>
              <div className="w-24 border-r border-gray-300 p-1">openai</div>
              <div className="w-24 border-r border-gray-300 p-1">GenerateResponse</div>
              <div className="w-24 border-r border-gray-300 p-1">HandleError</div>
            </div>
            <div className="flex text-xs">
              <div className="w-24 border-r border-gray-300 p-1">SimpleQA</div>
              <div className="w-24 border-r border-gray-300 p-1 font-medium">GenerateResponse</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
              <div className="w-32 border-r border-gray-300 p-1">Format response</div>
              <div className="w-24 border-r border-gray-300 p-1">echo</div>
              <div className="w-24 border-r border-gray-300 p-1">END</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
            </div>
            <div className="flex text-xs">
              <div className="w-24 border-r border-gray-300 p-1">SimpleQA</div>
              <div className="w-24 border-r border-gray-300 p-1 font-medium">HandleError</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
              <div className="w-32 border-r border-gray-300 p-1">Handle error</div>
              <div className="w-24 border-r border-gray-300 p-1">echo</div>
              <div className="w-24 border-r border-gray-300 p-1">END</div>
              <div className="w-24 border-r border-gray-300 p-1"></div>
            </div>
          </div>
        </div>
      )
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
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <svg width="500" height="220" viewBox="0 0 500 220">
            <defs>
              <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#4B5563" />
              </marker>
            </defs>
            {/* Nodes */}
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
            {/* Edges */}
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
      )
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
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <div className="space-y-4">
            <div className="flex items-center p-2 bg-blue-50 border border-blue-200 rounded-md">
              <div className="w-24 font-medium">GetInput</div>
              <div className="flex-1">
                <div className="text-sm">InputAgent</div>
                <div className="text-xs text-gray-500">Prompts the user for input</div>
              </div>
            </div>
            
            <div className="flex items-center p-2 bg-yellow-50 border border-yellow-200 rounded-md">
              <div className="w-24 font-medium">ProcessInput</div>
              <div className="flex-1">
                <div className="text-sm">OpenAIAgent</div>
                <div className="text-xs text-gray-500">Uses GPT for processing</div>
              </div>
            </div>
            
            <div className="flex items-center p-2 bg-green-50 border border-green-200 rounded-md">
              <div className="w-24 font-medium">GenerateResponse</div>
              <div className="flex-1">
                <div className="text-sm">EchoAgent</div>
                <div className="text-xs text-gray-500">Formats the response</div>
              </div>
            </div>
            
            <div className="flex items-center p-2 bg-red-50 border border-red-200 rounded-md">
              <div className="w-24 font-medium">HandleError</div>
              <div className="flex-1">
                <div className="text-sm">EchoAgent</div>
                <div className="text-xs text-gray-500">Formats error messages</div>
              </div>
            </div>
          </div>
        </div>
      )
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
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <div className="bg-gray-100 p-3 rounded-md mb-4">
            <div className="text-sm font-medium">StateGraph Compilation</div>
            <div className="text-xs mt-1">Internal representation of the workflow as a LangGraph StateGraph</div>
          </div>
          
          <div className="text-xs space-y-2">
            <div className="flex">
              <div className="w-32 font-medium">Nodes:</div>
              <div className="flex-1">GetInput, ProcessInput, GenerateResponse, HandleError</div>
            </div>
            <div className="flex">
              <div className="w-32 font-medium">Entry Point:</div>
              <div className="flex-1">GetInput</div>
            </div>
            <div className="flex">
              <div className="w-32 font-medium">Conditional Edges:</div>
              <div className="flex-1">
                <div>ProcessInput → GenerateResponse (if success)</div>
                <div>ProcessInput → HandleError (if failure)</div>
              </div>
            </div>
            <div className="flex">
              <div className="w-32 font-medium">Direct Edges:</div>
              <div className="flex-1">
                <div>GetInput → ProcessInput</div>
                <div>GenerateResponse → END</div>
                <div>HandleError → END</div>
              </div>
            </div>
          </div>
        </div>
      )
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
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <div className="space-y-3">
            <div className="p-2 bg-gray-100 rounded-md">
              <div className="text-xs font-semibold">Initial State</div>
              <pre className="text-xs mt-1">{"{\n  \"user_query\": \"What is AgentMap?\"\n}"}</pre>
            </div>
            
            <div className="flex justify-center">
              <div className="text-2xl">↓</div>
            </div>
            
            <div className="p-2 bg-blue-50 rounded-md">
              <div className="text-xs font-semibold">GetInput (InputAgent)</div>
              <pre className="text-xs mt-1">{"{\n  \"user_query\": \"What is AgentMap?\",\n  \"input\": \"What is AgentMap?\",\n  \"last_action_success\": true\n}"}</pre>
            </div>
            
            <div className="flex justify-center">
              <div className="text-2xl">↓</div>
            </div>
            
            <div className="p-2 bg-yellow-50 rounded-md">
              <div className="text-xs font-semibold">ProcessInput (OpenAIAgent)</div>
              <pre className="text-xs mt-1">{"{\n  \"user_query\": \"What is AgentMap?\",\n  \"input\": \"What is AgentMap?\",\n  \"answer\": \"AgentMap is a framework for building...\",\n  \"last_action_success\": true\n}"}</pre>
            </div>
            
            <div className="flex justify-center">
              <div className="text-2xl">↓</div>
            </div>
            
            <div className="p-2 bg-green-50 rounded-md">
              <div className="text-xs font-semibold">GenerateResponse (EchoAgent)</div>
              <pre className="text-xs mt-1">{"{\n  \"user_query\": \"What is AgentMap?\",\n  \"input\": \"What is AgentMap?\",\n  \"answer\": \"AgentMap is a framework for building...\",\n  \"formatted_answer\": \"Your answer is: AgentMap is a framework for building...\",\n  \"last_action_success\": true\n}"}</pre>
            </div>
            
            <div className="flex justify-center">
              <div className="text-2xl">↓</div>
            </div>
            
            <div className="p-2 bg-gray-100 rounded-md">
              <div className="text-xs font-semibold">Final State (Result)</div>
              <pre className="text-xs mt-1">{"{\n  \"user_query\": \"What is AgentMap?\",\n  \"input\": \"What is AgentMap?\",\n  \"answer\": \"AgentMap is a framework for building...\",\n  \"formatted_answer\": \"Your answer is: AgentMap is a framework for building...\",\n  \"last_action_success\": true\n}"}</pre>
            </div>
          </div>
        </div>
      )
    },
    {
      title: "The Complete AgentMap Workflow",
      description: "A comprehensive overview of how all parts work together.",
      details: "AgentMap combines CSV parsing, agent creation, graph building, and state management to create flexible workflows.",
      code: null,
      visual: (
        <div className="border border-gray-300 rounded-md p-4 bg-white">
          <svg width="550" height="400" viewBox="0 0 550 400">
            {/* Main flow components */}
            <g>
              {/* CSV file */}
              <rect x="10" y="20" width="120" height="60" rx="5" fill="#F3F4F6" stroke="#9CA3AF" strokeWidth="2" />
              <text x="70" y="55" fontSize="14" textAnchor="middle" fill="#4B5563">CSV Definition</text>
              
              {/* GraphBuilder */}
              <rect x="200" y="20" width="120" height="60" rx="5" fill="#DBEAFE" stroke="#3B82F6" strokeWidth="2" />
              <text x="260" y="55" fontSize="14" textAnchor="middle" fill="#1E40AF">Graph Builder</text>
              
              {/* Graph Definition */}
              <rect x="200" y="120" width="120" height="60" rx="5" fill="#E0F2FE" stroke="#0EA5E9" strokeWidth="2" />
              <text x="260" y="155" fontSize="14" textAnchor="middle" fill="#0C4A6E">Graph Definition</text>
              
              {/* Agent Registry */}
              <rect x="10" y="120" width="120" height="60" rx="5" fill="#F3E8FF" stroke="#A855F7" strokeWidth="2" />
              <text x="70" y="155" fontSize="14" textAnchor="middle" fill="#6B21A8">Agent Registry</text>
              
              {/* Agent Instances */}
              <rect x="200" y="220" width="120" height="60" rx="5" fill="#FCE7F3" stroke="#EC4899" strokeWidth="2" />
              <text x="260" y="255" fontSize="14" textAnchor="middle" fill="#9D174D">Agent Instances</text>
              
              {/* StateGraph */}
              <rect x="390" y="120" width="120" height="60" rx="5" fill="#D1FAE5" stroke="#10B981" strokeWidth="2" />
              <text x="450" y="155" fontSize="14" textAnchor="middle" fill="#065F46">StateGraph</text>
              
              {/* Compiled Graph */}
              <rect x="390" y="220" width="120" height="60" rx="5" fill="#A7F3D0" stroke="#059669" strokeWidth="2" />
              <text x="450" y="255" fontSize="14" textAnchor="middle" fill="#064E3B">Compiled Graph</text>
              
              {/* Initial State */}
              <rect x="10" y="320" width="120" height="60" rx="5" fill="#FEF3C7" stroke="#F59E0B" strokeWidth="2" />
              <text x="70" y="355" fontSize="14" textAnchor="middle" fill="#92400E">Initial State</text>
              
              {/* Runner */}
              <rect x="390" y="320" width="120" height="60" rx="5" fill="#FEE2E2" stroke="#EF4444" strokeWidth="2" />
              <text x="450" y="355" fontSize="14" textAnchor="middle" fill="#991B1B">Runner</text>
              
              {/* Result */}
              <rect x="200" y="320" width="120" height="60" rx="5" fill="#FFE4E6" stroke="#F43F5E" strokeWidth="2" />
              <text x="260" y="355" fontSize="14" textAnchor="middle" fill="#9F1239">Result State</text>
            </g>
            
            {/* Connecting arrows */}
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
            
            {/* Labels for arrows */}
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
      )
    }
  ];
  
  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };
  
  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };
  
  const currentStepData = steps[currentStep];
  
  // List of documentation files
  const documentationFiles = [
    { path: 'README.md', title: 'Main README' },
    { path: 'README_usage_details.md', title: 'Usage Details' },
    { path: 'agentmap/agents/builtins/storage/blob/README_cloud_storage.md', title: 'Cloud Storage' }
  ];
  
  // Function to fetch and display markdown content
  const fetchMarkdown = async (path, title) => {
    try {
      const response = await fetch(path);
      const text = await response.text();
      setMarkdownContent(text);
      setMarkdownTitle(title);
      setActiveTab('markdown');
    } catch (error) {
      console.error('Error fetching markdown:', error);
      setMarkdownContent('Error loading markdown content');
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-900 p-4">
      <header className="text-center mb-6">
        {/* Hero Image Banner */}
        <div className="relative mb-4 max-w-4xl mx-auto">
          <img 
            src="agentmap-hero.png" 
            alt="AgentMap - Declarative AI Workflow Orchestration" 
            className="w-full rounded-lg shadow-lg"
          />
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black bg-opacity-30 rounded-lg">
            <h1 className="text-4xl md:text-5xl font-bold text-amber-200 mb-2">AgentMap</h1>
            <p className="text-cyan-300 text-xl md:text-2xl">Declarative AI Workflow Orchestration</p>
          </div>
        </div>
        <p className="text-gray-300 mt-4">A step-by-step explanation of how AgentMap processes workflows</p>
      </header>
      
      {/* Main Navigation */}
      <div className="flex space-x-1 mb-6 border-b border-gray-700">
        <button 
          onClick={() => setActiveTab('workflow')}
          className={`px-4 py-2 font-medium rounded-t-lg ${activeTab === 'workflow' 
            ? 'bg-gray-800 border border-gray-700 border-b-gray-800 text-cyan-400' 
            : 'bg-gray-900 text-gray-400 hover:bg-gray-800 hover:text-gray-300'}`}
        >
          Workflow Visualization
        </button>
        <button 
          onClick={() => setActiveTab('documentation')}
          className={`px-4 py-2 font-medium rounded-t-lg ${activeTab === 'documentation' 
            ? 'bg-gray-800 border border-gray-700 border-b-gray-800 text-cyan-400' 
            : 'bg-gray-900 text-gray-400 hover:bg-gray-800 hover:text-gray-300'}`}
        >
          Documentation
        </button>
      </div>
      
      {/* Progress Bar - only show for workflow tab */}
      {activeTab === 'workflow' && (
        <div className="w-full bg-gray-800 rounded-full h-2.5 mb-6">
          <div 
            className="bg-cyan-500 h-2.5 rounded-full" 
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          ></div>
        </div>
      )}
      
      <div className="flex-grow">
        {activeTab === 'workflow' ? (
          <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-6 text-gray-200">
            <h2 className="text-2xl font-bold text-cyan-300 mb-2">{currentStepData.title}</h2>
            <p className="text-gray-200 text-lg mb-4">{currentStepData.description}</p>
            <p className="text-gray-300 mb-6">{currentStepData.details}</p>
            
            {/* Main content area */}
            <div className="flex flex-col md:flex-row gap-6 mb-6">
              {/* Visual representation */}
              <div className="md:w-1/2">
                <h3 className="text-lg font-semibold text-amber-200 mb-3">Visual Representation</h3>
                {currentStepData.visual}
              </div>
              
              {/* Code snippet */}
              {currentStepData.code && (
                <div className="md:w-1/2">
                  <h3 className="text-lg font-semibold text-amber-200 mb-3">Code Example</h3>
                  <div className="bg-gray-900 rounded-md p-4 overflow-auto max-h-96">
                    <pre className="text-cyan-100 text-xs whitespace-pre-wrap">{currentStepData.code}</pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : activeTab === 'documentation' ? (
          <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-6 text-gray-200">
            <h2 className="text-2xl font-bold text-cyan-300 mb-4">Project Documentation</h2>
            <p className="text-gray-200 mb-6">
              The AgentMap project includes several README files that document different aspects of the system. 
              Click on any of the links below to view the documentation.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {documentationFiles.map((doc, index) => (
                <div key={index} className="border border-gray-700 rounded-lg p-4 hover:bg-gray-700 transition-colors">
                  <h3 className="font-medium text-lg mb-2 text-amber-200">{doc.title}</h3>
                  <p className="text-gray-400 text-sm mb-3 truncate">{doc.path}</p>
                  <button 
                    onClick={() => fetchMarkdown(doc.path, doc.title)}
                    className="px-3 py-1 bg-cyan-900 text-cyan-200 rounded-md hover:bg-cyan-800"
                  >
                    View Documentation
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-6 text-gray-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-cyan-300">{markdownTitle}</h2>
              <button 
                onClick={() => setActiveTab('documentation')}
                className="px-3 py-1 bg-gray-700 text-gray-300 rounded-md hover:bg-gray-600 flex items-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17l-5-5m0 0l5-5m-5 5h12" />
                </svg>
                Back to Documentation
              </button>
            </div>
            <div 
              className="markdown-content prose prose-invert prose-cyan max-w-none" 
              dangerouslySetInnerHTML={{ __html: typeof marked !== 'undefined' ? marked.parse(markdownContent) : markdownContent }}
            />
          </div>
        )}
      </div>
      
      {/* Navigation buttons - only show for workflow tab */}
      {activeTab === 'workflow' && (
        <div className="flex justify-between mt-4">
          <button 
            onClick={handlePrev}
            disabled={currentStep === 0}
            className={`px-4 py-2 rounded-md ${currentStep === 0 ? 'bg-gray-700 cursor-not-allowed text-gray-500' : 'bg-cyan-700 hover:bg-cyan-600 text-white'}`}
          >
            Previous
          </button>
          
          <div className="text-gray-400 text-sm mt-2">
            Step {currentStep + 1} of {steps.length}
          </div>
          
          <button 
            onClick={handleNext}
            disabled={currentStep === steps.length - 1}
            className={`px-4 py-2 rounded-md ${currentStep === steps.length - 1 ? 'bg-gray-700 cursor-not-allowed text-gray-500' : 'bg-cyan-700 hover:bg-cyan-600 text-white'}`}
          >
            Next
          </button>
        </div>
      )}
      
      {/* Footer with attributions */}
      <footer className="mt-8 text-center text-gray-400 text-sm">
        <p className="mb-1">
          <span className="font-mono bg-gray-800 text-cyan-300 px-2 py-1 rounded">
            agentmap run -task WorldDomination -state {"{"}"input":"Greetings, AgentMap!"{"}"}
          </span>
        </p>
        <p className="mt-4">Made for GitHub Pages | Created with React</p>
        <p className="mt-1">© {new Date().getFullYear()} | AgentMap Workflow Visualization</p>
      </footer>
    </div>
  );
};

export default AgentMapWorkflow;