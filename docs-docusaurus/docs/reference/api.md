---
sidebar_position: 1
title: AgentMap API Reference
description: API reference for AgentMap framework including CLI tools and production-ready FastAPI server for host applications.
keywords: [AgentMap API, CLI API, FastAPI integration, host application integration, AgentMap documentation]
---

# AgentMap API Reference

API documentation for AgentMap framework. AgentMap provides both a comprehensive CLI interface and a production-ready FastAPI server for workflow management and host application integration.

## 🛠️ Current API Surface

### Command Line Interface
AgentMap's primary API is through the CLI, which provides complete workflow management capabilities:

- **Workflow Execution**: Run workflows from CSV definitions
- **Validation**: Validate workflow structure and dependencies  
- **Graph Inspection**: Analyze and debug workflow graphs
- **Code Generation**: Scaffold custom agents and project templates
- **Testing Tools**: Validate and benchmark workflows

**Complete CLI Reference**: [CLI Commands Documentation](/docs/deployment/04-cli-commands)

### Python Integration
For Python applications, AgentMap can be integrated programmatically:

```python
# Basic workflow execution
from agentmap import AgentMap

agent_map = AgentMap()
result = agent_map.run_workflow(
    csv_path="workflow.csv",
    graph_name="MyWorkflow",
    initial_state={"input": "Hello world"}
)
```

## Python Runtime API (runtime_api.py)

AgentMap provides a stable, production-ready Python API for programmatic workflow execution. This API is the foundation for all AgentMap integration points including the CLI, FastAPI server, and custom applications.

### Installation

The runtime API is included with the base AgentMap installation:

```bash
pip install agentmap
```

### Quick Start

```python
from agentmap import runtime_api

# Initialize the runtime
runtime_api.ensure_initialized()

# Run a workflow
result = runtime_api.run_workflow(
    graph_name="customer_support",
    inputs={"customer_message": "I need help with my order"}
)

# Check results
if result["success"]:
    print(f"Result: {result['outputs']}")
else:
    print(f"Error: {result.get('error')}")
```

---

### Initialization Functions

#### `ensure_initialized()`

Initialize the AgentMap runtime environment. This must be called before using any other runtime API functions.

**Parameters:**
- `refresh` (bool, optional): Force recreation of provider cache. Default: `False`
- `config_file` (str, optional): Path to custom configuration file. Default: `None` (uses default config)

**Returns:** None

**Raises:**
- `AgentMapNotInitialized`: If initialization fails

**When to use:**
- At application startup before any workflow operations
- After configuration changes to refresh the runtime
- When you need to force cache refresh

**Example:**

```python
from agentmap import runtime_api

# Basic initialization
runtime_api.ensure_initialized()

# Initialize with custom config
runtime_api.ensure_initialized(config_file="./config/production.yaml")

# Force refresh of provider cache
runtime_api.ensure_initialized(refresh=True)
```

#### `get_container()`

Get the dependency injection container for advanced use cases.

**Parameters:** None

**Returns:** Container instance with all registered services

**When to use:**
- Advanced scenarios requiring direct service access
- Custom extension development
- Testing and debugging

**Example:**

```python
from agentmap import runtime_api

# Get container after initialization
runtime_api.ensure_initialized()
container = runtime_api.get_container()

# Access specific services
logging_service = container.logging_service()
app_config = container.app_config_service()
```

---

### Workflow Operations

#### `run_workflow()`

Execute a workflow graph with the given inputs.

**Parameters:**
- `graph_name` (str, required): Name or identifier of the graph to run. Supports multiple syntaxes:
  - Simple name: `"customer_support"` (looks for `customer_support.csv` in repository)
  - Workflow::Graph: `"workflows::CustomerSupport"` (explicit graph in CSV)
  - Workflow/Graph: `"workflows/CustomerSupport"` (alternate syntax)
