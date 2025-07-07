---
sidebar_position: 1
title: AgentMap - Multi-Agent AI Workflows
description: Build autonomous multi-agent systems using CSV files. Simple orchestration of AI agents for complex workflows.
keywords: [multi-agent systems, AI workflows, agent orchestration, CSV workflows]
---

# Welcome to AgentMap

**Build Multi-Agent AI Workflows with Simple CSV Files**

AgentMap allows you to create sophisticated multi-agent AI systems using familiar CSV configuration files. Define workflows where AI agents collaborate autonomously to solve complex problems.

## What is AgentMap?

AgentMap is a multi-agent orchestration framework that enables you to:

- **Define workflows in CSV** - Use simple, version-controllable CSV files instead of complex YAML
- **Orchestrate AI agents** - Combine LLM reasoning, data processing, and custom logic seamlessly  
- **Build autonomous systems** - Agents make decisions and route intelligently based on context
- **Scale production workloads** - Built-in monitoring, error handling, and performance tracking

## Core Concepts

### Agents
All agents inherit from `BaseAgent` and implement a `process()` method:

```python
class WeatherAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        location = inputs.get('location', 'Unknown')
        # Call weather API and return data
        return f"Weather in {location}: Sunny, 72°F"
```

**Built-in Agent Types**: LLM agents, file operations, data processing, routing, and more.

### Services
Infrastructure services are injected via protocols for clean architecture:

```python
# Protocol-based injection for business services
class LLMAgent(BaseAgent, LLMCapableAgent):
    def configure_llm_service(self, llm_service: LLMServiceProtocol):
        self._llm_service = llm_service
```

**Service Categories**: LLM services, storage services, execution tracking, state management.

### Workflows
CSV files define the workflow structure - agents, connections, and data flow:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt
SimpleBot,GetInput,Get user question,input,ProcessQuestion,End,,question,Enter your question:
SimpleBot,ProcessQuestion,Process with AI,llm,GetInput,Error,question,response,Answer this question: {question}
SimpleBot,Error,Handle errors,echo,End,,error,error_msg,Sorry there was an error
SimpleBot,End,Complete workflow,echo,,,response,final_output,{response}
```

**Key Elements**: Node definitions, data routing, error handling, state management.

## Quick Example

Here's a simple 3-agent workflow for document analysis:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt
DocAnalyzer,LoadDoc,Load document,file_reader,AnalyzeContent,Error,file_path,document,
DocAnalyzer,AnalyzeContent,Extract insights,llm,CreateSummary,Error,document,insights,Analyze this document and extract key insights: {document}
DocAnalyzer,CreateSummary,Create summary,llm,End,Error,insights,summary,Create an executive summary from these insights: {insights}
DocAnalyzer,Error,Handle errors,echo,End,,error,error_msg,Analysis failed
DocAnalyzer,End,Complete analysis,echo,,,summary,final_result,{summary}
```

**What happens**:
1. `LoadDoc` agent reads a document file
2. `AnalyzeContent` agent uses LLM to extract insights  
3. `CreateSummary` agent creates an executive summary
4. Data flows automatically between agents via `input_fields` and `output_field`

## Documentation Overview

### 🏃‍♂️ [Getting Started](./getting-started)
Build your first workflow in 5 minutes with step-by-step guidance.

### 🎓 [Learning Paths](./guides/learning-paths/)
Progressive learning guides that build from basic concepts to advanced patterns:
- **[Understanding Workflows](./guides/learning-paths/understanding-workflows)** - How workflows work
- **[Core Concepts](./guides/learning-paths/core/)** - Agents, services, and state management

### 📚 [Learning Guides](./guides/learning/)
Progressive lessons with downloadable examples:
- **[Lesson 1: Basic Agents](./guides/learning/01-basic-agents)** - Your first agents and workflows
- **[Lesson 2: Data Processing](./guides/learning/02-data-processing)** - Transform and validate data
- **[Lesson 3: LLM Integration](./guides/learning/03-llm-integration)** - AI-powered workflows

### 📖 [Guides](./guides/)
In-depth development and deployment guides:
- **[Development](./guides/development/)** - Agent creation, testing, best practices
- **[Deployment](./guides/deploying/)** - Production deployment and monitoring

### 📚 [Reference](./reference/)
Complete specifications and API documentation:
- **[Agents](./reference/agents/)** - Built-in agent types and development patterns
- **[Services](./reference/services/)** - Service architecture and protocols
- **[CSV Schema](./reference/csv-schema)** - Complete workflow definition format

### 🤝 [Contributing](./contributing/)
Architecture guides and contribution patterns:
- **[Clean Architecture](./contributing/clean-architecture-overview)** - System design principles
- **[Dependency Injection](./contributing/dependency-injection)** - Service management patterns

---

**Ready to start building?** 

**[Begin Quick Start Guide →](./getting-started)**
