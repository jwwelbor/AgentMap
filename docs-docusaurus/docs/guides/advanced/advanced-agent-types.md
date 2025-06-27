---
title: "Advanced Agent Types"
description: "Comprehensive guide to AgentMap's advanced agents including GraphAgent, SummaryAgent, OrchestratorAgent, and complete context configuration reference for all agent types."
keywords:
  - advanced agents
  - GraphAgent
  - SummaryAgent
  - OrchestratorAgent
  - context configuration
  - agent routing
  - LLM agents
  - storage agents
  - field configuration
sidebar_position: 2
---

# Advanced Agent Types

This guide covers AgentMap's most sophisticated agents and provides comprehensive context configuration reference for building powerful, intelligent workflows.

:::info Related Documentation
- [Agent Development Contract](./agent-development-contract) - Agent interface requirements and patterns
- [Service Injection Patterns](./service-injection-patterns) - Dependency injection system for services
- [Reference: Agent Types](../../reference/agent-types) - Basic agent types and usage patterns
:::

## GraphAgent

Executes a subgraph and returns its result, enabling hierarchical workflow composition and reusable workflow modules.

- **Input Fields**: Passed to the subgraph
- **Output Field**: Result from the subgraph
- **Prompt Usage**: Name of the subgraph to execute

### Usage Example

```csv title="GraphAgent Configuration"
MainFlow,ProcessUser,ProcessingSubflow,,graph,Summarize,,user_input,processed_data,UserProcessingFlow
MainFlow,Summarize,,{"format": "User: {processed_data}"},summary,End,,processed_data,final_output,
```

## SummaryAgent

Combines and summarizes multiple input fields into a single output. Useful for consolidating outputs from parallel operations or creating concise summaries from multiple data sources.

- **Input Fields**: Multiple fields to be summarized (pipe-separated list)
- **Output Field**: Single field for the consolidated output
- **Prompt Usage**: Instructions for LLM-based summarization
- **Context**: Can contain configuration for formatting and LLM usage

The SummaryAgent operates in two modes:

### 1. Basic Concatenation Mode (Default)

Simply formats and joins the input fields according to templates.

```csv title="Basic Concatenation Example"
TestGraph,Summarize,,{"format":"{key}: {value}","separator":"\n\n"},summary,Next,,field1|field2|field3,summary_output,
```

**Configuration options:**
- `format`: Template for formatting each item (default: `"{key}: {value}"`)
- `separator`: String used to join formatted items (default: `"\n\n"`)
- `include_keys`: Whether to include field names in output (default: `true`)

### 2. LLM Summarization Mode

Uses an LLM to create an intelligent summary of the inputs.

```csv title="LLM Summarization Example"
TestGraph,Summarize,,{"llm":"openai","model":"gpt-3.5-turbo"},summary,Next,,field1|field2|field3,summary_output,Create a concise summary of these data points.
```

**LLM Configuration options:**
- `llm`: LLM provider to use (`"openai"`, `"anthropic"`, or `"google"`)
- `model`: Specific model to use (optional)
- `temperature`: Temperature for generation (optional)

The prompt field provides instructions to the LLM on how to create the summary.

### Usage Patterns

**Summarizing Parallel Branch Results:**
```csv title="Parallel Processing Summary"
ParallelFlow,Branch1,,Process first set of data,Default,Join,,input,result1,
ParallelFlow,Branch2,,Process second set of data,Default,Join,,input,result2,
ParallelFlow,Branch3,,Process third set of data,Default,Join,,input,result3,
ParallelFlow,Join,,{"separator":"\n\n---\n\n"},summary,NextStep,,result1|result2|result3,combined_results,
```

