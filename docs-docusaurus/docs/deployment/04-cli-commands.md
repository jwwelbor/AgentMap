---
sidebar_position: 2
title: CLI Commands Reference
description: Complete reference for AgentMap command-line interface and deployment commands
keywords: [CLI commands, command line, deployment, scaffolding, graph execution]
---

# CLI Commands Reference

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>CLI Commands</strong></span>
</div>

AgentMap provides a command-line interface (CLI) for deploying and managing workflows, with powerful scaffolding capabilities for custom agents and functions. The CLI is ideal for development, testing, automation scripts, and production deployments that don't require web API interfaces.

## Configuration Loading

AgentMap uses a **hierarchical configuration system** with automatic discovery:

### Configuration Precedence Order

1. **Explicit `--config` flag** (Highest Priority)
   ```bash
   agentmap run --config /path/to/custom.yaml
   ```

2. **`agentmap_config.yaml` in current directory** (Auto-Discovered)
   ```bash
   # If agentmap_config.yaml exists in current directory, automatically used
   agentmap run
   ```

3. **System defaults** (Lowest Priority)
   ```bash
   # If no config file found, uses built-in defaults
   agentmap run
   ```

### Configuration Discovery Logging

AgentMap shows which configuration source is being used:

```bash
[2024-08-06 10:30:15] INFO: Using configuration from: explicit config: /path/to/config.yaml
[2024-08-06 10:30:15] INFO: Using configuration from: auto-discovered: /current/dir/agentmap_config.yaml
[2024-08-06 10:30:15] INFO: Using configuration from: system defaults
```

### Quick Start with Local Config

1. Copy configuration template to your working directory:
   ```bash
   agentmap init-config
   ```

2. Edit `agentmap_config.yaml` as needed

3. Run commands without specifying `--config`:
   ```bash
   agentmap run --csv examples/lesson1.csv
   ```

## Installation

```bash
pip install agentmap
```

## Basic Commands

### Run a Graph

```bash
agentmap run --graph graph_name --state '{"input": "value"}'
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

## ✨ Simplified Graph Naming Syntax

AgentMap supports **intelligent default graph naming** that eliminates the need to specify graph names for simple workflows.

### Smart Defaults

**CSV filename automatically becomes the graph name:**

```bash
# Traditional approach
agentmap run --graph CustomerSupport --csv customer_support.csv --state '{"query": "help"}'

# ✨ New simplified approach
agentmap run --csv customer_support.csv --state '{"query": "help"}'
# Graph name is automatically "customer_support"
```

### :: Override Syntax

**Specify custom graph names when needed:**

```bash
# Override graph name for multi-graph CSV files
agentmap run --csv workflows.csv::ProductSupport --state '{"product": "AgentMap"}'

# Works with all commands
agentmap scaffold --csv complex_workflows.csv::SpecificGraph
agentmap compile --csv production.csv::MainFlow
agentmap export --csv analysis.csv::DataProcessor --format python
```

### HTTP API Integration

**URL encoding for web APIs:**

```bash
# HTTP API endpoints support :: syntax with URL encoding
curl -X POST "http://localhost:8000/execution/workflow.csv%3A%3AGraphName" \
     -H "Content-Type: application/json" \
     -d '{"state": {"input": "value"}}'

# RESTful endpoints for default graph names
curl -X POST "http://localhost:8000/execution/customer_support.csv" \
     -H "Content-Type: application/json" \
     -d '{"state": {"query": "help"}}'
```

### Migration Examples

**Side-by-side comparison:**

| Traditional Syntax | New Simplified Syntax | Use Case |
|-------------------|----------------------|----------|
| `--graph MyFlow --csv my_file.csv` | `--csv my_flow.csv` | Single graph per file |
| `--graph Graph1 --csv multi.csv` | `--csv multi.csv::Graph1` | Multiple graphs per file |
| `--graph Test --csv complex.csv` | `--csv complex.csv::Test` | Override default name |

**Benefits:**
- ⚡ **Faster Development**: Less typing for common workflows
- 📁 **Self-Documenting**: File names clearly indicate purpose
- 🔗 **URL-Safe**: Works seamlessly with HTTP APIs
- 🔄 **Backward Compatible**: All existing workflows continue working

## Scaffolding Commands

AgentMap's **service-aware scaffolding system** is a sophisticated code generation feature that automatically creates custom agent classes and routing functions from CSV definitions. It analyzes CSV context to detect service requirements and generates complete, working code with automatic service integration.

### Core Scaffolding Command

```bash
agentmap scaffold [OPTIONS]
```

**Options:**
- `--graph`, `-g`: Graph name to scaffold agents for (optional - defaults to all graphs)
- `--csv`: CSV path override (uses config default if not specified)
- `--output`, `-o`: Custom directory for agent output (overrides config)
- `--functions`, `-f`: Custom directory for function output (overrides config)
- `--config`, `-c`: Path to custom config file

### Service-Aware Code Generation

The scaffolding system automatically detects service requirements from CSV context and generates agents with proper service integration:

**Example CSV with Service Context:**
```csv
GraphName,Node,Edge,Description,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Context
IntelligentWorkflow,ProcessData,,"Analyze data using LLM",DataAnalyzer,FormatOutput,HandleError,data|query,analysis,"{""services"": [""llm"", ""storage""]}"
```

**Generated Agent with Service Integration:**
```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from typing import Dict, Any

class DataAnalyzerAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    """
    Analyze data using LLM with storage and LLM capabilities
    
    Node: ProcessData
    Expected input fields: data, query
    Expected output field: analysis
    
    Available Services:
    - self.llm_service: LLM service for calling language models
    - self.storage_service: Generic storage service (supports all storage types)
    """
    
    def __init__(self):
        super().__init__()
        
        # Service attributes (automatically injected during graph building)
        self.llm_service: LLMServiceProtocol = None
        self.storage_service: StorageServiceProtocol = None
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return the analysis result.
        
        Args:
            inputs (dict): Contains input values with keys: data, query
            
        Returns:
            The analysis result
        """
        # Access input fields
        data_value = inputs.get("data")
        query_value = inputs.get("query")
        
        # LLM SERVICE:
        if hasattr(self, 'llm_service') and self.llm_service:
            response = self.llm_service.call_llm(
                provider="openai",  # or "anthropic", "google"
                messages=[{"role": "user", "content": query_value}],
                model="gpt-4"  # optional
            )
            analysis_result = response.get("content")
        
        # STORAGE SERVICE:
        if hasattr(self, 'storage_service') and self.storage_service:
            # Save analysis for future reference
            self.storage_service.write("json", "analysis_results.json", {
                "query": query_value,
                "analysis": analysis_result,
                "timestamp": "2024-01-01T00:00:00Z"
            })
        
        return analysis_result
```

### Supported Service Types

The scaffolding system supports multiple service architectures and automatically chooses the appropriate approach:

**Unified Storage Services:**
- `"storage"` - Generic storage service supporting all storage types (CSV, JSON, File, Vector, Memory)

**Separate Service Protocols:**
- `"llm"` - Language model services (OpenAI, Anthropic, Google)
- `"csv"` - CSV file operations
- `"json"` - JSON file operations  
- `"file"` - General file operations
- `"vector"` - Vector search and embeddings
- `"memory"` - In-memory data storage
- `"node_registry"` - Access to graph node metadata for dynamic routing

### Service Context Configuration

Specify service requirements in your CSV using the Context field:

**JSON Format:**
```csv
Context
"{""services"": [""llm"", ""storage""]}"
"{""services"": [""llm"", ""vector"", ""memory""]}"
"{""services"": [""csv"", ""json""]}"
```

**String Format:**
```csv
Context
"services: llm|storage"
"services: vector|memory|llm"
```

### Service Architecture Auto-Detection

The system automatically chooses the appropriate service architecture:

**Unified Architecture** (when `"storage"` is requested):
```python
class Agent(BaseAgent, StorageCapableAgent):
    def __init__(self):
        self.storage_service: StorageServiceProtocol = None
    
    def process(self, inputs):
        # Access any storage type through unified interface
        data = self.storage_service.read("csv", "input.csv")
        result = self.storage_service.write("json", "output.json", processed_data)
```

**Separate Architecture** (when specific types are requested):
```python
class Agent(BaseAgent, CSVCapableAgent, VectorCapableAgent):
    def __init__(self):
        self.csv_service: Any = None  # CSV storage service
        self.vector_service: Any = None  # Vector storage service
    
    def process(self, inputs):
        # Use specific service interfaces
        csv_data = self.csv_service.read("data.csv")
        similar_docs = self.vector_service.search(collection="docs", query="query")
```

### Agent Registry Integration

The scaffolding system integrates with AgentRegistryService to:
- **Avoid conflicts**: Only scaffolds agents that aren't already registered
- **Smart detection**: Checks both built-in and custom agent types
- **Efficient workflow**: Focuses on creating only needed custom agents

```bash
# Example output
$ agentmap scaffold --graph MyWorkflow
✅ Scaffolded 3 agents/functions.
📊 Service integration: 2 with services, 1 basic agents
📁 Created files:
    data_analyzer_agent.py
    report_generator_agent.py
    routing_function.py

# Skipped already registered agents
ℹ️  Skipped 2 built-in agents (InputAgent, OutputAgent)
```

### Advanced Usage Examples

**Multi-Service Agent Scaffolding:**
```bash
# CSV with complex service requirements
GraphName,Node,Context
AIWorkflow,ProcessData,"{""services"": [""llm"", ""vector"", ""storage"", ""memory""]}"

# Generated agent inherits multiple protocols
class ProcessDataAgent(BaseAgent, LLMCapableAgent, VectorCapableAgent, StorageCapableAgent, MemoryCapableAgent):
    # Automatic service integration for all requested services
```

**Custom Output Directories:**
```bash
# Scaffold to custom directories
agentmap scaffold --output ./custom_agents --functions ./custom_functions

# Environment variable override
export AGENTMAP_CUSTOM_AGENTS_PATH="./my_agents"
export AGENTMAP_FUNCTIONS_PATH="./my_functions"
agentmap scaffold
```

**Graph-Specific Scaffolding:**
```bash
# Scaffold only agents for specific graph
agentmap scaffold --graph ProductionWorkflow

# Scaffold with custom CSV
agentmap scaffold --csv ./workflows/special_workflow.csv
```

## Export and Compile Commands

### Export a Graph

```bash
agentmap export -g graph_name -o output.py
```

Options:
- `--graph`, `-g`: Graph name to export
- `--output`, `-o`: Output file path
- `--format`, `-f`: Export format (python, source, debug, documentation)
- `--csv`: CSV path override
- `--state-schema`, `-s`: State schema type (dict, pydantic:ModelName, custom)
- `--config`, `-c`: Path to custom config file

**Supported Export Formats:**
- **python**: Complete executable Python code with imports (production ready)
- **source**: Basic code template for prototyping and scaffolding
- **debug**: Enhanced format with metadata and debugging information
- **documentation**: Generate Markdown or HTML documentation

**Note:** For pickle persistence, use the compile command instead. The export command focuses on human-readable formats.

**Examples:**
```bash
# Export production-ready Python code
agentmap export --graph MyWorkflow --format python --output workflow.py

# Export basic source template
agentmap export --graph MyWorkflow --format source --output template.py

# Export with debug information for development
agentmap export --graph MyWorkflow --format debug --output analysis.py

# Generate workflow documentation
agentmap export --graph MyWorkflow --format documentation --output docs.md

# Export with custom state schema
agentmap export --graph MyWorkflow --format python \
  --state-schema "pydantic:MyStateModel" --output workflow.py
```

For comprehensive export format documentation, see the **[Export Formats Guide](../guides/deployment/export-formats)** and **[Export Reference](../reference/export-reference)**.

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

## Validation Commands

AgentMap provides several commands to validate workflows and configurations. For detailed information, see the [Validation Commands](./08-cli-validation) documentation.

```bash
# Validate CSV workflow files
agentmap validate-csv --csv workflow.csv

# Validate configuration
agentmap validate-config --config custom_config.yaml

# Validate both CSV and configuration
agentmap validate-all

# Manage validation cache
agentmap validate-cache --stats
```

## Diagnostic Commands

Use the diagnose command to check system health and dependencies. For detailed information, see the [Diagnostic Commands](./09-cli-diagnostics) documentation.

```bash
# Check system health
agentmap diagnose
```

## Resume Workflows

Resume interrupted workflows with the resume command. For detailed information, see the [Workflow Resume Commands](./10-cli-resume) documentation.

```bash
# Resume a workflow with approval
agentmap resume thread_12345 approve

# Resume with additional data
agentmap resume thread_12345 respond --data '{"user_response": "Yes, proceed"}'
```

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

# Export for inspection with debug information
agentmap export --graph TestFlow --format debug --output ./debug/
# Expected output:
# ✅ Graph exported to: ./debug/TestFlow_debug.py
# ℹ️  Review the generated code and metadata for debugging

# Export basic source template
agentmap export --graph TestFlow --format source --output ./templates/
# Expected output:
# ✅ Graph exported to: ./templates/TestFlow_source.py
# ℹ️  Use as starting point for custom implementation
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

- **Graph not found**: Verify graph name matches CSV graph_name column
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
# next_nodes: 4
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
- **[Understanding Workflows](/docs/guides/learning/)**: Core workflow concepts and patterns
- **[CSV Schema Reference](reference/csv-schema)**: Complete CSV workflow format specification

### 🔧 **CLI Tools & Debugging**
- **[CLI Graph Inspector](deployment/cli-graph-inspector)**: Advanced graph analysis and debugging
- **[Interactive Playground](../playground)**: Test workflows in your browser
- **[Execution Tracking](/docs/deployment)**: Performance monitoring and debugging

### 🤖 **Agent Development**
- **[Agent Types Reference](reference/agent-types)**: Available agent types and configurations
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
