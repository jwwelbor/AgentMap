# AgentMap CSV Schema Documentation

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
---

---

[↑ Back to Index](index.md) | [Next: Prompt Management in AgentMap →](prompt_management_in_agentmap.md)