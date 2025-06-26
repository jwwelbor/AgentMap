# Storage Services Overview

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';

AgentMap provides a unified storage service system that supports multiple storage backends including CSV files, JSON files, text/binary files, and vector databases. All storage services implement consistent APIs and behavior patterns for reliable data operations.

:::info Storage Consistency
All AgentMap storage services follow the same core principles: unified interface, missing documents return `None`, raw content by default, structured format available, and comprehensive type safety.
:::

## Overview

The storage service system follows these consistent principles:

- **Unified Interface**: All services implement the same base protocol
- **Missing Documents Return `None`**: When requesting a specific document that doesn't exist
- **Raw Content by Default**: Returns actual content directly for consistency and simplicity
- **Structured Format Available**: Metadata-rich objects available via `format="structured"`
- **Type Safety**: Proper typing and error handling throughout

## Available Storage Services

### CSV Storage Service

The CSV storage service provides pandas-based operations on CSV files with support for querying, filtering, and data manipulation. It treats CSV files as tabular data where each row can be accessed as a document using intelligent ID field detection or explicit field specification.

<Tabs>
<TabItem value="config" label="Configuration">

```yaml
storage:
  csv:
    provider: csv
    options:
      base_directory: "./data/csv"
      encoding: "utf-8"
```

</TabItem>
<TabItem value="features" label="Key Features">

- **Smart ID Field Detection**: Automatically detects common ID patterns (`id`, `user_id`, `order_id`, etc.)
- **Explicit ID Field Override**: Specify custom ID fields for business identifiers (`sku`, `email`, `isbn`)
- **Multiple Format Support**: Returns data as dict (default), records, or DataFrame
- **Missing Documents Return None**: Consistent with other storage services
- **Query and Filter Support**: Pandas-style operations with sorting and pagination

</TabItem>
<TabItem value="operations" label="Supported Operations">

- Read entire CSV files or specific rows by ID
- Write DataFrames, dictionaries, or lists of dictionaries  
- Query and filter data with pandas-style operations
- Update and append operations with merge capabilities

</TabItem>
</Tabs>

#### Format Options

The CSV service supports multiple output formats for different use cases:

```python
# Default format: dict (index-based keys)
result = storage_service.read("users")
# Returns: {0: {"id": 1, "name": "Alice"}, 1: {"id": 2, "name": "Bob"}}

# Records format: list of row dictionaries
result = storage_service.read("users", format="records")
# Returns: [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# DataFrame format: pandas DataFrame for advanced operations
result = storage_service.read("users", format="dataframe")
# Returns: pandas.DataFrame with all CSV data
```

#### Smart ID Field Detection

The CSV storage service implements intelligent ID field detection that automatically identifies the appropriate ID column in your CSV data, eliminating the need for manual configuration in most cases.

:::tip Automatic ID Detection Logic
The service searches for ID fields using this priority order:

1. **Exact match**: `"id"` (case insensitive)
2. **Ends with `_id`**: `user_id`, `customer_id`, `order_id`, etc.
3. **Starts with `id_`**: `id_user`, `id_customer`, etc.
4. **If multiple candidates exist**: Prefer first column position, then alphabetical order
:::

<details>
<summary>ID Detection Examples</summary>

```python
# Example 1: Standard 'id' column (most common)
csv_data = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
]
user = storage_service.read("users", document_id=1)
# ✅ Automatically detects 'id' column
# Returns: {"id": 1, "name": "Alice", "email": "alice@example.com"}

# Example 2: Domain-specific ID columns
order_data = [
    {"order_id": "ORD001", "customer": "Alice", "total": 100.00},
    {"order_id": "ORD002", "customer": "Bob", "total": 150.00}
]
order = storage_service.read("orders", document_id="ORD001")
# ✅ Automatically detects 'order_id' column (ends with _id)
# Returns: {"order_id": "ORD001", "customer": "Alice", "total": 100.00}

# Example 3: Multiple potential ID columns (uses priority)
complex_data = [
    {"record_id": "R001", "user_id": "U001", "id": 1, "data": "..."},
    {"record_id": "R002", "user_id": "U002", "id": 2, "data": "..."}
]
record = storage_service.read("complex", document_id=1)
# ✅ Uses 'id' (highest priority), not 'record_id' or 'user_id'
# Returns: {"record_id": "R001", "user_id": "U001", "id": 1, "data": "..."}
```

