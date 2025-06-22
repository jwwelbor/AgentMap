# Storage Services in AgentMap

AgentMap provides a unified storage service system that supports multiple storage backends including CSV files, JSON files, text/binary files, and vector databases. All storage services implement consistent APIs and behavior patterns for reliable data operations.

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

**Configuration:**
```yaml
storage:
  csv:
    provider: csv
    options:
      base_directory: "./data/csv"
      encoding: "utf-8"
```

**Key Features:**
- **Smart ID Field Detection**: Automatically detects common ID patterns (`id`, `user_id`, `order_id`, etc.)
- **Explicit ID Field Override**: Specify custom ID fields for business identifiers (`sku`, `email`, `isbn`)
- **Multiple Format Support**: Returns data as dict (default), records, or DataFrame
- **Missing Documents Return None**: Consistent with other storage services
- **Query and Filter Support**: Pandas-style operations with sorting and pagination

**Supported Operations:**
- Read entire CSV files or specific rows by ID
- Write DataFrames, dictionaries, or lists of dictionaries  
- Query and filter data with pandas-style operations
- Update and append operations with merge capabilities

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

**Automatic ID Detection Logic**

The service searches for ID fields using this priority order:

1. **Exact match**: `"id"` (case insensitive)
2. **Ends with `_id`**: `user_id`, `customer_id`, `order_id`, etc.
3. **Starts with `id_`**: `id_user`, `id_customer`, etc.
4. **If multiple candidates exist**: Prefer first column position, then alphabetical order

**ID Detection Examples**

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

**Explicit ID Field Override**

For business identifiers that don't follow standard naming conventions, you can explicitly specify the ID field. This is particularly useful for:

- **Business identifiers**: `sku`, `email`, `isbn`, `ticker_symbol`
- **Legacy systems**: Non-standard naming conventions
- **Ambiguous cases**: Multiple ID-like columns where auto-detection might be unclear

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

# Example 2: Email as identifier
user_data = [
    {"email": "alice@corp.com", "name": "Alice", "role": "admin"},
    {"email": "bob@corp.com", "name": "Bob", "role": "user"}
]

user = storage_service.read("users", document_id="alice@corp.com", id_field="email")
# Returns: {"email": "alice@corp.com", "name": "Alice", "role": "admin"}

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

**When Auto-Detection Fails**

When no ID field is detected and no explicit `id_field` is provided, operations will fail with clear error messages:

```python
# CSV with no conventional ID fields
data_without_ids = [
    {"name": "Alice", "score": 95},
    {"name": "Bob", "score": 87}
]

# Write works fine
storage_service.write("scores", data_without_ids)

# Read specific document fails
result = storage_service.read("scores", document_id="Alice")
# Returns: None (no ID field detected)

# Delete specific document fails with clear error
result = storage_service.delete("scores", document_id="Alice")
# Returns: StorageResult(success=False, error="ID field not found in CSV...")

# Solution: Use explicit id_field
result = storage_service.read("scores", document_id="Alice", id_field="name")
# Returns: {"name": "Alice", "score": 95}
```

**CSV ID Detection Best Practices**

1. **Use Standard Naming**: Prefer common ID field names (`id`, `user_id`, `order_id`, etc.) for automatic detection
2. **Explicit Override for Business Identifiers**: Use `id_field` parameter for non-standard identifiers like `sku`, `email`, `isbn`
3. **Consistent Data Structure**: Maintain consistent ID field naming across your CSV files for predictable behavior
4. **Clear Error Handling**: Handle cases where no ID field exists and operations fail
5. **Format Selection**: Choose appropriate output formats based on downstream processing needs

**Common Usage Patterns**

```python
# Standard case: Auto-detection works
users = storage_service.read("users", document_id=123)
orders = storage_service.read("orders", document_id="ORD001")

# Business identifier case: Explicit id_field needed
product = storage_service.read("products", document_id="WIDGET001", id_field="sku")
user = storage_service.read("users", document_id="alice@corp.com", id_field="email")
stock = storage_service.read("stocks", document_id="AAPL", id_field="ticker_symbol")

# Bulk operations: Use format parameter for efficiency
all_users_dict = storage_service.read("users")  # Index-based dict
all_users_list = storage_service.read("users", format="records")  # List for iteration
all_users_df = storage_service.read("users", format="dataframe")  # DataFrame for analysis

# Query operations: Always specify format for clarity
active_users = storage_service.read("users", 
                                  query={"active": True, "limit": 100},
                                  format="records")  # List for processing
```