**Creating a Report with LLM:**
```csv title="Executive Report Generation"
ReportFlow,GetData1,,Fetch financial data,ApiClient,Summarize,,query,financial_data,
ReportFlow,GetData2,,Fetch market data,ApiClient,Summarize,,query,market_data,
ReportFlow,GetData3,,Fetch competitor data,ApiClient,Summarize,,query,competitor_data,
ReportFlow,Summarize,,{"llm":"anthropic"},summary,Store,,financial_data|market_data|competitor_data,executive_summary,Create a concise executive summary of the financial market and competitor data. Highlight key insights and trends.
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

```csv title="OrchestratorAgent Basic Configuration"
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

```python title="Node Metadata Structure"
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

```csv title="Tiered Matching Configuration"
RouterFlow,RoutingNode,,matching_strategy:tiered,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

#### Algorithm-Only Matching

Uses only fast algorithmic matching without LLM calls:

1. Checks if node names appear in user input 
2. Otherwise, counts matching keywords between node prompts and user input
3. Returns the node with highest keyword match ratio

```csv title="Algorithm-Only Configuration"
RouterFlow,RoutingNode,,matching_strategy:algorithm,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

#### LLM-Only Matching

Uses only LLM-based matching for highest quality but slower performance:

```csv title="LLM-Only Configuration"
RouterFlow,RoutingNode,,matching_strategy:llm,orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

### Usage Examples

#### General Intent Router

```csv title="General Intent Routing"
IntentRouter,RouteIntent,,nodes:AnswerQuestion|FetchData|GenerateReport,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Route the user request to the appropriate node."
```

#### Type-Based Router

```csv title="Type-Based Routing"
DataProcessor,RouteDataOp,,nodeType:data_processor,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Select the appropriate data processing operation."
```

#### All Nodes Router

```csv title="Universal Router"
Router,RouteRequest,,nodes:all,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,"Route to the most appropriate node."
```

### Complete Workflow Example

