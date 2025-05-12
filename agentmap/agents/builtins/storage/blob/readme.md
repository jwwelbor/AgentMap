# Cloud Storage Module for AgentMap

This module provides integration with cloud blob storage providers for the JSON document agents in AgentMap. It allows reading and writing JSON documents from/to Azure Blob Storage, AWS S3, and Google Cloud Storage using a consistent interface.

## Architecture

The module follows a clean separation of concerns:

1. **BlobStorageConnector Interface**: Defines common operations for all storage connectors
2. **Provider-Specific Implementations**: Implement the interface for each cloud provider
3. **CloudJSONDocumentAgent**: Extends JSON agents to work with cloud storage

### Key Components

```
blob/
├── __init__.py                 # Package exports
├── base_connector.py           # Base interface and utilities
├── local_connector.py          # Local filesystem implementation
├── azure_connector.py          # Azure Blob Storage implementation
├── aws_connector.py            # AWS S3 implementation
└── gcp_connector.py            # Google Cloud Storage implementation
```

## Implementation Details

### BlobStorageConnector Interface

The base connector provides:
- Abstract methods for reading, writing, and checking blobs
- URI parsing and normalization
- Environment variable resolution
- Connector factory function

### CloudJSONDocumentAgent

The cloud-enabled JSON agent:
- Dynamically selects the appropriate connector based on URI scheme
- Handles named collections via configuration
- Preserves all JSON document functionality
- Manages connector lifecycle and caching

## URI Format

The module supports these URI formats:
- Azure: `azure://container/path/to/blob.json`
- AWS: `s3://bucket/path/to/object.json`
- GCP: `gs://bucket/path/to/blob.json`
- Local: Plain path or `file:///path/to/file.json`

## Configuration

The storage configuration should include:

```yaml
json:
  providers:
    azure:
      # Azure-specific config
    aws:
      # AWS-specific config
    gcp:
      # GCP-specific config
  collections:
    # Named collection mappings
```

## Optional Dependencies

Each cloud provider has its own SDK dependency:
- Azure: `azure-storage-blob`
- AWS: `boto3`
- GCP: `google-cloud-storage`

The module uses lazy imports to avoid requiring all SDKs to be installed.

## Error Handling

Errors are converted to these standard exceptions:
- `FileNotFoundError`: When a blob doesn't exist
- `StorageConnectionError`: For authentication/connection issues
- `StorageOperationError`: For failed operations

## Adding New Providers

To add a new cloud provider:
1. Create a new connector class implementing `BlobStorageConnector`
2. Add URI scheme handling to `get_connector_for_uri`
3. Update configuration schema

## Security Considerations

- Credentials should be stored as environment variables
- Connection strings and keys should never be hardcoded
- Use appropriate IAM roles and permissions