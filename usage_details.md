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

# Prompt Management in AgentMap

AgentMap includes a robust prompt management system that helps you organize, maintain, and reuse prompts across your workflows. This system makes it easy to separate prompt content from application logic and provides a centralized way to manage prompts.

## Prompt Reference Types

The PromptManager supports three types of prompt references:

### 1. Registry Prompts

Reference prompts that are stored in a central registry:

```
prompt:prompt_name
```

Registry prompts are managed through the `prompts/registry.yaml` file (configurable) and provide a simple way to reuse common prompts across workflows.

### 2. File Prompts

Reference prompts stored in separate files:

```
file:path/to/prompt.txt
```

File prompts are ideal for longer prompts or those that include complex formatting. Paths can be absolute or relative to the prompts directory.

### 3. YAML Key Prompts

Reference specific keys within YAML files:

```
yaml:path/to/file.yaml#key.path
```

YAML key prompts allow you to organize multiple related prompts in a structured YAML document and reference specific sections.

## Using Prompt References in AgentMap

You can use prompt references in the `Prompt` field of your CSV:

```csv
GraphName,LLMNode,,Process user input,OpenAI,NextNode,,input,response,prompt:system_instructions
```

Or directly in your code:

```python
from agentmap.prompts import resolve_prompt

# Resolve a prompt reference
prompt_text = resolve_prompt("prompt:customer_service")
```

## Configuration Options

Prompt management can be configured in your `agentmap_config.yaml`:

```yaml
prompts:
  directory: "prompts"  # Directory for prompt files
  registry_file: "prompts/registry.yaml"  # Registry file location
  enable_cache: true  # Cache resolved prompts for performance
```

Or using environment variables:

```bash
export AGENTMAP_PROMPTS_DIR="my_prompts"
export AGENTMAP_PROMPT_REGISTRY="my_prompts/registry.yaml"
export AGENTMAP_PROMPT_CACHE="true"
```

## Using the PromptManager API

For more advanced use cases, you can use the PromptManager directly:

```python
from agentmap.prompts import get_prompt_manager

# Get the global PromptManager instance
manager = get_prompt_manager()

# Resolve a prompt reference
prompt_text = manager.resolve_prompt("file:prompts/system.txt")

# Register a new prompt
manager.register_prompt("greeting", "Hello, I'm an AI assistant.", save=True)

# Get all registered prompts
registry = manager.get_registry()
```

## Best Practices for Prompt Management

1. **Use descriptive prompt names** - Choose clear, purpose-oriented names for registry prompts
2. **Organize prompt files logically** - Group related prompts in the same directory
3. **Use YAML for complex prompt sets** - Organize related prompts in YAML files
4. **Include version info** - Add version information in prompt files for tracking changes
5. **Document prompt parameters** - Note any template parameters in comments

# File Agents in AgentMap

AgentMap provides specialized agents for working with files and documents. These agents leverage LangChain document loaders to support a wide range of document formats, making it easy to incorporate file operations into your workflows.

## FileReaderAgent

The FileReaderAgent reads and processes various document types, with optional chunking and filtering capabilities.

### Supported File Formats

- Text files (.txt)
- PDF files (.pdf)
- Markdown (.md)
- HTML (.html, .htm)
- Word documents (.docx, .doc)

### Configuration Options

The FileReaderAgent can be configured via the Context field or in code:

```csv
GraphName,ReadDocs,{"chunk_size": 1000, "chunk_overlap": 200, "should_split": true},Read documents,file_reader,Process,,collection,documents,
```

Available configurations:
- `chunk_size`: Size of text chunks when splitting (default: 1000)
- `chunk_overlap`: Overlap between chunks (default: 200)
- `should_split`: Whether to split documents (default: false)
- `include_metadata`: Include document metadata (default: true)

### Using FileReaderAgent

Basic usage in a workflow:

```csv
GraphName,ReadFile,,Read document,file_reader,Process,,collection,document,path/to/file.pdf
```

The agent requires:
- `collection`: Path to the file to read
- `document_id`: Optional specific section to extract
- `query`: Optional filtering criteria
- `path`: Optional path within document
- `format`: Optional output format (default, raw, text)

Example state output:
```python
{
    "document": {
        "success": true,
        "file_path": "path/to/file.pdf",
        "data": [
            {"content": "Document text here", "metadata": {...}}
        ],
        "count": 1
    }
}
```

