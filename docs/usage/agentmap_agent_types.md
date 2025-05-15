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
---
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
## File Agents in AgentMap

AgentMap provides specialized agents for working with files and documents. These agents leverage LangChain document loaders to support a wide range of document formats, making it easy to incorporate file operations into your workflows.

### FileReaderAgent

The FileReaderAgent reads and processes various document types, with optional chunking and filtering capabilities.

#### Supported File Formats

- Text files (.txt)
- PDF files (.pdf)
- Markdown (.md)
- HTML (.html, .htm)
- Word documents (.docx, .doc)

#### Configuration Options

The FileReaderAgent can be configured via the Context field or in code:

```csv
GraphName,ReadDocs,{"chunk_size": 1000, "chunk_overlap": 200, "should_split": true},Read documents,file_reader,Process,,collection,documents,
```

Available configurations:
- `chunk_size`: Size of text chunks when splitting (default: 1000)
- `chunk_overlap`: Overlap between chunks (default: 200)
- `should_split`: Whether to split documents (default: false)
- `include_metadata`: Include document metadata (default: true)

#### Using FileReaderAgent

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

### FileWriterAgent

The FileWriterAgent writes content to various text-based formats with support for different write modes.

#### Supported File Formats

Text-based formats including:
- Text files (.txt)
- Markdown (.md)
- HTML (.html, .htm)
- CSV (.csv)
- Log files (.log)
- Code files (.py, .js, etc.)

#### Write Modes

- `write`: Create or overwrite file (default)
- `append`: Add to existing file
- `update`: Similar to write for text files
- `delete`: Delete the file

#### Using FileWriterAgent

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
    "data": "## Report\n\nThis is the content of the report.",
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

### Integration with LangChain

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

---