```csv title="Complete Orchestrator Workflow"
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

## Context Configuration Reference

The `Context` field in CSV configurations accepts JSON objects that control agent behavior. This section provides a comprehensive reference for all available context configuration options organized by agent type.

### General Context Patterns

Context configurations follow these patterns:

**Simple Configuration:**
```csv title="Simple Context"
MyGraph,Node1,,{"temperature":0.5},llm,Next,,input,output,Your prompt here
```

**Complex Configuration:**
```csv title="Complex Context"
MyGraph,Node1,,{"routing_enabled":true,"task_type":"analysis","memory_key":"conversation","max_memory_messages":10},llm,Next,,input|conversation,output,Your prompt here
```

### LLM Agent Context Configuration

LLM agents support two operational modes with different configuration options.

#### Legacy Mode (Direct Provider)

For direct control over LLM provider and model selection:

```json title="Direct Provider Configuration"
{
  "provider": "anthropic",
  "model": "claude-3-sonnet-20240229",
  "temperature": 0.7,
  "max_tokens": 1000,
  "api_key": "your-api-key"
}
```

**Configuration Options:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `provider` | LLM provider to use | `"anthropic"` | `"openai"`, `"anthropic"`, `"google"` |
| `model` | Specific model name | Provider default | Provider-specific model names |
| `temperature` | Randomness in generation | `0.7` | `0.0` - `2.0` |
| `max_tokens` | Maximum tokens to generate | Provider default | Integer |
| `api_key` | API key (optional if in env) | Environment variable | String |

**Example:**
```csv title="Direct Provider Example"
Analysis,LLMNode,,{"provider":"openai","model":"gpt-4","temperature":0.3},llm,Next,,query,analysis,Analyze this data and provide insights.
```

#### Routing Mode (Intelligent Selection)

For automatic provider and model selection based on task complexity:

```json title="Intelligent Routing Configuration"
{
  "routing_enabled": true,
  "task_type": "analysis",
  "complexity_override": "high",
  "provider_preference": ["anthropic", "openai"],
  "cost_optimization": true,
  "prefer_quality": true
}
```

**Core Routing Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `routing_enabled` | Enable intelligent routing | `false` | `true`, `false` |
| `task_type` | Type of task for optimization | `"general"` | `"analysis"`, `"creative"`, `"factual"`, `"coding"` |
| `complexity_override` | Force complexity level | Auto-detect | `"low"`, `"medium"`, `"high"` |
| `auto_detect_complexity` | Auto-detect task complexity | `true` | `true`, `false` |

**Provider Selection:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `provider_preference` | Preferred providers in order | `[]` | Array of provider names |
| `excluded_providers` | Providers to exclude | `[]` | Array of provider names |
| `model_override` | Force specific model | None | Model name string |
| `fallback_provider` | Fallback if preferred unavailable | `"anthropic"` | Provider name |
| `fallback_model` | Fallback model | Provider default | Model name |

**Optimization Settings:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `max_cost_tier` | Maximum cost tier to use | None | `1`, `2`, `3`, `4` |
| `cost_optimization` | Optimize for cost | `true` | `true`, `false` |
| `prefer_speed` | Prioritize response speed | `false` | `true`, `false` |
| `prefer_quality` | Prioritize output quality | `false` | `true`, `false` |
| `retry_with_lower_complexity` | Retry with simpler model on failure | `true` | `true`, `false` |

**Advanced Routing Example:**
```csv title="Advanced Routing Configuration"
ComplexAnalysis,AnalyzeData,,{"routing_enabled":true,"task_type":"analysis","provider_preference":["anthropic","openai"],"max_cost_tier":3,"prefer_quality":true},llm,Summary,,data|context,analysis,Perform deep analysis on this dataset.
```

#### Memory Configuration

Both modes support memory management for conversational agents:

```json title="Memory Configuration"
{
  "memory_key": "chat_history",
  "max_memory_messages": 20
}
```

**Memory Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `memory_key` | State field for conversation memory | `"memory"` | String |
| `max_memory_messages` | Max messages to retain | None (unlimited) | Integer |

**Memory Example:**
```csv title="Conversational Agent with Memory"
Chatbot,ChatNode,,{"provider":"anthropic","memory_key":"conversation","max_memory_messages":10},llm,ChatNode,,user_input|conversation,response,You are a helpful assistant.
```

#### Debugging Configuration

For debugging and development:

```json title="Debug Configuration"
{
  "debug_routing": true,
  "log_model_selection": true,
  "log_token_usage": true
}
```

### SummaryAgent Context Configuration

SummaryAgent operates in two modes: basic concatenation and LLM-powered summarization.

#### Basic Mode Configuration

```json title="Basic Summary Configuration"
{
  "format": "{key}: {value}",
  "separator": "\n\n",
  "include_keys": true
}
```

**Basic Mode Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `format` | Template for each item | `"{key}: {value}"` | Template string |
| `separator` | String between items | `"\n\n"` | String |
| `include_keys` | Include field names | `true` | `true`, `false` |

#### LLM Mode Configuration

```json title="LLM Summary Configuration"
{
  "llm": "anthropic",
  "model": "claude-3-sonnet-20240229",
  "temperature": 0.3
}
```

**LLM Mode Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `llm` | LLM provider for summarization | None | `"openai"`, `"anthropic"`, `"google"` |
| `model` | Specific model to use | Provider default | Model name |
| `temperature` | Generation temperature | `0.7` | `0.0` - `2.0` |

**Example Configurations:**

**Basic formatting:**
```csv title="Basic Summary Formatting"
Report,Combine,,{"format":"**{key}**: {value}","separator":"\n---\n"},summary,Save,,section1|section2|section3,combined,
```

**LLM summarization:**
```csv title="Intelligent Summary Generation"
Report,Summarize,,{"llm":"anthropic","temperature":0.3},summary,Save,,research|analysis|conclusions,executive_summary,Create a concise executive summary highlighting key findings and recommendations.
```

### OrchestratorAgent Context Configuration

Orchestrator agents route requests to appropriate nodes using various matching strategies.

#### Core Configuration

```json title="Orchestrator Core Configuration"
{
  "matching_strategy": "tiered",
  "confidence_threshold": 0.8,
  "default_target": "DefaultHandler"
}
```

**Core Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `matching_strategy` | Matching approach | `"tiered"` | `"algorithm"`, `"llm"`, `"tiered"` |
| `confidence_threshold` | Threshold for algorithm match | `0.8` | `0.0` - `1.0` |
| `default_target` | Fallback node | `Success_Next` | Node name |

#### Node Filtering

```json title="Node Filtering Configuration"
{
  "nodes": "ProcessData|AnalyzeData|GenerateReport",
  "nodeType": "data_processor"
}
```

**Filtering Parameters:**

| Parameter | Description | Options |
|-----------|-------------|----------|
| `nodes` | Specific nodes to consider | Pipe-separated names or `"all"` |
| `nodeType` | Filter by agent type | Agent type string |

#### LLM Configuration (for LLM/Tiered modes)

```json title="Orchestrator LLM Configuration"
{
  "llm_type": "openai",
  "temperature": 0.2
}
```

**LLM Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `llm_type` | LLM provider for matching | `"openai"` | `"openai"`, `"anthropic"`, `"google"` |
| `temperature` | LLM generation temperature | `0.2` | `0.0` - `2.0` |

**Strategy Examples:**

**Algorithm-only (fast):**
```csv title="Fast Algorithmic Routing"
Router,Route,,{"matching_strategy":"algorithm","nodes":"DataProcessor|ReportGenerator"},orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

