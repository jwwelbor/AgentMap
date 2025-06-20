# Storage Services in AgentMap

AgentMap provides a unified storage service system that supports multiple storage backends including CSV files, text/binary files, and vector databases. All storage services implement consistent APIs and behavior patterns for reliable data operations.

## Overview

The storage service system follows these consistent principles:

- **Unified Interface**: All services implement the same base protocol
- **Missing Documents Return `None`**: When requesting a specific document that doesn't exist
- **Structured Default Format**: Returns metadata-rich objects by default
- **Explicit Raw Formats**: Raw content available via format parameters
- **Type Safety**: Proper typing and error handling throughout

## Available Storage Services

### CSV Storage Service

The CSV storage service provides pandas-based operations on CSV files with support for querying, filtering, and data manipulation.

**Configuration:**
```yaml
storage:
  csv:
    provider: csv
    options:
      base_directory: "./data/csv"
      encoding: "utf-8"
```

**Supported Operations:**
- Read entire CSV files or specific rows by ID
- Write DataFrames, dictionaries, or lists of dictionaries
- Query and filter data with pandas-style operations
- Update and append operations with merge capabilities

### File Storage Service

The file storage service handles text files, binary files, and document formats with optional LangChain loader integration.

**Configuration:**
```yaml
storage:
  file:
    provider: file
    options:
      base_directory: "./data/files"
      encoding: "utf-8"
      allow_binary: true
      chunk_size: 1000
      chunk_overlap: 200
```

**Supported Operations:**
- Read/write text files with automatic encoding detection
- Handle binary files (images, PDFs, etc.) when enabled
- Document parsing via LangChain loaders (PDF, DOCX, etc.)
- Directory operations and file metadata retrieval

## API Reference

### Common Read Operations

#### Reading Entire Collections

```python
# CSV: Read entire CSV file as DataFrame (default)
data = storage_service.read("users")
# Returns: pandas DataFrame

# File: Read directory listing
files = storage_service.read("documents")  
# Returns: List of filenames in directory
```

#### Reading Specific Documents

```python
# CSV: Read specific row by ID
user = storage_service.read("users", document_id=1)
# Returns: Dict with user data, or None if not found

# File: Read specific file with structured metadata (default)
doc = storage_service.read("documents", "readme.txt")
# Returns: {"content": "file content", "metadata": {...}}

# File: Read specific file as raw text
content = storage_service.read("documents", "readme.txt", format="text")
# Returns: "file content" (string)
```

#### Output Format Options

All storage services support these format options:

```python
# Default format: Structured with metadata
result = storage_service.read("collection", "document")
# Returns: {"content": "...", "metadata": {"source": "...", "size": 123, "type": "text"}}

# Text/Raw format: Plain content
content = storage_service.read("collection", "document", format="text")
# Returns: Raw content as string

# Raw format: Unprocessed data
raw = storage_service.read("collection", "document", format="raw")
# Returns: Raw content (bytes for binary, string for text)
```

### Common Write Operations

#### Basic Write Operations

```python
from agentmap.services.storage.types import WriteMode

# CSV: Write DataFrame or list of dicts
result = storage_service.write("users", [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
])

# File: Write text content
result = storage_service.write("documents", "Hello, World!", "greeting.txt")

# File: Write binary content
result = storage_service.write("images", binary_data, "photo.jpg", binary_mode=True)
```

#### Write Modes

```python
# WRITE: Create new or overwrite existing (default)
result = storage_service.write("collection", data, mode=WriteMode.WRITE)

# APPEND: Add to existing content
result = storage_service.write("collection", data, mode=WriteMode.APPEND)

# UPDATE: Update existing rows or append new ones (CSV only)
result = storage_service.write("collection", data, mode=WriteMode.UPDATE)
```

### Query and Filter Operations

#### CSV Query Examples

```python
# Query with filters
filtered_data = storage_service.read("users", query={
    "active": True,           # Exact match filter
    "city": ["NYC", "LA"],   # List filter (isin)
    "sort": "name",          # Sort by field
    "order": "asc",          # Sort direction
    "limit": 10,             # Limit results
    "offset": 20             # Skip first N results
})

# Complex query combination
results = storage_service.read("sales", query={
    "region": "North",
    "amount": {"$gt": 1000},  # Would need custom implementation
    "date": {"$gte": "2024-01-01"},
    "sort": "amount",
    "order": "desc",
    "limit": 50
})
```

