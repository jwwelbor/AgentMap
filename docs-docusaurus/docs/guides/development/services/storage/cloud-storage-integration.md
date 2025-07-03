# Cloud Storage Integration

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';

AgentMap supports seamless integration with major cloud storage providers for JSON document operations. This feature allows you to read and write JSON documents directly from/to Azure Blob Storage, AWS S3, and Google Cloud Storage without changing your workflow structure.

:::info Cloud Storage Benefits
- **Scalability**: Handle large datasets without local storage limitations
- **Reliability**: Built-in redundancy and backup features
- **Security**: Enterprise-grade encryption and access controls
- **Collaboration**: Share data across teams and environments
- **Cost-Effective**: Pay only for what you use
:::

## Supported Cloud Providers

<Tabs>
<TabItem value="azure" label="Azure Blob Storage">

- **Service**: Azure Blob Storage
- **Authentication**: Connection string or account key
- **Features**: Container-based organization, metadata support
- **Best For**: Microsoft ecosystem integration

</TabItem>
<TabItem value="aws" label="AWS S3">

- **Service**: Amazon S3
- **Authentication**: Access key/secret or IAM roles
- **Features**: Bucket-based organization, versioning
- **Best For**: AWS ecosystem integration

</TabItem>
<TabItem value="gcp" label="Google Cloud Storage">

- **Service**: Google Cloud Storage
- **Authentication**: Service account or application default credentials
- **Features**: Bucket-based organization, fine-grained permissions
- **Best For**: Google Cloud ecosystem integration

</TabItem>
</Tabs>

## Configuration

### Basic Configuration Structure

Update your `storage_config.yaml` file with cloud provider configurations:

```yaml
json:
  default_provider: "local"  # Default provider if not specified in URI
  providers:
    local:
      base_dir: "data/json"
    
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
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

### Provider-Specific Configuration

<Tabs>
<TabItem value="azure" label="Azure Configuration">

```yaml
azure:
  # Primary authentication method (recommended)
  connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
  
  # Alternative authentication
  # account_name: "env:AZURE_STORAGE_ACCOUNT"
  # account_key: "env:AZURE_STORAGE_KEY"
  
  # Container configuration
  default_container: "documents"
  containers:
    users: "users-prod-container"
    configs: "app-configs"
    logs: "application-logs"
  
  # Optional settings
  timeout: 30  # Connection timeout in seconds
  retry_count: 3
  enable_logging: true
```

</TabItem>
<TabItem value="aws" label="AWS Configuration">

```yaml
aws:
  # Authentication
  region: "us-west-2"
  access_key: "env:AWS_ACCESS_KEY_ID"
  secret_key: "env:AWS_SECRET_ACCESS_KEY"
  
  # Optional session token for assumed roles
  # session_token: "env:AWS_SESSION_TOKEN"
  
  # Bucket configuration
  default_bucket: "my-documents"
  buckets:
    users: "users-prod-bucket"
    analytics: "analytics-data"
    backups: "system-backups"
  
  # Optional settings
  endpoint_url: null  # Custom endpoint for LocalStack/MinIO
  use_ssl: true
  verify_ssl: true
  timeout: 30
```

</TabItem>
<TabItem value="gcp" label="GCP Configuration">

```yaml
gcp:
  # Project and authentication
  project_id: "env:GCP_PROJECT_ID"
  
  # Authentication options
  credentials_file: "path/to/service-account.json"
  # Or use application default credentials (for GCE/Cloud Run)
  # use_default_credentials: true
  
  # Bucket configuration
  default_bucket: "documents"
  buckets:
    users: "users-prod-bucket"
    ml_models: "ml-model-storage"
    logs: "application-logs"
  
  # Optional settings
  timeout: 30
  retry_count: 3
```

</TabItem>
</Tabs>

## URI Format for Cloud Storage

Cloud storage locations are specified using these URI formats:

| Provider | URI Format | Example | Description |
|----------|------------|---------|-------------|
| Azure Blob Storage | `azure://container/path/to/blob.json` | `azure://documents/users.json` | Container-based storage |
| AWS S3 | `s3://bucket/path/to/object.json` | `s3://my-bucket/data/config.json` | Bucket-based storage |
| Google Cloud Storage | `gs://bucket/path/to/blob.json` | `gs://my-bucket/reports/monthly.json` | Bucket-based storage |

