---
sidebar_position: 2
title: CLI Commands Reference
description: Complete reference for AgentMap command-line interface
---

# CLI Commands Reference

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

## Common Usage Patterns

### Development Workflow

1. **Create CSV workflow**
   ```bash
   # Create your workflow.csv file with your favorite editor
   vim customer_workflow.csv
   ```

2. **Validate workflow structure**
   ```bash
   agentmap validate-csv --csv customer_workflow.csv
   # Expected output:
   # ✅ CSV validation successful
   # ✅ Found 5 nodes in workflow
   # ✅ All required columns present
   ```

3. **Scaffold missing agents**
   ```bash
   agentmap scaffold --csv customer_workflow.csv
   # Expected output:
   # ✅ Generated WeatherAgent in custom_agents/weather_agent.py
   # ✅ Generated PaymentAgent in custom_agents/payment_agent.py
   # ℹ️  Edit generated files to implement your logic
   ```

4. **Implement custom agents**
   ```bash
   # Edit generated files in custom_agents/
   code custom_agents/weather_agent.py
   ```

5. **Test workflow**
   ```bash
   agentmap run --graph CustomerWorkflow --csv customer_workflow.csv
   # Expected output:
   # ✅ Graph execution completed successfully
   # ✅ Execution time: 2.34s
   # ✅ All 5 nodes executed successfully
   ```

6. **Compile for production**
   ```bash
   agentmap compile --graph CustomerWorkflow --output ./compiled/
   # Expected output:
   # ✅ Graph compiled successfully
   # ✅ Output saved to: ./compiled/CustomerWorkflow.pkl
   # ✅ Ready for production deployment
   ```

### Configuration Management

```bash
# View current configuration
agentmap config
# Expected output:
# Configuration loaded from: /path/to/agentmap_config.yaml
# ✅ CSV Path: ./workflows/
# ✅ Custom Agents: ./custom_agents/
# ✅ Compiled Graphs: ./compiled/
# ✅ Storage: Local file system

# View specific configuration section
agentmap config --section execution
# Expected output:
# Execution Configuration:
# ✅ Auto-compile: true
# ✅ Tracking enabled: false
# ✅ Success policy: all_nodes

# Use custom config file
agentmap run --config ./configs/production.yaml --graph ProductionFlow

# Initialize storage configuration
agentmap storage-config --init
# Expected output:
# ✅ Storage configuration initialized
# ✅ Created: agentmap_storage_config.yaml
# ℹ️  Edit the file to configure cloud storage
```

### Debugging and Development

```bash
# Run with debug logging
agentmap run --graph TestFlow --log-level DEBUG
# Expected output:
# DEBUG: Loading graph definition from CSV
# DEBUG: Resolving agent dependencies
# DEBUG: [Node: start] Executing with inputs: {...}
# DEBUG: [Node: start] Completed in 0.123s
# ✅ Graph execution completed

# Run with detailed execution tracking
agentmap run --graph TestFlow --track-detailed
# Expected output:
# ✅ Graph execution completed
# 📊 Execution Summary:
#    Total time: 2.45s
#    Nodes executed: 4
#    Success rate: 100%

# Auto-compile before running
agentmap run --graph TestFlow --autocompile
# Expected output:
# ℹ️  Auto-compiling graph...
# ✅ Compilation completed
# ✅ Graph execution completed

# Export for inspection
agentmap export --graph TestFlow --format source --output ./debug/
# Expected output:
# ✅ Graph exported to: ./debug/TestFlow_source.py
# ℹ️  Review the generated code for debugging
```

## Environment Variables

AgentMap respects several environment variables for configuration:

- `AGENTMAP_CONFIG_PATH`: Default configuration file path
- `AGENTMAP_CSV_PATH`: Default CSV file path
- `AGENTMAP_CUSTOM_AGENTS_PATH`: Custom agents directory
- `AGENTMAP_FUNCTIONS_PATH`: Functions directory
- `AGENTMAP_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Error Handling

### Common CLI Errors

- **Graph not found**: Verify graph name matches CSV GraphName column
- **Missing agents**: Run scaffold command to generate missing custom agents
- **Configuration errors**: Check config file syntax and required fields
- **Permission errors**: Ensure write access to output directories

### Debugging Tips

1. Use `--log-level DEBUG` for verbose output
2. Verify CSV syntax with a CSV validator
3. Check that custom agents are in the correct directory
4. Ensure all required environment variables are set

## Monitoring and Operations

### Health Checks

```bash
# Check system health
agentmap diagnose
# Expected output:
# 🔍 AgentMap System Diagnosis
# ✅ Configuration: Valid
# ✅ Dependencies: All available
# ✅ Storage: Accessible
# ✅ Custom agents: 3 found
# ✅ Compiled graphs: 2 found

# Validate specific workflow
agentmap validate-csv --csv production_workflow.csv
# Expected output:
# ✅ CSV structure valid
# ✅ All agent types available
# ✅ Dependency chain complete
# ⚠️  Warning: Large prompt in node 'process_data'

# Check configuration validity
agentmap validate-config
# Expected output:
# ✅ Configuration file syntax valid
# ✅ All required paths exist
# ✅ Storage configuration valid
# ❌ Error: Invalid LLM API key format
```

### Performance Monitoring

```bash
# Run with performance profiling
agentmap run --graph MyWorkflow --profile
# Expected output:
# ✅ Graph execution completed
# 📊 Performance Profile:
#    Node 'validate_input': 0.045s
#    Node 'process_data': 1.234s ⚠️  (slow)
#    Node 'generate_output': 0.123s
#    Total execution: 1.402s