#### File Query Examples

```python
# Document search with LangChain loaders
docs = storage_service.read("documents", "large_doc.pdf", query={
    "document_index": 2,      # Specific chunk/section
    "metadata": {"page": 1}   # Metadata filter
})

# Path extraction from documents
content = storage_service.read("documents", "data.json", path="metadata.title")
```

### Delete Operations

```python
# Delete specific document
result = storage_service.delete("collection", "document_id")

# Delete entire collection/file
result = storage_service.delete("collection")

# File: Recursive directory deletion
result = storage_service.delete("directory", recursive=True)
```

### Utility Operations

```python
# Check existence
exists = storage_service.exists("collection", "document_id")

# Count documents/rows
count = storage_service.count("collection")
count_filtered = storage_service.count("collection", query={"active": True})

# List collections
collections = storage_service.list_collections()

# File: Get detailed metadata
metadata = storage_service.get_file_metadata("documents", "file.txt")
# Returns: {"name": "file.txt", "size": 123, "created_at": ..., "is_text": True}
```

## Usage in Agents

### Storage-Capable Agent Implementation

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import StorageCapableAgent

class DataProcessorAgent(BaseAgent, StorageCapableAgent):
    """Agent that processes data using storage services."""
    
    def configure_storage_service(self, storage_service):
        """Configure storage service for this agent."""
        self._storage_service = storage_service
        self.log_debug("Storage service configured")
    
    @property
    def storage_service(self):
        """Get storage service, raising if not configured."""
        if self._storage_service is None:
            raise ValueError(f"Storage service not configured for agent '{self.name}'")
        return self._storage_service
    
    def process(self, inputs):
        """Process data with storage operations."""
        collection = inputs.get("collection", "data")
        operation = inputs.get("operation", "read")
        
        if operation == "read":
            # Read with different formats based on needs
            if inputs.get("raw_content"):
                data = self.storage_service.read(collection, format="text")
            else:
                data = self.storage_service.read(collection)  # Structured format
            
            self.log_info(f"Read data from {collection}")
            return data
            
        elif operation == "write":
            data = inputs.get("data")
            document_id = inputs.get("document_id")
            
            result = self.storage_service.write(collection, data, document_id)
            if result.success:
                self.log_info(f"Successfully wrote to {collection}")
                return {"status": "success", "rows_written": result.rows_written}
            else:
                self.log_error(f"Write failed: {result.error}")
                return {"status": "error", "message": result.error}
        
        elif operation == "query":
            query = inputs.get("query", {})
            results = self.storage_service.read(collection, query=query)
            
            self.log_info(f"Query returned {len(results) if results else 0} results")
            return results
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
```

### CSV Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,LoadUsers,,Load user data,csv_reader,ProcessUsers,ErrorHandler,"",users,users.csv
DataFlow,ProcessUsers,,Process user list,DataProcessor,SaveResults,ErrorHandler,"users",processed_users,
DataFlow,SaveResults,,Save processed data,csv_writer,End,ErrorHandler,"processed_users",save_result,results.csv
DataFlow,End,,Completion,Echo,,,"save_result",final_message,Data processing complete
DataFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

### File Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,ReadDoc,,"{'format': 'structured'}",file_reader,ProcessDoc,ErrorHandler,"",document,documents/input.pdf
DocFlow,ProcessDoc,,Process document,openai,SaveSummary,ErrorHandler,"document",summary,Summarize this document: {document.content}
DocFlow,SaveSummary,,"{'format': 'text'}",file_writer,End,ErrorHandler,"summary",result,output/summary.md
DocFlow,End,,Completion,Echo,,,"result",final_message,Document processed successfully
DocFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

## Advanced Configuration

### Context Configuration for Storage Agents

```yaml
# CSV Agent Context
{
  "collection": "sales_data",
  "format": "records",           # Output format preference
  "id_field": "transaction_id",  # Custom ID field
  "encoding": "utf-8",
  "query_defaults": {
    "sort": "date",
    "order": "desc"
  }
}

