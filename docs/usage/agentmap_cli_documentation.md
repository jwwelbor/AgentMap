# AgentMap CLI Documentation

AgentMap provides a command-line interface (CLI) for managing workflows, with powerful scaffolding capabilities for custom agents and functions.

## Installation

```bash
pip install agentmap
```

## Basic Commands

### Run a Graph

```bash
agentmap run --graph GraphName --state '{"input": "value"}'
```

Options:
- `--graph`, `-g`: Name of the graph to run
- `--state`, `-s`: Initial state as JSON string
- `--csv`: Optional path to CSV file
- `--autocompile`, `-a`: Automatically compile the graph
- `--config`, `-c`: Path to custom config file

### View Configuration

```bash
agentmap config
```

Options:
- `--path`, `-p`: Path to config file to display

## Scaffolding Commands

The scaffolding functionality is one of AgentMap's most powerful features, allowing you to quickly generate starter code for custom agents and functions.

### Scaffold Agents and Functions

```bash
agentmap scaffold [OPTIONS]
```

Options:
- `--graph`, `-g`: Graph name to scaffold agents for
- `--csv`: CSV path override
- `--config`, `-c`: Path to custom config file

### How Scaffolding Works

The scaffolding command:
1. Analyzes your CSV file to find agent types and functions that aren't built-in
2. Generates Python files for each custom agent and function
3. Places them in the configured directories (default: `agentmap/agents/custom` and `agentmap/functions`)

Example:

```csv
MyGraph,WeatherNode,,Get weather data,Weather,NextNode,,location,weather,Get weather for {location}
```

Running `agentmap scaffold` will generate:
- `agentmap/agents/custom/weather_agent.py` - A starter agent implementation

### Scaffold Output

For custom agents, the scaffold generates:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class WeatherAgent(BaseAgent):
    """
    Get weather data
    
    Node: WeatherNode
    Expected input fields: location
    Expected output field: weather
    Default prompt: Get weather for {location}
    """
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return the output value.
        
        Args:
            inputs (dict): Contains the input values with keys: location
            
        Returns:
            The value for weather
        """
        # Access input fields directly from inputs dictionary
        location = inputs.get("location")
        
        # Implement your agent logic here
        # ...
        
        # Return just the output value (not the whole state)
        return "Your WeatherAgent implementation here"
```

For functions, it generates:

```python
from typing import Dict, Any

def choose_route(state: Any, success_node="SuccessPath", failure_node="FailurePath") -> str:
    """
    Decision function to route between success and failure nodes.
    
    Args:
        state: The current graph state
        success_node (str): Node to route to on success
        failure_node (str): Node to route to on failure
        
    Returns:
        str: Name of the next node to execute
    
    Node: DecisionNode
    Node Context: Decision node description
    
    Available in state:
    - input: Input from previous node
    """
    # TODO: Implement routing logic
    # Determine whether to return success_node or failure_node
    
    # Example implementation (replace with actual logic):
    if state.get("last_action_success", True):
        return success_node
    else:
        return failure_node
```

### Custom Scaffolding Directories

You can customize the directories where scaffolds are generated:

```yaml
### In agentmap_config.yaml
paths:
  custom_agents: "path/to/custom/agents"
  functions: "path/to/functions"
```

Or override them with environment variables:
```bash
export AGENTMAP_CUSTOM_AGENTS_PATH="path/to/custom/agents"
export AGENTMAP_FUNCTIONS_PATH="path/to/functions"
```

### Best Practices for Scaffolding

1. **Write clear Context descriptions** - These become class docstrings
2. **Use descriptive Node names** - These are used in error messages and logs
3. **Specify Input_Fields and Output_Field** - These generate typed method signatures
4. **Include helpful Prompts** - These provide guidance in the scaffolded code

## Export and Compile Commands

### Export a Graph

```bash
agentmap export -g GraphName -o output.py
```

Options:
- `--graph`, `-g`: Graph name to export
- `--output`, `-o`: Output file path
- `--format`, `-f`: Format (python, pickle, source)
- `--csv`: CSV path override
- `--state-schema`, `-s`: State schema type
- `--config`, `-c`: Path to custom config file

### Compile Graphs

```bash
agentmap compile [OPTIONS]
```

Options:
- `--graph`, `-g`: Compile a single graph
- `--output`, `-o`: Output directory for compiled graphs
- `--csv`: CSV path override
- `--state-schema`, `-s`: State schema type
- `--config`, `-c`: Path to custom config file

## Storage Configuration

```bash
agentmap storage-config [OPTIONS]
```

Options:
- `--init`, `-i`: Initialize a default storage configuration file
- `--path`, `-p`: Path to storage config file
- `--config`, `-c`: Path to custom config file

---