# Monitor execution over time
agentmap run --graph MyWorkflow --monitor
# Expected output:
# 🔄 Monitoring mode enabled
# ✅ Execution 1: 1.23s (success)
# ✅ Execution 2: 1.18s (success)
# ❌ Execution 3: failed (error in process_data)
# 📊 Average: 1.21s, Success rate: 66.7%
```

### Troubleshooting Commands

```bash
# Inspect graph structure
agentmap inspect --graph MyWorkflow
# Expected output:
# 📊 Graph Structure: MyWorkflow
# Nodes: 5
# Edges: 4
# Entry points: 1 (start_node)
# Exit points: 1 (end_node)
# 
# Flow diagram:
# start_node → validate_input → process_data → generate_output → end_node

# Check dependencies
agentmap validate-dependencies --graph MyWorkflow
# Expected output:
# ✅ All required agents available
# ✅ All custom functions found
# ⚠️  Warning: WeatherAgent uses deprecated API
# ℹ️  Suggestion: Update to use WeatherService v2

# Clear cache and rebuild
agentmap clear-cache
agentmap compile --graph MyWorkflow --force
# Expected output:
# ✅ Cache cleared
# ✅ Force compilation completed
# ℹ️  All compiled graphs refreshed
```

## Advanced CLI Features

### Batch Operations

```bash
# Compile all graphs in directory
agentmap compile-all --csv-dir ./workflows/
# Expected output:
# ✅ Compiled: CustomerOnboarding (3.2s)
# ✅ Compiled: OrderProcessing (2.1s)
# ❌ Failed: PaymentWorkflow (missing WeatherAgent)
# 📊 Summary: 2/3 successful

# Validate all workflows
agentmap validate-all --csv-dir ./workflows/
# Expected output:
# ✅ CustomerOnboarding.csv: Valid
# ⚠️  OrderProcessing.csv: 1 warning
# ❌ PaymentWorkflow.csv: 2 errors
```

### Integration with CI/CD

```bash
# Validate for CI/CD pipeline
agentmap validate-all --format json --output validation_report.json
# Generates JSON report for automated processing

# Export deployment package
agentmap package --graph ProductionWorkflow --output deployment.tar.gz
# Expected output:
# ✅ Packaging workflow for deployment
# ✅ Including: compiled graph, dependencies, config
# ✅ Package created: deployment.tar.gz (2.3MB)
```

## Output Formats and Logging

### JSON Output for Automation

```bash
# Get machine-readable output
agentmap run --graph MyWorkflow --format json
# Output:
# {
#   "success": true,
#   "execution_time": 1.234,
#   "nodes_executed": 5,
#   "result": {...},
#   "errors": []
# }

# Structured validation output
agentmap validate-csv --csv workflow.csv --format json
# Output:
# {
#   "valid": true,
#   "errors": [],
#   "warnings": ["Large prompt in node 'process'"],
#   "statistics": {
#     "nodes": 5,
#     "agents_used": ["input", "llm", "output"]
#   }
# }
```

### Logging Configuration

```bash
# Set log level for detailed debugging
AGENTMAP_LOG_LEVEL=DEBUG agentmap run --graph MyWorkflow

# Log to file
agentmap run --graph MyWorkflow --log-file execution.log

# Structured logging for monitoring systems
agentmap run --graph MyWorkflow --log-format json
```

## Security and Production

### Secure Execution

```bash
# Run in sandbox mode (limited permissions)
agentmap run --graph MyWorkflow --sandbox

# Validate security before deployment
agentmap security-check --graph MyWorkflow
# Expected output:
# 🔒 Security Analysis: MyWorkflow
# ✅ No file system access outside workspace
# ✅ No network access to sensitive endpoints
# ⚠️  Warning: Custom agent executes shell commands
# ℹ️  Review: custom_agents/system_agent.py:45
```

### Production Deployment

```bash
# Create production build
agentmap build --graph MyWorkflow --env production
# Expected output:
# ✅ Production build created
# ✅ Optimizations applied
# ✅ Security validations passed
# 📦 Build artifacts in: ./dist/MyWorkflow/

# Deploy to production
agentmap deploy --build ./dist/MyWorkflow/ --target production
```

## Related Documentation

### 🚀 **Getting Started**
- **[Quick Start Guide](../getting-started)**: Build your first workflow in 5 minutes
- **[Understanding Workflows](/docs/guides/learning-paths/understanding-workflows)**: Core workflow concepts and patterns
- **[CSV Schema Reference](csv-schema)**: Complete CSV workflow format specification

### 🔧 **CLI Tools & Debugging**
- **[CLI Graph Inspector](cli-graph-inspector)**: Advanced graph analysis and debugging
- **[Interactive Playground](../playground)**: Test workflows in your browser
- **[Execution Tracking](/docs/guides/deploying/monitoring)**: Performance monitoring and debugging

### 🤖 **Agent Development**
- **[Agent Types Reference](agent-types)**: Available agent types and configurations
- **[Advanced Agent Types](/docs/guides/development/agents/advanced-agent-types)**: Custom agent development
- **[Agent Development Contract](/docs/guides/development/agents/agent-development)**: Agent interface requirements

### 🏗️ **Advanced Operations**
- **[Service Injection Patterns](../contributing/service-injection)**: Dependency injection in agents
- **[Host Service Integration](/docs/guides/development/agents/host-service-integration)**: Custom service integration
- **[Testing Patterns](/docs/guides/development/testing)**: Testing strategies for CLI workflows

### 📚 **Tutorials & Examples**
- **[Weather Bot Tutorial](../tutorials/weather-bot)**: Complete CLI workflow example
- **[Data Processing Pipeline](../tutorials/data-processing-pipeline)**: ETL workflow with CLI operations
- **[Example Workflows](../examples/)**: Real-world CLI usage patterns
