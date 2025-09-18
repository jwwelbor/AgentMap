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