## FileWriterAgent

The FileWriterAgent writes content to various text-based formats with support for different write modes.

### Supported File Formats

Text-based formats including:
- Text files (.txt)
- Markdown (.md)
- HTML (.html, .htm)
- CSV (.csv)
- Log files (.log)
- Code files (.py, .js, etc.)

### Write Modes

- `write`: Create or overwrite file (default)
- `append`: Add to existing file
- `update`: Similar to write for text files
- `delete`: Delete the file

### Using FileWriterAgent

Basic usage in a workflow:

```csv
GraphName,WriteFile,,Write document,file_writer,Next,,data,result,path/to/output.txt
```

The agent requires:
- `collection`: Path to the file to write
- `data`: Content to write
- `mode`: Write mode (write, append, update, delete)

Example input:
```python
{
    "collection": "output/report.md",
    "data": "# Report\n\nThis is the content of the report.",
    "mode": "write"
}
```

Example output:
```python
{
    "result": {
        "success": true,
        "mode": "write",
        "file_path": "output/report.md",
        "created_new": true
    }
}
```

## Integration with LangChain

Both file agents integrate with LangChain's document loaders, providing advanced document handling capabilities. The integration brings several benefits:

1. **Standard document format**: Documents are represented with content and metadata
2. **Text splitting**: Split long documents into manageable chunks
3. **Metadata extraction**: Extract and utilize document metadata
4. **Format conversion**: Handle various document formats with a unified API

Example of a document processing workflow:

```csv
GraphName,ReadDocs,{"should_split": true},Read documents,file_reader,Summarize,,collection,documents,reports/*.pdf
GraphName,Summarize,,Generate summary,openai,Save,,documents,summary,"Summarize these documents: {documents}"
GraphName,Save,,Save the summary,file_writer,End,,summary,result,output/summary.md
GraphName,End,,Workflow complete,echo,,,result,message,
```

# AgentMap Agent Types

AgentMap includes several built-in agent types for different purposes. Each agent type processes inputs and produces outputs differently.

## Core Agent Types

### DefaultAgent

The simplest agent that logs its execution and returns a message with the prompt.

- **Input Fields**: Any (unused)
- **Output Field**: Returns a message including the agent's prompt
- **Prompt Usage**: Included in output message

Example:
```csv
TestGraph,Start,,Basic node,Default,Next,,input,output,Hello World
```

### EchoAgent

Simply returns the input data unchanged.

- **Input Fields**: Returns the first input field it finds
- **Output Field**: The input data unchanged
- **Prompt Usage**: Ignored

Example:
```csv
TestGraph,Echo,,Echo node,Echo,Next,,message,response,
```

### BranchingAgent

Used for testing conditional routing. Checks for success/failure indicators in inputs.

- **Input Fields**: Looks for `success`, `should_succeed`, `succeed`, or `branch` fields
- **Output Field**: Message describing the branching decision
- **Prompt Usage**: Included in output message

Example:
```csv
TestGraph,Branch,,Decision point,Branching,SuccessPath,FailurePath,input,decision,Make a choice
```

### SuccessAgent and FailureAgent

Testing agents that always succeed or fail.

- **Input Fields**: Any (unused)
- **Output Field**: Confirmation message
- **Prompt Usage**: Included in output message

SuccessAgent example:
```csv
TestGraph,AlwaysSucceed,,Success node,Success,Next,,input,result,I always succeed
```

FailureAgent example:
```csv
TestGraph,AlwaysFail,,Failure node,Failure,Next,,input,result,I always fail
```

### InputAgent

Prompts for user input during execution.

- **Input Fields**: Any (unused)
- **Output Field**: User's input response
- **Prompt Usage**: Shown to user as input prompt

Example:
```csv
TestGraph,GetInput,,User input node,Input,Process,,message,user_input,Please enter your name:
```

## LLM Agent Types

### OpenAIAgent (aliases: gpt, chatgpt)

Uses OpenAI's models for text generation.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Context**: Can contain model, temperature, memory settings

Example:
```csv
QAGraph,Question,,Ask a question,openai,Answer,,question,response,Answer this question: {question}
```

### AnthropicAgent (alias: claude)

Uses Anthropic's Claude models for text generation.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Context**: Can contain model, temperature, memory settings

Example:
```csv
QAGraph,Summarize,,Summarize text,claude,Next,,text,summary,Summarize this text in 3 bullet points: {text}
```