**LLM-only (accurate):**
```csv title="Accurate LLM Routing"
Router,Route,,{"matching_strategy":"llm","llm_type":"anthropic","temperature":0.1},orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

**Tiered (balanced):**
```csv title="Balanced Tiered Routing"
Router,Route,,{"matching_strategy":"tiered","confidence_threshold":0.9},orchestrator,Default,Error,available_nodes|user_input,selected_node,
```

### Storage Agent Context Configuration

Storage agents support various configuration options depending on the storage type.

#### Vector Storage Configuration

```json title="Vector Storage Configuration"
{
  "k": 5,
  "metadata_keys": ["source", "timestamp"],
  "collection": "documents"
}
```

**Vector Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `k` | Number of results to return | `4` | Integer |
| `metadata_keys` | Metadata fields to include | None | Array of strings |
| `collection` | Vector collection name | Required | String |

#### File Storage Configuration

```json title="File Storage Configuration"
{
  "path": "outputs/",
  "filename_template": "{timestamp}_{name}.txt",
  "encoding": "utf-8"
}
```

#### CSV Storage Configuration

```json title="CSV Storage Configuration"
{
  "delimiter": ",",
  "quoting": "minimal",
  "headers": true
}
```

### Input/Output Field Configuration

All agents support input/output field configuration through context:

```json title="Field Configuration"
{
  "input_fields": ["query", "context", "memory"],
  "output_field": "response"
}
```

**Field Parameters:**

| Parameter | Description | Default | Options |
|-----------|-------------|---------|----------|
| `input_fields` | Fields to extract from state | From CSV | Array of field names |
| `output_field` | Field to store result | From CSV | Field name |

### Best Practices for Context Configuration

1. **Start Simple**: Begin with basic configurations and add complexity as needed
2. **Test Configurations**: Use small test cases to validate configuration behavior
3. **Document Choices**: Comment complex configurations in your CSV descriptions
4. **Use Routing Wisely**: Enable routing for complex tasks, use direct providers for simple ones
5. **Memory Management**: Set reasonable memory limits to control costs and context size
6. **Error Handling**: Always specify fallback options for critical paths

### Configuration Validation

AgentMap validates context configurations at runtime. Common validation errors:

- **Invalid JSON**: Context must be valid JSON format
- **Unknown Parameters**: Unrecognized parameters are logged as warnings
- **Type Mismatches**: Parameters must match expected types (e.g., numbers for temperature)
- **Required Services**: Some configurations require specific services to be available

### Debugging Context Issues

To debug context configuration problems:

1. **Check Logs**: Context validation errors appear in agent logs
2. **Test Incrementally**: Add configuration options one at a time
3. **Verify JSON**: Use a JSON validator to check syntax
4. **Review Defaults**: Understand which values are defaults vs. configured

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

```csv title="Simple Edge Routing"
GraphA,Start,Next,,...
GraphA,Next,End,...
GraphA,End,,...
```

#### Conditional Routing with Success_Next/Failure_Next

When `Success_Next` and/or `Failure_Next` are specified, routing depends on the `last_action_success` flag:

```csv title="Conditional Routing"
GraphA,Start,,,...,Next,ErrorHandler,...
GraphA,Next,,,...,End,ErrorHandler,...
GraphA,End,,,...,,,,...
GraphA,ErrorHandler,,,...,End,,,...
```

The node's `run` method sets `last_action_success` to `True` by default, or `False` if an error occurs.

### Advanced Routing with Functions

For complex routing logic, use function references:

```csv title="Function-Based Routing"
GraphA,Start,func:choose_route,...
```

The function should be defined in the `functions` directory with this signature:

```python title="Custom Routing Function"
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
```csv title="JSON Context Configuration"
GraphA,MemoryNode,,{"memory":{"type":"buffer","memory_key":"chat_history"}},...
```

