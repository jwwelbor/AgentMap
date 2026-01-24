# AgentMap Integration API Reference

This document provides comprehensive technical documentation for integrating AgentMap into host applications. It covers the Runtime API, configuration, and complete working examples.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Workflows](#workflows)
- [Runtime API Reference](#runtime-api-reference)
- [Integration Examples](#integration-examples)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

The fastest way to run a workflow from your Python application:

```python
from agentmap import run_workflow

# Run a workflow - initialization happens automatically
result = run_workflow(
    graph_name="hello_world",
    inputs={"name": "Alice"}
)

# Check result
if result["success"]:
    outputs = result["outputs"]
    print(f"Workflow completed: {outputs}")
else:
    print(f"Workflow failed: {result.get('error')}")
```

**Note:** AgentMap initializes automatically on first use. For advanced scenarios (web app startup, custom config, cache refresh), see [agentmap_initialize()](#agentmap_initialize).

---

## Installation

### Install AgentMap as a Dependency

```bash
# Basic installation
pip install agentmap

# With LLM support (OpenAI, Anthropic, Google)
pip install agentmap[llm]

# With storage support (vector databases, Firebase, etc.)
pip install agentmap[storage]

# Full installation with all extras
pip install agentmap[all]
```

### Verify Installation

```python
from agentmap.runtime_api import diagnose_system

# Diagnose system - initialization happens automatically
diagnosis = diagnose_system()

print(f"Status: {diagnosis['outputs']['overall_status']}")
print(f"LLM Providers: {diagnosis['outputs']['features']['llm']['available_providers']}")
print(f"Storage Types: {diagnosis['outputs']['features']['storage']['available_types']}")
```

---

## Configuration

AgentMap requires a configuration file (`agentmap_config.yaml`) in your project root. This file specifies:

- **Workflow locations**: Where to find your CSV workflow files
- **LLM providers**: API keys and model settings (OpenAI, Anthropic, Google)
- **Storage backends**: Data persistence configuration
- **Logging and tracing**: Monitoring and debugging settings

### Quick Configuration Setup

**Minimal `agentmap_config.yaml`:**

```yaml
# Workflow file location
csv_path: "workflows/main.csv"

# Workflow repository directory
paths:
  csv_repository: "workflows"

# LLM provider (required for AI agents)
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-5-sonnet-20241022"
```

### Complete Configuration Documentation

For full configuration options including:
- LLM routing and cost optimization
- Storage backends (CSV, JSON, Vector databases, Firebase)
- Memory management for conversational agents
- Authentication and security settings
- Performance tuning and tracing

**See: [Configuration Documentation](../configuration/)**

Key sections:
- **[Main Configuration](../configuration/main-config)** - Core settings and LLM providers
- **[Storage Configuration](../configuration/storage-config)** - Data persistence setup
- **[Environment Variables](../configuration/environment-variables)** - Secure credential management
- **[Configuration Examples](../configuration/examples)** - Ready-to-use templates

---

## Workflows

### What are Workflows?

In AgentMap, **workflows are defined in CSV files**. Each CSV file can contain one or more workflow graphs that specify:
- The agents (nodes) in your workflow
- How data flows between agents
- What each agent should do

### Workflow Location

Workflows are stored in the directory specified in your configuration:

```yaml
# agentmap_config.yaml
paths:
  csv_repository: "workflows"  # Default location for workflow CSV files
```

**Example workflow structure:**
```
my_app/
├── agentmap_config.yaml
└── workflows/              # Workflow repository
    ├── main_workflow.csv
    ├── data_processing.csv
    └── user_management.csv
```

### Running Workflows

Use workflow names (without the .csv extension) in API calls:

```python
# Runs workflows/data_processing.csv
result = run_workflow("data_processing", inputs={"data": [1, 2, 3]})

# Runs specific graph from a workflow file
result = run_workflow("main_workflow::DataFlow", inputs={...})
```

### Workflow Documentation

For complete information on creating and structuring workflows:

- **[Your First Workflow](../getting-started/first-workflow)** - Step-by-step tutorial
- **[CSV Column Reference](./csv-column-aliases)** - Complete column specification
- **[Agent Catalog](./agent-catalog)** - Available agent types

**Quick CSV Structure:**
```csv
GraphName,Node,AgentType,Edge,Input_Fields,Output_Field,Prompt
MyWorkflow,Start,input,,,"user_input","Enter data:",
MyWorkflow,Process,llm,End,"user_input","result","Process: {user_input}"
MyWorkflow,End,echo,,"result",,"Done: {result}"
```

---

## Runtime API Reference

### Initialization Functions

#### `agentmap_initialize()`

Initialize the AgentMap runtime explicitly. **This is optional** - all workflow functions initialize automatically on first use.

```python
def agentmap_initialize(
    *,
    refresh: bool = False,
    config_file: str | None = None
) -> None
```

**⚠️ When to Use:**
- **Web app startup**: Pre-warm the runtime before handling requests to avoid cold start delays
- **Force cache refresh**: Reload provider availability cache (`refresh=True`)
- **Custom config**: Initialize with a specific config file before using `get_container()`
- **Testing/debugging**: Reset runtime state between tests

**When NOT Needed:**
- Simple scripts or applications - `run_workflow()` and other functions initialize automatically
- If you're just running workflows - initialization happens on first call

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh` | `bool` | `False` | Force re-initialization even if already initialized |
| `config_file` | `str | None` | `None` | Path to configuration file. If None, searches for `agentmap_config.yaml` |

**Raises:**
- `AgentMapNotInitialized`: If initialization fails

**Example:**

```python
from agentmap import agentmap_initialize

# Web app startup - pre-warm the runtime
@app.on_event("startup")
async def startup():
    agentmap_initialize()  # Optional - avoids cold start on first request

# Force cache refresh
agentmap_initialize(refresh=True)

# Custom config file
agentmap_initialize(config_file="/path/to/custom_config.yaml")
```

**Alias:** Also available as `ensure_initialized()` for backward compatibility.

#### `get_container()`

Get the DI container for advanced use cases.

```python
def get_container() -> ApplicationContainer
```

**Returns:** The initialized dependency injection container.

**Raises:**
- `AgentMapNotInitialized`: If runtime not initialized

---

### Workflow Execution Functions

#### `run_workflow()`

Execute a workflow graph with the given inputs.

```python
def run_workflow(
    graph_name: str,
    inputs: Dict[str, Any],
    *,
    profile: Optional[str] = None,
    resume_token: Optional[str] = None,
    config_file: Optional[str] = None,
    force_create: bool = False,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `graph_name` | `str` | *required* | Name or identifier of the graph to run |
| `inputs` | `Dict[str, Any]` | *required* | Initial state/inputs for the workflow |
| `profile` | `str | None` | `None` | Optional profile/environment (dev, stage, prod) |
| `resume_token` | `str | None` | `None` | Resume from checkpoint if provided |
| `config_file` | `str | None` | `None` | Optional configuration file path |
| `force_create` | `bool` | `False` | Force bundle recreation even if cached |

**Returns:**

```python
# Success response
{
    "success": True,
    "outputs": {
        # Final workflow state - all output fields from agents
        "field1": "value1",
        "field2": "value2",
        ...
    },
    "execution_id": "uuid-string",
    "execution_summary": ExecutionSummary,  # Detailed execution tracking
    "metadata": {
        "graph_name": "workflow_name",
        "profile": "dev"
    }
}

# Interrupted response (human interaction required)
{
    "success": False,
    "interrupted": True,
    "thread_id": "thread-uuid",
    "message": "Execution interrupted for human interaction",
    "interaction_request": {...},  # Details about required interaction
    "metadata": {
        "graph_name": "workflow_name",
        "checkpoint_available": True
    }
}
```

**Raises:**
- `GraphNotFound`: If the graph cannot be located
- `InvalidInputs`: If inputs fail validation
- `AgentMapNotInitialized`: If runtime not initialized
- `RuntimeError`: For unexpected execution errors

**Graph Name Syntax:**

The `graph_name` parameter supports multiple formats:

```python
# Simple name - looks for GraphName in csv_repository
run_workflow("HelloWorld", inputs={})

# Workflow::Graph syntax - explicit CSV file and graph name
run_workflow("my_workflow::MainGraph", inputs={})

# Path/Graph syntax - path to CSV with graph name
run_workflow("workflows/advanced::MyGraph", inputs={})
```

**Example:**

```python
from agentmap import run_workflow

# Execute a workflow - initialization happens automatically
result = run_workflow(
    graph_name="DataProcessor",
    inputs={
        "data": [1, 2, 3, 4, 5],
        "operation": "sum"
    }
)

if result["success"]:
    print(f"Result: {result['outputs']['result']}")
    print(f"Execution time: {result['execution_summary'].total_duration}s")
else:
    print(f"Error: {result.get('error')}")
```

#### `resume_workflow()`

Resume a previously interrupted workflow.

```python
def resume_workflow(
    resume_token: str,
    *,
    profile: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resume_token` | `str` | *required* | Token containing thread_id and response data |
| `profile` | `str | None` | `None` | Optional profile/environment |
| `config_file` | `str | None` | `None` | Optional configuration file path |

**Resume Token Format:**

The resume token can be a simple thread_id string or a JSON object:

```python
# Simple thread ID
resume_token = "thread-uuid-string"

# JSON with action and data
resume_token = json.dumps({
    "thread_id": "thread-uuid-string",
    "response_action": "continue",
    "response_data": {"user_input": "approved"}
})
```

**Returns:**

```python
{
    "success": True,
    "outputs": {...},  # Final state after resumption
    "execution_summary": ExecutionSummary,
    "metadata": {
        "thread_id": "thread-uuid",
        "response_action": "continue",
        "graph_name": "workflow_name",
        "duration": 1.23
    }
}
```

**Example:**

```python
import json
from agentmap import ensure_initialized, run_workflow, resume_workflow

ensure_initialized()

# Initial execution that may interrupt
result = run_workflow("ApprovalWorkflow", inputs={"request_id": "123"})

if result.get("interrupted"):
    # Workflow needs human input
    thread_id = result["thread_id"]

    # Get user approval...
    user_approved = True

    # Resume with response
    resume_token = json.dumps({
        "thread_id": thread_id,
        "response_action": "continue",
        "response_data": {"approved": user_approved}
    })

    final_result = resume_workflow(resume_token)
    print(f"Final result: {final_result['outputs']}")
```

---

### Discovery Functions

#### `list_graphs()`

List all available graphs in the configured repository.

```python
def list_graphs(
    *,
    profile: Optional[str] = None,
    config_file: Optional[str] = None
) -> Dict[str, Any]
```

**Returns:**

```python
{
    "success": True,
    "outputs": {
        "graphs": [
            {
                "name": "GraphName",
                "workflow": "workflow_file",
                "filename": "workflow_file.csv",
                "file_path": "/full/path/to/workflow_file.csv",
                "file_size": 1234,
                "last_modified": 1704067200.0,
                "total_nodes": 5,
                "graph_count_in_workflow": 2,
                "meta": {
                    "type": "csv_workflow",
                    "repository_path": "/path/to/workflows",
                    "profile": None
                }
            },
            ...
        ],
        "total_count": 10
    },
    "metadata": {
        "profile": None,
        "repository_path": "/path/to/workflows"
    }
}
```

**Example:**

```python
from agentmap import ensure_initialized, list_graphs

ensure_initialized()

graphs = list_graphs()
print(f"Found {graphs['outputs']['total_count']} graphs:")

for graph in graphs["outputs"]["graphs"]:
    print(f"  - {graph['name']} ({graph['total_nodes']} nodes)")
```

#### `inspect_graph()`

Inspect the structure and configuration of a graph.

```python
def inspect_graph(
    graph_name: str,
    *,
    csv_file: Optional[str] = None,
    node: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `graph_name` | `str` | *required* | Name of the graph to inspect |
| `csv_file` | `str | None` | `None` | Explicit CSV file path |
| `node` | `str | None` | `None` | Inspect specific node only |
| `config_file` | `str | None` | `None` | Optional configuration file path |

**Returns:**

```python
{
    "success": True,
    "outputs": {
        "resolved_name": "GraphName",
        "total_nodes": 5,
        "unique_agent_types": 3,
        "all_resolvable": True,
        "resolution_rate": 1.0,
        "structure": {
            "nodes": [
                {
                    "name": "Start",
                    "agent_type": "input",
                    "description": "Initial input node"
                },
                ...
            ],
            "entry_point": "Start"
        },
        "issues": [],  # List of any issues found
        "required_agents": ["input", "echo", "llm"],
        "required_services": ["llm_service"]
    },
    "metadata": {
        "graph_name": "GraphName",
        "csv_file": "/path/to/workflow.csv",
        "inspected_node": None,
        "csv_hash": "abc123..."
    }
}
```

**Example:**

```python
from agentmap.runtime_api import ensure_initialized, inspect_graph

ensure_initialized()

# Inspect entire graph
info = inspect_graph("DataProcessor")
print(f"Nodes: {info['outputs']['total_nodes']}")
print(f"Entry point: {info['outputs']['structure']['entry_point']}")

# Check for issues
if info["outputs"]["issues"]:
    print("Issues found:")
    for issue in info["outputs"]["issues"]:
        print(f"  - {issue}")
```

#### `validate_workflow()`

Validate a workflow's CSV structure and agent declarations.

```python
def validate_workflow(
    graph_name: str,
    *,
    config_file: Optional[str] = None,
) -> Dict[str, Any]
```

**Returns:**

```python
{
    "success": True,
    "outputs": {
        "csv_structure_valid": True,
        "total_nodes": 5,
        "total_edges": 4,
        "missing_declarations": [],  # List of undefined agent types
        "all_agents_defined": True
    },
    "metadata": {
        "graph_name": "GraphName",
        "bundle_name": "GraphName",
        "csv_path": "/path/to/workflow.csv"
    }
}
```

---

### System Functions

#### `diagnose_system()`

Get comprehensive diagnostic information about the AgentMap installation.

```python
def diagnose_system(
    *,
    config_file: Optional[str] = None
) -> Dict[str, Any]
```

**Returns:**

```python
{
    "success": True,
    "outputs": {
        "overall_status": "fully_operational",  # or "llm_only", "storage_only", "limited_functionality"
        "features": {
            "llm": {
                "enabled": True,
                "available_providers": ["anthropic", "openai"],
                "provider_details": {
                    "anthropic": {
                        "status": "available",
                        "available": True,
                        "has_dependencies": True,
                        "missing_dependencies": []
                    },
                    ...
                }
            },
            "storage": {
                "enabled": True,
                "available_types": ["csv", "json", "file"],
                "storage_details": {...}
            }
        },
        "suggestions": [
            "For vector storage: pip install chromadb"
        ],
        "environment": {
            "python_version": "3.11.0",
            "python_path": "/path/to/python",
            "current_directory": "/path/to/project",
            "package_versions": {
                "OpenAI SDK": "v1.0.0",
                "Anthropic SDK": "v0.7.0",
                ...
            }
        }
    },
    "metadata": {
        "llm_ready": True,
        "storage_ready": True
    }
}
```

#### `get_config()`

Get the current configuration values.

```python
def get_config(
    *,
    config_file: Optional[str] = None
) -> Dict[str, Any]
```

**Returns:**

```python
{
    "success": True,
    "outputs": {
        # Complete configuration dictionary
        "csv_path": "workflows/main.csv",
        "paths": {...},
        "logging": {...},
        "llm": {...},
        ...
    },
    "metadata": {
        "config_file": "/path/to/config.yaml"
    }
}
```

#### `refresh_cache()`

Refresh the provider availability cache.

```python
def refresh_cache(
    *,
    force: bool = False,
    llm_only: bool = False,
    storage_only: bool = False,
    config_file: Optional[str] = None,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | `bool` | `False` | Force refresh even if cache exists |
| `llm_only` | `bool` | `False` | Only refresh LLM providers |
| `storage_only` | `bool` | `False` | Only refresh storage providers |

---

### Bundle Management Functions

#### `update_bundle()`

Update an existing workflow bundle with current agent mappings.

```python
def update_bundle(
    graph_name: str,
    *,
    config_file: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]
```

#### `scaffold_agents()`

Generate boilerplate code for custom agents in a workflow.

```python
def scaffold_agents(
    graph_name: str,
    *,
    output_dir: Optional[str] = None,
    func_dir: Optional[str] = None,
    config_file: Optional[str] = None,
    overwrite: bool = False,
    force: bool = False,
) -> Dict[str, Any]
```

---

## Integration Examples

### Example 1: Basic Workflow Execution

```python
"""
Basic workflow execution example.
Initialization happens automatically - no setup required!
"""
from agentmap import run_workflow, list_graphs

def main():
    # List available workflows (auto-initializes on first call)
    available = list_graphs()
    print(f"Available graphs: {[g['name'] for g in available['outputs']['graphs']]}")

    # Run a simple workflow
    result = run_workflow(
        graph_name="HelloWorld",
        inputs={"name": "World"}
    )

    if result["success"]:
        print(f"Success! Output: {result['outputs']}")
    else:
        print(f"Failed: {result.get('error')}")

if __name__ == "__main__":
    main()
```

### Example 2: Passing State and Accessing Results

```python
"""
Demonstrating state passing and result extraction.
"""
from typing import Dict, Any
from agentmap import run_workflow

def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process data through an AgentMap workflow."""

    # Pass complex initial state
    initial_state = {
        "raw_data": data,
        "processing_options": {
            "validate": True,
            "transform": True,
            "output_format": "json"
        },
        "metadata": {
            "source": "api",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }

    result = run_workflow(
        graph_name="DataProcessor",
        inputs=initial_state
    )

    if not result["success"]:
        raise RuntimeError(f"Processing failed: {result.get('error')}")

    # Extract specific outputs
    outputs = result["outputs"]

    return {
        "processed_data": outputs.get("processed_data"),
        "validation_result": outputs.get("validation_result"),
        "summary": outputs.get("summary"),
        "execution_time": result.get("execution_summary", {}).get("total_duration")
    }

# Usage
if __name__ == "__main__":
    input_data = {
        "items": [
            {"id": 1, "value": 100},
            {"id": 2, "value": 200}
        ]
    }

    result = process_data(input_data)
    print(f"Processed: {result}")
```

### Example 3: Error Handling Patterns

```python
"""
Comprehensive error handling for AgentMap workflows.
"""
from agentmap import (
    run_workflow,
    AgentMapError,
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs
)

def execute_workflow_safely(graph_name: str, inputs: dict) -> dict:
    """Execute a workflow with comprehensive error handling."""

    try:
        # Run workflow - initialization happens automatically
        result = run_workflow(graph_name=graph_name, inputs=inputs)

        # Handle interrupted workflows (human interaction needed)
        if result.get("interrupted"):
            return {
                "success": False,
                "error_type": "workflow_interrupted",
                "thread_id": result.get("thread_id"),
                "message": result.get("message"),
                "action": "Use resume_workflow() with user response"
            }

        return result

    except GraphNotFound as e:
        return {
            "success": False,
            "error_type": "graph_not_found",
            "graph_name": e.graph_name,
            "message": str(e),
            "action": "Check graph name and CSV file location"
        }

    except InvalidInputs as e:
        return {
            "success": False,
            "error_type": "invalid_inputs",
            "reason": e.reason,
            "message": str(e),
            "action": "Validate input data against workflow requirements"
        }

    except AgentMapError as e:
        return {
            "success": False,
            "error_type": "agentmap_error",
            "message": str(e),
            "action": "Check logs for detailed error information"
        }

    except Exception as e:
        return {
            "success": False,
            "error_type": "unexpected_error",
            "message": str(e),
            "action": "Review error details and check system logs"
        }

# Usage with retry logic
def execute_with_retry(graph_name: str, inputs: dict, max_retries: int = 3):
    """Execute workflow with retry logic for transient failures."""
    import time

    for attempt in range(max_retries):
        result = execute_workflow_safely(graph_name, inputs)

        if result["success"]:
            return result

        # Don't retry certain error types
        non_retryable = ["graph_not_found", "invalid_inputs", "workflow_interrupted"]
        if result.get("error_type") in non_retryable:
            return result

        # Exponential backoff for retryable errors
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            time.sleep(wait_time)

    return result

if __name__ == "__main__":
    result = execute_with_retry("DataProcessor", {"data": [1, 2, 3]})
    print(f"Result: {result}")
```

### Example 4: Advanced Configuration with Custom Config

```python
"""
Advanced configuration scenarios.
"""
import os
from pathlib import Path
from agentmap import agentmap_initialize, run_workflow
from agentmap.runtime_api import get_config, diagnose_system

def setup_environment(env: str = "development"):
    """Configure AgentMap for different environments."""

    # Environment-specific config files
    config_map = {
        "development": "config/agentmap_dev.yaml",
        "staging": "config/agentmap_staging.yaml",
        "production": "config/agentmap_prod.yaml"
    }

    config_file = config_map.get(env, config_map["development"])

    # Verify config exists
    if not Path(config_file).exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    # Pre-initialize with environment-specific config
    # This is optional but useful for startup validation
    agentmap_initialize(config_file=config_file, refresh=True)

    # Verify setup
    diagnosis = diagnose_system(config_file=config_file)

    if diagnosis["outputs"]["overall_status"] == "limited_functionality":
        print("Warning: Running with limited functionality")
        print(f"Suggestions: {diagnosis['outputs']['suggestions']}")

    return diagnosis

def run_with_profile(graph_name: str, inputs: dict, profile: str = None):
    """Run workflow with profile-specific settings."""

    # Profile can be used for workflow-specific configuration
    result = run_workflow(
        graph_name=graph_name,
        inputs=inputs,
        profile=profile
    )

    return result

class AgentMapClient:
    """Reusable client for AgentMap workflows."""

    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self._prewarmed = False

    def prewarm(self, force: bool = False):
        """
        Optional: Pre-warm the runtime (useful for web apps).
        AgentMap initializes automatically, but this avoids first-request latency.
        """
        if self._prewarmed and not force:
            return

        agentmap_initialize(
            config_file=self.config_file,
            refresh=force
        )
        self._prewarmed = True

    def run(self, graph_name: str, inputs: dict, **kwargs) -> dict:
        """Run a workflow (auto-initializes if needed)."""
        return run_workflow(
            graph_name,
            inputs,
            config_file=self.config_file,
            **kwargs
        )

    def get_status(self) -> dict:
        """Get system status (auto-initializes if needed)."""
        return diagnose_system(config_file=self.config_file)

    def get_config(self) -> dict:
        """Get current configuration (auto-initializes if needed)."""
        return get_config(config_file=self.config_file)

# Usage
if __name__ == "__main__":
    # Environment-based setup
    env = os.getenv("APP_ENV", "development")
    setup_environment(env)

    # Using the client
    client = AgentMapClient(config_file="config/agentmap_prod.yaml")

    # Check status
    status = client.get_status()
    print(f"System status: {status['outputs']['overall_status']}")

    # Run workflow
    result = client.run("DataProcessor", {"data": [1, 2, 3]})
    print(f"Result: {result}")
```

### Example 5: FastAPI Integration

```python
"""
FastAPI integration example.
"""
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import json

from agentmap import (
    agentmap_initialize,
    run_workflow,
    resume_workflow,
    list_graphs,
    GraphNotFound,
    InvalidInputs
)
from agentmap.runtime_api import inspect_graph, diagnose_system

app = FastAPI(title="AgentMap API")

class WorkflowRequest(BaseModel):
    graph_name: str
    inputs: Dict[str, Any] = {}
    profile: Optional[str] = None

class ResumeRequest(BaseModel):
    thread_id: str
    response_action: str = "continue"
    response_data: Optional[Dict[str, Any]] = None

@app.on_event("startup")
async def startup_event():
    """
    Optional: Pre-warm AgentMap runtime on startup.
    This avoids cold-start latency on first request.
    If omitted, AgentMap initializes automatically on first API call.
    """
    agentmap_initialize()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    diagnosis = diagnose_system()
    return {
        "status": "healthy",
        "agentmap_status": diagnosis["outputs"]["overall_status"],
        "llm_ready": diagnosis["metadata"]["llm_ready"],
        "storage_ready": diagnosis["metadata"]["storage_ready"]
    }

@app.get("/workflows")
async def get_workflows():
    """List available workflows."""
    result = list_graphs()
    return result

@app.get("/workflows/{graph_name}")
async def get_workflow_info(graph_name: str):
    """Get workflow details."""
    try:
        result = inspect_graph(graph_name)
        return result
    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/workflows/execute")
async def execute_workflow(request: WorkflowRequest):
    """Execute a workflow."""
    try:
        result = run_workflow(
            graph_name=request.graph_name,
            inputs=request.inputs,
            profile=request.profile
        )

        if result.get("interrupted"):
            return {
                "status": "interrupted",
                "thread_id": result["thread_id"],
                "message": result["message"],
                "resume_endpoint": f"/workflows/resume"
            }

        return result

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflows/resume")
async def resume_workflow_endpoint(request: ResumeRequest):
    """Resume an interrupted workflow."""
    try:
        resume_token = json.dumps({
            "thread_id": request.thread_id,
            "response_action": request.response_action,
            "response_data": request.response_data
        })

        result = resume_workflow(resume_token)
        return result

    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload
```

---

---

## Error Handling

### Exception Types

AgentMap provides specific exception types for different error conditions:

```python
from agentmap import (
    AgentMapError,           # Base exception for all AgentMap errors
    AgentMapNotInitialized,  # Runtime not initialized
    GraphNotFound,           # Graph/workflow not found
    InvalidInputs            # Input validation failed
)
```

### Exception Details

#### `AgentMapNotInitialized`

Raised when initialization fails (e.g., missing config file, invalid configuration).

**Note:** This is NOT raised for missing `agentmap_initialize()` - workflows initialize automatically. This exception indicates an initialization *failure*, not missing initialization.

```python
from agentmap import agentmap_initialize, AgentMapNotInitialized

try:
    # Force initialization with specific config
    agentmap_initialize(config_file="missing_config.yaml")
except AgentMapNotInitialized as e:
    # Initialization failed - config file not found or invalid
    print(f"Initialization failed: {e}")
```

#### `GraphNotFound`

Raised when a requested graph cannot be located.

```python
try:
    run_workflow("nonexistent_graph", {})
except GraphNotFound as e:
    # e.graph_name - the graph that wasn't found
    print(f"Graph '{e.graph_name}' not found")
```

#### `InvalidInputs`

Raised when provided inputs fail validation.

```python
try:
    run_workflow("test", {"invalid": "data"})
except InvalidInputs as e:
    # e.reason - why validation failed
    print(f"Invalid inputs: {e.reason}")
```

---

## Troubleshooting

### Common Issues

#### 1. "AgentMap initialization failed"

**Cause:** Missing configuration file, invalid YAML, or missing required settings.

**Solution:**
```python
from agentmap import agentmap_initialize, AgentMapNotInitialized

try:
    agentmap_initialize()
except AgentMapNotInitialized as e:
    print(f"Check your agentmap_config.yaml: {e}")
```

**Note:** You typically don't need to call `agentmap_initialize()` - workflows initialize automatically. This error usually means your config file has an issue.

#### 2. "Graph not found"

**Cause:** The workflow CSV file doesn't exist or the graph name is incorrect.

**Solution:**
1. Check that the CSV file exists in the configured `csv_repository` path
2. Verify the graph name matches the `GraphName` column in the CSV
3. Use `list_graphs()` to see available graphs

```python
from agentmap import list_graphs
graphs = list_graphs()
print([g['name'] for g in graphs['outputs']['graphs']])
```

#### 3. "Configuration not loaded"

**Cause:** The configuration file is missing or malformed.

**Solution:**
1. Ensure `agentmap_config.yaml` exists in the project root
2. Or specify the config path in API calls:

```python
run_workflow("my_graph", inputs={}, config_file="/path/to/config.yaml")
```

3. Or pre-initialize with custom config:

```python
from agentmap import agentmap_initialize
agentmap_initialize(config_file="/path/to/config.yaml")
```

#### 4. LLM providers not available

**Cause:** Missing dependencies or API keys.

**Solution:**
1. Install required packages:
```bash
pip install agentmap[llm]
```

2. Set environment variables:
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
```

3. Check with diagnostics:
```python
from agentmap.runtime_api import diagnose_system
diagnosis = diagnose_system()
print(diagnosis['outputs']['suggestions'])
```

#### 5. Workflow hangs or times out

**Cause:** Agent execution taking too long or infinite loops.

**Solution:**
1. Check for cycles in your workflow graph
2. Use `inspect_graph()` to verify structure
3. Enable detailed logging:

```yaml
# In agentmap_config.yaml
logging:
  loggers:
    agentmap:
      level: DEBUG
```

### Diagnostic Commands

```python
from agentmap.runtime_api import (
    diagnose_system,
    get_config,
    validate_workflow,
    inspect_graph
)

# Full system diagnosis (auto-initializes)
diagnosis = diagnose_system()
print(f"Status: {diagnosis['outputs']['overall_status']}")
print(f"Suggestions: {diagnosis['outputs']['suggestions']}")

# Check configuration
config = get_config()
print(f"CSV Repository: {config['outputs'].get('paths', {}).get('csv_repository')}")

# Validate a specific workflow
validation = validate_workflow("MyWorkflow")
print(f"Valid: {validation['outputs']['csv_structure_valid']}")
print(f"Missing agents: {validation['outputs']['missing_declarations']}")

# Inspect workflow structure
info = inspect_graph("MyWorkflow")
print(f"Nodes: {[n['name'] for n in info['outputs']['structure']['nodes']]}")
```

---

## API Response Format

All Runtime API functions return a consistent response structure:

```python
{
    "success": bool,           # Whether the operation succeeded
    "outputs": {...},          # Operation-specific output data
    "metadata": {...},         # Additional metadata about the operation
    "error": str | None,       # Error message if success=False
    "execution_summary": {...} # Detailed execution info (for workflows)
}
```

This format makes it easy to handle responses uniformly across different operations:

```python
def handle_response(result: dict):
    if result["success"]:
        return result["outputs"]
    else:
        error = result.get("error", "Unknown error")
        raise RuntimeError(f"Operation failed: {error}")
```

---

## Version Information

- **API Version:** 2.0
- **Documentation Date:** 2025-01-23

For the latest updates, visit the [AgentMap GitHub repository](https://github.com/jwwelbor/agentmap).
