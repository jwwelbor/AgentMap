# Advanced Agent Types

## GraphAgent

Executes a subgraph and returns its result.

- **Input Fields**: Passed to the subgraph
- **Output Field**: Result from the subgraph
- **Prompt Usage**: Name of the subgraph to execute

## SummaryAgent

Combines and summarizes multiple input fields into a single output. Useful for consolidating outputs from parallel operations or creating concise summaries from multiple data sources.

- **Input Fields**: Multiple fields to be summarized (pipe-separated list)
- **Output Field**: Single field for the consolidated output
- **Prompt Usage**: Instructions for LLM-based summarization
- **Context**: Can contain configuration for formatting and LLM usage

The SummaryAgent operates in two modes:
### 1. Basic Concatenation Mode (Default)

Simply formats and joins the input fields according to templates.

Example:
```csv
TestGraph,Summarize,,{"format":"{key}: {value}","separator":"\n\n"},summary,Next,,field1|field2|field3,summary_output,
```

Configuration options:
- `format`: Template for formatting each item (default: `"{key}: {value}"`)
- `separator`: String used to join formatted items (default: `"\n\n"`)
- `include_keys`: Whether to include field names in output (default: `true`)

### 2. LLM Summarization Mode

Uses an LLM to create an intelligent summary of the inputs.

Example:
```csv
TestGraph,Summarize,,{"llm":"openai","model":"gpt-3.5-turbo"},summary,Next,,field1|field2|field3,summary_output,Create a concise summary of these data points.
```

LLM Configuration options:
- `llm`: LLM provider to use (`"openai"`, `"anthropic"`, or `"google"`)
- `model`: Specific model to use (optional)
- `temperature`: Temperature for generation (optional)

The prompt field provides instructions to the LLM on how to create the summary.

### Usage Patterns

**Summarizing Parallel Branch Results:**
```csv
ParallelFlow,Branch1,,Process first set of data,Default,Join,,input,result1,
ParallelFlow,Branch2,,Process second set of data,Default,Join,,input,result2,
ParallelFlow,Branch3,,Process third set of data,Default,Join,,input,result3,
ParallelFlow,Join,,{"separator":"\n\n---\n\n"},summary,NextStep,,result1|result2|result3,combined_results,
```

**Creating a Report with LLM:**
```csv
ReportFlow,GetData1,,Fetch financial data,ApiClient,Summarize,,query,financial_data,
ReportFlow,GetData2,,Fetch market data,ApiClient,Summarize,,query,market_data,
ReportFlow,GetData3,,Fetch competitor data,ApiClient,Summarize,,query,competitor_data,
ReportFlow,Summarize,,{"llm":"anthropic"},summary,Store,,financial_data|market_data|competitor_data,executive_summary,Create a concise executive summary of the financial, market, and competitor data. Highlight key insights and trends.
ReportFlow,Store,,Save the report,json_writer,,,executive_summary,report_status,
```

## OrchestratorAgent

The `OrchestratorAgent` is designed to dynamically route user input to the most appropriate node in your workflow based on intent matching. It uses LLMs or algorithmic matching to determine which node best matches the user's request.

### Key Features

- **Built-in Routing**: Automatically navigates to the selected node without requiring a separate routing function
- **Multiple Matching Strategies**: Choose between LLM-based, algorithmic, or tiered matching
- **Flexible Node Filtering**: Filter available nodes by type, specific list, or use all nodes
- **Confidence Thresholds**: Configure when to use LLM vs. algorithmic matching

