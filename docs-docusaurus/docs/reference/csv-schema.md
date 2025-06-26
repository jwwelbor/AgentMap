---
sidebar_position: 1
title: CSV Schema Reference
description: Complete reference for AgentMap CSV workflow schema
---

# CSV Schema Reference

AgentMap uses CSV files to define workflows as directed graphs. Each row in the CSV represents a node in the graph and its connections to other nodes. This document explains the structure and fields of these CSV files.

## CSV Columns

| Column | Required | Description |
|--------|----------|-------------|
| `GraphName` | Yes | Name of the workflow graph. Multiple nodes can share the same GraphName to form a complete workflow. |
| `Node` | Yes | Unique identifier for this node within the graph. |
| `Edge` | No | Direct connection to another node. Use this for simple linear flows. |
| `Context` | No | Description or JSON configuration for the node. Can contain memory configuration. |
| `AgentType` | No | Type of agent to use (e.g., "openai", "claude", "echo"). Defaults to "Default" if not specified. |
| `Success_Next` | No | Where to go on success. Can be a node name or multiple nodes with pipe separators. |
| `Failure_Next` | No | Where to go on failure. Can be a node name or multiple nodes with pipe separators. |
| `Input_Fields` | No | State fields to extract as input for this agent. Pipe-separated list. |
| `Output_Field` | No | Field in state where this agent's output should be stored. |
| `Prompt` | No | Text or template used by LLM agents. For some agent types, this can be configuration data. Can reference managed prompts using the prompt: notation. |
| `Description` | No | Detailed documentation for the node's purpose. Unlike Context (which can be used for configuration), Description is solely for documentation and does not affect functionality. |

## Field Details

### Routing Fields (Edge, Success_Next, Failure_Next)

You can define routing in two ways:
1. Using `Edge` for simple linear flows
2. Using `Success_Next` and `Failure_Next` for conditional branching based on `last_action_success`

**Important:** Don't use both `Edge` and `Success_Next`/`Failure_Next` in the same row - this will raise an `InvalidEdgeDefinitionError`.

### Function References

You can use function references for advanced routing:
```
func:function_name
```

The function should be defined in the functions directory and will be called to determine the next node.

### Context and Description Fields

AgentMap provides two fields for documenting and configuring nodes:

- **Context**: Can contain plain text description or JSON for advanced configuration
- **Description**: Purely for documentation purposes - doesn't affect functionality

Examples:

```csv
GraphA,Node1,"{'memory':{'type':'buffer'}}","This node processes user input to extract key entities",...
```

The Description field is useful for:
- Documenting complex node behavior
- Explaining the node's role in the workflow
- Documenting expected inputs and outputs
- Adding notes for other developers

### Input_Fields and Output_Field

These fields control data flow between nodes:
- `Input_Fields`: Which state values this node can access (pipe-separated)
- `Output_Field`: Where this node's output is stored in state

### Complex Routing

For complex routing patterns:
- Function references: `func:choose_next`
- Multiple targets: Use pipe-separator in Success_Next or Failure_Next

## Example CSV Structure

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name:,Input node for weather workflow
WeatherFlow,FetchWeather,,{"api_key": "env:WEATHER_API"},weather_api,GenerateReport,ErrorHandler,location,weather_data,,Fetches weather data from API
WeatherFlow,GenerateReport,,{"provider": "openai"},llm,End,ErrorHandler,weather_data|location,report,Generate weather report for {location},Creates natural language weather report
WeatherFlow,ErrorHandler,,Handle any errors,echo,End,,error,error_message,,Error handling node
WeatherFlow,End,,Complete workflow,echo,,,report|error_message,output,,Final output node
```

## Best Practices

### Node Naming
- Use descriptive node names that indicate their purpose
- Avoid spaces and special characters
- Use PascalCase or snake_case consistently

### Graph Organization
- Group related nodes with consistent GraphName
- Design clear flow from start to end
- Include error handling paths

### Context Configuration
- Use JSON format for complex configurations
- Reference environment variables with `env:VARIABLE_NAME`
- Document configuration options in Description field

### Data Flow
- Specify Input_Fields to control what data flows between nodes
- Use Output_Field to name result storage consistently
- Avoid overwriting important state values

### Error Handling
- Always include error handling nodes
- Use Failure_Next to route to error handlers
- Design graceful degradation paths

### Documentation
- Use Description field for detailed node documentation
- Include expected inputs and outputs
- Document any special configuration requirements

## Common Patterns

### Linear Flow
```csv
MyGraph,Start,,Initial node,input,Process,,data,user_input,Enter data:
MyGraph,Process,,Process the data,transform,End,,user_input,result,
MyGraph,End,,Final output,echo,,,result,output,
```

### Conditional Branching
```csv
MyGraph,Decision,,Make decision,branching,Success,Failure,input,decision,
MyGraph,Success,,Success path,echo,End,,decision,success_result,
MyGraph,Failure,,Failure path,echo,End,,decision,failure_result,
MyGraph,End,,Final output,echo,,,success_result|failure_result,output,
```

### Parallel Processing
```csv
MyGraph,Split,,Split work,default,TaskA|TaskB|TaskC,Error,data,tasks,
MyGraph,TaskA,,Process A,worker_a,Join,Error,tasks,result_a,
MyGraph,TaskB,,Process B,worker_b,Join,Error,tasks,result_b,
MyGraph,TaskC,,Process C,worker_c,Join,Error,tasks,result_c,
MyGraph,Join,,Combine results,summary,End,Error,result_a|result_b|result_c,final_result,
MyGraph,End,,Output results,echo,,,final_result,output,
```

## See Also

- [CLI Commands Reference](cli-commands.md) - Command-line interface documentation
- [Agent Types Reference](agent-types.md) - Available agent types and their configurations
- [Quick Start Guide](../getting-started/quick-start.md) - Build your first workflow