### Description
The Description field is purely for documentation purposes:
1. **Node purpose** - What the node is meant to accomplish
2. **Implementation notes** - Details about how the node operates
3. **Developer documentation** - Notes for other developers

**Example:**
```csv title="Context and Description Example"
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

```csv title="Input Fields Configuration"
GraphA,Node1,,,...,,,"input|context|history",response,...
```

Special formats:
- **Field mapping** - Map input fields to different names: `target=source`
- **Function mapping** - Transform inputs with a function: `func:transform_inputs`

### Output_Field

The field where the agent's output will be stored:

```csv title="Output Field Configuration"
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

## Related Documentation

### 🚀 **Getting Started**
- **[Quick Start Guide](../../getting-started/quick-start)**: Build your first workflow in 5 minutes
- **[Understanding Workflows](../understanding-workflows)**: Core workflow concepts and interactive examples
- **[CSV Schema Reference](../../reference/csv-schema)**: Complete workflow format specification

### 🤖 **Agent Development**
- **[Agent Development Contract](./agent-development-contract)**: Required interface and patterns for all agents
- **[Service Injection Patterns](./service-injection-patterns)**: Protocol-based dependency injection system
- **[Reference: Agent Types](../../reference/agent-types)**: Basic agent types and usage patterns
- **[Agent Catalog](../../reference/agent-catalog)**: Comprehensive agent reference

### 💻 **Tools & Development**
- **[CLI Commands](../../reference/cli-commands)**: Complete command-line reference
- **[CLI Graph Inspector](../../reference/cli-graph-inspector)**: Debug and analyze workflows
- **[Interactive Playground](../../playground)**: Test workflows in your browser

### 🏗️ **Advanced Topics**
- **[Memory Management](./memory-and-orchestration/memory-management)**: Persistent state across workflow runs
- **[Host Service Integration](./host-service-integration)**: Custom service integration
- **[State Management](../state-management)**: How data flows between agents

### 📚 **Tutorials & Examples**
- **[Weather Bot Tutorial](../../tutorials/weather-bot)**: Custom agent development example
- **[Data Processing Pipeline](../../tutorials/data-processing-pipeline)**: Advanced agent orchestration
- **[Customer Support Bot](../../tutorials/customer-support-bot)**: OrchestratorAgent usage patterns
- **[Example Workflows](../../examples/)**: Real-world advanced agent examples

### 🏗️ **Architecture**
- **[Clean Architecture Overview](../../advanced/architecture/clean-architecture-overview)**: System architecture principles
- **[Service Catalog](../../advanced/architecture/service-catalog)**: Complete service reference
