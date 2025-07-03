---
sidebar_position: 1
title: AgentMap API Reference
description: API reference for AgentMap framework including CLI tools and planned FastAPI integration for host applications.
keywords: [AgentMap API, CLI API, FastAPI integration, host application integration, AgentMap documentation]
---

# AgentMap API Reference

API documentation for AgentMap framework. Currently, AgentMap provides a comprehensive CLI interface for workflow management. A FastAPI integration for host applications is planned.

## 🛠️ Current API Surface

### Command Line Interface
AgentMap's primary API is through the CLI, which provides complete workflow management capabilities:

- **Workflow Execution**: Run workflows from CSV definitions
- **Validation**: Validate workflow structure and dependencies  
- **Graph Inspection**: Analyze and debug workflow graphs
- **Code Generation**: Scaffold custom agents and project templates
- **Testing Tools**: Validate and benchmark workflows

**Complete CLI Reference**: [CLI Commands Documentation](/docs/reference/cli-commands)

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

## 🚧 Planned: FastAPI Integration

A FastAPI-based API server is planned for integrating AgentMap workflows into host applications:

### Planned Endpoints
- `POST /workflows/{workflow_name}/execute` - Execute workflows via HTTP
- `GET /workflows/{workflow_name}/status` - Check workflow status
- `POST /workflows/validate` - Validate workflow definitions
- `GET /health` - Service health check

### Use Cases
- **Microservice Integration**: Embed AgentMap in larger applications
- **Webhook Endpoints**: Trigger workflows from external events
- **Service Mesh**: Deploy workflows as independent services
- **API Gateway**: Expose workflows through standardized REST API

---

## 🔧 Current Development Interface

### CSV Workflow Definition
The primary "API" for AgentMap is the CSV workflow format:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
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
- **[CLI Commands Reference](/docs/reference/cli-commands)** - Complete command-line interface
- **[Architecture Overview](/docs/contributing/clean-architecture-overview)** - System design principles

### Development Resources
- **[Quick Start Guide](/docs/getting-started)** - Get started with AgentMap
- **[Weather Bot Tutorial](/docs/tutorials/weather-bot)** - Build your first custom agent
- **[Contributing Guide](/docs/contributing)** - How to contribute to AgentMap

---

## 🚀 FastAPI Integration Timeline

The FastAPI integration is planned for a future release. It will enable:

- **HTTP Workflow Execution**: Trigger workflows via REST endpoints
- **Host Application Integration**: Embed AgentMap in larger systems
- **Microservice Architecture**: Deploy workflows as independent services
- **Event-Driven Processing**: React to webhooks and external events

**Stay Updated**: [Watch AgentMap on GitHub](https://github.com/jwwelbor/AgentMap) for announcements about the FastAPI integration.

---

*Last updated: June 27, 2025*  
*Current Version: CLI-based workflow execution*  
*Planned: FastAPI integration for host applications*