- `inputs` (Dict[str, Any], required): Input values for the workflow
- `profile` (str, optional): Environment profile (e.g., "dev", "prod"). Default: `None`
- `resume_token` (str, optional): Token to resume from checkpoint. Default: `None`
- `config_file` (str, optional): Path to configuration file. Default: `None`
- `force_create` (bool, optional): Force bundle recreation. Default: `False`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        # Workflow output data
    },
    "execution_id": "exec-uuid-12345",
    "execution_summary": {
        "total_nodes": 5,
        "duration": 2.34,
        # ... execution statistics
    },
    "metadata": {
        "graph_name": "customer_support",
        "profile": "production"
    }
}
```

For interrupted workflows (suspend/human interaction):

```python
{
    "success": False,
    "interrupted": True,
    "thread_id": "thread-uuid-12345",
    "interaction_request": {
        "type": "approval",
        "prompt": "Approve this action?",
        # ... interaction details
    },
    "message": "Execution interrupted for human interaction",
    "metadata": {
        "checkpoint_available": True,
        "interrupt_type": "approval"
    }
}
```

**Raises:**
- `GraphNotFound`: If the graph cannot be located
- `InvalidInputs`: If inputs fail validation
- `AgentMapNotInitialized`: If runtime not initialized

**When to use:**
- Primary method for executing workflows
- Automating business processes
- Building AI-powered applications
- Serverless function handlers

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Simple workflow execution
result = runtime_api.run_workflow(
    graph_name="email_classifier",
    inputs={"email_text": "Hello, I need support..."}
)

if result["success"]:
    classification = result["outputs"]["category"]
    print(f"Email classified as: {classification}")

# Workflow with explicit CSV file
result = runtime_api.run_workflow(
    graph_name="workflows::DataPipeline",
    inputs={"data_source": "s3://bucket/data.csv"},
    profile="production",
    config_file="./config/prod.yaml"
)

# Handle interrupted workflows
result = runtime_api.run_workflow(
    graph_name="approval_workflow",
    inputs={"request": "Deploy to production"}
)

if result.get("interrupted"):
    print(f"Workflow paused: {result['message']}")
    print(f"Thread ID: {result['thread_id']}")
    # Store thread_id for later resume
    save_for_later(result["thread_id"])
```

#### `resume_workflow()`

Resume a previously interrupted workflow with user response.

**Parameters:**
- `resume_token` (str, required): Token from interrupted workflow. Can be:
  - Simple thread ID string: `"thread-uuid-12345"`
  - JSON token with action: `'{"thread_id": "...", "response_action": "approve", "response_data": {...}}'`
- `profile` (str, optional): Environment profile. Default: `None`
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        # Final workflow outputs
    },
    "execution_summary": {
        # Execution statistics
    },
    "metadata": {
        "thread_id": "thread-uuid-12345",
        "response_action": "approve",
        "graph_name": "approval_workflow",
        "duration": 1.23
    }
}
```

**When to use:**
- Resuming workflows after human approval
- Continuing suspended workflows
- Handling asynchronous user interactions

**Examples:**

```python
from agentmap import runtime_api
import json

runtime_api.ensure_initialized()

# Simple resume with thread ID
result = runtime_api.resume_workflow(
    resume_token="thread-uuid-12345"
)

# Resume with explicit action
token = json.dumps({
    "thread_id": "thread-uuid-12345",
    "response_action": "approve",
    "response_data": {"decision": "approved", "notes": "Looks good"}
})

result = runtime_api.resume_workflow(resume_token=token)

if result["success"]:
    print(f"Workflow completed: {result['outputs']}")
else:
    print(f"Resume failed: {result['error']}")
```

#### `list_graphs()`

List all available workflow graphs in the configured repository.

**Parameters:**
- `profile` (str, optional): Environment profile. Default: `None`
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "graphs": [
            {
                "name": "CustomerSupport",
                "workflow": "customer_support",
                "filename": "customer_support.csv",
                "file_path": "/path/to/customer_support.csv",
                "total_nodes": 12,
                "graph_count_in_workflow": 2,
                "last_modified": 1234567890.0
            },
            # ... more graphs
        ],
        "total_count": 15
    },
    "metadata": {
        "repository_path": "/path/to/workflows"
    }
}
```

**When to use:**
- Discovering available workflows
- Building workflow selection UIs
- Monitoring workflow repositories
- API gateway implementations

**Example:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# List all available workflows
result = runtime_api.list_graphs()

