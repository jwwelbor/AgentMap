# Enhancement Guide: Cloud Storage Module

This guide provides a detailed explanation of how we extended the JSON agent to support cloud storage providers in the AgentMap framework.

## Design Philosophy

Our implementation follows these key principles:

1. **Separation of Concerns**: Cloud storage connectors handle only I/O operations, while JSON processing remains in the core agent.
2. **Minimal Code Duplication**: We reuse existing functionality and extend only what's necessary.
3. **Interface Consistency**: Cloud storage operations match the interface of local storage.
4. **Progressive Enhancement**: Existing workflows continue to work without changes.

## Key Components Overview

### 1. BlobStorageConnector Interface

The base `BlobStorageConnector` class defines a common interface that all storage providers must implement:

```python
class BlobStorageConnector(ABC):
    @abstractmethod
    def read_blob(self, uri: str) -> bytes:
        """Read raw bytes from blob storage."""
        pass
    
    @abstractmethod
    def write_blob(self, uri: str, data: bytes) -> None:
        """Write raw bytes to blob storage."""
        pass
    
    @abstractmethod
    def blob_exists(self, uri: str) -> bool:
        """Check if a blob exists."""
        pass
```

This interface allows us to abstract away the differences between cloud providers, focusing solely on raw I/O operations.

### 2. Provider-Specific Connectors

Each cloud provider has its own connector that implements the interface:

- **AzureBlobConnector**: Uses `azure-storage-blob` SDK
- **AWSS3Connector**: Uses `boto3` SDK
- **GCPStorageConnector**: Uses `google-cloud-storage` SDK
- **LocalFileConnector**: Uses local filesystem (fallback)

Each connector handles:
- Authentication and connection setup
- Translating URIs to provider-specific paths
- Error conversion to standard exceptions

### 3. CloudJSONDocumentAgent

The `CloudJSONDocumentAgent` extends the existing `JSONDocumentAgent` to work with cloud connectors:

```python
class CloudJSONDocumentAgent(JSONDocumentAgent):
    def _read_json_file(self, collection: str) -> Any:
        # Get appropriate connector
        connector = self._get_connector_for_collection(collection)
        # Read raw bytes
        json_bytes = connector.read_blob(collection)
        # Parse JSON (reusing existing functionality)
        return json.loads(json_bytes.decode('utf-8'))
```

This approach preserves all the JSON processing logic in the core agent while delegating only the raw I/O to cloud connectors.

## Implementation Strategy

### URI-Based Connector Selection

We use URI schemes to dynamically select the appropriate connector:

```
azure://container/path/to/blob.json -> AzureBlobConnector
s3://bucket/path/to/object.json -> AWSS3Connector
gs://bucket/path/to/blob.json -> GCPStorageConnector
```

### Configuration Structure

Our configuration schema allows for:
- Provider-specific settings
- Named collection mappings
- Bucket/container mappings
- Credential management

```yaml
json:
  providers:
    azure: { ... }
    aws: { ... }
  collections:
    users: "azure://container/users.json"
```

### Lazy Loading

We use lazy imports to avoid requiring all cloud SDKs as dependencies:

```python
if uri.startswith("azure://"):
    from agentmap.agents.builtins.storage.blob.azure_connector import AzureBlobConnector
    return AzureBlobConnector(config)
```

This means users only need to install the SDKs for the cloud providers they actually use.

## Error Handling

We convert provider-specific errors to standard exceptions:

```python
try:
    # Azure-specific code
except AzureError as e:
    raise StorageOperationError(f"Azure error: {str(e)}")
```

This ensures consistent error handling across all providers.

## Integration Points

### 1. Registration with Agent Registry

We register the cloud-enabled agents in the registry:

```python
register_agent("cloud_json_reader", CloudJSONDocumentReaderAgent)
register_agent("cloud_json_writer", CloudJSONDocumentWriterAgent)
```

### 2. Storage Configuration

We extend the storage configuration to support cloud providers:

```python
def load_storage_config(config_path=None):
    # Load existing config
    # Add default cloud provider entries
```

### 3. CSV Workflow Integration

Users can specify cloud storage in CSV workflows:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CloudFlow,ReadData,,Read from Azure,cloud_json_reader,Process,,collection,data,"azure://container/data.json"
```

## Testing Strategy

The implementation should be tested at these levels:

1. **Unit tests** for each connector's core functionality
2. **Integration tests** with mock storage services
3. **End-to-end tests** with actual cloud services (using test credentials)

## Extension Points

The design allows for easy extensions:

1. **New cloud providers** can be added by implementing the `BlobStorageConnector` interface
2. **Additional operations** can be added to the interface as needed
3. **Enhanced authentication methods** can be implemented within connectors

By following this architecture, we've created a flexible, maintainable solution that seamlessly integrates cloud storage with the existing JSON agent functionality.