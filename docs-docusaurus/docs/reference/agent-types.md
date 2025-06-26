---
sidebar_position: 3
title: Agent Types Reference
description: Complete reference for all available AgentMap agent types
---

# Agent Types Reference

> **Related Documentation**: 
> - [Clean Architecture Overview](../advanced/architecture/clean-architecture-overview.md) - System architecture and design patterns
> - [Service Catalog](../advanced/architecture/service-catalog.md) - Available services and protocols

AgentMap includes several built-in agent types for different purposes. Each agent type uses the modern protocol-based dependency injection pattern with infrastructure services injected via constructor and business services configured post-construction.

## Modern Agent Architecture

All AgentMap agents follow the clean architecture pattern:

- **Infrastructure Services**: Core services injected via constructor (logger, execution_tracker_service, state_adapter_service)
- **Business Services**: Specialized services configured via protocols (LLM, storage, prompt management)
- **Context Configuration**: Service settings and agent behavior configured via context

## Core Agent Types

### DefaultAgent

The simplest agent that logs its execution and returns a message with the prompt.

- **Input Fields**: Any (unused)
- **Output Field**: Returns a message including the agent's prompt
- **Prompt Usage**: Included in output message
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: None required

**CSV Example:**
```csv
TestGraph,Start,,Basic node,default,Next,,input,output,Hello World
```

### EchoAgent

Simply returns the input data unchanged.

- **Input Fields**: Returns the first input field it finds
- **Output Field**: The input data unchanged
- **Prompt Usage**: Ignored
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: None required

**CSV Example:**
```csv
TestGraph,Echo,,Echo node,echo,Next,,message,response,
```

### BranchingAgent

Used for testing conditional routing. Checks for success/failure indicators in inputs.

- **Input Fields**: Looks for `success`, `should_succeed`, `succeed`, or `branch` fields
- **Output Field**: Message describing the branching decision
- **Prompt Usage**: Included in output message
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: None required

**CSV Example:**
```csv
TestGraph,Branch,,Decision point,branching,SuccessPath,FailurePath,input,decision,Make a choice
```

### SuccessAgent and FailureAgent

Testing agents that always succeed or fail.

- **Input Fields**: Any (unused)
- **Output Field**: Confirmation message
- **Prompt Usage**: Included in output message
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: None required

**SuccessAgent Example:**
```csv
TestGraph,AlwaysSucceed,,Success node,success,Next,,input,result,I always succeed
```

**FailureAgent Example:**
```csv
TestGraph,AlwaysFail,,Failure node,failure,Next,,input,result,I always fail
```

### InputAgent

Prompts for user input during execution.

- **Input Fields**: Any (unused)
- **Output Field**: User's input response
- **Prompt Usage**: Shown to user as input prompt
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: None required

**CSV Example:**
```csv
TestGraph,GetInput,,User input node,input,Process,,message,user_input,Please enter your name:
```

## LLM Agent Types

All LLM agents implement the `LLMCapableAgent` protocol and require LLM service configuration.

### LLMAgent (Base LLM Agent)

Uses configurable LLM providers for text generation with intelligent routing support.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template or system message
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter, PromptManager (optional)
- **Business Services**: LLMService (configured via LLMCapableAgent protocol)
- **Protocol Implementation**: LLMCapableAgent, PromptCapableAgent

**Context Configuration Options:**
```python
context = {
    # Core configuration
    "input_fields": ["question"], 
    "output_field": "response",
    
    # LLM Routing (Modern approach)
    "routing_enabled": True,
    "task_type": "analysis",  # analysis, generation, conversation, etc.
    "complexity_override": "high",  # low, medium, high
    "provider_preference": ["anthropic", "openai"],
    "excluded_providers": ["google"],
    "cost_optimization": True,
    "prefer_quality": True,
    
    # Legacy mode (Direct provider specification)
    "provider": "anthropic",
    "model": "claude-3-sonnet-20240229", 
    "temperature": 0.7,
    "max_tokens": 1000,
    
    # Memory configuration
    "memory_key": "chat_history",
    "max_memory_messages": 10,
    
    # Prompt management
    "prompt_template": "prompt:analysis_template"
}
```

**CSV Examples:**

**Modern Routing Mode:**
```csv
QAGraph,Question,{"routing_enabled": true, "task_type": "analysis"},Ask a question,llm,Answer,,question,response,Answer this question: {question}
```

