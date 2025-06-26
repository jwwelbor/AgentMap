---
sidebar_position: 1
title: Understanding Workflows
description: Learn how AgentMap workflows work with interactive visualizations
---

import WorkflowVisualizer from '@site/src/components/WorkflowVisualizer';

# Understanding AgentMap Workflows

AgentMap workflows are defined using simple CSV files that describe how AI agents connect and pass data between each other. This guide will help you understand the structure and flow of these workflows through interactive visualizations.

:::tip Try Workflows Live!
🎮 **Ready to build your own?** Jump straight to our [Interactive Playground](../playground) to create and test workflows with live simulation!
:::

## Interactive Workflow Builder

Use the tool below to explore how CSV definitions translate into visual workflow diagrams. You can start with our pre-built templates or create your own workflows from scratch.

<WorkflowVisualizer />

---

## Workflow Structure Fundamentals

Every AgentMap workflow consists of:

### 1. **Nodes (Agents)**
Each row in your CSV represents a node in your workflow. Nodes are individual agents that perform specific tasks:

- **Core Agents**: Basic functionality (input, echo, branching)
- **LLM Agents**: AI-powered text processing (GPT, Claude, Gemini)
- **Storage Agents**: Data persistence (CSV, JSON, databases)
- **File Agents**: File operations (reading, writing documents)
- **Custom Agents**: Your own specialized implementations

### 2. **Connections (Edges)**
Nodes connect through two types of paths:

- **Success Path**: Where execution goes when the agent succeeds
- **Failure Path**: Where execution goes when the agent fails

### 3. **Data Flow**
Information flows between agents through:

- **Input Fields**: What data the agent expects to receive
- **Output Field**: What data the agent produces
- **Context**: Configuration and settings for the agent

## CSV Format Breakdown

Each CSV row follows this structure:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
```

### Field Descriptions

| Field | Purpose | Example |
|-------|---------|---------|
| **GraphName** | Workflow identifier | `WeatherBot` |
| **Node** | Unique node name | `GetLocation` |
| **Edge** | Connection metadata | Usually empty |
| **Context** | Agent configuration | `{"temperature": 0.7}` |
| **AgentType** | Type of agent | `llm`, `input`, `csv_reader` |
| **Success_Next** | Next node on success | `ProcessData` |
| **Failure_Next** | Next node on failure | `HandleError` |
| **Input_Fields** | Expected inputs | `location,weather_data` |
| **Output_Field** | Produced output | `weather_info` |
| **Prompt** | Agent instructions | `Get weather for {location}` |
| **Description** | Human-readable description | `Fetch weather data` |

## Common Workflow Patterns

### 1. **Linear Pipeline**
Simple sequential processing:
```
Input → Process → Transform → Output
```

### 2. **Branching Logic**
Conditional routing based on results:
```
Input → Classify → Route A / Route B → Combine → Output
```

### 3. **Error Handling**
Graceful failure management:
```
Process → Success Path / Error Handler → Recovery → Continue
```

### 4. **Parallel Processing**
Multiple concurrent operations:
```
Input → Split → Process A | Process B | Process C → Merge → Output
```

### 5. **Feedback Loops**
Iterative improvement:
```
Process → Validate → (Pass/Retry) → Improve → Process
```

## Best Practices

### ✅ **Do This**

1. **Start Simple**: Begin with linear workflows before adding complexity
2. **Handle Errors**: Always include failure paths for critical operations
3. **Descriptive Names**: Use clear, descriptive node names
4. **Logical Grouping**: Group related operations together
5. **Test Incrementally**: Build and test workflows step by step

### ❌ **Avoid This**

1. **Circular Dependencies**: Ensure workflows have clear end points
2. **Missing Error Handling**: Don't ignore potential failure scenarios
3. **Overly Complex Flows**: Keep workflows focused and manageable
4. **Poor Naming**: Avoid cryptic or generic node names
5. **Monolithic Workflows**: Break large workflows into smaller, reusable parts

## Advanced Features

### Custom Agent Integration

You can extend AgentMap with custom agents:

```python
from agentmap.agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def process(self, inputs):
        # Your custom logic here
        return processed_data
```

Then use in CSV:
```csv
MyGraph,CustomStep,,{},custom:MyCustomAgent,Next,Error,input,output,Custom processing,Process custom data
```

### Context Configuration

Configure agents with JSON context:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
AIChat,Generate,,"{"model": "gpt-4", "temperature": 0.7, "max_tokens": 1000}",llm,Respond,Error,user_message,ai_response,Respond helpfully to: {user_message},Generate AI response
```

### Dynamic Routing

Use branching agents for conditional logic:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
Router,Classify,,{},llm,RouteDecision,Error,message,intent,Classify this message as: urgent|normal|spam,Classify user message
Router,RouteDecision,,{},branching,UrgentHandler|NormalHandler|SpamHandler,Error,intent,routing,Route based on classification,Route to appropriate handler
```

## Debugging Workflows

### Common Issues

1. **Missing Nodes**: Referenced nodes that don't exist
2. **Circular References**: Nodes that reference each other infinitely
3. **Invalid Agent Types**: Using non-existent agent types
4. **Configuration Errors**: Malformed JSON in Context field
5. **Input/Output Mismatches**: Expecting data that isn't provided

### Debugging Tips

1. **Use the Visualizer**: The interactive tool above shows errors and warnings
2. **Start Small**: Test with minimal workflows first
3. **Check Connections**: Ensure all referenced nodes exist
4. **Validate JSON**: Use proper JSON format in Context fields
5. **Test Incrementally**: Add nodes one at a time

## Real-World Examples

The templates in the visualizer above demonstrate real-world patterns:

- **Weather Bot**: Simple API integration with error handling
- **Data Pipeline**: ETL processing with validation steps
- **Support Bot**: Multi-intent classification and routing
- **API Integration**: Complex multi-source data processing

Each template showcases different aspects of workflow design and can serve as starting points for your own implementations.

## Next Steps

Ready to build your own workflows? Check out these resources:

- **[Quick Start Guide](../getting-started/quick-start)**: Build your first workflow in 5 minutes
- **[Agent Reference](../reference/agent-types)**: Complete list of available agents
- **[Tutorial Workflows](../tutorials/weather-bot)**: Step-by-step workflow examples
- **[Examples](../examples/index)**: Real-world workflow examples

---

*💡 **Tip**: Use the interactive visualizer above to experiment with different workflow patterns and see how they translate into visual diagrams. This is the best way to understand the relationship between CSV structure and workflow execution.*