### CSV Configuration

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
MyGraph,RouteIntent,,nodes:NodeA|NodeB|NodeC,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Route the user request to the appropriate node."
```

#### Context Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| nodes | Filter to specific nodes (pipe-separated) or "all" | "all" |
| nodeType | Filter nodes by type | |
| llm_type | LLM to use for matching ("openai", "anthropic", "google") | "openai" |
| temperature | Temperature setting for LLM | 0.2 |
| default_target | Default node if no match found | Success_Next |
| matching_strategy | Strategy to use ("tiered", "algorithm", or "llm") | "tiered" |
| confidence_threshold | Threshold for algorithmic confidence (0.0-1.0) | 0.8 |

#### Node Filtering Options

There are three ways to filter which nodes are available for the orchestrator:

1. **Specific List**: `nodes:NodeA|NodeB|NodeC` - Only include listed nodes
2. **By Type**: `nodeType:data_processor` - Only include nodes of specified type
3. **All Nodes**: `nodes:all` - Include all available nodes (default)

#### Input/Output Fields

The `OrchestratorAgent` expects:
- **First Input Field**: Location in state of available nodes (`available_nodes`)
- **Second Input Field**: Text input to match against node intents (`user_input`)
- **Output Field**: Where to store the selected node name

### Built-in Routing

The OrchestratorAgent has built-in routing capability. Unlike other agents that require explicit routing function definitions, the OrchestratorAgent will automatically:

1. Select the best node for the user input
2. Store this node name in the output field
3. Automatically navigate to that node in the graph

This means you do not need to use a routing function in the Edge column when using the OrchestratorAgent.

### Node Metadata

Each node in the available nodes dictionary has this structure:

```python
{
    "node_name": {
        "description": "Human-readable description of the node's purpose",
        "prompt": "The node's prompt from the CSV definition",
        "type": "The agent type of the node"
    }
}
```

The node registry is automatically populated from:
1. **description**: Extracted from the Context column's `description:` parameter
2. **prompt**: Directly from the node's Prompt column
3. **type**: Directly from the node's AgentType column

### Matching Strategies

#### Tiered Matching (Default)

Combines the speed of algorithmic matching with the intelligence of LLM matching:

1. First attempts algorithmic matching
2. If confidence exceeds threshold (default 0.8), uses that result
3. Otherwise, falls back to LLM-based matching

Example:
```csv
RouterFlow,RoutingNode,,matching_strategy:tiered,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

#### Algorithm-Only Matching

Uses only fast algorithmic matching without LLM calls:

1. Checks if node names appear in user input 
2. Otherwise, counts matching keywords between node prompts and user input
3. Returns the node with highest keyword match ratio

Example:
```csv
RouterFlow,RoutingNode,,matching_strategy:algorithm,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

#### LLM-Only Matching

Uses only LLM-based matching for highest quality but slower performance:

Example:
```csv
RouterFlow,RoutingNode,,matching_strategy:llm,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

### Usage Examples

#### General Intent Router

```csv
IntentRouter,RouteIntent,,nodes:AnswerQuestion|FetchData|GenerateReport,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Route the user request to the appropriate node."
```

#### Type-Based Router

```csv
DataProcessor,RouteDataOp,,nodeType:data_processor,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Select the appropriate data processing operation."
```

#### All Nodes Router

```csv
Router,RouteRequest,,nodes:all,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Route to the most appropriate node."
```

### Complete Workflow Example

```csv
Router,GetUserInput,,Get user request,Input,RouteRequest,,message,user_input,What would you like to do?
Router,RouteRequest,,nodes:all,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,Route to the appropriate node
Router,WeatherNode,,Get weather,Default,End,,location,weather,Getting weather for {location}
Router,NewsNode,,Get news,Default,End,,topic,news,Getting news about {topic}
Router,DefaultHandler,,Handle unmatched requests,Default,End,,user_input,response,I can't handle that request
Router,ErrorHandler,,Handle errors,Default,End,,error,error_message,An error occurred
Router,End,,End flow,Echo,,,response|weather|news|error_message,final_output,
```

In this example:
1. `GetUserInput` collects user input
2. `RouteRequest` (OrchestratorAgent) analyzes the input and selects the best node
3. The graph automatically navigates to the selected node
4. The selected node processes the input
5. All paths end at the `End` node which consolidates outputs

### Best Practices

1. **Descriptive Metadata**: Ensure each node has a clear description and prompt
2. **Unique Node Purposes**: Make each node's purpose distinct to avoid confusion
3. **Input Text Clarity**: Ensure the user input field contains the relevant text for matching
4. **Fallback Handling**: Set a default_target for cases where no good match is found
5. **Testing**: Test with a variety of inputs to ensure proper routing behavior

---
## Field Usage in AgentMap

This document explains how each field in the CSV is used by different components of AgentMap.

### GraphName

The `GraphName` field groups nodes together into a single workflow. When running a graph with `run_graph(graph_name)`, only nodes with the matching `GraphName` are included.

**Usage examples:**
- Create separate workflows in a single CSV file
- Organize related nodes under a common name

