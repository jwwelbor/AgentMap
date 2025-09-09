---
title: Storage Configuration
sidebar_position: 3
description: Complete guide to AgentMap storage providers including CSV, JSON, Vector databases, Firebase, and cloud storage with authentication and optimization.
keywords: [storage configuration, CSV storage, JSON storage, vector databases, Firebase, cloud storage]
---

# Storage Configuration

AgentMap provides a unified storage service system supporting multiple backends including CSV files, JSON documents, vector databases, Firebase, and cloud storage providers. This guide covers complete storage configuration with authentication, optimization, and best practices.

## 📋 Storage Configuration Overview

Storage configuration is defined in a separate YAML file (typically `agentmap_config_storage.yaml`) and supports:

- **Local Storage**: CSV, JSON, File storage with intelligent management
- **Vector Databases**: Pinecone, Supabase Vector, local vector storage
- **Key-Value Stores**: Redis, local JSON, in-memory storage
- **Firebase**: Firestore, Realtime Database, Cloud Storage
- **Cloud Storage**: Azure Blob, AWS S3, Google Cloud Storage
- **Memory Storage**: High-performance in-memory operations

## 🗂️ Complete Storage Configuration Structure

```yaml
# CSV storage configuration
csv:
  default_directory: "data/csv"
  # Enable automatic CSV file creation on write operations
  auto_create_files: false
  collections:
    users: "data/csv/users.csv"
    products: "data/csv/products.csv"
    orders: "data/csv/orders.csv"

# JSON document storage
json:
  default_directory: "data/json"
  encoding: "utf-8"
  indent: 2
  collections:
    configs: "data/json/configs.json"
    user_profiles: "data/json/profiles.json"

# Vector database storage
vector:
  default_provider: "local"
  collections:
    documents:
      provider: "pinecone"
      index_name: "document-index"
      namespace: "general"
      dimension: 1536
      metric: "cosine"
      api_key: "env:PINECONE_API_KEY"

# Key-value storage
kv:
  default_provider: "local"
  collections:
    cache:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "agentmap:"

# Firebase configuration
firebase:
  default_project: "env:FIREBASE_DEFAULT_PROJECT"
  auth:
    service_account_key: "env:FIREBASE_SERVICE_ACCOUNT"
  firestore:
    collections:
      users:
        collection_path: "users"

# File storage configuration
file:
  default_directory: "data/files"
  encoding: "utf-8"
  allow_binary: true
  chunk_size: 1000
  chunk_overlap: 200

# Memory storage (high-performance)
memory:
  default_ttl: 3600  # Time to live in seconds
  max_size: 10000    # Maximum number of items
  cleanup_interval: 300  # Cleanup interval in seconds
```

## 📄 CSV Storage Configuration

CSV storage provides pandas-based operations with intelligent ID field detection and multiple output formats.

### Basic CSV Configuration

```yaml
csv:
  # Default directory for CSV files
  default_directory: "data/csv"
  
  # Optional: Global encoding setting
  encoding: "utf-8"
  
  # File creation behavior
  auto_create_files: false  # Enable automatic CSV file creation on write operations
  
  # Named CSV collections
  collections:
    # Simple filename mapping
    users: "data/csv/users.csv"
    products: "data/csv/products.csv"
    orders: "data/csv/orders.csv"
    
    # Subdirectory organization
    customers: "data/csv/customers/info.csv"
    transactions: "data/csv/financial/transactions.csv"
    
    # Log files
    app_logs: "logs/app_events.csv"
    audit_logs: "logs/audit/security_events.csv"
```

### Advanced CSV Configuration

```yaml
csv:
  default_directory: "data/csv"
  
  # Global CSV options
  options:
    encoding: "utf-8"
    delimiter: ","
    quotechar: '"'
    escapechar: null
    
  # Collection-specific configurations
  collections:
    # Standard configuration
    users:
      path: "data/csv/users.csv"
      encoding: "utf-8"
    
    # Custom delimiter and encoding
    legacy_data:
      path: "imports/legacy.txt"
      delimiter: "|"
      encoding: "latin-1"
    
    # Large dataset optimization
    large_dataset:
      path: "data/csv/big_data.csv"
      chunk_size: 10000
      low_memory: true
    
    # Custom ID field specification
    products:
      path: "data/csv/products.csv"
      id_field: "sku"  # Use SKU as identifier instead of auto-detection
    
    # Business identifier examples
    employees:
      path: "data/csv/employees.csv"
      id_field: "employee_id"
    
    stocks:
      path: "data/csv/stocks.csv"
      id_field: "ticker_symbol"
```