if result["success"]:
    graphs = result["outputs"]["graphs"]
    print(f"Found {result['outputs']['total_count']} graphs:")

    for graph in graphs:
        print(f"  - {graph['name']}: {graph['total_nodes']} nodes")
```

#### `inspect_graph()`

Get detailed information about a specific workflow graph including structure and dependencies.

**Parameters:**
- `graph_name` (str, required): Name of the graph to inspect
- `csv_file` (str, optional): Path to specific CSV file. Default: `None`
- `node` (str, optional): Inspect specific node only. Default: `None` (all nodes)
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "resolved_name": "CustomerSupport",
        "total_nodes": 8,
        "unique_agent_types": 4,
        "all_resolvable": True,
        "resolution_rate": 1.0,
        "structure": {
            "nodes": [
                {
                    "name": "Start",
                    "agent_type": "input",
                    "description": "Get customer message"
                },
                # ... more nodes
            ],
            "entry_point": "Start"
        },
        "required_agents": ["input", "openai", "echo"],
        "required_services": ["llm"],
        "issues": []
    },
    "metadata": {
        "graph_name": "CustomerSupport",
        "csv_file": "/path/to/workflow.csv"
    }
}
```

**When to use:**
- Debugging workflow structure
- Validating agent dependencies
- Building workflow visualization tools
- Pre-execution validation

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Inspect entire graph
result = runtime_api.inspect_graph("customer_support")

if result["success"]:
    outputs = result["outputs"]
    print(f"Graph: {outputs['resolved_name']}")
    print(f"Nodes: {outputs['total_nodes']}")
    print(f"Agent types: {outputs['required_agents']}")

    if outputs["issues"]:
        print(f"Issues found: {outputs['issues']}")

# Inspect specific node
result = runtime_api.inspect_graph(
    graph_name="customer_support",
    node="ClassifyIntent"
)

# Inspect graph in specific CSV
result = runtime_api.inspect_graph(
    graph_name="DataPipeline",
    csv_file="./workflows/etl.csv"
)
```

#### `validate_workflow()`

Validate a workflow's CSV structure and agent configuration.

**Parameters:**
- `graph_name` (str, required): Name or identifier of the graph to validate
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "csv_structure_valid": True,
        "total_nodes": 12,
        "total_edges": 15,
        "missing_declarations": [],
        "all_agents_defined": True
    },
    "metadata": {
        "graph_name": "customer_support",
        "bundle_name": "CustomerSupport",
        "csv_path": "/path/to/customer_support.csv"
    }
}
```

**Raises:**
- `GraphNotFound`: If the graph cannot be located
- `InvalidInputs`: If validation fails
- `AgentMapNotInitialized`: If runtime not initialized

**When to use:**
- Pre-deployment validation
- CI/CD pipeline checks
- Workflow development and testing
- Quality assurance

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Validate workflow before deployment
try:
    result = runtime_api.validate_workflow("customer_support")

    if result["success"]:
        outputs = result["outputs"]

        if outputs["all_agents_defined"]:
            print("✓ All agents are properly defined")
        else:
            print(f"⚠ Missing declarations: {outputs['missing_declarations']}")

        print(f"Graph has {outputs['total_nodes']} nodes and {outputs['total_edges']} edges")

except Exception as e:
    print(f"Validation failed: {e}")

# Use in CI/CD
import sys

result = runtime_api.validate_workflow("production_workflow")
if not result["success"] or not result["outputs"]["all_agents_defined"]:
    print("Validation failed - blocking deployment")
    sys.exit(1)
```

---

### Bundle & Code Generation

#### `scaffold_agents()`

Generate agent code templates for undefined agents in a workflow.

**Parameters:**
- `graph_name` (str, required): Name or identifier of the graph
- `output_dir` (str, optional): Directory for agent files. Default: uses config
- `func_dir` (str, optional): Directory for function files. Default: uses config
- `config_file` (str, optional): Path to configuration file. Default: `None`
- `overwrite` (bool, optional): Overwrite existing files. Default: `False`
- `force` (bool, optional): Force re-scaffolding. Default: `False`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "scaffolded_count": 3,
        "errors": [],
        "created_files": [
            "/path/to/agents/custom_classifier_agent.py",
            "/path/to/agents/data_processor_agent.py"
        ],
        "skipped_files": [
            "/path/to/agents/existing_agent.py"
        ],
        "service_stats": {
            "llm": 2,
            "storage": 1
        },
        "missing_declarations": [],
        "progress_messages": [
            "📦 Analyzing graph structure...",
            "🔨 Scaffolding agents for graph: DataPipeline",
            "🔄 Bundle updated with newly scaffolded agents"
        ]
    },
    "metadata": {
        "bundle_name": "DataPipeline",
        "csv_path": "/path/to/workflow.csv",
        "total_agents_in_bundle": 8,
        "agents_needing_scaffold": 3
    }
}
```