### URI Examples

<Tabs>
<TabItem value="simple" label="Simple Paths">

```yaml
collections:
  user_profiles: "azure://users/profiles.json"
  app_config: "s3://config/app.json"
  reports: "gs://analytics/reports.json"
```

</TabItem>
<TabItem value="nested" label="Nested Paths">

```yaml
collections:
  daily_logs: "azure://logs/2024/01/daily.json"
  model_configs: "s3://ml/models/v1/config.json"
  user_analytics: "gs://data/users/analytics/summary.json"
```

</TabItem>
<TabItem value="environments" label="Environment-Specific">

```yaml
collections:
  # Production
  prod_users: "azure://prod-users/data.json"
  prod_config: "s3://prod-config/app.json"
  
  # Staging
  staging_users: "azure://staging-users/data.json"
  staging_config: "s3://staging-config/app.json"
  
  # Development
  dev_users: "azure://dev-users/data.json"
  dev_config: "s3://dev-config/app.json"
```

</TabItem>
</Tabs>

## Authentication Methods

### Environment Variables

The recommended approach is to use environment variables for sensitive credentials:

<Tabs>
<TabItem value="azure" label="Azure Environment">

```bash
# Azure Blob Storage
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"

# Alternative approach
export AZURE_STORAGE_ACCOUNT="mystorageaccount"
export AZURE_STORAGE_KEY="your-account-key"
```

</TabItem>
<TabItem value="aws" label="AWS Environment">

```bash
# AWS S3
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-west-2"

# For assumed roles
export AWS_SESSION_TOKEN="your-session-token"
```

</TabItem>
<TabItem value="gcp" label="GCP Environment">

```bash
# Google Cloud Storage
export GCP_PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# For Cloud Run/GCE (uses metadata service)
# No environment variables needed when using default credentials
```

</TabItem>
</Tabs>

### Authentication Best Practices

:::tip Security Best Practices

1. **Use Environment Variables**: Never hardcode credentials in configuration files
2. **Rotate Credentials Regularly**: Set up automatic credential rotation where possible
3. **Least Privilege Access**: Grant only the minimum required permissions
4. **Use IAM Roles**: Prefer IAM roles over static credentials in cloud environments
5. **Enable Audit Logging**: Track access to sensitive data

:::

<details>
<summary>Advanced Authentication Options</summary>

**Azure Managed Identity** (for Azure VMs/App Service):
```yaml
azure:
  use_managed_identity: true
  default_container: "documents"
```

**AWS IAM Roles** (for EC2/Lambda):
```yaml
aws:
  region: "us-west-2"
  # No credentials needed - uses instance profile
  default_bucket: "my-documents"
```

**GCP Service Account** (detailed configuration):
```yaml
gcp:
  project_id: "env:GCP_PROJECT_ID"
  credentials_file: "/opt/app/credentials/service-account.json"
  scopes:
    - "https://www.googleapis.com/auth/devstorage.read_write"
  default_bucket: "documents"
```

</details>

## Using Cloud Storage in Workflows

### CSV Workflow Examples

<Tabs>
<TabItem value="basic" label="Basic Cloud Operations">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CloudFlow,ReadData,,Read from Azure,cloud_json_reader,Process,,collection,data,"azure://container/data.json"
CloudFlow,Process,,Process data,DataProcessor,SaveData,,data,processed_data,"Process the data"
CloudFlow,SaveData,,Save to AWS S3,cloud_json_writer,End,,processed_data,result,"s3://bucket/output.json"
CloudFlow,End,,Completion,Echo,,,"result",final_message,Data processing complete
```

</TabItem>
<TabItem value="named" label="Named Collections">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CloudFlow,ReadUsers,,Read user data,cloud_json_reader,ProcessUsers,,collection,users,"azure_users"
CloudFlow,ProcessUsers,,Process users,UserProcessor,SaveResults,,users,processed_users,
CloudFlow,SaveResults,,Save to cloud,cloud_json_writer,End,,processed_users,result,"aws_reports"
CloudFlow,End,,Completion,Echo,,,"result",final_message,User processing complete
```

