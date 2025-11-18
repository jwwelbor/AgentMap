# AgentMap

Build and deploy LangGraph agentic workflows from CSV files.

AgentMap is a declarative orchestration framework that transforms simple CSV files into powerful AI agent workflows. Instead of writing hundreds of lines of boilerplate code for multi-agent systems, you define entire workflows in a spreadsheet format.

## Why AgentMap?

- **Declarative Workflows**: Define complex multi-agent workflows in readable CSV format
- **Rapid Prototyping**: Iterate quickly without recompiling or redeploying
- **Multiple LLM Providers**: Built-in support for OpenAI, Anthropic Claude, and Google Gemini
- **Flexible Deployment**: Run from CLI, embed in Python code, or serve via FastAPI
- **Production Ready**: Includes execution tracking, memory management, and intelligent LLM routing

## Installation

```bash
# Basic installation
pip install agentmap

# With LLM support (OpenAI, Anthropic, Google)
pip install agentmap[llm]

# With storage support (Firebase, Chroma, document processing)
pip install agentmap[storage]

# Everything included
pip install agentmap[all]
```

**Requirements**: Python 3.11+

## Quick Start

### 1. Initialize Configuration

```bash
agentmap init-config
```

This creates three files in your current directory:

| File | Purpose |
|------|---------|
| `agentmap_config.yaml` | Main configuration (LLM providers, paths, memory, tracing) |
| `agentmap_config_storage.yaml` | Storage configuration (CSV, JSON, vector DBs, cloud storage) |
| `hello_world.csv` | Sample workflow to get started |

### 2. Configure Your LLM Provider

Edit `agentmap_config.yaml` and add your API key:

```yaml
llm:
  openai:
    api_key: "your-openai-key"  # Or use env var: OPENAI_API_KEY
    model: "gpt-4o-mini-2024-07-18"

  anthropic:
    api_key: "your-anthropic-key"  # Or use env var: ANTHROPIC_API_KEY
    model: "claude-3-5-sonnet-20241022"

  google:
    api_key: "your-google-key"  # Or use env var: GOOGLE_API_KEY
    model: "gemini-1.5-flash"
```

You can also set API keys via environment variables:

```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
```

### 3. Run a Sample Workflow

```bash
# Run the hello world example
agentmap run hello_world.csv

# With formatted output
agentmap run hello_world.csv --pretty

# With initial state
agentmap run hello_world.csv --state '{"name": "Alice"}' --pretty
```

## Configuration Reference

### Main Configuration (`agentmap_config.yaml`)

| Section | Purpose |
|---------|---------|
| `paths` | Directory locations for agents, functions, and workflows |
| `llm` | LLM provider settings (API keys, models, parameters) |
| `memory` | Conversation memory settings |
| `execution` | Tracking and success policies |
| `tracing` | Execution tracing (local or LangSmith) |
| `routing` | Intelligent LLM routing configuration |
| `logging` | Log levels and output configuration |

**Path Configuration:**

```yaml
paths:
  custom_agents: "agentmap_data/custom_agents"
  functions: "agentmap_data/custom_functions"
  csv_repository: "agentmap_data/workflows"
```

**Memory Configuration:**

```yaml
memory:
  enabled: true
  default_type: "buffer_window"  # buffer, buffer_window, summary, token_buffer
  buffer_window_size: 5
  max_token_limit: 2000
```

### Storage Configuration (`agentmap_config_storage.yaml`)

```yaml
core:
  base_directory: "agentmap_data/data"

csv:
  enabled: true
  auto_create_files: true
  collections:
    users: "csv/users.csv"
    products: "csv/products.csv"

json:
  enabled: true
  auto_create_files: true
```

## Workflow CSV Format

Workflows are defined in CSV files with these columns:

| Column | Description |
|--------|-------------|
| `graph_name` | Identifies the workflow graph |
| `node_name` | Unique node identifier |
| `agent_type` | Type of agent (input, echo, openai, claude, etc.) |
| `next_node` | Next node on success |
| `on_failure` | Next node on failure |
| `prompt` | Instruction or message for the agent |
| `input_fields` | Fields consumed from state (pipe-separated) |
| `output_field` | Field name for storing output |

**Example (`hello_world.csv`):**

```csv
graph_name,node_name,agent_type,next_node,on_failure,prompt,input_fields,output_field
HelloWorld,Start,input,PrintResult,HandleError,"Hello world! What is your name? ",,name
HelloWorld,PrintResult,echo,,,"Hello {name}. Welcome to AgentMap!",name,result
HelloWorld,HandleError,echo,,,Error occurred
```

## CLI Commands

### Workflow Execution