**Advanced CSV Context Configuration**

```yaml
# Automatic ID detection with default format (recommended)
{
  "collection": "users",
  "format": "dict"           # Default: index-based dict
}

# Explicit ID field for business identifiers
{
  "collection": "products", 
  "id_field": "sku",          # Override auto-detection
  "format": "records"         # List format for iteration
}

# Query-based operations
{
  "collection": "sales_data",
  "query": {
    "region": "North",
    "sort": "date",
    "order": "desc",
    "limit": 50
  },
  "format": "dataframe"       # DataFrame for analysis
}

# Agent workflow configuration
{
  "collection": "transaction_details",
  "id_field": "transaction_id", # Primary identifier
  "format": "records",          # List for processing
  "encoding": "utf-8"           # File encoding
}
```

### JSON Storage Service

The JSON storage service provides document-based operations on JSON files with support for nested data structures, path-based access, and document management. It uses a **direct storage** model where each document is stored exactly as provided.

**Key Concept:** The JSON service uses direct storage for maximum simplicity:
- `document_id` = storage key (never injected into user data)
- `data` = document content (stored exactly as provided)
- Storage structure: `{document_id: user_data}`
- Read operations return data exactly as stored

**Configuration:**
```yaml
storage:
  json:
    provider: json
    options:
      base_directory: "./data/json"
      encoding: "utf-8"
      indent: 2
```

**Supported Operations:**
- Read entire JSON files or specific documents by ID
- Write documents with automatic structure creation
- Update documents with merge capabilities
- Path-based operations using dot notation
- Query and filter documents
- Delete documents or specific nested paths

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

**Direct Storage for All Data Types:**

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

**Reading returns data exactly as stored:**

```python
config = storage_service.read("configs", "app_config")  
# Returns: {"debug": True, "port": 8080}

env = storage_service.read("configs", "environment")  
# Returns: "production"

items = storage_service.read("configs", "allowed_items")  
# Returns: ["item1", "item2"]

max_users = storage_service.read("configs", "max_users")  
# Returns: 42
```

#### Direct Storage Usage Patterns

**Pattern 1: Multiple Documents in Collection**
```python
# Multiple user documents
storage_service.write("users", {"name": "Alice", "role": "admin"}, "user001")
storage_service.write("users", {"name": "Bob", "role": "user"}, "user002")

# Storage structure:
{
  "user001": {"name": "Alice", "role": "admin"},
  "user002": {"name": "Bob", "role": "user"}
}

# Read individual documents
user = storage_service.read("users", "user001")
# Returns: {"name": "Alice", "role": "admin"}

# Read entire collection
all_users = storage_service.read("users")
# Returns: {"user001": {"name": "Alice", "role": "admin"}, "user002": {"name": "Bob", "role": "user"}}
```

**Pattern 2: Single Document with List User Data**
```python
# Single document containing a list of items
items_list = [
    {"id": "item1", "title": "First Item"},
    {"id": "item2", "title": "Second Item"}
]
storage_service.write("collections", items_list, "item_list")

# Storage structure:
{
  "item_list": [
    {"id": "item1", "title": "First Item"},
    {"id": "item2", "title": "Second Item"}
  ]
}

# Read the list document
items = storage_service.read("collections", "item_list")
# Returns: [{"id": "item1", "title": "First Item"}, {"id": "item2", "title": "Second Item"}]

# To find "item1" within the list, use queries, not ID lookup:
filtered = storage_service.read("collections", "item_list", query={"id": "item1"})
```

#### ID Lookup vs Content Queries

**ID Lookup** - Direct document retrieval by storage key:
```python
# ✅ ID lookup finds documents by storage key
user = storage_service.read("users", "user001")  # Finds document with ID "user001"
config = storage_service.read("configs", "app_settings")  # Finds document with ID "app_settings"

# ✅ Works for any document regardless of content structure
list_doc = storage_service.read("collections", "item_list")  # Finds document with ID "item_list"
string_doc = storage_service.read("configs", "environment")  # Finds document with ID "environment"
```

**Content Queries** - Searching within user data:
```python
# ❌ ID lookup CANNOT search inside user data
item = storage_service.read("collections", "item1")  # Returns None (not a storage key)

# ✅ Use queries to search within user data
results = storage_service.read("user_list", query={"role": "admin"})  # Searches content
filtered = storage_service.read("items", query={"category": "electronics"})  # Searches content
```

