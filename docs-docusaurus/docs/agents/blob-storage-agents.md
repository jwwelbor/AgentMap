---
sidebar_position: 3
title: Blob Storage Agents
description: Cloud storage connectors for Azure, AWS, GCP, and local file systems
---

# Blob Storage Agents

> **Note:** This documentation is currently being expanded. The full documentation will be available soon.

AgentMap includes robust cloud storage connectors for accessing files across different storage platforms using a unified interface. These agents implement the `StorageCapableAgent` protocol and extend the storage capabilities to major cloud providers.

## Cloud Storage Connectors

### Available Providers

AgentMap supports the following blob storage providers:

- **Azure Blob Storage**: Access and manage Azure Blob Storage containers
- **AWS S3**: Read from and write to S3 buckets with full AWS integration
- **Google Cloud Storage**: Interact with GCP storage buckets
- **Local File System**: Use the same interface for local file operations

### Blob Reader Agent

The Blob Reader Agent retrieves files from blob storage systems:

- **Input Fields**: `path` (relative path within container/bucket), optional `collection` (container/bucket override)
- **Output Field**: Retrieved document data with metadata
- **Prompt Usage**: Optional path override
- **Protocol Implementation**: StorageCapableAgent, BlobCapableAgent

#### Core Features

- **Universal Interface**: Same API regardless of underlying storage provider
- **Streaming Support**: Efficient handling of large files
- **Content Type Detection**: Automatic detection of file types
- **Metadata Preservation**: Maintains file metadata across providers
- **Authentication Flexibility**: Environment variables or explicit credentials

#### Configuration Options

```python
context = {
    "input_fields": ["path"],
    "output_field": "document",
    
    # Provider configuration (required)
    "provider": "azure",                      # azure, aws, gcp, local
    
    # Azure-specific options
    "connection_string": "env:AZURE_STORAGE", # Environment variable reference
    "container": "documents",                 # Container name
    
    # AWS-specific options
    "bucket": "data-bucket",                  # S3 bucket name
    "region": "us-west-2",                    # AWS region
    
    # GCP-specific options
    "project_id": "my-gcp-project",           # GCP project ID
    "bucket": "gcp-bucket",                   # GCP bucket name
    
    # Common options
    "path_prefix": "data/",                   # Optional path prefix prepended to all paths
    "cache_ttl": 300,                         # Cache time-to-live in seconds
    "include_metadata": True                  # Include metadata in response
}
```

#### CSV Examples

**Azure Blob Storage:**
```csv
AzureGraph,ReadBlob,{"provider":"azure","container":"reports"},Read from Azure,blob_reader,Process,,path,document,quarterly/q2-results.pdf
```

**AWS S3:**
```csv
AWSGraph,ReadS3,{"provider":"aws","bucket":"company-data","region":"us-east-1"},Read from S3,blob_reader,Process,,path,document,analytics/june-metrics.csv
```

**GCP Storage:**
```csv
GCPGraph,ReadGCS,{"provider":"gcp","bucket":"project-files"},Read from GCP,blob_reader,Process,,path,document,presentations/roadmap.pptx
```

**Local File System:**
```csv
LocalGraph,ReadFile,{"provider":"local"},Read local file,blob_reader,Process,,path,document,data/config.json
```

### Blob Writer Agent

The Blob Writer Agent writes data to blob storage systems:

- **Input Fields**: `data` (content to write), `path` (destination path)
- **Output Field**: Operation result status
- **Prompt Usage**: Optional destination path override
- **Protocol Implementation**: StorageCapableAgent, BlobCapableAgent

#### Writer Features

- **Write Modes**: Create, overwrite, append modes
- **Metadata Support**: Optional metadata storage
- **Content Type Setting**: Automatic or manual MIME type detection
- **Access Control**: Permission and access control configuration
- **Concurrency Handling**: Safe concurrent access patterns

#### Configuration Options

```python
context = {
    "input_fields": ["data", "path"],
    "output_field": "result",
    
    # Provider configuration (same as reader)
    "provider": "aws",
    "bucket": "output-bucket",
    
    # Write options
    "mode": "write",                          # write, append, update
    "content_type": "auto",                   # auto, or specific MIME type
    "metadata": {"source": "agentmap"},       # Custom metadata to store
    "public_access": False,                   # Whether file should be publicly accessible
    "overwrite_existing": True                # Whether to overwrite existing files
}
```

#### CSV Examples

**Azure Blob Storage Writer:**
```csv
AzureGraph,WriteBlob,{"provider":"azure","container":"outputs","content_type":"application/json"},Write to Azure,blob_writer,Next,,processed_data,write_result,results/analysis.json
```