**Raises:**
- `GraphNotFound`: If the graph cannot be located
- `AgentMapNotInitialized`: If runtime not initialized

**When to use:**
- Rapid workflow prototyping
- Creating custom agent templates
- Onboarding new developers
- Workflow development workflow

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Basic scaffolding
result = runtime_api.scaffold_agents("customer_support")

if result["success"]:
    outputs = result["outputs"]
    print(f"Created {outputs['scaffolded_count']} agent files")

    for file_path in outputs["created_files"]:
        print(f"  ✓ {file_path}")

    if outputs["skipped_files"]:
        print(f"Skipped {len(outputs['skipped_files'])} existing files")

# Custom output directories
result = runtime_api.scaffold_agents(
    graph_name="data_pipeline",
    output_dir="./src/custom_agents",
    func_dir="./src/functions",
    overwrite=False
)

# Force re-scaffolding with overwrite
result = runtime_api.scaffold_agents(
    graph_name="customer_support",
    overwrite=True,
    force=True
)
```

#### `update_bundle()`

Update a graph bundle with current agent declarations and mappings.

**Parameters:**
- `graph_name` (str, required): Name or identifier of the graph
- `config_file` (str, optional): Path to configuration file. Default: `None`
- `dry_run` (bool, optional): Preview changes without saving. Default: `False`
- `force` (bool, optional): Force update even if no changes. Default: `False`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "current_mappings": 8,
        "missing_declarations": [],
        "required_services": 2
    },
    "metadata": {
        "bundle_name": "CustomerSupport",
        "csv_path": "/path/to/customer_support.csv",
        "force_recreated": True
    }
}
```

**When to use:**
- After adding new custom agents
- After modifying agent configurations
- Synchronizing bundle with code changes
- Development and testing

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Preview bundle update
result = runtime_api.update_bundle(
    graph_name="customer_support",
    dry_run=True
)

if result["success"]:
    outputs = result["outputs"]
    print(f"Would update {outputs.get('would_update', [])} mappings")
    print(f"Missing: {outputs['missing_declarations']}")

# Actually update the bundle
result = runtime_api.update_bundle(
    graph_name="customer_support",
    force=True
)

print(f"Bundle updated: {result['outputs']['current_mappings']} mappings")
```

---

### System Operations

#### `diagnose_system()`

Run comprehensive system diagnostics including dependency checks and provider availability.

**Parameters:**
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "overall_status": "fully_operational",
        "features": {
            "llm": {
                "enabled": True,
                "available_providers": ["openai", "anthropic"],
                "provider_details": {
                    "openai": {
                        "status": "available",
                        "available": True,
                        "has_dependencies": True,
                        "missing_dependencies": []
                    },
                    # ... more providers
                }
            },
            "storage": {
                "enabled": True,
                "available_types": ["json", "csv", "file"],
                "storage_details": {
                    # ... storage type details
                }
            }
        },
        "suggestions": [
            "For Google: pip install google-generativeai langchain-google-genai"
        ],
        "environment": {
            "python_version": "3.11.0",
            "python_path": "/usr/bin/python3",
            "current_directory": "/app",
            "package_versions": {
                "OpenAI SDK": "v1.12.0",
                "Anthropic SDK": "v0.18.1",
                # ... more packages
            }
        }
    },
    "metadata": {
        "llm_ready": True,
        "storage_ready": True
    }
}
```

**When to use:**
- Troubleshooting installation issues
- Verifying deployment environments
- Health check endpoints
- Pre-flight checks

