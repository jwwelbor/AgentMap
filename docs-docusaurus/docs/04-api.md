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
# Install AgentMap with FastAPI dependencies
pip install agentmap[fastapi]

# Start the server
agentmap-server --host 0.0.0.0 --port 8000

# Or using Python module
python -m agentmap.server_cli
```

### Available Endpoints
- `POST /execute` - Execute workflows via HTTP
- `GET /workflows` - List available workflows
- `GET /workflows/{workflow_name}` - Get workflow details
- `POST /validation/csv` - Validate workflow definitions
- `GET /health` - Service health check
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

### Use Cases
- **Microservice Integration**: Embed AgentMap in larger applications
- **Webhook Endpoints**: Trigger workflows from external events
- **Service Mesh**: Deploy workflows as independent services
- **API Gateway**: Expose workflows through standardized REST API

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