### CSV Auto-Creation Behavior

CSV Storage Service can automatically create CSV files that don't exist when write operations are performed. This behavior is controlled by the `auto_create_files` configuration option:

```yaml
csv:
  default_directory: "data/csv"
  auto_create_files: true  # Enable automatic CSV file creation on write
```

**Key Features:**
- When `auto_create_files: true`, missing CSV files are automatically created during write operations
- When `auto_create_files: false` (default), write operations to non-existent files will fail with a clear error message
- File structure is determined by the data being written
- Directories are always created automatically regardless of this setting
- Default value is `false` for backward compatibility

**Example Error Message (when disabled):**
```
CSV file does not exist: data/csv/new_file.csv. Enable auto_create_files: true in CSV config to create automatically.
```

### CSV ID Field Detection

AgentMap automatically detects ID fields using smart logic:

**Automatic Detection Priority:**
1. Exact match: `"id"` (case insensitive)
2. Ends with `_id`: `user_id`, `customer_id`, `order_id`
3. Starts with `id_`: `id_user`, `id_customer`
4. First column position if multiple candidates exist

**Explicit ID Field Override:**
```yaml
csv:
  collections:
    # Business identifiers require explicit configuration
    products:
      path: "products.csv"
      id_field: "sku"  # Product SKU as identifier
    
    users:
      path: "users.csv"
      id_field: "email"  # Email as identifier
    
    stocks:
      path: "stocks.csv"
      id_field: "ticker"  # Stock ticker symbol
```

## 📄 JSON Document Storage

JSON storage provides document-based operations with direct storage model and path-based access.

### Basic JSON Configuration

```yaml
json:
  # Default directory for JSON files
  default_directory: "data/json"
  
  # Global JSON formatting
  encoding: "utf-8"
  indent: 2
  ensure_ascii: false
  
  # Named JSON collections
  collections:
    # Application configuration
    app_config: "data/json/config.json"
    user_preferences: "data/json/preferences.json"
    
    # User data
    user_profiles: "data/json/users.json"
    session_data: "data/json/sessions.json"
    
    # Business data
    product_catalog: "data/json/products.json"
    order_history: "data/json/orders.json"
```

### Advanced JSON Configuration

```yaml
json:
  default_directory: "data/json"
  
  # Global options
  options:
    encoding: "utf-8"
    indent: 2
    ensure_ascii: false
    sort_keys: true
  
  # Collection-specific configurations
  collections:
    # Standard document collection
    users:
      path: "data/json/users.json"
      format: "pretty"  # Pretty-printed JSON
    
    # Compact storage for large datasets
    analytics:
      path: "data/json/analytics.json"
      format: "compact"  # No indentation
      compression: true
    
    # Secure configuration
    secrets:
      path: "secure/secrets.json"
      encryption: true
      encryption_key: "env:ENCRYPTION_KEY"
    
    # Versioned documents
    versioned_config:
      path: "data/json/config.json"
      versioning: true
      max_versions: 10
    
    # Cloud storage integration
    cloud_documents: "azure://container/documents.json"
    s3_backup: "s3://backup-bucket/data.json"
    gcs_archive: "gs://archive-bucket/historical.json"
```

## 🔍 Vector Database Configuration

Vector storage supports multiple providers for semantic search and embeddings.

### Pinecone Configuration

```yaml
vector:
  default_provider: "pinecone"
  
  collections:
    documents:
      provider: "pinecone"
      index_name: "document-index"
      namespace: "general"
      dimension: 1536  # OpenAI embeddings dimension
      metric: "cosine"
      api_key: "env:PINECONE_API_KEY"
      environment: "env:PINECONE_ENVIRONMENT"
    
    product_embeddings:
      provider: "pinecone"
      index_name: "products"
      namespace: "catalog"
      dimension: 768   # Alternative embedding dimension
      metric: "euclidean"
      api_key: "env:PINECONE_API_KEY"
```

### Supabase Vector Configuration

```yaml
vector:
  collections:
    knowledge_base:
      provider: "supabase"
      table: "embeddings"
      connection_string: "env:SUPABASE_URL"
      api_key: "env:SUPABASE_KEY"
      dimension: 1536
      
    user_content:
      provider: "supabase"
      table: "user_embeddings"
      connection_string: "env:SUPABASE_URL"
      api_key: "env:SUPABASE_KEY"
      query_limit: 100
```