**Example:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Run diagnostics
result = runtime_api.diagnose_system()

if result["success"]:
    outputs = result["outputs"]

    print(f"System Status: {outputs['overall_status']}")

    # Check LLM availability
    llm_providers = outputs["features"]["llm"]["available_providers"]
    print(f"Available LLM providers: {', '.join(llm_providers)}")

    # Show installation suggestions
    if outputs["suggestions"]:
        print("\nSuggestions:")
        for suggestion in outputs["suggestions"]:
            print(f"  - {suggestion}")

    # Check package versions
    for pkg, version in outputs["environment"]["package_versions"].items():
        print(f"  {pkg}: {version}")
```

#### `get_config()`

Get current configuration values from the runtime.

**Parameters:**
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with all configuration values

**When to use:**
- Debugging configuration issues
- Verifying settings
- Configuration validation

**Example:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

result = runtime_api.get_config()

if result["success"]:
    config = result["outputs"]
    print(f"CSV Repository: {config.get('csv_repository_path')}")
    print(f"Custom Agents: {config.get('custom_agents_path')}")
```

#### `refresh_cache()`

Refresh the provider availability cache by re-discovering and validating all providers.

**Parameters:**
- `force` (bool, optional): Force refresh even if cache exists. Default: `False`
- `llm_only` (bool, optional): Only refresh LLM providers. Default: `False`
- `storage_only` (bool, optional): Only refresh storage providers. Default: `False`
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with structure:

```python
{
    "success": True,
    "outputs": {
        "cache_invalidated": True,
        "llm_results": {
            "openai": True,
            "anthropic": True,
            "google": False
        },
        "storage_results": {
            "json": True,
            "csv": True,
            "vector": True
        },
        "status_summary": {
            # Provider status summary
        }
    },
    "metadata": {
        "force": False,
        "llm_only": False,
        "storage_only": False
    }
}
```

**When to use:**
- After installing new dependencies
- When provider availability changes
- Troubleshooting provider issues
- Environment updates

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Refresh all providers
result = runtime_api.refresh_cache(force=True)

if result["success"]:
    outputs = result["outputs"]
    print("LLM Providers:")
    for provider, available in outputs["llm_results"].items():
        status = "✓" if available else "✗"
        print(f"  {status} {provider}")

# Refresh only LLM providers
result = runtime_api.refresh_cache(llm_only=True)

# Refresh only storage providers
result = runtime_api.refresh_cache(storage_only=True)
```

#### `validate_cache()`

Manage the validation result cache.

**Parameters:**
- `clear` (bool, optional): Clear all validation cache. Default: `False`
- `cleanup` (bool, optional): Remove expired cache entries. Default: `False`
- `stats` (bool, optional): Show cache statistics. Default: `False`
- `file_path` (str, optional): Clear cache for specific file only. Default: `None`
- `config_file` (str, optional): Path to configuration file. Default: `None`

**Returns:** Dict with cache management results

**When to use:**
- After modifying workflow files
- Troubleshooting validation issues
- Cache maintenance
- Performance optimization

**Examples:**

```python
from agentmap import runtime_api

runtime_api.ensure_initialized()

# Show cache statistics
result = runtime_api.validate_cache(stats=True)
print(f"Cache stats: {result['outputs']['cache_stats']}")

# Clear cache for specific file
result = runtime_api.validate_cache(
    clear=True,
    file_path="/path/to/workflow.csv"
)

# Clear all cache
result = runtime_api.validate_cache(clear=True)

# Clean up expired entries
result = runtime_api.validate_cache(cleanup=True)
```

---

### Error Handling

The runtime API uses structured exceptions for predictable error handling:

```python
from agentmap import runtime_api
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)

try:
    result = runtime_api.run_workflow(
        graph_name="my_workflow",
        inputs={"data": "value"}
    )

    if result["success"]:
        # Handle successful execution
        outputs = result["outputs"]
    elif result.get("interrupted"):
        # Handle interrupted workflow
        thread_id = result["thread_id"]
        # Store for later resume
    else:
        # Handle execution failure
        error = result.get("error")

except GraphNotFound as e:
    # Workflow not found in repository
    print(f"Graph not found: {e}")