**Legacy Provider Mode:**
```csv
QAGraph,Question,{"provider": "anthropic", "model": "claude-3-sonnet-20240229"},Ask a question,llm,Answer,,question,response,Answer this question: {question}
```

### OpenAIAgent (aliases: gpt, chatgpt)

Backward compatibility wrapper for LLMAgent with OpenAI provider.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: LLMService (configured automatically to use OpenAI)
- **Protocol Implementation**: LLMCapableAgent

**CSV Example:**
```csv
QAGraph,Question,{"model": "gpt-4", "temperature": 0.7},Ask a question,openai,Answer,,question,response,Answer this question: {question}
```

### AnthropicAgent (alias: claude)

Backward compatibility wrapper for LLMAgent with Anthropic provider.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: LLMService (configured automatically to use Anthropic)
- **Protocol Implementation**: LLMCapableAgent

**CSV Example:**
```csv
QAGraph,Summarize,{"model": "claude-3-sonnet-20240229"},Summarize text,claude,Next,,text,summary,Summarize this text in 3 bullet points: {text}
```

### GoogleAgent (alias: gemini)

Backward compatibility wrapper for LLMAgent with Google provider.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: LLMService (configured automatically to use Google)
- **Protocol Implementation**: LLMCapableAgent

**CSV Example:**
```csv
QAGraph,Generate,{"model": "gemini-1.0-pro"},Generate content,gemini,Next,,prompt,content,Generate content based on: {prompt}
```

## Storage Agent Types

All storage agents implement the `StorageCapableAgent` protocol and require storage service configuration.

### CSVReaderAgent and CSVWriterAgent

Read from and write to CSV files using the unified storage system.

- **Input Fields**: Must contain `collection` (file path), optional `document_id`, `query`, `path`
- **Output Field**: For reader: CSV data, For writer: Operation result
- **Prompt Usage**: Optional CSV path override
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, CSVCapableAgent

**Context Configuration Options:**
```python
context = {
    "input_fields": ["collection", "document_id", "query"],
    "output_field": "data",
    "format": "records",  # records, list, dict, raw
    "id_field": "id",
    "encoding": "utf-8",
    "delimiter": ",",
    "quotechar": '"'
}
```

**CSV Examples:**
```csv
DataGraph,ReadCustomers,{"format": "records", "id_field": "customer_id"},Read customer data,csv_reader,Process,,collection,customers,data/customers.csv
DataGraph,WriteResults,{"format": "records", "mode": "write"},Write processed data,csv_writer,End,,data,result,data/output.csv
```

### JSONDocumentReaderAgent and JSONDocumentWriterAgent

Read from and write to JSON files using the unified storage system.

- **Input Fields**: Must contain `collection` (file path), optional `document_id`, `path`
- **Output Field**: For reader: JSON data, For writer: Operation result
- **Prompt Usage**: Optional JSON path override
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, JSONCapableAgent

**CSV Examples:**
```csv
ConfigGraph,ReadConfig,{"format": "dict", "encoding": "utf-8"},Read configuration,json_reader,Process,,collection,config,config/app.json
ConfigGraph,SaveState,{"format": "dict", "indent": 2},Save application state,json_writer,End,,state,result,data/state.json
```

### VectorReaderAgent and VectorWriterAgent

Work with vector databases and embeddings for semantic search and document retrieval.

- **Input Fields**: For reader: `query` for similarity search, For writer: document data
- **Output Field**: For reader: Retrieved documents, For writer: Operation status
- **Prompt Usage**: Optional configuration override
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, VectorCapableAgent

**Context Configuration Options:**
```python
context = {
    "input_fields": ["query", "documents"],
    "output_field": "search_results",
    "provider": "chroma",
    "embedding_model": "text-embedding-ada-002",
    "persist_directory": "./vector_db",
    "collection_name": "documents",
    "similarity_threshold": 0.8,
    "max_results": 10
}
```

**CSV Examples:**
```csv
VectorGraph,LoadDocs,{"provider": "chroma", "embedding_model": "text-embedding-ada-002"},Load documents into vector store,vector_writer,Search,,documents,load_result,
VectorGraph,Search,{"similarity_threshold": 0.8, "max_results": 5},Search for similar documents,vector_reader,Process,,query,search_results,
```

## File Agents

### FileReaderAgent

The FileReaderAgent reads and processes various document types with optional chunking and filtering.