### Node

The `Node` field defines a unique identifier for each node in the graph. It is used:

- As an identifier in routing fields (`Edge`, `Success_Next`, `Failure_Next`)
- In logging and debugging to track execution flow
- As the default name for the agent instance

**Best practices:**
- Use descriptive names (e.g., "ProcessUserInput" instead of "Node1")
- Ensure uniqueness within a graph
- CamelCase or snake_case naming is recommended

### Edge vs Success_Next/Failure_Next

There are two routing methods in AgentMap:

#### Simple Routing with Edge

When `Edge` is specified, the node will always proceed to the target node:

```csv
GraphA,Start,Next,,...
GraphA,Next,End,...
GraphA,End,,...
```

#### Conditional Routing with Success_Next/Failure_Next

When `Success_Next` and/or `Failure_Next` are specified, routing depends on the `last_action_success` flag:

```csv
GraphA,Start,,,...,Next,ErrorHandler,...
GraphA,Next,,,...,End,ErrorHandler,...
GraphA,End,,,...,,,,...
GraphA,ErrorHandler,,,...,End,,,...
```

The node's `run` method sets `last_action_success` to `True` by default, or `False` if an error occurs.

### Advanced Routing with Functions

For complex routing logic, use function references:

```csv
GraphA,Start,func:choose_route,...
```

The function should be defined in the `functions` directory with this signature:

```python
def choose_route(state: Any, success_node: str = "Success", failure_node: str = "Failure") -> str:
    # Custom routing logic
    return next_node_name
```

## Context and Description

The `Context` and `Description` fields serve different but complementary purposes:

### Context
The Context field can contain:
1. **Text description** - For basic documentation
2. **JSON configuration** - For advanced agent configuration

**JSON configuration example:**
```csv
GraphA,MemoryNode,,{"memory":{"type":"buffer","memory_key":"chat_history"}},...
```

### Description
The Description field is purely for documentation purposes:
1. **Node purpose** - What the node is meant to accomplish
2. **Implementation notes** - Details about how the node operates
3. **Developer documentation** - Notes for other developers

**Example:**
```csv
GraphA,ProcessInput,,{"memory":{"type":"buffer"}},"This node extracts key entities from user input and classifies the intent. Used for routing to appropriate handler nodes.",...
```

Common JSON configurations for Context:
- Memory settings for LLM agents
- Vector database configurations
- Storage settings

## AgentType

The `AgentType` field determines which agent implementation to use. Available types include:

- `default` - Simple output agent
- `echo` - Returns input unchanged
- `openai`, `claude`, `gemini` - LLM agents
- `branching`, `success`, `failure` - Testing agents
- `input` - User input agent
- `csv_reader`, `csv_writer` - CSV file operations
- `json_reader`, `json_writer` - JSON file operations
- `file_reader`, `file_writer` - File operations
- Custom agent types with `scaffold` command

If not specified, defaults to `default`.

## Input_Fields and Output_Field

These fields control data flow between nodes:

### Input_Fields

A pipe-separated list of fields to extract from state:

```csv
GraphA,Node1,,,...,,,"input|context|history",response,...
```

Special formats:
- **Field mapping** - Map input fields to different names: `target=source`
- **Function mapping** - Transform inputs with a function: `func:transform_inputs`

### Output_Field

The field where the agent's output will be stored:

```csv
GraphA,Node1,,,...,,,input,response,...
```

**Data flow example:**
```
Node1(output_field=result1) → Node2(input_fields=result1, output_field=result2) → Node3(input_fields=result2)
```

## Prompt

The `Prompt` field serves different purposes depending on the agent type:

1. **LLM Agents** - Template string with placeholders for input values:
   ```
   Answer this question: {question}
   ```

2. **Default/Echo Agents** - Text to include in output message

3. **GraphAgent** - Name of the subgraph to execute

4. **Storage Agents** - Optional path or configuration

5. **Prompt References** - References to managed prompts:
   ```
   prompt:system_instructions
   file:prompts/system.txt
   yaml:prompts/system.yaml#instructions.default
   ```


---

[↑ Back to Index](index.md) | [← Previous: AgentMap Agent Types](agentmap_agent_types.md) | [Next: State Management and Data Flow →](state_management_and_data_flow.md)