</details>

**Explicit ID Field Override**

For business identifiers that don't follow standard naming conventions, you can explicitly specify the ID field. This is particularly useful for:

- **Business identifiers**: `sku`, `email`, `isbn`, `ticker_symbol`
- **Legacy systems**: Non-standard naming conventions
- **Ambiguous cases**: Multiple ID-like columns where auto-detection might be unclear

<Tabs>
<TabItem value="business" label="Business Identifiers">

```python
# Example 1: Business identifier (SKU)
product_data = [
    {"sku": "WIDGET001", "name": "Super Widget", "price": 19.99},
    {"sku": "GADGET002", "name": "Cool Gadget", "price": 29.99}
]

# Auto-detection fails (no conventional ID columns)
result = storage_service.read("products", document_id="WIDGET001")
# Returns: None (no ID field detected)

# Explicit id_field works
product = storage_service.read("products", document_id="WIDGET001", id_field="sku")
# Returns: {"sku": "WIDGET001", "name": "Super Widget", "price": 19.99}
```

</TabItem>
<TabItem value="email" label="Email Identifiers">

```python
# Example 2: Email as identifier
user_data = [
    {"email": "alice@corp.com", "name": "Alice", "role": "admin"},
    {"email": "bob@corp.com", "name": "Bob", "role": "user"}
]

user = storage_service.read("users", document_id="alice@corp.com", id_field="email")
# Returns: {"email": "alice@corp.com", "name": "Alice", "role": "admin"}
```

</TabItem>
<TabItem value="operations" label="Multiple Operations">

```python
# Example 3: Multiple operations with custom ID field
# Read
stock = storage_service.read("stocks", document_id="AAPL", id_field="ticker")

# Write  
storage_service.write("stocks", new_stock_data, document_id="TSLA", id_field="ticker")

# Delete
storage_service.delete("stocks", document_id="MSFT", id_field="ticker")

# Check existence
exists = storage_service.exists("stocks", document_id="GOOGL", id_field="ticker")
```

</TabItem>
</Tabs>

:::warning When Auto-Detection Fails
When no ID field is detected and no explicit `id_field` is provided, operations will fail with clear error messages. Always check for None returns and handle missing ID fields appropriately.
:::

**CSV ID Detection Best Practices**

1. **Use Standard Naming**: Prefer common ID field names (`id`, `user_id`, `order_id`, etc.) for automatic detection
2. **Explicit Override for Business Identifiers**: Use `id_field` parameter for non-standard identifiers like `sku`, `email`, `isbn`
3. **Consistent Data Structure**: Maintain consistent ID field naming across your CSV files for predictable behavior
4. **Clear Error Handling**: Handle cases where no ID field exists and operations fail
5. **Format Selection**: Choose appropriate output formats based on downstream processing needs

### JSON Storage Service

The JSON storage service provides document-based operations on JSON files with support for nested data structures, path-based access, and document management. It uses a **direct storage** model where each document is stored exactly as provided.

:::info Direct Storage Model
The JSON service uses direct storage for maximum simplicity:
- `document_id` = storage key (never injected into user data)
- `data` = document content (stored exactly as provided)
- Storage structure: `{document_id: user_data}`
- Read operations return data exactly as stored
:::

<Tabs>
<TabItem value="config" label="Configuration">

```yaml
storage:
  json:
    provider: json
    options:
      base_directory: "./data/json"
      encoding: "utf-8"
      indent: 2
```

</TabItem>
<TabItem value="operations" label="Supported Operations">

- Read entire JSON files or specific documents by ID
- Write documents with automatic structure creation
- Update documents with merge capabilities
- Path-based operations using dot notation
- Query and filter documents
- Delete documents or specific nested paths

</TabItem>
</Tabs>

#### Direct Storage Model

The JSON service uses direct storage where user data is stored exactly as provided:

```python
# Write operation
storage_service.write("users", {"name": "John", "age": 30}, "user123")

# Internal storage structure (in users.json)
{
  "user123": {"name": "John", "age": 30}  # User data stored directly
}

# Read operation  
user = storage_service.read("users", "user123")
# Returns: {"name": "John", "age": 30}  # Data exactly as stored
```

<details>
<summary>Direct Storage for All Data Types</summary>