### Local Vector Storage

```yaml
vector:
  collections:
    local_documents:
      provider: "local"
      path: "data/vector/documents"
      dimension: 768
      index_type: "hnsw"  # Hierarchical Navigable Small World
      ef_construction: 200
      m: 16
    
    development_vectors:
      provider: "local"
      path: "data/vector/dev"
      dimension: 384      # Smaller dimension for development
      index_type: "flat"  # Simple flat index
```

## 🔑 Key-Value Storage Configuration

Key-value storage provides fast, simple data operations with multiple backend options.

### Redis Configuration

```yaml
kv:
  default_provider: "redis"
  
  collections:
    # Session cache
    sessions:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "session:"
      ttl: 3600  # 1 hour
    
    # Application cache
    app_cache:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "cache:"
      ttl: 300   # 5 minutes
    
    # Rate limiting
    rate_limits:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "ratelimit:"
      ttl: 60    # 1 minute
```

### Local Key-Value Storage

```yaml
kv:
  collections:
    # Local JSON storage
    local_cache:
      provider: "local"
      path: "data/kv/cache.json"
      auto_save: true
      save_interval: 30  # Auto-save every 30 seconds
    
    # Application settings
    settings:
      provider: "local"
      path: "data/kv/settings.json"
      backup: true
      backup_interval: 3600  # Backup every hour
```

### Memory Key-Value Storage

```yaml
kv:
  collections:
    # High-speed memory cache
    temp_cache:
      provider: "memory"
      ttl: 300      # 5 minutes
      max_size: 1000  # Maximum 1000 entries
    
    # Session storage
    user_sessions:
      provider: "memory"
      ttl: 1800     # 30 minutes
      cleanup_interval: 300  # Cleanup every 5 minutes
```

## 🔥 Firebase Configuration

Firebase integration supports Firestore, Realtime Database, and Cloud Storage.

### Firebase Authentication

```yaml
firebase:
  # Default project ID
  default_project: "env:FIREBASE_DEFAULT_PROJECT"
  
  # Authentication configuration
  auth:
    # Service account key file (recommended for server applications)
    service_account_key: "env:FIREBASE_SERVICE_ACCOUNT"
    
    # Alternative: API key authentication (for client applications)
    # api_key: "env:FIREBASE_API_KEY"
    # email: "env:FIREBASE_EMAIL"
    # password: "env:FIREBASE_PASSWORD"
```

### Firestore Configuration

```yaml
firebase:
  firestore:
    collections:
      # User management
      users:
        collection_path: "users"
        project_id: "env:FIREBASE_PROJECT_ID"  # Optional project override
      
      # Product catalog
      products:
        collection_path: "inventory/products"
        query_limit: 100
        order_by: "created_at"
        direction: "desc"
      
      # Order tracking
      orders:
        collection_path: "transactions/orders"
        query_limit: 50
        filters:
          status: "active"
      
      # Nested collections
      user_preferences:
        collection_path: "users/{user_id}/preferences"
        dynamic_path: true  # Supports path parameters
```

### Realtime Database Configuration

```yaml
firebase:
  realtime_db:
    collections:
      # Active user tracking
      active_users:
        db_url: "env:FIREBASE_RTDB_URL"
        path: "users/active"
        
      # Real-time game state
      game_state:
        path: "games/current"
        ordered_by: "timestamp"
        limit_to_last: 100
      
      # Chat messages
      chat_messages:
        path: "chat/rooms/{room_id}/messages"
        dynamic_path: true
        query_limit: 50
        order_by: "timestamp"
```

### Firebase Cloud Storage

```yaml
firebase:
  storage:
    collections:
      # User file uploads
      user_uploads:
        bucket: "env:FIREBASE_STORAGE_BUCKET"
        path: "uploads/user"
        max_file_size: "10MB"
        allowed_types: ["image/jpeg", "image/png", "application/pdf"]
      
      # Product images
      product_images:
        bucket: "products-images-bucket"
        path: "images/products"
        max_file_size: "5MB"
        allowed_types: ["image/jpeg", "image/png"]
      
      # System backups
      backup_files:
        bucket: "backups-bucket"
        path: "automated/daily"
        retention_days: 30
```

## ☁️ Cloud Storage Configuration

AgentMap supports major cloud storage providers with unified URI-based access.

### Azure Blob Storage