</TabItem>
<TabItem value="multicloud" label="Multi-Cloud Pipeline">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
MultiCloud,ReadAzure,,Read from Azure,cloud_json_reader,Process1,,collection,azure_data,"azure://source/data.json"
MultiCloud,Process1,,Process Azure data,DataProcessor,ReadAWS,,azure_data,processed_azure,
MultiCloud,ReadAWS,,Read from AWS,cloud_json_reader,Process2,,collection,aws_data,"s3://source/data.json"
MultiCloud,Process2,,Combine data,DataCombiner,SaveGCP,,processed_azure;aws_data,combined_data,
MultiCloud,SaveGCP,,Save to GCP,cloud_json_writer,End,,combined_data,result,"gs://output/combined.json"
MultiCloud,End,,Completion,Echo,,,"result",final_message,Multi-cloud processing complete
```

</TabItem>
</Tabs>

### Agent Context Configuration

<Tabs>
<TabItem value="reader" label="Cloud Reader Agent">

```yaml
# Cloud JSON Reader Agent Context
{
  "collection": "azure://prod-data/users.json",
  "format": "raw",
  "timeout": 30,
  "retry_count": 3,
  "cache_enabled": true
}
```

</TabItem>
<TabItem value="writer" label="Cloud Writer Agent">

```yaml
# Cloud JSON Writer Agent Context
{
  "collection": "s3://prod-output/results.json",
  "mode": "update",
  "create_if_missing": true,
  "backup_enabled": true,
  "compression": "gzip"
}
```

</TabItem>
<TabItem value="batch" label="Batch Operations">

```yaml
# Batch Processing Agent Context
{
  "source_collections": [
    "azure://data/batch1.json",
    "azure://data/batch2.json",
    "azure://data/batch3.json"
  ],
  "destination": "s3://processed/combined.json",
  "batch_size": 100,
  "parallel_processing": true
}
```

</TabItem>
</Tabs>

## Container/Bucket Mappings

You can map logical container/bucket names to actual storage containers for better organization and environment management:

```yaml
azure:
  containers:
    users: "users-prod-container"      # Production users
    configs: "app-configs-v2"          # Application configurations
    logs: "application-logs-2024"      # Current year logs
    temp: "temporary-processing"       # Temporary data

aws:
  buckets:
    analytics: "analytics-prod-us-west-2"  # Regional analytics data
    backups: "system-backups-encrypted"    # Encrypted backups
    ml_models: "ml-models-versioned"       # Versioned ML models
    user_uploads: "user-uploads-secure"    # Secure user uploads

gcp:
  buckets:
    documents: "documents-prod-global"     # Global document storage
    images: "images-cdn-optimized"         # CDN-optimized images
    archives: "long-term-archives"         # Long-term archival
    processing: "temp-processing-queue"    # Temporary processing queue
```

Then use logical names in URIs:
```yaml
collections:
  user_data: "azure://users/profiles.json"        # Uses "users-prod-container"
  app_config: "s3://configs/app.json"             # Uses "app-configs-v2" 
  documents: "gs://documents/archive.json"        # Uses "documents-prod-global"
```

## Required Dependencies

Install the appropriate cloud SDK packages:

<Tabs>
<TabItem value="install" label="Installation Commands">

```bash
# Azure Blob Storage
pip install azure-storage-blob

# AWS S3
pip install boto3

# Google Cloud Storage
pip install google-cloud-storage

# Install all cloud providers
pip install azure-storage-blob boto3 google-cloud-storage
```

</TabItem>
<TabItem value="requirements" label="requirements.txt">

```txt
# Cloud storage dependencies
azure-storage-blob>=12.19.0
boto3>=1.34.0
google-cloud-storage>=2.10.0

# Optional: for enhanced features
aiofiles>=23.2.0          # Async file operations
tenacity>=8.2.0           # Retry logic
cryptography>=41.0.0      # Enhanced encryption
```

</TabItem>
<TabItem value="docker" label="Docker">

```dockerfile
FROM python:3.11-slim

# Install cloud storage dependencies
RUN pip install \
    azure-storage-blob>=12.19.0 \
    boto3>=1.34.0 \
    google-cloud-storage>=2.10.0