#### Basic JSON Operations

**Writing Documents:**

```python
from agentmap.services.storage.types import WriteMode

# Write new document
result = storage_service.write("users", {
    "name": "Alice",
    "email": "alice@example.com",
    "preferences": {"theme": "dark"}
}, "user_001")

# Write non-dict data (stored directly)
result = storage_service.write("settings", "production", "environment")
# Stored as: {"environment": "production"}

# Update existing document (merges with existing data)
result = storage_service.write("users", {
    "preferences": {"notifications": True}
}, "user_001", mode=WriteMode.UPDATE)
```

**Reading Documents:**

```python
# Read specific document
user = storage_service.read("users", "user_001")
# Returns: {"name": "Alice", "email": "alice@example.com", "preferences": {...}}

# Read entire collection
all_users = storage_service.read("users")
# Returns: {"user_001": {...}, "user_002": {...}}

# Missing document returns None
missing = storage_service.read("users", "nonexistent")
# Returns: None
```

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

#### Query and Filtering

```python
# Basic filtering (works with list-structured JSON)
filtered_users = storage_service.read("user_list", query={
    "active": True,
    "role": "admin"
})

# Sorting and pagination
results = storage_service.read("user_list", query={
    "active": True,
    "sort": "name",
    "order": "asc",
    "limit": 10,
    "offset": 20
})

# Complex nested queries
advanced_results = storage_service.read("orders", query={
    "status": "completed",
    "sort": "total",
    "order": "desc"
})
```

#### Write Modes

```python
# WRITE: Create new or overwrite (default)
storage_service.write("docs", {"title": "New Doc"}, "doc1", WriteMode.WRITE)

# UPDATE: Merge with existing document
storage_service.write("docs", {"status": "published"}, "doc1", WriteMode.UPDATE)

# APPEND: Add to existing collections
storage_service.write("logs", [{"event": "login"}], mode=WriteMode.APPEND)
```

#### Mixed Data Types

The JSON service handles different data types with direct storage:

```python
# Dictionary data (stored directly)
storage_service.write("configs", {"debug": True, "port": 8080}, "app_config")

# All data types stored directly as-is
storage_service.write("configs", "production", "environment")
storage_service.write("configs", 42, "max_users")
storage_service.write("configs", ["item1", "item2"], "allowed_items")

# Reading back
config = storage_service.read("configs", "app_config")  
# Returns: {"debug": True, "port": 8080}

env = storage_service.read("configs", "environment")  
# Returns: "production"

max_count = storage_service.read("configs", "max_users")  
# Returns: 42

items = storage_service.read("configs", "allowed_items")
# Returns: ["item1", "item2"]
```

#### Error Handling

```python
# Check if document exists
if storage_service.exists("users", "user_001"):
    user = storage_service.read("users", "user_001")

# Handle write failures
result = storage_service.write("users", invalid_data, "user_001")
if not result.success:
    print(f"Write failed: {result.error}")

# Safe document updates
result = storage_service.write("users", updates, "user_001", WriteMode.UPDATE)
if not result.success:
    print(f"Update failed: {result.error}")
```

#### Usage in Agents

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import StorageCapableAgent

class DocumentManagerAgent(BaseAgent, StorageCapableAgent):
    """Agent that manages JSON documents."""
    
    def process(self, inputs):
        """Process document operations."""
        operation = inputs.get("operation", "read")
        collection = inputs.get("collection", "documents")
        
        if operation == "create_document":
            doc_data = inputs.get("data", {})
            doc_id = inputs.get("document_id")
            
            result = self.storage_service.write(collection, doc_data, doc_id)
            if result.success:
                return {"status": "created", "document_id": doc_id}
            else:
                return {"status": "error", "message": result.error}
        
        elif operation == "update_document":
            doc_id = inputs.get("document_id")
            updates = inputs.get("updates", {})
            
            # Check if document exists
            if not self.storage_service.exists(collection, doc_id):
                return {"status": "error", "message": "Document not found"}
            
            # Perform update
            result = self.storage_service.write(
                collection, updates, doc_id, WriteMode.UPDATE
            )
            
            if result.success:
                return {"status": "updated", "document_id": doc_id}
            else:
                return {"status": "error", "message": result.error}
        
        elif operation == "get_document":
            doc_id = inputs.get("document_id")
            path = inputs.get("path")  # Optional nested path
            
            doc = self.storage_service.read(collection, doc_id, path=path)
            if doc is not None:
                return {"status": "found", "document": doc}
            else:
                return {"status": "not_found", "document_id": doc_id}
        
        else:
            return {"status": "error", "message": f"Unknown operation: {operation}"}