```bash
# Run a workflow
agentmap run <workflow.csv>
agentmap run workflow.csv --state '{"input": "value"}' --pretty --verbose

# Resume a suspended workflow
agentmap resume <thread_id> <action> --data '{"key": "value"}'
```

### Configuration & Setup

```bash
# Initialize configuration files
agentmap init-config
agentmap init-config --force  # Overwrite existing

# Check system dependencies
agentmap diagnose

# Refresh provider cache
agentmap refresh --force
```

### Validation & Scaffolding

```bash
# Validate CSV structure
agentmap validate workflow.csv

# Generate agent templates
agentmap scaffold workflow.csv --output agents/ --overwrite
```

### HTTP Server

```bash
# Start the API server
agentmap serve --host 0.0.0.0 --port 8000

# With auto-reload for development
agentmap serve --port 8000 --reload
```

API documentation available at `http://localhost:8000/docs`

## Interfaces

AgentMap provides three ways to execute workflows:

### 1. Command Line Interface

Best for quick testing and scripting:

```bash
agentmap run my_workflow.csv --state '{"user_id": 123}' --pretty
```

### 2. Python API

Best for embedding in applications:

```python
from agentmap import ensure_initialized, run_workflow

# Initialize once at startup
ensure_initialized()

# Execute a workflow
result = run_workflow(
    graph_name="my_workflow::MyGraph",
    inputs={"user_message": "Hello"},
    config_file="agentmap_config.yaml"
)

if result.get("success"):
    print(result.get("outputs"))
```

**Available Functions:**

```python
from agentmap import (
    ensure_initialized,   # Initialize the runtime
    run_workflow,         # Execute a workflow
    resume_workflow,      # Resume suspended execution
    list_graphs,          # List available workflows
    inspect_graph,        # Get graph structure
    validate_workflow,    # Validate CSV
)
```

### 3. FastAPI HTTP Server

Best for microservices and REST APIs:

**Start the Server:**

```bash
agentmap serve --host 0.0.0.0 --port 8000
```

**Execute via HTTP:**

```bash
# Execute a workflow
curl -X POST http://localhost:8000/execute/my_workflow/MyGraph \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"message": "Hello"}}'

# List workflows
curl http://localhost:8000/workflows

# Resume suspended execution
curl -X POST http://localhost:8000/resume/<thread_id> \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "data": {}}'
```

**Embed in Existing FastAPI App:**

```python
from fastapi import FastAPI
from agentmap.deployment.http.api.server import create_sub_application

app = FastAPI(title="My Application")

# Mount AgentMap routes
agentmap_app = create_sub_application(
    config_file="agentmap_config.yaml",
    prefix="/agentmap"
)
app.mount("/agentmap", agentmap_app)

# AgentMap endpoints now at /agentmap/execute, /agentmap/workflows, etc.
```

## Built-in Agent Types

AgentMap includes 20+ agent types:

| Category | Agents |
|----------|--------|
| **Core** | `default`, `echo`, `input`, `branching`, `success`, `failure` |
| **LLM** | `openai`, `claude`, `gemini` |
| **Storage** | `csv_reader`, `csv_writer`, `json_reader`, `json_writer`, `file_reader`, `file_writer` |
| **Advanced** | `orchestrator`, `summary`, `tool`, `graph` (sub-workflows), `suspend` |

## Example: LLM Chatbot

```csv
graph_name,node_name,agent_type,input_fields,output_field,next_node,prompt
ChatBot,GetInput,input,,user_input,Respond,"How can I help you?"
ChatBot,Respond,openai,user_input|chat_memory,response,GetInput,"You are a helpful assistant. User says: {user_input}"
```

Run it:

```bash
agentmap run chatbot.csv --pretty
```

## Example: Conditional Workflow

```csv
graph_name,node_name,agent_type,input_fields,output_field,next_node,on_failure,prompt
ReviewFlow,Start,input,,request,Classify,,"Enter your request:"
ReviewFlow,Classify,branching,request,decision,Approve,Reject,
ReviewFlow,Approve,default,request,result,,,"Request approved: {request}"
ReviewFlow,Reject,default,request,result,,,"Request rejected: {request}"
```

## Useful Commands

```bash
# Check version
agentmap --version

# Get help
agentmap --help
agentmap run --help

# Diagnose system
agentmap diagnose

# Initialize API keys
agentmap auth init --config agentmap_config.yaml
```

## Project Links

- **Documentation**: https://jwwelbor.github.io/AgentMap
- **Repository**: https://github.com/jwwelbor/AgentMap
- **Issue Tracker**: https://github.com/jwwelbor/AgentMap/issues
- **Changelog**: https://github.com/jwwelbor/AgentMap/blob/main/CHANGELOG.md

## License

This project is licensed under the MIT License.