### GoogleAgent (alias: gemini)

Uses Google's Gemini models for text generation.

- **Input Fields**: Used to format the prompt template
- **Output Field**: LLM response
- **Prompt Usage**: Used as prompt template
- **Context**: Can contain model, temperature, memory settings

## Storage Agent Types

### CSVReaderAgent and CSVWriterAgent

Read from and write to CSV files.

- **Input Fields**: Must contain `collection` (file path)
- **Output Field**: For reader: CSV data, For writer: Operation result
- **Prompt Usage**: Optional CSV path

### JSONDocumentReaderAgent and JSONDocumentWriterAgent

Read from and write to JSON files.

- **Input Fields**: Must contain `collection` (file path)
- **Output Field**: For reader: JSON data, For writer: Operation result
- **Prompt Usage**: Optional JSON path

### FirebaseDocumentReaderAgent and FirebaseDocumentWriterAgent

Read from and write to Firebase databases.

- **Input Fields**: Must contain `collection` (defined in storage config)
- **Output Field**: For reader: Firebase data, For writer: Operation result
- **Prompt Usage**: Optional collection override

### VectorReaderAgent and VectorWriterAgent

Work with vector databases and embeddings for semantic search and document retrieval using LangChain.

- **Input Fields**: For reader: `query` for similarity search, For writer: document data
- **Output Field**: For reader: Retrieved documents, For writer: Operation status
- **Prompt Usage**: Optional configuration  
- **Context**: Can contain vector store configuration like `store_key`, `persist_directory`, `provider`, and `embedding_model`

Example:
```csv
VectorGraph,LoadDocs,,Load documents into vector store,VectorWriter,Search,,documents,load_result,
VectorGraph,Search,,Search for similar documents,VectorReader,Process,,query,search_results,
```

The `VectorReaderAgent` allows you to perform similarity searches against vector databases, while the `VectorWriterAgent` handles adding documents and embeddings to the database. These agents integrate with LangChain's vector stores like Chroma and FAISS for semantic search capabilities.

## Advanced Agent Types

### GraphAgent

Executes a subgraph and returns its result.

- **Input Fields**: Passed to the subgraph
- **Output Field**: Result from the subgraph
- **Prompt Usage**: Name of the subgraph to execute

# Field Usage in AgentMap

This document explains how each field in the CSV is used by different components of AgentMap.

## GraphName

The `GraphName` field groups nodes together into a single workflow. When running a graph with `run_graph(graph_name)`, only nodes with the matching `GraphName` are included.

**Usage examples:**
- Create separate workflows in a single CSV file
- Organize related nodes under a common name

## Node

The `Node` field defines a unique identifier for each node in the graph. It is used:

- As an identifier in routing fields (`Edge`, `Success_Next`, `Failure_Next`)
- In logging and debugging to track execution flow
- As the default name for the agent instance

**Best practices:**
- Use descriptive names (e.g., "ProcessUserInput" instead of "Node1")
- Ensure uniqueness within a graph
- CamelCase or snake_case naming is recommended

## Edge vs Success_Next/Failure_Next

There are two routing methods in AgentMap:

### Simple Routing with Edge

When `Edge` is specified, the node will always proceed to the target node:

```csv
GraphA,Start,Next,,...
GraphA,Next,End,...
GraphA,End,,...
```

### Conditional Routing with Success_Next/Failure_Next

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

# State Management and Data Flow

AgentMap uses a shared state object to pass data between nodes. Understanding how state is managed and flows through the graph is crucial for effective workflow design.

## State Structure

The state is a dictionary that contains:

- Input fields from the initial state
- Output fields from each node's execution
- System fields like `last_action_success`
- Optional memory fields

Example state evolution:
```python
# Initial state
state = {"input": "Hello, world!"}

# After Node1 (Echo)
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",  # output_field from Node1
    "last_action_success": True
}

# After Node2 (OpenAI)
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",
    "response": "Greetings, human!",  # output_field from Node2
    "last_action_success": True
}
```

## State Adapter

The `StateAdapter` class handles different state formats:

- Dictionary state (default)
- Pydantic models
- Custom state objects

It provides methods for getting and setting values regardless of state type:

```python
# Get a value
value = StateAdapter.get_value(state, "field_name", default="default value")

# Set a value
new_state = StateAdapter.set_value(state, "field_name", "new value")
```