except InvalidInputs as e:
    # Input validation failed
    print(f"Invalid inputs: {e}")

except AgentMapNotInitialized as e:
    # Runtime not properly initialized
    print(f"Runtime error: {e}")
```

---

### Best Practices

#### Initialize Once

```python
# ✓ Good: Initialize at application startup
from agentmap import runtime_api

def initialize_app():
    runtime_api.ensure_initialized(config_file="./config/prod.yaml")

def run_workflow(graph_name, inputs):
    # Runtime already initialized
    return runtime_api.run_workflow(graph_name, inputs)

# ✗ Avoid: Initializing on every request
def run_workflow(graph_name, inputs):
    runtime_api.ensure_initialized()  # Expensive!
    return runtime_api.run_workflow(graph_name, inputs)
```

#### Check Success Status

```python
# ✓ Good: Always check success
result = runtime_api.run_workflow("my_graph", inputs)

if result["success"]:
    process_outputs(result["outputs"])
else:
    handle_error(result.get("error"))

# ✗ Avoid: Assuming success
result = runtime_api.run_workflow("my_graph", inputs)
outputs = result["outputs"]  # May not exist!
```

#### Handle Interruptions

```python
# ✓ Good: Handle interrupted workflows
result = runtime_api.run_workflow("approval_flow", inputs)

if result.get("interrupted"):
    # Store thread ID for later resume
    store_pending_approval(
        thread_id=result["thread_id"],
        request=result.get("interaction_request")
    )
    return {"status": "pending_approval"}

# Later, when user responds
result = runtime_api.resume_workflow(resume_token=thread_id)
```

#### Use Graph Name Conventions

```python
# ✓ Good: Use consistent naming
result = runtime_api.run_workflow(
    graph_name="customer_support",  # Looks for customer_support.csv
    inputs=inputs
)

# ✓ Good: Explicit CSV::Graph syntax
result = runtime_api.run_workflow(
    graph_name="workflows::EmailProcessor",  # Clear and explicit
    inputs=inputs
)

# ✓ Good: Alternative slash syntax
result = runtime_api.run_workflow(
    graph_name="workflows/EmailProcessor",  # Also works
    inputs=inputs
)
```

---

### Integration Examples

#### Flask Application

```python
from flask import Flask, request, jsonify
from agentmap import runtime_api

app = Flask(__name__)

# Initialize at startup
@app.before_first_request
def initialize():
    runtime_api.ensure_initialized(config_file="./config.yaml")

@app.route('/workflows/<graph_name>', methods=['POST'])
def execute_workflow(graph_name):
    try:
        inputs = request.get_json()

        result = runtime_api.run_workflow(
            graph_name=graph_name,
            inputs=inputs
        )

        if result["success"]:
            return jsonify(result["outputs"]), 200
        elif result.get("interrupted"):
            return jsonify({
                "status": "interrupted",
                "thread_id": result["thread_id"],
                "message": result["message"]
            }), 202
        else:
            return jsonify({"error": result.get("error")}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/workflows/<thread_id>/resume', methods=['POST'])
def resume_workflow(thread_id):
    try:
        result = runtime_api.resume_workflow(resume_token=thread_id)

        if result["success"]:
            return jsonify(result["outputs"]), 200
        else:
            return jsonify({"error": result.get("error")}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()
```

#### AWS Lambda Handler

```python
import json
from agentmap import runtime_api

# Initialize outside handler for container reuse
runtime_api.ensure_initialized()

def lambda_handler(event, context):
    """
    AWS Lambda handler for AgentMap workflows.

    Event format:
    {
        "graph_name": "workflow_name",
        "inputs": {"key": "value"}
    }
    """
    try:
        graph_name = event.get("graph_name")
        inputs = event.get("inputs", {})

        if not graph_name:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "graph_name required"})
            }

        result = runtime_api.run_workflow(
            graph_name=graph_name,
            inputs=inputs
        )

        if result["success"]:
            return {
                "statusCode": 200,
                "body": json.dumps(result["outputs"])
            }
        elif result.get("interrupted"):
            # Store thread_id in DynamoDB for later resume
            store_interrupted_workflow(result["thread_id"])

            return {
                "statusCode": 202,
                "body": json.dumps({
                    "status": "interrupted",
                    "thread_id": result["thread_id"]
                })
            }
        else:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": result.get("error")})
            }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