**AWS S3 Writer:**
```csv
AWSGraph,WriteS3,{"provider":"aws","bucket":"data-export","mode":"append"},Append to S3 file,blob_writer,Complete,,log_entry,write_result,logs/application.log
```

## Integration with Other Agents

Blob storage agents integrate seamlessly with other agent types:

### Document Processing Pipeline

```csv
Pipeline,FetchFromCloud,{"provider":"azure","container":"documents"},Fetch document,blob_reader,ProcessDocument,Error,path,raw_document,reports/annual-2024.pdf
Pipeline,ProcessDocument,{"chunk_size":1000,"should_split":true},Process document,file_reader,AnalyzeContent,Error,raw_document,processed_document,
Pipeline,AnalyzeContent,{"routing_enabled":true},Analyze content,llm,GenerateReport,Error,processed_document,analysis,Analyze this document and extract key insights: {processed_document}
Pipeline,GenerateReport,{"provider":"anthropic"},Generate report,llm,SaveReport,Error,analysis,report,Generate a detailed report based on this analysis: {analysis}
Pipeline,SaveReport,{"provider":"aws","bucket":"processed-reports"},Save to S3,blob_writer,Complete,Error,report,save_result,reports/processed/annual-2024-analysis.pdf
```

### Cross-Cloud Migration

```csv
Migration,SourceSelection,,Select source cloud,input,ConfigureSource,End,message,source_cloud,Select source cloud (azure, aws, gcp):
Migration,ConfigureSource,,{"nodes":"FromAzure|FromAWS|FromGCP"},Configure source,orchestrator,DestinationSelection,Error,available_nodes|source_cloud,selected_source,
Migration,FromAzure,{"provider":"azure","container":"source-container"},Azure source,blob_reader,DestinationSelection,Error,path,source_data,data/to-migrate/
Migration,FromAWS,{"provider":"aws","bucket":"source-bucket"},AWS source,blob_reader,DestinationSelection,Error,path,source_data,data/to-migrate/
Migration,FromGCP,{"provider":"gcp","bucket":"source-bucket"},GCP source,blob_reader,DestinationSelection,Error,path,source_data,data/to-migrate/
Migration,DestinationSelection,,Select destination cloud,input,ConfigureDestination,End,message,destination_cloud,Select destination cloud (azure, aws, gcp):
Migration,ConfigureDestination,,{"nodes":"ToAzure|ToAWS|ToGCP"},Configure destination,orchestrator,MigrationComplete,Error,available_nodes|destination_cloud,selected_destination,
Migration,ToAzure,{"provider":"azure","container":"destination-container"},Azure destination,blob_writer,MigrationComplete,Error,source_data,migration_result,data/migrated/
Migration,ToAWS,{"provider":"aws","bucket":"destination-bucket"},AWS destination,blob_writer,MigrationComplete,Error,source_data,migration_result,data/migrated/
Migration,ToGCP,{"provider":"gcp","bucket":"destination-bucket"},GCP destination,blob_writer,MigrationComplete,Error,source_data,migration_result,data/migrated/
Migration,MigrationComplete,,Migration complete,echo,End,End,migration_result,final_status,
```

## Configuration Best Practices

### Environment Variables for Credentials

For security, use environment variables to store credentials:

```python
context = {
    "provider": "azure",
    "connection_string": "env:AZURE_STORAGE_CONNECTION_STRING"
}
```

```python
context = {
    "provider": "aws",
    "access_key": "env:AWS_ACCESS_KEY_ID",
    "secret_key": "env:AWS_SECRET_ACCESS_KEY"
}
```

### Caching for Performance

Enable caching for frequently accessed files:

```python
context = {
    "provider": "aws",
    "bucket": "data-bucket",
    "cache_ttl": 300,  # Cache for 5 minutes
    "cache_size_limit": "500MB"
}
```

### Error Handling

Configure retry behavior for transient errors:

```python
context = {
    "provider": "gcp",
    "bucket": "analytics-bucket",
    "max_retries": 3,
    "retry_delay": 2,  # seconds
    "backoff_factor": 2  # exponential backoff
}
```

## Implementation Details

Full implementation details and advanced configuration options will be provided in the upcoming documentation update. For now, refer to the examples above for basic usage patterns.

## See Also

- [Agent Types Reference](../agent-types) - Complete reference for all agent types
- [Storage Agent Types](../agent-types#storage-agent-types) - Other storage agents
- [Service Catalog](../service-catalog) - Available services and protocols