## State Flow in an Agent's Lifecycle

1. **Input Extraction**:
   - Agent's `run` method extracts input fields from state
   - Only fields listed in `Input_Fields` are accessible

2. **Processing**:
   - Agent's `process` method transforms inputs to output
   - Custom logic determines the result

3. **Output Setting**:
   - Output is stored in the field specified by `Output_Field`
   - `last_action_success` flag is set based on execution result

4. **Routing**:
   - Next node is determined based on routing rules and `last_action_success`

## Memory Management

For agents with memory (like LLM agents), there's additional state handling:

1. **Memory Serialization/Deserialization**:
   - Memory objects are serialized when stored in state
   - They're deserialized when retrieved by an agent

2. **Memory Flow**:
   - Memory is passed between nodes via a designated memory field (e.g., `chat_memory`)
   - Agents can add to the memory during processing

Example with memory:
```python
# After LLM agent with memory
state = {
    "input": "Hello",
    "response": "Hi there!",
    "chat_memory": {
        "_type": "langchain_memory",
        "memory_type": "buffer",
        "messages": [
            {"type": "human", "content": "Hello"},
            {"type": "ai", "content": "Hi there!"}
        ]
    },
    "last_action_success": True
}
```

## Execution Tracking

AgentMap tracks execution steps in the `execution_steps` field:

```python
state["execution_steps"] = [
    {
        "node": "Start",
        "timestamp": 1622547212.456,
        "duration": 0.123,
        "success": True
    },
    {
        "node": "Process",
        "timestamp": 1622547212.789,
        "duration": 0.456,
        "success": True
    }
]
```

This tracking is useful for:
- Debugging workflow execution
- Monitoring performance
- Understanding the execution path

## Error Handling

If an agent encounters an error:

1. The error is logged
2. `last_action_success` is set to `False`
3. An `error` field may be added to state
4. Routing follows the `Failure_Next` path

Custom error handling can be implemented in agents' `process` method.

# AgentMap Example Workflows

This document provides examples of different workflow patterns using AgentMap's CSV format.

## Simple Linear Workflow

A basic workflow where nodes execute in sequence:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
LinearFlow,Start,,Starting node,Echo,Process,,"input",initial_data,
LinearFlow,Process,,Processing node,Default,,,"initial_data",processed_data,Processing: {initial_data}
LinearFlow,End,,Final node,Echo,,,"processed_data",final_output,
```

This workflow:
1. Echoes the input into `initial_data`
2. Processes the data and stores in `processed_data`
3. Echoes the processed data as the final output

## Branching Workflow with Error Handling

A workflow with conditional branching based on success/failure:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
BranchFlow,Start,,Starting node,Echo,Validate,,"input",initial_data,
BranchFlow,Validate,,Validate input data,Branching,Process,ErrorHandler,"initial_data",validation_result,Check if valid
BranchFlow,Process,,Process valid data,Default,End,ErrorHandler,"initial_data",processed_data,Processing: {initial_data}
BranchFlow,End,,Completion node,Echo,,,"processed_data",final_output,
BranchFlow,ErrorHandler,,Handle errors,Echo,End,,"initial_data",error_message,Error occurred
```

This workflow:
1. Echoes the input
2. Validates the data and branches based on result
3. On success, processes the data
4. On failure, goes to error handler
5. Both paths eventually reach the End node

## LLM Chain with Memory

A conversational workflow that maintains memory between interactions:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatFlow,UserInput,,{"memory":{"type":"buffer","memory_key":"chat_memory"}},Input,Process,ErrorHandler,"",user_message,Enter your message:
ChatFlow,Process,,Process user input,Echo,Respond,ErrorHandler,"user_message|chat_memory",processed_input,
ChatFlow,Respond,,Generate response,OpenAI,Format,ErrorHandler,"processed_input|chat_memory",ai_response,"You are a helpful assistant. User: {processed_input}"
ChatFlow,Format,,Format the response,Default,UserInput,ErrorHandler,"ai_response|chat_memory",formatted_response,"Assistant: {ai_response}"
ChatFlow,ErrorHandler,,Handle errors,Echo,UserInput,,"error",error_message,Error: {error}
```

This workflow:
1. Gets user input
2. Processes the input
3. Generates a response with an LLM, preserving conversation memory
4. Formats the response
5. Returns to user input for the next interaction

## Document Processing Workflow with File Agents

A workflow for processing documents:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,ReadFile,,"{'should_split': true, 'chunk_size': 1000}",file_reader,Summarize,ErrorHandler,"collection",documents,path/to/document.pdf
DocFlow,Summarize,,Generate summary,openai,SaveSummary,ErrorHandler,"documents",summary,"prompt:document_summary"
DocFlow,SaveSummary,,Save the summary,file_writer,End,ErrorHandler,"summary",write_result,output/summary.md
DocFlow,End,,Workflow complete,Echo,,,"write_result",final_message,"Summary saved successfully"
DocFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error processing document: {error}"
```

