---
sidebar_position: 1
title: What is AgentMap?
description: AgentMap lets you build multi-agent AI workflows using simple CSV files. Learn core concepts and when to use this framework.
keywords: [multi-agent systems, AI workflows, agent orchestration, CSV workflows, introduction]
---

# What is AgentMap?

**Build Multi-Agent AI Workflows with Simple CSV Files**

AgentMap is a framework for creating sophisticated AI workflows where multiple agents collaborate to solve complex problems. Instead of complex YAML or code, you define your workflows using familiar CSV files.

## When Should You Use AgentMap?

AgentMap is perfect when you need:

✅ **Multi-step AI processing** - Chain together different AI operations  
✅ **Version-controlled workflows** - CSV files work great with Git  
✅ **Rapid prototyping** - Build and modify workflows quickly  
✅ **Production orchestration** - Scale from prototype to production  
✅ **Mixed AI providers** - Combine OpenAI, Anthropic, Google in one workflow  

## Core Concepts (3 Minutes)

### 🤖 Agents
Agents are the workers in your workflow. Each agent has one job:

```python
class WeatherAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        location = inputs.get('location', 'Unknown')
        # Call weather API and return data
        return f"Weather in {location}: Sunny, 72°F"
```

**Built-in Agent Types**: LLM agents, file operations, data processing, routing, user input.

### 📋 Workflows (CSV Files)
Your workflow is a CSV file that defines how agents connect:

```csv
graph_name,node_name,agent_type,next_node,input_fields,output_field,prompt
HelloWorld,Start,input,Greet,,name,"What's your name?"
HelloWorld,Greet,echo,End,name,greeting,"Hello {name}!"
HelloWorld,End,echo,,greeting,result,"Thanks for using AgentMap!"
```

**Key Elements**: Nodes (agents), connections (next_node), data flow (input_fields → output_field).

### 🔧 Services
Services provide infrastructure like LLM APIs, databases, and file storage:

```python
# Agents automatically get the services they need
class MyLLMAgent(BaseAgent, LLMCapableAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        # self.llm_service is automatically injected
        response = self.llm_service.call_llm(
            provider="openai",
            messages=[{"role": "user", "content": inputs["question"]}]
        )
        return response["content"]
```

## Simple Example: Document Analysis

Here's a complete 3-agent workflow:

```csv
graph_name,node_name,agent_type,next_node,input_fields,output_field,prompt
DocAnalyzer,LoadDoc,file_reader,Analyze,file_path,document,
DocAnalyzer,Analyze,llm,Summarize,document,insights,"Extract key insights: {document}"
DocAnalyzer,Summarize,llm,End,insights,summary,"Create summary: {insights}"
DocAnalyzer,End,echo,,summary,result,"{summary}"
```

**What happens**:
1. `LoadDoc` reads a document file
2. `Analyze` extracts insights using AI
3. `Summarize` creates an executive summary
4. Data flows automatically between agents

## Ready to Build?

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap', margin: '2rem 0'}}>

**Next Step**: [**Quick Start →**](./quick-start)  
*Install and run your first workflow in 5 minutes*

</div>

---

**Alternative Learning Paths**:
- 📖 [Learning Guides](/docs/learning/basic-agents) - Step-by-step tutorials with examples
- 🔧 [Built-in Agents](/docs/agents/built-in-agents) - See what agents are available  
- ⚙️ [Configuration](/docs/configuration/) - Advanced setup and deployment