- **Supported File Formats**: Text, PDF, Markdown, HTML, Word documents
- **Input Fields**: `collection` (file path), optional `document_id`, `query`, `path`, `format`
- **Output Field**: Document data with metadata
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, FileCapableAgent

**Context Configuration Options:**
```python
context = {
    "input_fields": ["collection"],
    "output_field": "documents",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "should_split": True,
    "include_metadata": True,
    "format": "default"  # default, raw, text
}
```

**CSV Example:**
```csv
DocGraph,ReadDocs,{"chunk_size": 1000, "chunk_overlap": 200, "should_split": true},Read documents,file_reader,Process,,collection,documents,
```

### FileWriterAgent

The FileWriterAgent writes content to various text-based formats with different write modes.

- **Supported File Formats**: Text, Markdown, HTML, CSV, Log files, Code files
- **Input Fields**: `collection` (file path), `data` (content), optional `mode`
- **Output Field**: Write operation result
- **Write Modes**: write, append, update, delete
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, FileCapableAgent

**CSV Example:**
```csv
DocGraph,WriteFile,{"mode": "write", "encoding": "utf-8"},Write document,file_writer,Next,,data,result,path/to/output.txt
```

## Specialized Agents

### GraphAgent

Executes a subgraph and returns its result. Useful for modular workflow design and reusable sub-processes.

- **Input Fields**: Passed to the subgraph
- **Output Field**: Result from the subgraph  
- **Prompt Usage**: Name of the subgraph to execute
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: GraphRunnerService (configured automatically)

**CSV Example:**
```csv
MainFlow,ProcessData,,Execute data processing subgraph,graph,CombineResults,Error,input_data,processed_data,DataProcessingGraph
```

### SummaryAgent

Combines and summarizes multiple input fields into a single output. Useful for consolidating outputs from parallel operations or creating concise summaries from multiple data sources.

- **Input Fields**: Multiple fields to be summarized (pipe-separated list)
- **Output Field**: Single field for the consolidated output
- **Prompt Usage**: Instructions for LLM-based summarization (when using LLM mode)
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: LLMService (when using LLM mode)
- **Protocol Implementation**: LLMCapableAgent (when using LLM mode)

#### Basic Concatenation Mode (Default)

Simply formats and joins the input fields according to templates.

**Context Configuration Options:**
```python
context = {
    "format": "{key}: {value}",        # Template for formatting each item
    "separator": "\n\n",              # String used to join formatted items
    "include_keys": True               # Whether to include field names in output
}
```

**CSV Example:**
```csv
DataGraph,Combine,{"format":"{key}: {value}","separator":"\n\n---\n\n"},Combine results,summary,Next,Error,result_a|result_b|result_c,combined_results,
```

#### LLM Summarization Mode

Uses an LLM to create an intelligent summary of the inputs.

**Context Configuration Options:**
```python
context = {
    "llm": "anthropic",               # LLM provider ("openai", "anthropic", "google")
    "model": "claude-3-sonnet-20240229",  # Specific model to use (optional)
    "temperature": 0.3                # Temperature for generation (optional)
}
```

**CSV Example:**
```csv
ReportFlow,ExecutiveSummary,{"llm":"anthropic","temperature":0.3},Create executive summary,summary,Store,Error,financial_data|market_data|competitor_data,executive_summary,Create a concise executive summary highlighting key insights and trends from the financial, market, and competitor data.
```

### OrchestratorAgent

Dynamically routes user input to the most appropriate node in your workflow based on intent matching. Uses LLMs or algorithmic matching to determine which node best matches the user's request.

- **Input Fields**: First field = available nodes, Second field = user input text
- **Output Field**: Selected node name
- **Prompt Usage**: Instructions for routing logic
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: LLMService (when using LLM or tiered matching)
- **Protocol Implementation**: LLMCapableAgent (when using LLM modes)
- **Built-in Routing**: Automatically navigates to selected node without separate routing function

#### Key Features
- **Multiple Matching Strategies**: Choose between LLM-based, algorithmic, or tiered matching
- **Flexible Node Filtering**: Filter available nodes by type, specific list, or use all nodes
- **Confidence Thresholds**: Configure when to use LLM vs. algorithmic matching
- **Automatic Navigation**: Built-in routing to selected node

#### Context Configuration Options