```yaml
# Azure configuration in JSON storage section
json:
  providers:
    azure:
      # Primary authentication method
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      
      # Alternative authentication
      # account_name: "env:AZURE_STORAGE_ACCOUNT"
      # account_key: "env:AZURE_STORAGE_KEY"
      
      default_container: "documents"
      
      # Container mappings
      containers:
        users: "users-container"
        reports: "reports-container"
        backups: "backup-container"
  
  collections:
    # Direct URI access
    azure_users: "azure://users/data.json"
    azure_config: "azure://documents/config.json"
    
    # Named container access
    user_profiles: "azure://users-container/profiles.json"
```

### AWS S3 Configuration

```yaml
json:
  providers:
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      
      # Optional: Session token for temporary credentials
      session_token: "env:AWS_SESSION_TOKEN"
      
      default_bucket: "my-documents"
      
      # Bucket mappings
      buckets:
        users: "users-bucket"
        reports: "reports-bucket"
        archives: "archive-bucket"
  
  collections:
    # Direct S3 URIs
    s3_reports: "s3://reports/monthly.json"
    s3_config: "s3://my-documents/config.json"
    
    # Named bucket access
    user_data: "s3://users-bucket/profiles.json"
```

### Google Cloud Storage

```yaml
json:
  providers:
    gcp:
      project_id: "env:GCP_PROJECT_ID"
      
      # Service account authentication (recommended)
      credentials_file: "path/to/service-account.json"
      
      # Alternative: Application default credentials
      # use_default_credentials: true
      
      default_bucket: "documents"
      
      # Bucket mappings
      buckets:
        users: "users-bucket"
        analytics: "analytics-bucket"
  
  collections:
    # Direct GCS URIs
    gcs_data: "gs://documents/data.json"
    gcs_config: "gs://my-bucket/config.json"
```

## 📁 File Storage Configuration

File storage handles text files, binary files, and document formats with LangChain integration.

### Basic File Configuration

```yaml
file:
  # Default directory for file operations
  default_directory: "data/files"
  
  # Text file settings
  encoding: "utf-8"
  
  # Binary file support
  allow_binary: true
  
  # Document processing
  chunk_size: 1000
  chunk_overlap: 200
  
  # Collections (directory mappings)
  collections:
    documents: "data/files/documents"
    images: "data/files/images"
    uploads: "data/files/uploads"
```

### Advanced File Configuration

```yaml
file:
  default_directory: "data/files"
  
  # Global file options
  options:
    encoding: "utf-8"
    allow_binary: true
    max_file_size: "100MB"
    
  # Document processing with LangChain
  document_processing:
    enable_loaders: true
    chunk_size: 1000
    chunk_overlap: 200
    
    # Supported document types
    loaders:
      pdf: "PyPDFLoader"
      docx: "UnstructuredWordDocumentLoader"
      txt: "TextLoader"
      md: "UnstructuredMarkdownLoader"
  
  # Collection-specific configurations
  collections:
    # Document storage
    documents:
      path: "data/files/documents"
      allowed_types: [".pdf", ".docx", ".txt", ".md"]
      processing:
        chunk_size: 500
        enable_ocr: true
    
    # Image storage
    images:
      path: "data/files/images"
      allowed_types: [".jpg", ".jpeg", ".png", ".gif"]
      max_file_size: "10MB"
      generate_thumbnails: true
    
    # Secure file storage
    secure_files:
      path: "secure/files"
      encryption: true
      encryption_key: "env:FILE_ENCRYPTION_KEY"
      access_control: true
```

## 💾 Memory Storage Configuration

High-performance in-memory storage for temporary data and caching.

```yaml
memory:
  # Global memory settings
  default_ttl: 3600        # Default time to live (1 hour)
  max_size: 10000          # Maximum number of items
  cleanup_interval: 300    # Cleanup interval (5 minutes)
  
  # Memory collections
  collections:
    # Session cache
    sessions:
      ttl: 1800            # 30 minutes
      max_size: 1000
      cleanup_on_access: true
    
    # API response cache
    api_cache:
      ttl: 300             # 5 minutes
      max_size: 5000
      compression: true     # Compress stored data
    
    # Temporary workflow data
    temp_data:
      ttl: 600             # 10 minutes
      max_size: 500
      persist_on_shutdown: false
```

## 🔐 Storage Authentication

### Environment Variable Security

```yaml
# Secure credential management
vector:
  collections:
    documents:
      provider: "pinecone"
      api_key: "env:PINECONE_API_KEY"        # Environment variable
      environment: "env:PINECONE_ENVIRONMENT"

firebase:
  auth:
    service_account_key: "env:FIREBASE_SERVICE_ACCOUNT"  # File path from env

kv:
  collections:
    cache:
      provider: "redis"
      connection: "env:REDIS_URL"            # Full connection string
```