```

#### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from agentmap import runtime_api

app = FastAPI()

# Initialize at startup
@app.on_event("startup")
async def startup():
    runtime_api.ensure_initialized()

class WorkflowRequest(BaseModel):
    inputs: Dict[str, Any]
    profile: str = None

@app.post("/workflows/{graph_name}")
async def execute_workflow(graph_name: str, request: WorkflowRequest):
    try:
        result = runtime_api.run_workflow(
            graph_name=graph_name,
            inputs=request.inputs,
            profile=request.profile
        )

        if result["success"]:
            return result["outputs"]
        elif result.get("interrupted"):
            return {
                "status": "interrupted",
                "thread_id": result["thread_id"],
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflows")
async def list_workflows():
    result = runtime_api.list_graphs()
    return result["outputs"]

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

## ✅ FastAPI Server (Available Now)

AgentMap includes a production-ready FastAPI server for integrating workflows into host applications:

### Quick Start
```bash
# Install AgentMap (FastAPI included in base install)
pip install agentmap

# Start the server
agentmap-server --host 0.0.0.0 --port 8000

# Or using Python module
python -m agentmap.server_cli
```

### Available Endpoints
- `POST /execution/{workflow}/{graph}` - Execute specific workflow graph (RESTful)
- `POST /execution/{csv_file}` - Execute graph from CSV file (simplified syntax)
- `POST /execution/{csv_file::graph_name}` - Execute specific graph from CSV (override syntax)
- `POST /execution/run` - Legacy execution endpoint with flexible parameters
- `POST /execution/resume` - Resume interrupted/paused workflows
- `GET /workflows` - List available workflows in repository
- `GET /workflows/{workflow}` - Get detailed workflow information
- `GET /workflows/{workflow}/{graph}` - Get specific graph details
- `POST /validation/csv` - Validate CSV workflow definitions
- `GET /graph/compile` - Compile workflow graphs
- `GET /info/diagnose` - System diagnostics and health information
- `GET /health` - Basic service health check
- `GET /docs` - Interactive OpenAPI documentation
- `GET /redoc` - Alternative API documentation

### ✨ Simplified Graph Naming API

AgentMap's HTTP API now supports **intelligent default graph naming** for cleaner, more RESTful endpoints.

#### Smart Default Behavior

**CSV filename automatically becomes the graph name:**

```http
POST /execution/customer_support.csv
Content-Type: application/json

{
  "state": {
    "customer_query": "Help with my order"
  }
}
```

#### :: Override Syntax

**Custom graph names with URL encoding:**

```http
# :: becomes %3A%3A in URLs
POST /execution/workflows.csv%3A%3AProductSupport
Content-Type: application/json

{
  "state": {
    "product": "AgentMap",
    "query": "pricing information"
  }
}
```

#### Migration Examples

| Traditional API | New Simplified API | Benefits |
|----------------|-------------------|----------|
| `/execution/customer_service/support_flow` | `/execution/customer_support.csv` | Self-documenting, RESTful |
| `/execution/workflows/product_info` | `/execution/workflows.csv::ProductInfo` | Clear syntax, explicit |
| `/execution/main/data_pipeline` | `/execution/data_pipeline.csv` | Shorter URLs, intuitive |

### Use Cases
- **Microservice Integration**: Embed AgentMap in larger applications
- **Webhook Endpoints**: Trigger workflows from external events
- **Service Mesh**: Deploy workflows as independent services
- **API Gateway**: Expose workflows through standardized REST API

### API Examples

#### Execute Workflow Graph

**✨ New Simplified Syntax (Recommended):**
```bash
# RESTful execution with filename as graph name
curl -X POST "http://localhost:8000/execution/customer_support.csv" \
     -H "Content-Type: application/json" \
     -d '{
       "state": {
         "customer_message": "I need help with my order",
         "priority": "high"
       },
       "autocompile": true,
       "execution_id": "api-exec-001"
     }'