This workflow:
1. Reads a PDF file and splits it into chunks
2. Summarizes the documents using OpenAI with a prompt from the registry
3. Saves the summary to a Markdown file
4. Reports completion or handles errors

## Data Processing Pipeline

A workflow for processing and analyzing data:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,LoadData,,Load data from CSV,CSVReader,Validate,ErrorHandler,"collection",data_raw,
DataFlow,Validate,,Validate data structure,Branching,Transform,ErrorHandler,"data_raw",validation_result,
DataFlow,Transform,,Transform data,Default,Analyze,ErrorHandler,"data_raw",data_transformed,"Transform raw data"
DataFlow,Analyze,,Analyze transformed data,OpenAI,SaveResults,ErrorHandler,"data_transformed",analysis_results,"Analyze this data and provide insights: {data_transformed}"
DataFlow,SaveResults,,Save results to CSV,CSVWriter,End,ErrorHandler,"analysis_results",save_result,
DataFlow,End,,Workflow complete,Echo,,,"save_result",final_message,"Analysis complete and saved"
DataFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error during data processing: {error}"
```

This workflow:
1. Loads data from a CSV file
2. Validates the data structure
3. Transforms the data
4. Analyzes the data using an LLM
5. Saves the results to another CSV
6. Reports completion

## Integration with External Services

A workflow that interacts with external services:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
APIFlow,GetRequest,,Get API request details,Input,Prepare,ErrorHandler,"",request_input,"Enter search query:"
APIFlow,Prepare,,Prepare API request,Default,MakeRequest,ErrorHandler,"request_input",api_params,"Preparing API request"
APIFlow,MakeRequest,,Make API call,HttpClient,ProcessResponse,ErrorHandler,"api_params",api_response,"https://api.example.com/search"
APIFlow,ProcessResponse,,Process API response,Default,Format,ErrorHandler,"api_response",processed_data,"Extracting relevant data"
APIFlow,Format,,Format results for display,Default,End,ErrorHandler,"processed_data",formatted_results,"Formatting results"
APIFlow,End,,Show results,Echo,,,"formatted_results",display_output,
APIFlow,ErrorHandler,,Handle API errors,Echo,End,,"error",error_message,"API Error: {error}"
```

Note: This example assumes an HttpClient agent type, which would be a custom implementation.

## Parallel Processing with Join