# Copy your application
COPY . /app
WORKDIR /app

# Run your application
CMD ["python", "main.py"]
```

</TabItem>
</Tabs>

## Error Handling and Troubleshooting

### Common Issues and Solutions

<details>
<summary>Authentication Failures</summary>

**Problem**: `AuthenticationError` or `Unauthorized` exceptions

**Solutions**:
1. Verify environment variables are set correctly
2. Check credential expiration dates
3. Ensure proper permissions on containers/buckets
4. Validate connection strings format

```python
# Debug authentication
import os
print("Azure connection string:", os.getenv("AZURE_STORAGE_CONNECTION_STRING", "Not set"))
print("AWS access key:", os.getenv("AWS_ACCESS_KEY_ID", "Not set"))
print("GCP project:", os.getenv("GCP_PROJECT_ID", "Not set"))
```

</details>

<details>
<summary>Network Connectivity Issues</summary>

**Problem**: `ConnectionError` or timeout exceptions

**Solutions**:
1. Check internet connectivity
2. Verify firewall rules allow outbound HTTPS
3. Increase timeout values in configuration
4. Check cloud provider service status

```yaml
# Increase timeouts
azure:
  timeout: 60  # Increase from default 30
  retry_count: 5

aws:
  timeout: 60
  verify_ssl: false  # Only for testing

gcp:
  timeout: 60
  retry_count: 5
```

</details>

<details>
<summary>Container/Bucket Not Found</summary>

**Problem**: `ContainerNotFound` or `NoSuchBucket` errors

**Solutions**:
1. Verify container/bucket exists in cloud console
2. Check spelling and case sensitivity
3. Ensure proper region configuration
4. Create containers/buckets if needed

```python
# Check if container/bucket exists
def check_storage_exists():
    # Implementation depends on provider
    # Add checks before workflow execution
    pass
```

</details>

<details>
<summary>Permission Denied Errors</summary>

**Problem**: `PermissionDenied` or `AccessDenied` exceptions

**Solutions**:
1. Verify IAM permissions include required operations
2. Check if containers/buckets have public access restrictions
3. Ensure service account has proper roles
4. Review bucket policies and ACLs

**Required Permissions by Provider**:

**Azure**: `Storage Blob Data Contributor` or custom role with:
- `Microsoft.Storage/storageAccounts/blobServices/containers/read`
- `Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read`
- `Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write`

**AWS**: Policy with actions:
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

**GCP**: Role `Storage Object Admin` or custom role with:
- `storage.objects.get`
- `storage.objects.create`
- `storage.objects.update`
- `storage.objects.delete`

</details>

### Monitoring and Logging

<Tabs>
<TabItem value="logging" label="Enable Logging">

```yaml
# Enhanced logging configuration
azure:
  enable_logging: true
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

aws:
  enable_logging: true
  log_requests: true
  log_responses: false  # Avoid logging sensitive data

gcp:
  enable_logging: true
  log_level: "INFO"
```

</TabItem>
<TabItem value="monitoring" label="Health Checks">

```python
# Storage health check implementation
async def check_cloud_storage_health():
    """Check connectivity to all configured cloud providers."""
    health_status = {}
    
    # Azure check
    try:
        result = storage_service.read("azure://health/check.json")
        health_status["azure"] = "healthy" if result else "degraded"
    except Exception as e:
        health_status["azure"] = f"error: {str(e)}"
    
    # AWS check
    try:
        result = storage_service.read("s3://health/check.json")
        health_status["aws"] = "healthy" if result else "degraded"
    except Exception as e:
        health_status["aws"] = f"error: {str(e)}"
    
    # GCP check
    try:
        result = storage_service.read("gs://health/check.json")
        health_status["gcp"] = "healthy" if result else "degraded"
    except Exception as e:
        health_status["gcp"] = f"error: {str(e)}"
    
    return health_status
```

</TabItem>
<TabItem value="metrics" label="Performance Metrics">

```python
# Track performance metrics
import time