```python
# Dict data - stored directly
storage_service.write("configs", {"debug": True, "port": 8080}, "app_config")
# Stored as: {"app_config": {"debug": True, "port": 8080}}

# String data - stored directly
storage_service.write("configs", "production", "environment")
# Stored as: {"environment": "production"}

# List data - stored directly
storage_service.write("configs", ["item1", "item2"], "allowed_items")
# Stored as: {"allowed_items": ["item1", "item2"]}

# Number data - stored directly
storage_service.write("configs", 42, "max_users")
# Stored as: {"max_users": 42}
```

</details>

#### Path-Based Operations

The JSON service supports dot notation for accessing nested data:

```python
# Write to nested path
storage_service.write("users", "alice@newdomain.com", "user_001", 
                     mode=WriteMode.UPDATE, path="email")

# Read from nested path
theme = storage_service.read("users", "user_001", path="preferences.theme")
# Returns: "dark"

# Update deeply nested value
storage_service.write("users", True, "user_001",
                     mode=WriteMode.UPDATE, path="preferences.notifications.email")

# Delete nested path
storage_service.delete("users", "user_001", path="preferences.theme")
```

#### Write Modes

<Tabs>
<TabItem value="write" label="WRITE Mode">

```python
# WRITE: Create new or overwrite (default)
storage_service.write("docs", {"title": "New Doc"}, "doc1", WriteMode.WRITE)
```

</TabItem>
<TabItem value="update" label="UPDATE Mode">

```python
# UPDATE: Merge with existing document
storage_service.write("docs", {"status": "published"}, "doc1", WriteMode.UPDATE)
```

</TabItem>
<TabItem value="append" label="APPEND Mode">

```python
# APPEND: Add to existing collections
storage_service.write("logs", [{"event": "login"}], mode=WriteMode.APPEND)
```

</TabItem>
</Tabs>

### File Storage Service

The file storage service handles text files, binary files, and document formats with optional LangChain loader integration.

<Tabs>
<TabItem value="config" label="Configuration">

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

</TabItem>
<TabItem value="operations" label="Supported Operations">

- Read/write text files with automatic encoding detection
- Handle binary files (images, PDFs, etc.) when enabled
- Document parsing via LangChain loaders (PDF, DOCX, etc.)
- Directory operations and file metadata retrieval

</TabItem>
</Tabs>

## API Reference

### Common Read Operations

#### Reading Entire Collections

<Tabs>
<TabItem value="csv" label="CSV Operations">

```python
# CSV: Read entire CSV file as dict (default)
data = storage_service.read("users")
# Returns: {0: {"id": 1, "name": "Alice"}, 1: {"id": 2, "name": "Bob"}}

# CSV: Read as records for list-like access
data = storage_service.read("users", format="records")
# Returns: [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# CSV: Read as DataFrame for pandas operations
data = storage_service.read("users", format="dataframe")
# Returns: pandas DataFrame
```

</TabItem>
<TabItem value="json" label="JSON Operations">

```python
# JSON: Read entire JSON file as dict structure
data = storage_service.read("users")
# Returns: {"user_001": {...}, "user_002": {...}}
```

</TabItem>
<TabItem value="file" label="File Operations">

```python
# File: Read directory listing
files = storage_service.read("documents")  
# Returns: List of filenames in directory
```

</TabItem>
</Tabs>

#### Reading Specific Documents

<Tabs>
<TabItem value="csv" label="CSV Document">

```python
# CSV: Read specific row by ID
user = storage_service.read("users", document_id=1)
# Returns: Dict with user data, or None if not found
```

</TabItem>
<TabItem value="json" label="JSON Document">

```python
# JSON: Read specific document by ID
user = storage_service.read("users", document_id="user_001")
# Returns: {"name": "Alice", "email": "alice@example.com"}, or None if not found
```

</TabItem>
<TabItem value="file" label="File Content">

```python
# File: Read specific file as raw content (default)
content = storage_service.read("documents", "readme.txt")
# Returns: "file content" (string)

# File: Read specific file with metadata when needed
doc = storage_service.read("documents", "readme.txt", format="structured")
# Returns: {"content": "file content", "metadata": {...}}
```

</TabItem>
</Tabs>

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

#### JSON Query Examples