```

#### Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,CreateUser,,"{'collection': 'users'}",json_writer,GetUser,ErrorHandler,"user_data",create_result,
DocFlow,GetUser,,"{'collection': 'users'}",json_reader,UpdateUser,ErrorHandler,"user_id",user_doc,
DocFlow,UpdateUser,,"{'collection': 'users', 'mode': 'update'}",json_writer,End,ErrorHandler,"user_id,updates",update_result,
DocFlow,End,,Completion,Echo,,,"update_result",final_message,User updated successfully
DocFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

#### Advanced Context Configuration

```yaml
# Basic JSON agent context
{
  "collection": "user_profiles",
  "format": "raw"                # Default: returns user data unchanged
}

# Document operations with paths
{
  "collection": "configurations",
  "document_id": "app_settings",
  "path": "database.connection",   # Access nested values
  "mode": "update"                 # For write operations
}

# Query-based operations
{
  "collection": "order_history", 
  "query": {
    "status": "completed",
    "sort": "date",
    "order": "desc",
    "limit": 50
  }
}
```

#### Best Practices

1. **Document ID Strategy**: Use meaningful, unique IDs that don't conflict with your data structure
2. **Data Immutability**: The service preserves your data exactly as provided - plan your structure accordingly
3. **Path Operations**: Use dot notation for efficient nested updates instead of reading/modifying/writing entire documents
4. **Error Handling**: Always check `StorageResult.success` for write operations and handle `None` returns for reads
5. **Performance**: Use path-based operations for large documents to avoid unnecessary data transfer

#### Storage Structure Examples

**Simple Documents:**
```json
{
  "user_123": {"name": "Alice", "role": "admin"},
  "user_456": {"name": "Bob", "role": "user"}
}
```

**Mixed Data Types:**
```json
{
  "string_setting": "production",
  "number_setting": 8080,
  "object_setting": {"debug": true, "features": ["auth", "logging"]},
  "list_setting": ["item1", "item2", "item3"]
}
```

**Nested Structures:**
```json
{
  "app_config": {
    "database": {
      "host": "localhost",
      "port": 5432,
      "credentials": {"username": "admin"}
    },
    "features": ["auth", "logging", "metrics"]
  }
}
```

The JSON storage service provides a simple, efficient foundation for document-based data operations with direct storage that preserves your data exactly as provided.

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
# CSV: Read entire CSV file as dict (default)
data = storage_service.read("users")
# Returns: {0: {"id": 1, "name": "Alice"}, 1: {"id": 2, "name": "Bob"}}

# CSV: Read as records for list-like access
data = storage_service.read("users", format="records")
# Returns: [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# CSV: Read as DataFrame for pandas operations
data = storage_service.read("users", format="dataframe")
# Returns: pandas DataFrame

# JSON: Read entire JSON file as dict structure
data = storage_service.read("users")
# Returns: {"user_001": {...}, "user_002": {...}}

# File: Read directory listing
files = storage_service.read("documents")  
# Returns: List of filenames in directory
```

#### Reading Specific Documents

```python
# CSV: Read specific row by ID
user = storage_service.read("users", document_id=1)
# Returns: Dict with user data, or None if not found

# JSON: Read specific document by ID
user = storage_service.read("users", document_id="user_001")
# Returns: {"name": "Alice", "email": "alice@example.com"}, or None if not found

# File: Read specific file as raw content (default)
content = storage_service.read("documents", "readme.txt")
# Returns: "file content" (string)

# File: Read specific file with metadata when needed
doc = storage_service.read("documents", "readme.txt", format="structured")
# Returns: {"content": "file content", "metadata": {...}}
```

#### Output Format Options

All storage services support format options, with CSV offering the most flexibility:

```python
# CSV Default format: dict with index-based keys (storage-agnostic)
result = storage_service.read("users")
# Returns: {0: {"id": 1, "name": "Alice"}, 1: {"id": 2, "name": "Bob"}}

# CSV Records format: list of row dictionaries
result = storage_service.read("users", format="records")
# Returns: [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# CSV DataFrame format: pandas DataFrame for advanced operations
result = storage_service.read("users", format="dataframe")
# Returns: pandas.DataFrame with all CSV data

# JSON/File default: Raw content (consistent across all services)
content = storage_service.read("documents", "file.txt")
# Returns: "file content" (string for text, bytes for binary, dict for JSON)

# Structured format: Content with metadata (when available)
structured = storage_service.read("documents", "file.txt", format="structured")
# Returns: {"content": "...", "metadata": {"source": "...", "size": 123, "type": "text"}}
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

# JSON: Write document with ID
result = storage_service.write("users", {
    "name": "Alice", 
    "email": "alice@example.com"
}, "user_001")

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

# Complex JSON queries
order_results = storage_service.read("orders", query={
    "status": "completed",
    "sort": "total",
    "order": "desc",
    "limit": 25
})

# Path-based JSON access
user_email = storage_service.read("users", "user_001", path="contact.email")
user_preferences = storage_service.read("users", "user_001", path="settings")
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

### CSV Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,LoadUsers,,Load user data,csv_reader,ProcessUsers,ErrorHandler,"",users,users.csv
DataFlow,ProcessUsers,,Process user list,DataProcessor,SaveResults,ErrorHandler,"users",processed_users,
DataFlow,SaveResults,,Save processed data,csv_writer,End,ErrorHandler,"processed_users",save_result,results.csv
DataFlow,End,,Completion,Echo,,,"save_result",final_message,Data processing complete
DataFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

### JSON Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,LoadConfig,,"{'collection': 'config'}",json_reader,ProcessConfig,ErrorHandler,"",config_data,
DocFlow,ProcessConfig,,Process configuration,DataProcessor,UpdateConfig,ErrorHandler,"config_data",updated_config,
DocFlow,UpdateConfig,,"{'collection': 'config', 'mode': 'update'}",json_writer,End,ErrorHandler,"document_id,updated_config",update_result,
DocFlow,End,,Completion,Echo,,,"update_result",final_message,Configuration updated successfully
DocFlow,ErrorHandler,,Handle errors,Echo,End,,"error",error_message,Error: {error}
```

### File Workflow Examples

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,ReadDoc,,"{'format': 'structured'}",file_reader,ProcessDoc,ErrorHandler,"",document,documents/input.pdf
DocFlow,ProcessDoc,,Process document,openai,SaveSummary,ErrorHandler,"document",summary,Summarize this document: {document.content}
DocFlow,SaveSummary,,,file_writer,End,ErrorHandler,"summary",result,output/summary.md
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

# JSON Agent Context
{
  "collection": "user_profiles",
  "format": "raw",              # Default: returns user data unchanged
  "document_id": "user_001",    # Optional: specific document
  "path": "preferences.theme",  # Optional: nested path access
  "mode": "update"              # For write operations
}

# File Agent Context  
{
  "collection": "documents",
  "format": "default",          # Raw content by default (use "structured" for metadata)
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

1. **CSV Default Format Change**: CSV service now returns dict by default instead of DataFrame
2. **Missing Document Handling**: Update code that expected empty DataFrames or lists to handle `None` returns
3. **ID Field Detection**: CSV service now has smarter ID detection and `id_field` parameter support
4. **File Service Default Format**: File service now returns raw content by default (consistent with other services)
5. **Error Result Updates**: Check for new fields in `StorageResult` objects

**Before:**
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

**After:**
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

# New CSV ID field capabilities
# Auto-detection works for standard cases
user = storage_service.read("users", document_id=123)  # Uses 'id' column
order = storage_service.read("orders", document_id="ORD001")  # Uses 'order_id' column

# Explicit id_field for business identifiers
product = storage_service.read("products", document_id="WIDGET001", id_field="sku")
user = storage_service.read("users", document_id="alice@corp.com", id_field="email")
```

### Key Benefits of the New Approach

1. **Storage-Agnostic Default**: Dict format works consistently across CSV, JSON, and other backends
2. **Explicit Format Control**: Choose the right format for your use case (dict/records/dataframe)
3. **Clearer Error Handling**: `None` returns are unambiguous indicators of missing data
4. **Flexible ID Handling**: Auto-detection for common cases, explicit override for edge cases
5. **Better Performance**: Dict format avoids unnecessary DataFrame overhead for simple operations

The storage services now provide a consistent, powerful foundation for data operations in AgentMap workflows while maintaining flexibility for different use cases and requirements.