# Custom graph name using :: syntax (URL encoded as %3A%3A)
curl -X POST "http://localhost:8000/execution/workflows.csv%3A%3ACustomerSupport" \
     -H "Content-Type: application/json" \
     -d '{
       "state": {
         "customer_message": "I need help with my order"
       }
     }'
```

**Traditional Syntax (Still Supported):**
```bash
# RESTful execution
curl -X POST "http://localhost:8000/execution/customer_service/support_flow" \
     -H "Content-Type: application/json" \
     -d '{
       "state": {
         "customer_message": "I need help with my order",
         "priority": "high"
       },
       "autocompile": true,
       "execution_id": "api-exec-001"
     }'
```

#### List Available Workflows
```bash
# Get all workflows in repository
curl -X GET "http://localhost:8000/workflows" \
     -H "Accept: application/json"
```

#### Get Workflow Details
```bash
# Get detailed information about a specific workflow
curl -X GET "http://localhost:8000/workflows/customer_service" \
     -H "Accept: application/json"
```

#### Resume Interrupted Workflow
```bash
# Resume a paused workflow
curl -X POST "http://localhost:8000/execution/resume" \
     -H "Content-Type: application/json" \
     -d '{
       "thread_id": "thread-uuid-12345",
       "response_action": "approve",
       "response_data": {"decision": "approved"}
     }'
```

### Authentication & Security

The FastAPI server supports multiple authentication modes:

- **Public Mode**: No authentication required (default for embedded usage)
- **API Key**: Use `X-API-Key` header for server-to-server integration  
- **Bearer Token**: Use `Authorization: Bearer <token>` for user-based access

```bash
# API Key authentication
curl -H "X-API-Key: your-api-key" http://localhost:8000/workflows

# Bearer token authentication  
curl -H "Authorization: Bearer your-token" http://localhost:8000/workflows
```

### Rate Limiting

API endpoints include rate limiting for stability:

- **Execution endpoints**: 60 requests per minute
- **Validation endpoints**: 120 requests per minute
- **Information endpoints**: 300 requests per minute

### Documentation Links
- **[FastAPI Standalone Deployment](/docs/deployment/fastapi-standalone)** - Complete deployment guide
- **[FastAPI Integration Guide](/docs/deployment/fastapi-integration)** - Integrate with existing apps
- **[CLI Commands Reference](/docs/deployment/cli-commands)** - Command-line interface

---

## 🔧 Current Development Interface

### CSV Workflow Definition
The primary "API" for AgentMap is the CSV workflow format:

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
MyFlow,Start,,Get input,input,Process,Error,,user_input,What can I help with?
MyFlow,Process,,LLM processing,openai,End,Error,user_input,response,You are helpful: {user_input}
MyFlow,End,,Complete,echo,,,response,result,
```

**Complete Format Reference**: [CSV Schema Documentation](/docs/reference/csv-schema)

### Custom Agent Development
Extend AgentMap with custom business logic:

```python
from agentmap.agents.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def process(self, inputs):
        # Your business logic here
        return {"result": "processed"}
```

**Development Guide**: [Agent Development Contract](/docs/guides/development/agents/agent-development)

### CLI Tools
```bash
# Generate custom agent template
agentmap scaffold --agent CustomAgent

# Validate workflow
agentmap validate --csv workflow.csv

# Run workflow
agentmap run --graph MyFlow --csv workflow.csv
```

---

## 📖 Related Documentation

### Current Documentation
- **[CSV Schema Reference](/docs/reference/csv-schema)** - Complete workflow definition format
- **[Agent Development Contract](/docs/guides/development/agents/agent-development)** - Custom agent development patterns
- **[CLI Commands Reference](/docs/deployment/cli-commands)** - Complete command-line interface
- **[Architecture Overview](/docs/contributing/clean-architecture-overview)** - System design principles

### Development Resources
- **[Quick Start Guide](/docs/getting-started)** - Get started with AgentMap
- **[Learning Guide: AI Automation](/docs/guides/learning/01-basic-agents)** - Build your first custom workflow
- **[Contributing Guide](/docs/contributing)** - How to contribute to AgentMap

---

---

*Last updated: July 25, 2025*  
*Current Version: CLI and FastAPI server for workflow execution*  
*Status: Full implementation with production-ready FastAPI server available*