# File Agent Context  
{
  "collection": "documents",
  "format": "structured",        # Default to metadata format
  "binary_mode": false,          # Text files only
  "should_split": true,          # Enable document chunking
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "include_metadata": true
}
```

### Error Handling Patterns

```python
def safe_storage_operation(storage_service, operation_type, **kwargs):
    """Safely perform storage operations with comprehensive error handling."""
    try:
        if operation_type == "read":
            result = storage_service.read(**kwargs)
            if result is None:
                return {"status": "not_found", "message": "Document not found"}
            return {"status": "success", "data": result}
            
        elif operation_type == "write":
            result = storage_service.write(**kwargs)
            if result.success:
                return {
                    "status": "success", 
                    "rows_written": result.rows_written,
                    "created_new": result.created_new
                }
            else:
                return {"status": "error", "message": result.error}
                
        elif operation_type == "delete":
            result = storage_service.delete(**kwargs)
            if result.success:
                return {
                    "status": "success",
                    "file_deleted": result.file_deleted,
                    "total_affected": result.total_affected
                }
            else:
                return {"status": "error", "message": result.error}
                
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

## Best Practices

### Data Consistency

1. **Use Appropriate ID Fields**: Ensure CSV data has consistent ID fields for reliable updates
2. **Handle Missing Documents**: Always check for `None` returns when reading specific documents  
3. **Format Selection**: Choose appropriate output formats based on downstream processing needs
4. **Error Handling**: Implement comprehensive error handling for all storage operations

### Performance Optimization

1. **Batch Operations**: Use batch writes for multiple documents when possible
2. **Query Optimization**: Use filters and limits to reduce data transfer
3. **Format Efficiency**: Use raw formats when metadata isn't needed
4. **Chunking**: Enable document chunking for large files to improve processing

### Security Considerations

1. **Path Validation**: File service automatically validates paths to prevent directory traversal
2. **Binary Safety**: Configure `allow_binary` appropriately for your security requirements
3. **Encoding Handling**: Specify explicit encodings for consistent text processing
4. **Permission Management**: Ensure storage directories have appropriate permissions

### Testing Storage Operations

```python
import unittest
from unittest.mock import Mock
from agentmap.services.storage.types import StorageResult

class TestStorageOperations(unittest.TestCase):
    def setUp(self):
        self.mock_storage = Mock()
        
    def test_read_missing_document(self):
        """Test handling of missing documents."""
        # Arrange
        self.mock_storage.read.return_value = None
        
        # Act
        result = self.mock_storage.read("collection", "missing_id")
        
        # Assert
        self.assertIsNone(result)
        self.mock_storage.read.assert_called_once_with("collection", "missing_id")
    
    def test_write_operation_success(self):
        """Test successful write operation."""
        # Arrange
        expected_result = StorageResult(
            success=True,
            operation="write",
            rows_written=5,
            created_new=True
        )
        self.mock_storage.write.return_value = expected_result
        
        # Act
        result = self.mock_storage.write("collection", [{"id": 1, "name": "test"}])
        
        # Assert
        self.assertTrue(result.success)
        self.assertEqual(result.rows_written, 5)
        self.assertTrue(result.created_new)
    
    def test_structured_format_response(self):
        """Test structured format returns metadata."""
        # Arrange
        expected_response = {
            "content": "file content",
            "metadata": {
                "source": "/path/to/file.txt",
                "size": 12,
                "type": "text"
            }
        }
        self.mock_storage.read.return_value = expected_response
        
        # Act
        result = self.mock_storage.read("documents", "file.txt")
        
        # Assert
        self.assertIn("content", result)
        self.assertIn("metadata", result)
        self.assertEqual(result["content"], "file content")
        self.assertEqual(result["metadata"]["type"], "text")
```

## Migration Guide

### Updating from Previous Versions

If you're migrating from earlier versions of AgentMap storage services:

1. **Missing Document Handling**: Update code that expected empty DataFrames or lists to handle `None` returns
2. **Default Format Changes**: Code expecting raw content by default should specify `format="text"` or `format="raw"`
3. **Error Result Updates**: Check for new fields in `StorageResult` objects

**Before:**
```python
# Old behavior
result = storage_service.read("collection", "missing_id")
if result.empty:  # DataFrame check
    handle_missing()

content = storage_service.read("files", "doc.txt")  # Raw string
process_content(content)
```

**After:**
```python
# New consistent behavior
result = storage_service.read("collection", "missing_id")
if result is None:  # None check
    handle_missing()

# Structured format (new default)
doc = storage_service.read("files", "doc.txt")  
process_document(doc["content"], doc["metadata"])

# Or explicit raw format
content = storage_service.read("files", "doc.txt", format="text")
process_content(content)
```

The storage services now provide a consistent, powerful foundation for data operations in AgentMap workflows while maintaining flexibility for different use cases and requirements.
