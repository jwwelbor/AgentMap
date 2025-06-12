# AgentMap Agent Types

> **Related Documentation**: 
> - [Agent Development Contract](agent_contract.md) - Agent interface requirements and implementation patterns
> - [Service Injection](service_injection.md) - Protocol-based dependency injection system
> - [Advanced Agent Types](advanced_agent_types.md) - Context configuration and advanced features

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

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.default_agent import DefaultAgent

agent = DefaultAgent(
    name="Start",
    prompt="Hello World",
    context={"input_fields": ["input"], "output_field": "output"},
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service
)
```

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

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.echo_agent import EchoAgent

agent = EchoAgent(
    name="Echo",
    prompt="",
    context={"input_fields": ["message"], "output_field": "response"},
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service
)
```

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

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.llm.llm_agent import LLMAgent

agent = LLMAgent(
    name="Question",
    prompt="Answer this question: {question}",
    context={
        "input_fields": ["question"], 
        "output_field": "response",
        "routing_enabled": True,
        "task_type": "analysis",
        "provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
        "temperature": 0.7,
        "memory_key": "chat_history",
        "max_memory_messages": 10
    },
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service,
    prompt_manager_service=prompt_manager_service  # Optional
)

# Configure LLM service (done by GraphRunnerService automatically)
agent.configure_llm_service(llm_service)
```

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

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent

agent = OpenAIAgent(
    name="Question",
    prompt="Answer this question: {question}",
    context={
        "input_fields": ["question"], 
        "output_field": "response",
        "model": "gpt-4",
        "temperature": 0.7
    },
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service
)
```

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

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent

agent = CSVReaderAgent(
    name="ReadData",
    prompt="data/customers.csv",
    context={
        "input_fields": ["collection", "query"], 
        "output_field": "data",
        "format": "records",
        "id_field": "customer_id"
    },
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service
)

# Configure storage services (done by GraphRunnerService automatically)
agent.configure_storage_service(storage_service_manager)
agent.configure_csv_service(csv_storage_service)
```

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
- **Context**: Can contain vector store configuration like `store_key`, `persist_directory`, `provider`, and `embedding_model`

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

## File Agents in AgentMap

AgentMap provides specialized agents for working with files and documents using LangChain document loaders.

### FileReaderAgent

The FileReaderAgent reads and processes various document types with optional chunking and filtering.

- **Supported File Formats**: Text, PDF, Markdown, HTML, Word documents
- **Input Fields**: `collection` (file path), optional `document_id`, `query`, `path`, `format`
- **Output Field**: Document data with metadata
- **Infrastructure Services**: Logger, ExecutionTracker, StateAdapter
- **Business Services**: StorageService (configured via StorageCapableAgent protocol)
- **Protocol Implementation**: StorageCapableAgent, FileCapableAgent

**Modern Constructor Pattern:**
```python
from agentmap.agents.builtins.storage.file.reader import FileReaderAgent

agent = FileReaderAgent(
    name="ReadDocs",
    prompt="",
    context={
        "input_fields": ["collection"], 
        "output_field": "documents",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "should_split": True,
        "include_metadata": True
    },
    logger=logger,
    execution_tracker_service=execution_tracker_service,
    state_adapter_service=state_adapter_service
)
```

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

## Advanced Service Configuration Examples

### Multi-Service Agent Implementation

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent, PromptCapableAgent

class AdvancedProcessorAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent, PromptCapableAgent):
    """Advanced agent using multiple services."""
    
    def __init__(
        self, 
        name: str, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
        prompt_manager_service: Optional[Any] = None
    ):
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service
        )
        self._prompt_manager_service = prompt_manager_service
    
    # Protocol implementations
    def configure_llm_service(self, llm_service):
        self._llm_service = llm_service
        self.log_debug("LLM service configured")
    
    def configure_storage_service(self, storage_service):
        self._storage_service = storage_service
        self.log_debug("Storage service configured")
    
    def configure_prompt_service(self, prompt_service):
        self._prompt_manager_service = prompt_service
        self.log_debug("Prompt service configured")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        # Use all configured services
        data = self._storage_service.read(inputs["collection"])
        prompt = self._prompt_manager_service.resolve_prompt(self.prompt)
        response = self._llm_service.call_llm(
            provider="auto",
            messages=[{"role": "user", "content": f"{prompt}: {data}"}]
        )
        return response
```

### Context-Based Service Configuration

```csv
GraphName,ProcessData,{"routing_enabled": true, "task_type": "analysis", "storage_type": "csv", "format": "records"},Advanced data processing,advanced_processor,Next,,collection|query,result,process:data_analysis
```

### Memory and State Management

```csv
ChatGraph,ChatAgent,{"memory_key": "conversation", "max_memory_messages": 20, "routing_enabled": true},Chat with user,llm,Continue,,user_input,response,You are a helpful assistant
```

## Testing Agent Types

### Testing Infrastructure Services

```python
def test_modern_agent():
    from unittest.mock import Mock
    
    # Mock infrastructure services
    mock_logger = Mock()
    mock_tracker = Mock()
    mock_state_adapter = Mock()
    
    # Create agent with modern constructor
    agent = DefaultAgent(
        name="test",
        prompt="test prompt",
        context={"input_fields": ["input"], "output_field": "output"},
        logger=mock_logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    # Verify infrastructure services
    assert agent.logger == mock_logger
    assert agent.execution_tracker_service == mock_tracker
    assert agent.state_adapter_service == mock_state_adapter
```

### Testing Business Services

```python
def test_llm_agent_service_configuration():
    from unittest.mock import Mock
    from agentmap.services.protocols import LLMCapableAgent
    
    # Create agent
    agent = LLMAgent(name="test", prompt="test", context={})
    
    # Verify protocol implementation
    assert isinstance(agent, LLMCapableAgent)
    
    # Configure business service
    mock_llm_service = Mock()
    agent.configure_llm_service(mock_llm_service)
    
    # Verify service configuration
    assert agent.llm_service == mock_llm_service
```

## Migration from Legacy Patterns

### Old Pattern (Deprecated)
```python
# OLD: Simple constructor
agent = EchoAgent("Echo", "prompt", {"input_fields": ["input"]})
```

### Modern Pattern (Recommended)
```python
# NEW: Infrastructure services via constructor, business services via protocols
agent = EchoAgent(
    name="Echo",
    prompt="prompt", 
    context={"input_fields": ["input"]},
    logger=logger,
    execution_tracker_service=tracker_service,
    state_adapter_service=state_adapter_service
)
# Business services configured automatically by GraphRunnerService
```

All agent types now follow this modern pattern, providing clean separation of concerns, type-safe dependency injection, and comprehensive debugging capabilities while maintaining backward compatibility for CSV-based workflows.

## Next Steps

After understanding built-in agent types:

1. **Learn Agent Architecture**: Read [Agent Development Contract](agent_contract.md) for implementation requirements and patterns
2. **Understand Service Injection**: Study [Service Injection](service_injection.md) for detailed dependency injection examples
3. **Explore Advanced Configuration**: Check [Advanced Agent Types](advanced_agent_types.md) for comprehensive context configuration options
4. **Build Custom Agents**: See `custom_agents/README.md` for complete custom agent development examples