```python
# Query JSON documents with filters
filtered_users = storage_service.read("user_list", query={
    "active": True,           # Exact match filter
    "role": "admin",          # Role filter
    "sort": "name",          # Sort by field
    "order": "asc",          # Sort direction
    "limit": 10,             # Limit results
    "offset": 0              # Skip first N results
})

# Path-based JSON access
user_email = storage_service.read("users", "user_001", path="contact.email")
user_preferences = storage_service.read("users", "user_001", path="settings")
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
            if inputs.get("with_metadata"):
                data = self.storage_service.read(collection, format="structured")
            else:
                data = self.storage_service.read(collection)  # Raw content (default)
            
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

### Workflow Examples

<Tabs>
<TabItem value="csv" label="CSV Workflow">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,LoadUsers,,Load user data,csv_reader,ProcessUsers,ErrorHandler,"",users,users.csv
DataFlow,ProcessUsers,,Process user list,DataProcessor,SaveResults,ErrorHandler,"users",processed_users,
DataFlow,SaveResults,,Save processed data,csv_writer,End,ErrorHandler,"processed_users",save_result,results.csv
DataFlow,End,,Completion,Echo,,,"save_result",final_message,Data processing complete
DataFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

</TabItem>
<TabItem value="json" label="JSON Workflow">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,LoadConfig,,"{'collection': 'config'}",json_reader,ProcessConfig,ErrorHandler,"",config_data,
DocFlow,ProcessConfig,,Process configuration,DataProcessor,UpdateConfig,ErrorHandler,"config_data",updated_config,
DocFlow,UpdateConfig,,"{'collection': 'config', 'mode': 'update'}",json_writer,End,ErrorHandler,"document_id,updated_config",update_result,
DocFlow,End,,Completion,Echo,,,"update_result",final_message,Configuration updated successfully
DocFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

</TabItem>
<TabItem value="file" label="File Workflow">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,ReadDoc,,"{'format': 'structured'}",file_reader,ProcessDoc,ErrorHandler,"",document,documents/input.pdf
DocFlow,ProcessDoc,,Process document,openai,SaveSummary,ErrorHandler,"document",summary,Summarize this document: {document.content}
DocFlow,SaveSummary,,,file_writer,End,ErrorHandler,"summary",result,output/summary.md
DocFlow,End,,Completion,Echo,,,"result",final_message,Document processed successfully
DocFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

</TabItem>
</Tabs>

## Security Considerations

:::danger Important Security Guidelines

1. **Path Validation**: File service automatically validates paths to prevent directory traversal
2. **Binary Safety**: Configure `allow_binary` appropriately for your security requirements
3. **Encoding Handling**: Specify explicit encodings for consistent text processing
4. **Permission Management**: Ensure storage directories have appropriate permissions
5. **Input Validation**: Always validate user inputs before storage operations

:::

### Secure Configuration Examples

<Tabs>
<TabItem value="production" label="Production Config">

```yaml
storage:
  csv:
    provider: csv
    options:
      base_directory: "/var/app/data/csv"
      encoding: "utf-8"
      validate_paths: true
      max_file_size: "100MB"
  
  json:
    provider: json
    options:
      base_directory: "/var/app/data/json"
      encoding: "utf-8"
      validate_json: true
      backup_enabled: true
  
  file:
    provider: file
    options:
      base_directory: "/var/app/data/files"
      allow_binary: false  # Restrict to text files only
      max_file_size: "50MB"
      allowed_extensions: [".txt", ".md", ".json", ".csv"]
```

</TabItem>
<TabItem value="development" label="Development Config">

```yaml
storage:
  csv:
    provider: csv
    options:
      base_directory: "./data/csv"
      encoding: "utf-8"
  
  json:
    provider: json
    options:
      base_directory: "./data/json"
      encoding: "utf-8"
      indent: 2
  
  file:
    provider: file
    options:
      base_directory: "./data/files"
      allow_binary: true
      encoding: "utf-8"
```

</TabItem>
</Tabs>

## Troubleshooting

### Common Issues and Solutions

<details>
<summary>CSV ID Detection Issues</summary>

**Problem**: Auto-detection fails for business identifiers

**Solution**: Use explicit `id_field` parameter:
```python
# Instead of this (fails)
result = storage_service.read("products", document_id="SKU001")