### Cloud Provider Authentication

**Azure Authentication:**
```yaml
json:
  providers:
    azure:
      # Method 1: Connection string (recommended)
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      
      # Method 2: Account name and key
      account_name: "env:AZURE_STORAGE_ACCOUNT"
      account_key: "env:AZURE_STORAGE_KEY"
```

**AWS Authentication:**
```yaml
json:
  providers:
    aws:
      # Method 1: Access key and secret (recommended)
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      
      # Method 2: Temporary credentials
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      session_token: "env:AWS_SESSION_TOKEN"
```

**Google Cloud Authentication:**
```yaml
json:
  providers:
    gcp:
      # Method 1: Service account file (recommended)
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE"
      
      # Method 2: Application default credentials
      use_default_credentials: true
```

## ⚡ Storage Performance Optimization

### Connection Pooling

```yaml
# Global connection settings
connection_pool:
  max_connections: 100
  pool_timeout: 30
  retry_attempts: 3
  connection_lifetime: 3600

# Provider-specific pooling
vector:
  collections:
    documents:
      provider: "pinecone"
      connection_pool:
        max_connections: 50
        timeout: 15
```

### Caching Configuration

```yaml
# Storage-level caching
cache:
  enabled: true
  type: "memory"          # "memory", "redis", "file"
  ttl: 3600              # 1 hour
  max_size: 1000
  
  # Cache strategies
  strategies:
    read_through: true    # Cache read results
    write_through: true   # Cache write results
    write_behind: false   # Async write to storage
```

### Batch Operations

```yaml
# Batch processing settings
batch_processing:
  enabled: true
  batch_size: 100        # Items per batch
  batch_timeout: 5       # Seconds to wait for batch completion
  parallel_batches: 4    # Number of parallel batch processors
```

## 🔧 Storage Service Integration

### Agent Integration Example

```yaml
# Storage configuration for agents
agent_storage:
  # Default storage provider for agents
  default_provider: "json"
  
  # Agent-specific storage mappings
  agent_mappings:
    DataProcessorAgent: "csv"
    DocumentAnalyzer: "vector"
    SessionManager: "kv"
    FileProcessor: "file"
  
  # Storage context injection
  context_injection:
    enabled: true
    auto_configure: true
```

### Workflow Storage Context

```csv
graph_name,node_name,context,agent_type,input_fields,output_field
DataFlow,LoadUsers,"{'collection': 'users', 'format': 'records'}",csv_reader,user_query,users
DataFlow,ProcessUsers,"{'collection': 'processed_users'}",json_writer,processed_data,result
```

## 🛠️ Troubleshooting Storage Configuration

### Common Configuration Issues

**Connection Failures:**
```yaml
# ❌ Invalid Redis connection
kv:
  collections:
    cache:
      provider: "redis"
      connection: "redis://invalid-host:6379"  # Wrong host

# ✅ Correct Redis connection
kv:
  collections:
    cache:
      provider: "redis"
      connection: "env:REDIS_URL"  # Use environment variable
```

**Authentication Issues:**
```yaml
# ❌ Hardcoded credentials (security risk)
vector:
  collections:
    docs:
      api_key: "pk-1234567890abcdef"  # Never do this

# ✅ Environment variable credentials
vector:
  collections:
    docs:
      api_key: "env:PINECONE_API_KEY"  # Secure approach
```

**Path Configuration:**
```yaml
# ❌ Absolute paths (portability issues)
csv:
  collections:
    users: "/home/user/agentmap/data/users.csv"

# ✅ Relative paths (portable)
csv:
  collections:
    users: "data/csv/users.csv"
```

### Validation and Testing

```yaml
# Storage validation configuration
validation:
  enabled: true
  
  # Test storage connections on startup
  test_connections: true
  
  # Validate collection configurations
  validate_collections: true
  
  # Check required directories
  ensure_directories: true
```

## 📖 Next Steps

1. **Set [Environment Variables](./environment-variables)** - Configure authentication credentials
2. **Review [Configuration Examples](./examples)** - See complete storage setups  
3. **Test Storage Connections** - Validate your configuration
4. **Implement Storage in Workflows** - Use configured storage in your agents

Ready to set up environment variables? Continue to the [Environment Variables](./environment-variables) guide.