**Core Parameters:**
```python
context = {
    "matching_strategy": "tiered",     # "algorithm", "llm", or "tiered"
    "confidence_threshold": 0.8,       # Threshold for algorithmic confidence (0.0-1.0)
    "default_target": "DefaultHandler", # Fallback node if no match found
    
    # Node filtering options
    "nodes": "NodeA|NodeB|NodeC",      # Specific nodes or "all"
    "nodeType": "data_processor",      # Filter by agent type
    
    # LLM configuration (for LLM/tiered modes)
    "llm_type": "openai",             # LLM provider
    "temperature": 0.2                # LLM generation temperature
}
```

#### Matching Strategies

**Tiered Matching (Default)**
Combines speed of algorithmic matching with intelligence of LLM matching:
1. First attempts algorithmic matching
2. If confidence exceeds threshold, uses that result
3. Otherwise, falls back to LLM-based matching

**Algorithm-Only Matching**
Uses only fast algorithmic matching without LLM calls:
1. Checks if node names appear in user input
2. Counts matching keywords between node prompts and user input
3. Returns node with highest keyword match ratio

**LLM-Only Matching**
Uses only LLM-based matching for highest quality but slower performance.

#### CSV Examples

**General Intent Router:**
```csv
IntentRouter,RouteIntent,{"nodes":"AnswerQuestion|FetchData|GenerateReport"},Route user requests,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,Route the user request to the appropriate node.
```

**Type-Based Router:**
```csv
DataProcessor,RouteDataOp,{"nodeType":"data_processor","matching_strategy":"algorithm"},Select data operation,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,Select the appropriate data processing operation.
```

**Tiered Matching:**
```csv
Router,RouteRequest,{"matching_strategy":"tiered","confidence_threshold":0.9},Smart routing,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,Route to the most appropriate node.
```

#### Complete Workflow Example

```csv
Router,GetUserInput,,Get user request,input,RouteRequest,,message,user_input,What would you like to do?
Router,RouteRequest,{"nodes":"all"},Route to appropriate node,orchestrator,DefaultHandler,ErrorHandler,available_nodes|user_input,selected_node,Route to the appropriate node
Router,WeatherNode,,Get weather information,default,End,,location,weather,Getting weather for {location}
Router,NewsNode,,Get latest news,default,End,,topic,news,Getting news about {topic}
Router,DefaultHandler,,Handle unmatched requests,default,End,,user_input,response,I can't handle that request
Router,ErrorHandler,,Handle errors,default,End,,error,error_message,An error occurred
Router,End,,End workflow,echo,,,response|weather|news|error_message,final_output,
```

## Testing and Development

### Testing Agents

For development and testing purposes:

- **SuccessAgent**: Always succeeds (useful for testing success paths)
- **FailureAgent**: Always fails (useful for testing error handling)
- **BranchingAgent**: Conditional routing based on input values
- **EchoAgent**: Returns input unchanged (useful for debugging data flow)

### Custom Agent Development

Create custom agents by extending `BaseAgent`:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class CustomAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        # Your custom logic here
        return processed_result
```

Use the scaffolding system to generate templates:

```bash
agentmap scaffold --csv your_workflow.csv
```

## Configuration Best Practices

### Context Configuration

- Use JSON format for complex configurations
- Reference environment variables with `env:VARIABLE_NAME`
- Document configuration options in the Description field

### Memory Management

For conversational agents:

```csv
ChatGraph,ChatAgent,{"memory_key": "conversation", "max_memory_messages": 20},Chat agent,llm,Continue,,user_input,response,You are a helpful assistant
```

### Error Handling

Always provide error handling paths:

```csv
MyGraph,ProcessData,,Process user data,data_processor,Success,ErrorHandler,input,result,
MyGraph,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_message,
```

## Migration Guide

### From Legacy Patterns

**Old Pattern (Deprecated):**
```python
agent = EchoAgent("Echo", "prompt", {"input_fields": ["input"]})
```

**Modern Pattern (Recommended):**
```python
agent = EchoAgent(
    name="Echo",
    prompt="prompt", 
    context={"input_fields": ["input"]},
    logger=logger,
    execution_tracker_service=tracker_service,
    state_adapter_service=state_adapter_service
)
```

## See Also

- [CSV Schema Reference](csv-schema.md) - CSV workflow format documentation
- [CLI Commands Reference](cli-commands.md) - Command-line interface documentation
- [Quick Start Guide](../getting-started/quick-start.md) - Build your first workflow
- [Understanding Workflows](../guides/understanding-workflows.md) - Core concepts and workflow patterns
- [Clean Architecture Overview](../advanced/architecture/clean-architecture-overview.md) - System architecture
