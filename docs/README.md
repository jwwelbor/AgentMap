# AgentMap

AgentMap is a declarative orchestration framework for defining and executing LangGraph workflows through CSV and YAML configurations. It enables developers to create complex AI agent workflows without writing extensive code.

## 🌟 Features

- **CSV-Driven Workflow Definition:** Create agent workflows through simple CSV files
- **Agent & Function Scaffolding:** Auto-generate starter code for custom agents and functions
- **Built-in Agent Types:** Use pre-built agents or create custom ones
- **Multiple LLM Support:** Easily use OpenAI, Anthropic Claude, Google Gemini, and other LLMs
- **Dynamic Routing:** Support for conditional branching based on agent outputs
- **Shared State Management:** Maintain context across agent interactions
- **Execution Tracking:** Built-in logging and execution path tracking
- **CLI and API Interfaces:** Run workflows from command line or integrate via API

## 🚀 Installation

### From PyPI (Recommended)

```bash
pip install agentmap
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/agentmap.git
cd agentmap

# Install in development mode
pip install -e .
```

## 🔍 Building Workflows with CSV

AgentMap uses CSV files to define the structure and behavior of agent workflows. Each row in the CSV represents a node in the workflow graph.

### Required Columns

| Column | Description |
|--------|-------------|
| `GraphName` | Name of the workflow graph |
| `Node` | Name of a specific node in the graph |
| `Edge` | Connection to the next node or function reference (e.g., `func:choose_next`) |
| `Context` | Description or prompt for the node |
| `AgentType` | Type of agent to use (e.g., `openai`, `claude`, `echo`) |
| `Success_Next` | Where to go on success (can be multiple with `\|` separator) |
| `Failure_Next` | Where to go on failure (can be multiple with `\|` separator) |
| `Input_Fields` | Fields to extract from state (pipe-separated) |
| `Output_Field` | Field to store the agent's output |
| `Prompt` | Used to pass a prompt to the built-in LLM agents or to your custom agent, pair with input and output fields for extra power |

### Example Workflow CSV

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherFlow,InputCollector,,Collect user location,echo,DataFetcher,,user_input,location,
WeatherFlow,DataFetcher,,Fetch weather data for {location},ApiClient,Analyzer,ErrorHandler,location,weather_data,
WeatherFlow,Analyzer,,Analyze the weather patterns from the data,openai,Report,,weather_data,analysis,
WeatherFlow,Report,,Generate weather report,claude,,,analysis|weather_data,report,
WeatherFlow,ErrorHandler,,Handle API errors,echo,,,error,error_message,
```

## 📊 Complete Workflow Example

### 1. Create a CSV Workflow File

Create a file named `simple_workflow.csv` with the following content:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
SimpleWorkflow,Start,,Starting node of the workflow,Echo,Process,Error,input,initial_data,
SimpleWorkflow,Process,,Process the input data,Default,End,Error,initial_data,processed_data,Processing data from previous step
SimpleWorkflow,End,,Final node of the workflow,Echo,,,processed_data,final_output,
SimpleWorkflow,Error,,Error handling node,Echo,,,error,error_message,
```

This workflow has four nodes:
- **Start**: Takes initial input and passes it to the Process node
- **Process**: Processes the data and sends it to the End node on success
- **End**: Final node that outputs the processed data
- **Error**: Handles any errors that occur during processing

### 2. Run the Workflow Using Python

```python
from agentmap.runner import run_graph
from agentmap.logging import get_logger

logger = get_logger("MyApp")

# Define initial input data
initial_state = {
    "input": "Hello from AgentMap!"
}

# Run the workflow
result = run_graph(
    graph_name="SimpleWorkflow",
    initial_state=initial_state,
    csv_path="simple_workflow.csv"
)

# Display execution results
logger.info(f"Final output: {result.get('final_output')}")

# Display execution path
if "execution_steps" in result:
    logger.info("\nExecution path:")
    for step in result["execution_steps"]:
        node = step["node"]
        duration = step["duration"]
        success = "✓" if step["success"] else "✗"
        logger.info(f"  {success} {node} ({duration:.3f}s)")
```

### 3. Run the Workflow Using CLI

```bash
# Run with input from command line
agentmap run --graph SimpleWorkflow --csv simple_workflow.csv --state '{"input": "Hello from AgentMap!"}'
```

## 🧩 Built-in Agent Types

AgentMap comes with several built-in agent types:

| Agent Type | Description |
|------------|-------------|
| `default` | Simple agent that returns a message with the prompt |
| `echo` | Returns input data unchanged |
| `branching` | Test agent for conditional branching |
| `success` | Always succeeds |
| `failure` | Always fails |
| `input` | Prompts for user input during execution |
| `openai` | Uses OpenAI's models |
| `claude`/`anthropic` | Uses Anthropic's Claude models |
| `gemini`/`google` | Uses Google's Gemini models |

## 📝 Tracking Workflow Execution

### Automatic Execution Tracking