A workflow demonstrating parallel processing (functional but not explicit in CSV):

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ParallelFlow,Start,,Start the workflow,Echo,Split,,"input",initial_data,
ParallelFlow,Split,,Split into parallel tasks,func:split_tasks,,,initial_data,tasks,"Split the tasks"
ParallelFlow,ProcessA,,Process first branch,Default,Join,ErrorHandler,"tasks.a",result_a,"Processing branch A"
ParallelFlow,ProcessB,,Process second branch,Default,Join,ErrorHandler,"tasks.b",result_b,"Processing branch B"
ParallelFlow,ProcessC,,Process third branch,Default,Join,ErrorHandler,"tasks.c",result_c,"Processing branch C"
ParallelFlow,Join,,Join results,func:join_results,Summarize,ErrorHandler,"result_a|result_b|result_c",joined_results,"Join the results"
ParallelFlow,Summarize,,Summarize all results,Default,End,ErrorHandler,"joined_results",summary,"Summarize the results"
ParallelFlow,End,,Workflow complete,Echo,,,"summary",final_output,
ParallelFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error during processing: {error}"
```

This workflow uses custom functions (`split_tasks` and `join_results`) to implement parallel processing and synchronization.

# AgentMap CLI Documentation

AgentMap provides a command-line interface (CLI) for managing workflows, with powerful scaffolding capabilities for custom agents and functions.

## Installation

```bash
pip install agentmap
```

## Basic Commands

### Run a Graph

```bash
agentmap run --graph GraphName --state '{"input": "value"}'
```

Options:
- `--graph`, `-g`: Name of the graph to run
- `--state`, `-s`: Initial state as JSON string
- `--csv`: Optional path to CSV file
- `--autocompile`, `-a`: Automatically compile the graph
- `--config`, `-c`: Path to custom config file

### View Configuration

```bash
agentmap config
```

Options:
- `--path`, `-p`: Path to config file to display

## Scaffolding Commands

The scaffolding functionality is one of AgentMap's most powerful features, allowing you to quickly generate starter code for custom agents and functions.

### Scaffold Agents and Functions

```bash
agentmap scaffold [OPTIONS]
```

Options:
- `--graph`, `-g`: Graph name to scaffold agents for
- `--csv`: CSV path override
- `--config`, `-c`: Path to custom config file

### How Scaffolding Works

The scaffolding command:
1. Analyzes your CSV file to find agent types and functions that aren't built-in
2. Generates Python files for each custom agent and function
3. Places them in the configured directories (default: `agentmap/agents/custom` and `agentmap/functions`)

Example:

```csv
MyGraph,WeatherNode,,Get weather data,Weather,NextNode,,location,weather,Get weather for {location}
```

Running `agentmap scaffold` will generate:
- `agentmap/agents/custom/weather_agent.py` - A starter agent implementation

### Scaffold Output

For custom agents, the scaffold generates:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class WeatherAgent(BaseAgent):
    """
    Get weather data
    
    Node: WeatherNode
    Expected input fields: location
    Expected output field: weather
    Default prompt: Get weather for {location}
    """
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return the output value.
        
        Args:
            inputs (dict): Contains the input values with keys: location
            
        Returns:
            The value for weather
        """
        # Access input fields directly from inputs dictionary
        location = inputs.get("location")
        
        # Implement your agent logic here
        # ...
        
        # Return just the output value (not the whole state)
        return "Your WeatherAgent implementation here"
```

For functions, it generates:

```python
from typing import Dict, Any

def choose_route(state: Any, success_node="SuccessPath", failure_node="FailurePath") -> str:
    """
    Decision function to route between success and failure nodes.
    
    Args:
        state: The current graph state
        success_node (str): Node to route to on success
        failure_node (str): Node to route to on failure
        
    Returns:
        str: Name of the next node to execute
    
    Node: DecisionNode
    Node Context: Decision node description
    
    Available in state:
    - input: Input from previous node
    """
    # TODO: Implement routing logic
    # Determine whether to return success_node or failure_node
    
    # Example implementation (replace with actual logic):
    if state.get("last_action_success", True):
        return success_node
    else:
        return failure_node
```

### Custom Scaffolding Directories

You can customize the directories where scaffolds are generated:

```yaml
# In agentmap_config.yaml
paths:
  custom_agents: "path/to/custom/agents"
  functions: "path/to/functions"
```

Or override them with environment variables:
```bash
export AGENTMAP_CUSTOM_AGENTS_PATH="path/to/custom/agents"
export AGENTMAP_FUNCTIONS_PATH="path/to/functions"
```

### Best Practices for Scaffolding

1. **Write clear Context descriptions** - These become class docstrings
2. **Use descriptive Node names** - These are used in error messages and logs
3. **Specify Input_Fields and Output_Field** - These generate typed method signatures
4. **Include helpful Prompts** - These provide guidance in the scaffolded code

## Export and Compile Commands

### Export a Graph

```bash
agentmap export -g GraphName -o output.py
```

Options:
- `--graph`, `-g`: Graph name to export
- `--output`, `-o`: Output file path
- `--format`, `-f`: Format (python, pickle, source)
- `--csv`: CSV path override
- `--state-schema`, `-s`: State schema type
- `--config`, `-c`: Path to custom config file

### Compile Graphs

```bash
agentmap compile [OPTIONS]
```

Options:
- `--graph`, `-g`: Compile a single graph
- `--output`, `-o`: Output directory for compiled graphs
- `--csv`: CSV path override
- `--state-schema`, `-s`: State schema type
- `--config`, `-c`: Path to custom config file

## Storage Configuration

```bash
agentmap storage-config [OPTIONS]
```

Options:
- `--init`, `-i`: Initialize a default storage configuration file
- `--path`, `-p`: Path to storage config file
- `--config`, `-c`: Path to custom config file