# Use this (works)
result = storage_service.read("products", document_id="SKU001", id_field="sku")
```

</details>

<details>
<summary>JSON Path Access Errors</summary>

**Problem**: Path not found in nested JSON

**Solution**: Check path exists before accessing:
```python
# Check if path exists
if storage_service.exists("users", "user_001"):
    theme = storage_service.read("users", "user_001", path="preferences.theme")
    if theme is not None:
        # Use theme
        pass
```

</details>

<details>
<summary>File Encoding Issues</summary>

**Problem**: Garbled text when reading files

**Solution**: Specify correct encoding:
```yaml
file:
  options:
    encoding: "utf-8"  # or "latin-1", "cp1252", etc.
```

</details>

<details>
<summary>Performance Issues with Large Files</summary>

**Problem**: Slow operations with large CSV/JSON files

**Solutions**:
1. Use pagination with `limit` and `offset`
2. Use specific document ID reads instead of full collection reads
3. Consider chunking for file operations
4. Use appropriate format (dict vs records vs dataframe)

```python
# Instead of reading entire collection
all_data = storage_service.read("large_collection")

# Use pagination
page_data = storage_service.read("large_collection", query={
    "limit": 100,
    "offset": 0
})
```

</details>

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
```

## Migration Guide

### Updating from Previous Versions

If you're migrating from earlier versions of AgentMap storage services:

:::warning Breaking Changes

1. **CSV Default Format Change**: CSV service now returns dict by default instead of DataFrame
2. **Missing Document Handling**: Update code that expected empty DataFrames or lists to handle `None` returns
3. **ID Field Detection**: CSV service now has smarter ID detection and `id_field` parameter support
4. **File Service Default Format**: File service now returns raw content by default (consistent with other services)
5. **Error Result Updates**: Check for new fields in `StorageResult` objects

:::

<Tabs>
<TabItem value="before" label="Before (Old)">

```python
# Old CSV behavior - returned DataFrame by default
result = storage_service.read("users")
if result.empty:  # DataFrame check
    handle_missing()
for _, row in result.iterrows():  # DataFrame iteration
    process_user(row)

# Old missing document behavior
result = storage_service.read("collection", "missing_id")
if len(result) == 0:  # Empty list/DataFrame check
    handle_missing()

# Old file service returned structured format by default
doc = storage_service.read("files", "doc.txt")  # {"content": "...", "metadata": {...}}
process_document(doc["content"], doc["metadata"])
```

</TabItem>
<TabItem value="after" label="After (New)">

```python
# New CSV behavior - returns dict by default, use format parameter for DataFrame
result = storage_service.read("users")  # Returns: {0: {"id": 1, "name": "Alice"}, ...}
if result is None:  # None check for missing
    handle_missing()
for row_dict in result.values():  # Dict iteration
    process_user(row_dict)

# Use explicit format for DataFrame operations
result = storage_service.read("users", format="dataframe")
for _, row in result.iterrows():  # DataFrame iteration
    process_user(row)

# New consistent missing document behavior
result = storage_service.read("collection", "missing_id")
if result is None:  # None check
    handle_missing()

# File service now returns raw content by default (consistent behavior)
content = storage_service.read("files", "doc.txt")  # "file content string"
process_content(content)

# Use structured format when metadata is needed
doc = storage_service.read("files", "doc.txt", format="structured")
process_document(doc["content"], doc["metadata"])
```

</TabItem>
</Tabs>

### Key Benefits of the New Approach

1. **Storage-Agnostic Default**: Dict format works consistently across CSV, JSON, and other backends
2. **Explicit Format Control**: Choose the right format for your use case (dict/records/dataframe)
3. **Clearer Error Handling**: `None` returns are unambiguous indicators of missing data
4. **Flexible ID Handling**: Auto-detection for common cases, explicit override for edge cases
5. **Better Performance**: Dict format avoids unnecessary DataFrame overhead for simple operations

## Related Documentation

- [Cloud Storage Integration](./cloud-storage-integration.md) - Extend storage to cloud providers
- [Service Registry Patterns](./service-registry-patterns.md) - Host service integration
- [Agent Development Guide](/docs/guides/advanced/agent-development) - Building storage-capable agents
- [Configuration Reference](/docs/reference/configuration) - Complete configuration options

:::tip Next Steps

The storage services provide a consistent, powerful foundation for data operations in AgentMap workflows while maintaining flexibility for different use cases and requirements. Consider implementing [cloud storage integration](./cloud-storage-integration.md) for production deployments.

:::