AgentMap automatically tracks the execution of your workflow. Every node execution is recorded in the `execution_steps` field of the result state. Each step contains:

- **node**: Name of the executed node
- **timestamp**: When the node started executing
- **duration**: How long the node took to execute (in seconds)
- **success**: Whether the node executed successfully

```python
# Example of accessing execution steps
result = run_graph("MyWorkflow", initial_state)
steps = result.get("execution_steps", [])

for step in steps:
    print(f"Node: {step['node']}")
    print(f"Duration: {step['duration']}s")
    print(f"Success: {step['success']}")
    print("---")
```

### Visualizing the Execution Path

You can visualize the execution path using the recorded steps:

```python
from agentmap.runner import run_graph

result = run_graph("MyWorkflow", initial_state)

print("Execution path:")
for i, step in enumerate(result.get("execution_steps", [])):
    status = "✅" if step["success"] else "❌"
    print(f"{i+1}. {status} {step['node']} ({step['duration']:.3f}s)")
```

## 🧭 Data Flow and State Management

Data flows through the workflow via a shared state object:

1. Each node extracts inputs from state using `Input_Fields`
2. The agent processes inputs and generates an output
3. The output is stored in state at the location specified by `Output_Field`
4. The next node accesses this data via its own `Input_Fields`

### Inspecting State Changes

You can trace how data flows through your workflow by examining the state at each step:

```python
import json
from agentmap.runner import run_graph
from agentmap.logging import get_logger

logger = get_logger()
logger.setLevel("DEBUG")  # Enable detailed logging

# This will show state changes between nodes during execution
result = run_graph("MyWorkflow", initial_state)
```

## 🛠️ Customizing Agents

### Creating Custom Agents

You can use the scaffolding tool to create custom agents:

```bash
# Generate scaffold for custom agents in your workflow
agentmap scaffold --csv my_workflow.csv
```

This creates Python files in `agentmap/agents/custom/` that you can customize:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class MyCustomAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        # Access input fields
        input_text = inputs.get("input_field")
        
        # Process the inputs
        output = f"Processed: {input_text}"
        
        # Return the output
        return output
```

### Implementing Dynamic Routing

For complex routing logic, you can create custom routing functions:

```python
# In agentmap/functions/choose_route.py
def choose_route(state, success_target, failure_target):
    """
    Choose next node based on custom conditions.
    """
    # Access state data
    data = state.get("processed_data", {})
    
    # Apply custom routing logic
    if "important" in str(data).lower():
        return "PriorityNode"
    elif state.get("last_action_success", True):
        return success_target
    else:
        return failure_target
```

Then reference it in your CSV:

```csv
MyWorkflow,ProcessNode,,Process data,Default,SuccessNode,FailureNode,input,processed_data,
MyWorkflow,ProcessNode,func:choose_route,Process data,Default,SuccessNode,FailureNode,input,processed_data,
```

## 🔄 Running Workflows

### Via CLI

```bash
# Run a workflow with initial state
agentmap run --graph MyWorkflow --state '{"initial_data": "value"}'

# Override CSV path
agentmap run --graph MyWorkflow --csv path/to/workflow.csv --state '{"initial_data": "value"}'

# Enable autocompile
agentmap run --graph MyWorkflow --state '{"initial_data": "value"}' --autocompile
```

### Via Python

```python
from agentmap.runner import run_graph

result = run_graph(
    graph_name="MyWorkflow",
    initial_state={"initial_data": "value"},
    csv_path="path/to/workflow.csv",  # Optional
    autocompile_override=True         # Optional
)
```

### Via API Server

Start the server:

```bash
# Start the FastAPI server
uvicorn agentmap.server:app --reload
```

Then send requests:

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"graph": "MyWorkflow", "state": {"initial_data": "value"}}'
```

## 🔧 Configuration

AgentMap uses a YAML configuration file (`agentmap_config.yaml`) and environment variables:

```yaml
csv_path: path/to/default.csv
autocompile: false

paths:
  custom_agents: "agentmap/agents/custom"
  functions: "agentmap/functions"

llm:
  openai:
    api_key: ""  # Will fall back to OPENAI_API_KEY env var
    model: "gpt-3.5-turbo"
  anthropic:
    api_key: ""  # Will fall back to ANTHROPIC_API_KEY env var
    model: "claude-3-sonnet-20240229"
```

## 🌐 Serverless Deployment

AgentMap includes a handler for serverless deployment:

```python
# AWS Lambda
from agentmap.handler import handler

def lambda_handler(event, context):
    return handler(event, context)
```

## 📚 Advanced Topics

### Compiling Graphs for Performance

For production use, you can compile graphs to improve performance:

```bash
# Compile all graphs defined in your CSV
agentmap compile

# Compile a specific graph
agentmap compile --graph MyWorkflow
```

### Exporting Graphs as Python Code

You can export graphs as Python code for further customization:

```bash
# Export as Python script
agentmap export --graph MyWorkflow --output my_workflow.py
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License

[MIT License](LICENSE)