class CloudStorageMetrics:
    def __init__(self):
        self.operation_times = {}
        self.error_counts = {}
    
    def track_operation(self, provider, operation, duration):
        key = f"{provider}_{operation}"
        if key not in self.operation_times:
            self.operation_times[key] = []
        self.operation_times[key].append(duration)
    
    def track_error(self, provider, error_type):
        key = f"{provider}_{error_type}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
    
    def get_stats(self):
        return {
            "average_times": {
                k: sum(v) / len(v) for k, v in self.operation_times.items()
            },
            "error_counts": self.error_counts
        }
```

</TabItem>
</Tabs>

## Performance Optimization

### Caching Strategies

<Tabs>
<TabItem value="local" label="Local Caching">

```yaml
json:
  cache:
    enabled: true
    ttl: 300  # 5 minutes
    max_size: 100  # Max cached items
    strategy: "lru"  # Least Recently Used
```

</TabItem>
<TabItem value="redis" label="Redis Caching">

```yaml
json:
  cache:
    enabled: true
    provider: "redis"
    redis_url: "redis://localhost:6379/0"
    ttl: 600  # 10 minutes
    key_prefix: "agentmap:storage:"
```

</TabItem>
</Tabs>

### Batch Operations

```python
# Efficient batch processing
async def process_cloud_data_batch(collections, batch_size=10):
    """Process multiple cloud collections efficiently."""
    results = []
    
    for i in range(0, len(collections), batch_size):
        batch = collections[i:i + batch_size]
        
        # Process batch concurrently
        batch_tasks = [
            storage_service.read(collection) 
            for collection in batch
        ]
        
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(batch_results)
    
    return results
```

### Connection Pooling

```yaml
# Connection pool configuration
azure:
  connection_pool:
    max_connections: 10
    max_idle_time: 300

aws:
  connection_pool:
    max_connections: 10
    max_retries: 3
    backoff_mode: "adaptive"

gcp:
  connection_pool:
    max_connections: 10
    keepalive_timeout: 300
```

## Security Best Practices

### Data Encryption

<Tabs>
<TabItem value="transit" label="Encryption in Transit">

```yaml
# Ensure HTTPS/TLS for all providers
azure:
  use_ssl: true
  verify_ssl: true

aws:
  use_ssl: true
  verify_ssl: true

gcp:
  use_ssl: true  # Always enabled
```

</TabItem>
<TabItem value="rest" label="Encryption at Rest">

```yaml
# Provider-specific encryption settings
azure:
  encryption:
    enabled: true
    key_vault_url: "https://myvault.vault.azure.net/"
    key_name: "storage-encryption-key"

aws:
  encryption:
    server_side_encryption: "AES256"
    # Or use KMS
    # kms_key_id: "arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012"

gcp:
  encryption:
    # Uses Google-managed encryption by default
    # Or specify customer-managed key
    # kms_key_name: "projects/PROJECT_ID/locations/LOCATION/keyRings/RING_ID/cryptoKeys/KEY_ID"
```

</TabItem>
</Tabs>

### Access Control

```yaml
# Implement least privilege access
azure:
  rbac:
    enabled: true
    roles:
      - "Storage Blob Data Reader"  # For read-only operations
      - "Storage Blob Data Contributor"  # For read/write operations

aws:
  iam:
    policy_arn: "arn:aws:iam::123456789012:policy/AgentMapStoragePolicy"
    # Custom policy with minimal required permissions

gcp:
  iam:
    service_account: "agentmap-storage@project.iam.gserviceaccount.com"
    roles:
      - "roles/storage.objectViewer"  # Read access
      - "roles/storage.objectCreator"  # Write access
```

## Related Documentation

- [Storage Services Overview](/docs/guides/development/services/storage/storage-services-overview) - Core storage service concepts
- [Service Registry Patterns](/docs/guides/development/services/service-registry-patterns) - Host service integration
- [Configuration Reference](/docs/reference/configuration) - Complete configuration options
- [Security Guide](/docs/guides/deploying/deployment) - Security best practices

:::tip Production Deployment

For production deployments, consider implementing:
1. **Multi-region replication** for disaster recovery
2. **Automated backup strategies** with retention policies
3. **Monitoring and alerting** for storage operations
4. **Cost optimization** through lifecycle policies
5. **Compliance controls** for data governance

:::
