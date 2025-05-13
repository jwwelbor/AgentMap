# Cloud Storage Integration for AgentMap

AgentMap now supports seamless integration with major cloud storage providers for JSON document operations. This feature allows you to read and write JSON documents directly from/to Azure Blob Storage, AWS S3, and Google Cloud Storage without changing your workflow structure.

## Cloud Storage Configuration

To use cloud storage, you'll need to update your `storage_config.yaml` file with the appropriate provider configurations:

```yaml
json:
  default_provider: "local"  # Default provider if not specified in URI
  providers:
    local:
      base_dir: "data/json"
    
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      # Alternative authentication
      # account_name: "env:AZURE_STORAGE_ACCOUNT"
      # account_key: "env:AZURE_STORAGE_KEY"
      default_container: "documents"
      containers:
        users: "users-container"
        reports: "reports-container"
    
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      default_bucket: "my-documents"
      buckets:
        users: "users-bucket"
        reports: "reports-bucket"
    
    gcp:
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "path/to/service-account.json"
      default_bucket: "documents"
  
  collections:
    # Local files
    users: "users.json"  
    
    # Cloud storage with explicit URIs
    azure_users: "azure://users/data.json"
    aws_reports: "s3://reports/monthly.json"
    gcp_documents: "gs://documents/archive.json"
```

## URI Format for Cloud Storage

You can specify cloud storage locations using these URI formats:

| Provider | URI Format | Example |
|----------|------------|---------|
| Azure Blob Storage | `azure://container/path/to/blob.json` | `azure://documents/users.json` |
| AWS S3 | `s3://bucket/path/to/object.json` | `s3://my-bucket/data/config.json` |
| Google Cloud Storage | `gs://bucket/path/to/blob.json` | `gs://my-bucket/reports/monthly.json` |

## Using Cloud Storage in CSV Workflows

To use cloud storage in your CSV workflows, simply use the appropriate agent type and provide the cloud storage URI:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CloudFlow,ReadData,,Read from Azure,cloud_json_reader,Process,,collection,data,"azure://container/data.json"
CloudFlow,Process,,Process data,Default,SaveData,,data,processed_data,"Process the data"
CloudFlow,SaveData,,Save to AWS S3,cloud_json_writer,End,,processed_data,result,"s3://bucket/output.json"
```

You can also use named collections from your configuration:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CloudFlow,ReadData,,Read from named collection,cloud_json_reader,Process,,collection,data,"azure_users"
```

## Authentication Methods

### Azure Blob Storage

1. **Connection String** (Recommended):
   ```yaml
   azure:
     connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
   ```

2. **Account Name and Key**:
   ```yaml
   azure:
     account_name: "env:AZURE_STORAGE_ACCOUNT"
     account_key: "env:AZURE_STORAGE_KEY"
   ```

### AWS S3

1. **Access Key and Secret Key**:
   ```yaml
   aws:
     region: "us-west-2"
     access_key: "env:AWS_ACCESS_KEY_ID"
     secret_key: "env:AWS_SECRET_ACCESS_KEY"
   ```

2. **Assumed Role** (with session token):
   ```yaml
   aws:
     region: "us-west-2"
     access_key: "env:AWS_ACCESS_KEY_ID"
     secret_key: "env:AWS_SECRET_ACCESS_KEY"
     session_token: "env:AWS_SESSION_TOKEN"
   ```

### Google Cloud Storage

1. **Service Account File**:
   ```yaml
   gcp:
     project_id: "env:GCP_PROJECT_ID"
     credentials_file: "path/to/service-account.json"
   ```

2. **Application Default Credentials**:
   ```yaml
   gcp:
     project_id: "env:GCP_PROJECT_ID"
   ```

## Environment Variables

You can use environment variables in your configuration with the `env:` prefix:

```yaml
aws:
  access_key: "env:AWS_ACCESS_KEY_ID"
```

This will read the value from the `AWS_ACCESS_KEY_ID` environment variable.

## Container/Bucket Mappings

You can map logical container/bucket names to actual storage containers:

```yaml
azure:
  containers:
    users: "users-prod-container"  # Maps "users" to the actual container name
```

Then you can use the logical name in your URI:
```
azure://users/data.json  # Uses "users-prod-container" container
```

## Required Dependencies

To use cloud storage providers, you'll need to install the appropriate SDKs:

- **Azure**: `pip install azure-storage-blob`
- **AWS**: `pip install boto3`
- **GCP**: `pip install google-cloud-storage`

## Error Handling

Cloud storage operations may fail due to various reasons:

1. **Authentication errors**: Check your credentials and permissions
2. **Network errors**: Ensure connectivity to the cloud provider
3. **Container/bucket not found**: Verify that the container/bucket exists
4. **Permission issues**: Ensure your credentials have the necessary permissions

When an error occurs, the agent will set `last_action_success` to `False` and provide details in the `error` field of the state.