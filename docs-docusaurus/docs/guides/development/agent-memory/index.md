---
sidebar_position: 1
title: Memory and Orchestration
description: Advanced AgentMap features for building stateful, intelligent workflows with dynamic routing and context management
keywords: [agentmap, memory, orchestration, dynamic routing, conversation management, prompt management]
---

# Memory and Orchestration

This section covers AgentMap's advanced features for building sophisticated, stateful workflows that can maintain context and intelligently route between different agents and capabilities.

## Overview

Memory and orchestration are key features that transform simple AgentMap workflows into intelligent, adaptive systems:

- **Memory Management**: Enable agents to maintain conversation history and context
- **LangChain Integration**: Leverage advanced memory strategies for optimal performance
- **Dynamic Orchestration**: Route requests intelligently based on content and context
- **Prompt Management**: Organize and reuse prompts across complex workflows

## Quick Navigation

import DocCardList from '@theme/DocCardList';

<DocCardList />

## Core Concepts

### Memory Systems
AgentMap provides multiple memory approaches to suit different use cases:

- **Simple Memory**: Basic conversation history tracking
- **LangChain Memory**: Advanced strategies like buffer windows, token limits, and summarization
- **Shared Memory**: Context sharing between multiple agents in a workflow

### Orchestration Patterns
Build intelligent routing systems that adapt to user input:

- **Dynamic Routing**: Select the best agent based on request content
- **Multi-Strategy Selection**: Combine algorithmic and AI-based routing
- **Context-Aware Decisions**: Use conversation history to inform routing choices

### Prompt Organization
Maintain clean, reusable prompt libraries:

- **Registry-Based Prompts**: Centralized prompt management
- **File-Based Prompts**: Organize complex prompts in dedicated files
- **YAML Structures**: Hierarchical prompt organization for complex scenarios

## Integration Examples

### Memory + Orchestration
Combine memory and orchestration for intelligent conversational flows:

```csv
graph_name,node_name,next_node,agent_type,input_fields,output_field,prompt,context
ChatBot,Router,,orchestrator,available_nodes|user_input|conversation_memory,next_node,"Route based on input and context","memory:{""type"":""buffer_window"",""k"":5}"
ChatBot,GeneralChat,,claude,user_input|conversation_memory,response,"I handle general conversation","memory:{""type"":""buffer_window"",""k"":5}"
ChatBot,TaskHelper,,claude,user_input|conversation_memory,response,"I help with specific tasks","memory:{""type"":""buffer_window"",""k"":5}"
```

### Orchestration + Prompts
Use managed prompts with intelligent routing:

```csv
graph_name,node_name,next_node,agent_type,input_fields,output_field,prompt,context
Support,Router,,orchestrator,available_nodes|user_input,next_node,prompt:router_instructions,
Support,TechSupport,,claude,user_input,response,prompt:technical_support,
Support,CustomerService,,claude,user_input,response,prompt:customer_service,
```

### Complete Integration
Combine all three features for maximum flexibility:

```csv
graph_name,node_name,next_node,agent_type,input_fields,output_field,prompt,context
Advanced,Router,,orchestrator,available_nodes|user_input|session_memory,next_node,yaml:workflows.yaml#routing.intelligent,"memory:{""type"":""summary"",""memory_key"":""session_memory""}"
Advanced,Specialist,,claude,user_input|session_memory,response,yaml:workflows.yaml#responses.specialist,"memory:{""type"":""summary"",""memory_key"":""session_memory""}"
Advanced,Generalist,,claude,user_input|session_memory,response,yaml:workflows.yaml#responses.generalist,"memory:{""type"":""summary"",""memory_key"":""session_memory""}"
```

## Best Practices

1. **Start Simple**: Begin with basic memory and add complexity as needed
2. **Choose Appropriate Memory Types**: Match memory strategy to conversation length and complexity
3. **Design Clear Node Descriptions**: Help orchestrators make better routing decisions
4. **Organize Prompts Logically**: Create maintainable prompt libraries
5. **Test Integration Points**: Verify memory, routing, and prompts work together smoothly

## Getting Started

1. **[Memory Management](/docs/guides/development/agent-memory/memory-management)**: Start with basic conversation memory
2. **[LangChain Memory Integration](/docs/guides/development/agent-memory/langchain-memory-integration)**: Explore advanced memory strategies
3. **[Orchestration Patterns](guides/learning/04-orchestration)**: Add intelligent routing to your workflows
4. **[Prompt Management](./prompt-management)**: Organize your prompts for reusability

## Advanced Patterns

Once you're comfortable with the basics, explore these advanced patterns:

- **Multi-Agent Conversations**: Orchestrate between specialized agents while maintaining shared context
- **Hierarchical Routing**: Use nested orchestrators for complex decision trees
- **Context-Aware Prompting**: Adapt prompts based on conversation history and user context
- **Dynamic Memory Management**: Adjust memory strategies based on conversation flow

These features work together to create sophisticated AgentMap workflows that can handle complex, stateful interactions while remaining maintainable and easy to understand.
