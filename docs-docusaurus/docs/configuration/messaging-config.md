---
title: Messaging Configuration
sidebar_position: 4
description: Complete guide to AgentMap messaging services including AWS SNS/SQS, Google Cloud Pub/Sub, Azure Service Bus, and local messaging with templates and routing.
keywords: [messaging configuration, AWS SNS, AWS SQS, Google Cloud Pub/Sub, Azure Service Bus, message queues, cloud messaging]
---

# Messaging Configuration

AgentMap provides a unified messaging service system supporting multiple cloud providers for publishing messages to queues and topics. This enables asynchronous processing, external system integration, and long-running workflow coordination through cloud-native messaging services.

## 📋 Messaging Configuration Overview

Messaging configuration is defined in the main configuration file and supports:

- **AWS Messaging**: SNS topics and SQS queues with automatic topic/queue creation
- **Google Cloud Messaging**: Pub/Sub topics with automatic subscription management  
- **Azure Messaging**: Service Bus topics and queues with reliable delivery
- **Local Development**: File-based message storage for testing and development
- **Message Templates**: Consistent message formatting across different use cases
- **Retry Policies**: Configurable retry logic with exponential backoff
- **Provider Routing**: Intelligent provider selection with fallback support

## 🗂️ Complete Messaging Configuration Structure

```yaml
# Messaging service configuration
messaging:
  # Default provider selection
  default_provider: "local"  # "aws", "gcp", "azure", "local"
  
  # Provider configurations
  providers:
    # Local file-based messaging (development/testing)
    local:
      enabled: true
      storage_path: "data/messages"
    
    # AWS SNS/SQS configuration
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"  # "sns" or "sqs"
      profile_name: "default"  # Optional AWS profile
    
    # Google Cloud Pub/Sub configuration
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"
    
    # Azure Service Bus configuration
    azure:
      enabled: true
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"
      service_type: "topic"  # "topic" or "queue"
  
  # Message templates for consistent formatting
  message_templates:
    task_request:
      message_type: "task_request"
      priority: "normal"
      payload:
        task_id: "${task_id}"
        task_type: "${task_type}"
        parameters: "${parameters}"
        deadline: "${deadline}"
    
    workflow_trigger:
      message_type: "workflow_trigger"
      priority: "high"
      payload:
        workflow_name: "${workflow_name}"
        trigger_data: "${trigger_data}"
        source_node: "${source_node}"
  
  # Retry policy configuration
  retry_policy:
    max_retries: 3
    backoff_seconds: [1, 2, 4]  # Exponential backoff timing
```

## 🚀 AWS Messaging Configuration

AWS messaging supports both SNS (Simple Notification Service) and SQS (Simple Queue Service) with automatic resource creation.

### AWS SNS Configuration

```yaml
messaging:
  default_provider: "aws"
  
  providers:
    aws:
      enabled: true
      
      # AWS region configuration
      region_name: "us-east-1"
      
      # Service type selection
      service_type: "sns"  # Use SNS topics
      
      # Authentication options
      profile_name: "production"  # AWS profile name (optional)
      
      # Alternative: explicit credentials (not recommended for production)
      # access_key_id: "env:AWS_ACCESS_KEY_ID"
      # secret_access_key: "env:AWS_SECRET_ACCESS_KEY"
```

### AWS SQS Configuration

```yaml
messaging:
  providers:
    aws:
      enabled: true
      region_name: "us-west-2"
      service_type: "sqs"  # Use SQS queues
      
      # SQS-specific settings
      queue_settings:
        visibility_timeout: 300      # Message visibility timeout (seconds)
        message_retention: 1209600   # 14 days retention
        receive_wait_time: 20        # Long polling wait time
```

### AWS Multi-Service Configuration

```yaml
messaging:
  providers:
    # SNS for notifications
    aws_sns:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"
      profile_name: "notifications"
    
    # SQS for work queues
    aws_sqs:
      enabled: true
      region_name: "us-east-1"
      service_type: "sqs"
      profile_name: "processing"
```

### AWS Authentication Methods

**Method 1: AWS Profile (Recommended for Development)**
```yaml
messaging:
  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"
      profile_name: "env:AWS_PROFILE"  # AWS CLI profile
```

**Method 2: Environment Variables (Recommended for Production)**
```yaml
# Configuration relies on standard AWS environment variables:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
messaging:
  providers:
    aws:
      enabled: true
      region_name: "env:AWS_REGION"
      service_type: "sns"
```

**Method 3: IAM Roles (Recommended for AWS Infrastructure)**
```yaml
# When running on AWS infrastructure (EC2, Lambda, ECS)
# IAM roles provide automatic credential management
messaging:
  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"
      # No explicit credentials needed - uses IAM role
```

## ☁️ Google Cloud Pub/Sub Configuration

Google Cloud Pub/Sub provides scalable messaging with automatic topic creation and subscription management.

### Basic GCP Configuration

```yaml
messaging:
  providers:
    gcp:
      enabled: true
      
      # GCP project identification
      project_id: "env:GCP_PROJECT_ID"
      
      # Authentication options
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE"  # Service account JSON
      
      # Alternative: use application default credentials
      # use_default_credentials: true
```

### Advanced GCP Configuration

```yaml
messaging:
  providers:
    gcp:
      enabled: true
      project_id: "my-production-project"
      
      # Service account authentication (recommended for production)
      credentials_file: "/secrets/gcp-service-account.json"
      
      # Pub/Sub settings
      publisher_settings:
        batch_size: 100              # Messages per batch
        max_latency: 0.1             # Max batching latency (seconds)
        max_request_bytes: 1048576   # Max request size (1MB)
      
      # Subscription settings
      subscription_settings:
        ack_deadline: 600            # Message acknowledgment deadline
        max_extension: 600           # Max deadline extension
        min_duration_per_lease: 10   # Min lease duration
```

### GCP Authentication Methods

**Method 1: Service Account File (Recommended for Production)**
```yaml
messaging:
  providers:
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE"
```

**Method 2: Application Default Credentials (Development)**
```yaml
messaging:
  providers:
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"
      use_default_credentials: true  # Uses gcloud auth application-default login
```

**Method 3: Environment Variable (Service Account JSON)**
```bash
# Set the environment variable to the service account JSON content
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

```yaml
messaging:
  providers:
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"
      # Automatically uses GOOGLE_APPLICATION_CREDENTIALS
```

## 🔷 Azure Service Bus Configuration

Azure Service Bus provides enterprise messaging with topics and queues supporting complex routing scenarios.

### Basic Azure Configuration

```yaml
messaging:
  providers:
    azure:
      enabled: true
      
      # Service Bus connection string
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"
      
      # Service type selection
      service_type: "topic"  # "topic" or "queue"
```

### Advanced Azure Configuration

```yaml
messaging:
  providers:
    azure:
      enabled: true
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"
      service_type: "topic"
      
      # Service Bus settings
      topic_settings:
        default_ttl: 1209600         # Message TTL (14 days)
        max_size: 5120               # Max topic size (5GB)
        duplicate_detection: true     # Enable duplicate detection
        duplicate_window: 600         # Duplicate detection window (10 minutes)
      
      # Queue settings (when service_type: "queue")
      queue_settings:
        default_ttl: 1209600         # Message TTL (14 days)
        max_size: 5120               # Max queue size (5GB)
        max_delivery_count: 10       # Max delivery attempts
        dead_letter_enabled: true    # Enable dead letter queue
```

### Azure Authentication Methods

**Method 1: Connection String (Recommended)**
```yaml
messaging:
  providers:
    azure:
      enabled: true
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"
      service_type: "topic"
```

**Method 2: Shared Access Key**
```yaml
messaging:
  providers:
    azure:
      enabled: true
      namespace: "env:AZURE_SERVICEBUS_NAMESPACE"
      shared_access_key_name: "env:AZURE_SERVICEBUS_KEY_NAME"
      shared_access_key: "env:AZURE_SERVICEBUS_KEY"
      service_type: "topic"
```

## 🛠️ Local Development Configuration

Local messaging stores messages as JSON files for development and testing without requiring cloud infrastructure.

### Basic Local Configuration

```yaml
messaging:
  default_provider: "local"
  
  providers:
    local:
      enabled: true
      
      # Local storage path
      storage_path: "data/messages"
```

### Advanced Local Configuration

```yaml
messaging:
  providers:
    local:
      enabled: true
      storage_path: "data/messages"
      
      # File organization
      organization:
        by_topic: true               # Organize files by topic directories
        timestamp_format: "iso"      # Timestamp format in filenames
        compression: false           # Compress message files
      
      # Message retention
      retention:
        enabled: true
        max_age_days: 30            # Delete messages older than 30 days
        max_messages_per_topic: 1000 # Keep max 1000 messages per topic
        cleanup_interval: 3600       # Cleanup interval (1 hour)
      
      # Development features
      development:
        pretty_print: true          # Format JSON for readability
        include_metadata: true      # Include extra metadata
        simulate_delays: false      # Simulate network delays
```

### Local Storage Structure

When using local messaging, messages are organized as follows:

```
data/messages/
├── workflow-triggers/
│   ├── 2024-01-15T10-30-00-123_abc123def.json
│   ├── 2024-01-15T10-31-00-456_def456ghi.json
│   └── .topic_metadata.json
├── task-requests/
│   ├── 2024-01-15T10-32-00-789_ghi789jkl.json
│   └── .topic_metadata.json
└── notifications/
    ├── 2024-01-15T10-33-00-012_jkl012mno.json
    └── .topic_metadata.json
```

## 📋 Message Templates Configuration

Message templates provide consistent formatting and reduce duplication across different messaging scenarios.

### Basic Templates

```yaml
messaging:
  message_templates:
    # Simple task request template
    task_request:
      message_type: "task_request"
      priority: "normal"
      payload:
        task_id: "${task_id}"
        task_type: "${task_type}"
        parameters: "${parameters}"
    
    # Workflow trigger template
    workflow_trigger:
      message_type: "workflow_trigger"
      priority: "high"
      payload:
        workflow_name: "${workflow_name}"
        trigger_data: "${trigger_data}"
        source: "${source_node}"
```

### Advanced Templates

```yaml
messaging:
  message_templates:
    # Complex notification template
    notification:
      message_type: "notification"
      priority: "${priority}"
      payload:
        notification_id: "${notification_id}"
        recipient: "${recipient}"
        subject: "${subject}"
        body: "${body}"
        channels: "${channels}"
        urgency: "${urgency}"
      metadata:
        created_by: "agentmap"
        template_version: "1.0"
        retry_policy: "standard"
    
    # System alert template
    system_alert:
      message_type: "system_alert"
      priority: "critical"
      payload:
        alert_id: "${alert_id}"
        severity: "${severity}"
        component: "${component}"
        description: "${description}"
        timestamp: "${timestamp}"
        troubleshooting_steps: "${steps}"
      metadata:
        escalation_policy: "immediate"
        notification_channels: ["email", "slack", "pagerduty"]
    
    # Data processing request
    data_processing:
      message_type: "data_processing"
      priority: "normal"
      payload:
        job_id: "${job_id}"
        dataset: "${dataset}"
        processing_type: "${processing_type}"
        input_location: "${input_location}"
        output_location: "${output_location}"
        parameters:
          batch_size: "${batch_size}"
          timeout: "${timeout}"
          retries: "${max_retries}"
```

### Template Variable Substitution

Templates support variable substitution using `${variable_name}` syntax:

```python
# Using templates in MessagingAgent configuration
messaging_agent = MessagingAgent(
    name="TaskPublisher",
    topic="task-queue",
    message_type="task_request",
    template_name="task_request",  # Use the template
    context={
        "template_variables": {
            "task_id": "task_id_field",      # Map template var to input field
            "task_type": "type_field",
            "parameters": "params_field"
        }
    }
)
```

## ⚙️ Retry Policy Configuration

Retry policies provide resilient message delivery with configurable backoff strategies.

### Basic Retry Configuration

```yaml
messaging:
  retry_policy:
    max_retries: 3                    # Maximum retry attempts
    backoff_seconds: [1, 2, 4]       # Backoff timing between retries
```

### Advanced Retry Configuration

```yaml
messaging:
  retry_policy:
    max_retries: 5
    backoff_seconds: [1, 2, 4, 8, 16]  # Exponential backoff
    
    # Retry conditions
    retry_on:
      - "connection_error"            # Network connectivity issues
      - "service_unavailable"         # Temporary service outages
      - "rate_limit_exceeded"         # Rate limiting responses
    
    # Non-retriable conditions  
    no_retry_on:
      - "authentication_error"       # Invalid credentials
      - "permission_denied"          # Authorization failures
      - "invalid_message_format"     # Malformed message data
    
    # Advanced settings
    jitter: true                     # Add random jitter to backoff
    max_total_time: 300              # Max total retry time (5 minutes)
    circuit_breaker:
      enabled: true                  # Enable circuit breaker pattern
      failure_threshold: 10          # Failures before opening circuit
      recovery_timeout: 60           # Recovery attempt interval
```

### Provider-Specific Retry Policies

```yaml
messaging:
  providers:
    aws:
      enabled: true
      service_type: "sns"
      retry_policy:
        max_retries: 5               # AWS-specific retry count
        backoff_seconds: [1, 2, 4, 8, 16]
    
    gcp:
      enabled: true
      retry_policy:
        max_retries: 3               # GCP-specific retry count
        backoff_seconds: [2, 4, 8]
    
    azure:
      enabled: true
      retry_policy:
        max_retries: 4               # Azure-specific retry count
        backoff_seconds: [1, 3, 6, 12]
```

## 🔀 Multi-Provider Configuration

Configure multiple messaging providers for different use cases, environments, or failover scenarios.

### Environment-Based Configuration

```yaml
messaging:
  # Development environment
  development:
    default_provider: "local"
    providers:
      local:
        enabled: true
        storage_path: "dev/messages"
  
  # Staging environment
  staging:
    default_provider: "aws"
    providers:
      aws:
        enabled: true
        region_name: "us-west-2"
        service_type: "sqs"
        profile_name: "staging"
  
  # Production environment
  production:
    default_provider: "gcp"
    providers:
      gcp:
        enabled: true
        project_id: "env:GCP_PROD_PROJECT"
        credentials_file: "env:GCP_PROD_CREDENTIALS"
      
      # Failover provider
      aws:
        enabled: true
        region_name: "us-east-1"
        service_type: "sns"
```

### Use Case-Based Configuration

```yaml
messaging:
  providers:
    # High-priority notifications
    notifications:
      provider: "azure"
      enabled: true
      connection_string: "env:AZURE_NOTIFICATIONS_CONNECTION"
      service_type: "topic"
    
    # Background task processing
    tasks:
      provider: "aws"
      enabled: true
      region_name: "us-east-1"
      service_type: "sqs"
    
    # Real-time events
    events:
      provider: "gcp"
      enabled: true
      project_id: "env:GCP_EVENTS_PROJECT"
    
    # Development testing
    testing:
      provider: "local"
      enabled: true
      storage_path: "test/messages"
```

## 🛡️ Security Configuration

### Environment Variable Security

```yaml
messaging:
  providers:
    aws:
      enabled: true
      region_name: "env:AWS_REGION"                    # Region from environment
      # AWS credentials managed through environment variables or IAM roles
    
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"                 # Project ID from environment
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE" # Credentials file path
    
    azure:
      enabled: true
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"  # Secure connection
```

### Access Control Configuration

```yaml
messaging:
  security:
    # Message encryption
    encryption:
      enabled: true
      algorithm: "AES-256-GCM"
      key_source: "env:MESSAGE_ENCRYPTION_KEY"
    
    # Access control
    access_control:
      enabled: true
      default_policy: "deny"           # Deny by default
      
      # Topic-level permissions
      topic_permissions:
        "workflow-triggers":
          publish: ["workflow-service", "admin"]
          subscribe: ["processing-service"]
        
        "notifications":
          publish: ["notification-service", "admin"]  
          subscribe: ["email-service", "sms-service"]
    
    # Message validation
    validation:
      enabled: true
      schema_validation: true          # Validate against JSON schemas
      size_limits:
        max_message_size: "1MB"        # Maximum message size
        max_attribute_size: "64KB"     # Maximum attribute size
```

### Audit and Monitoring

```yaml
messaging:
  monitoring:
    # Message tracking
    tracking:
      enabled: true
      track_delivery: true             # Track delivery success/failure
      track_processing_time: true     # Track message processing time
      store_message_hashes: true      # Store message content hashes
    
    # Audit logging
    audit:
      enabled: true
      log_level: "INFO"               # DEBUG, INFO, WARN, ERROR
      include_message_content: false  # Don't log sensitive content
      retention_days: 90              # Audit log retention
    
    # Metrics collection
    metrics:
      enabled: true
      provider: "prometheus"          # Metrics collection system
      collection_interval: 30         # Collection interval (seconds)
      
      # Custom metrics
      custom_metrics:
        - "messages_published_total"
        - "messages_failed_total" 
        - "message_processing_duration"
        - "queue_depth"
```

## 🎯 MessagingAgent Integration

The MessagingAgent uses the messaging configuration to publish messages during graph execution.

### Basic MessagingAgent Configuration

```python
from agentmap.agents.builtins import MessagingAgent

# Basic message publishing
messaging_agent = MessagingAgent(
    name="TaskPublisher",
    prompt="Publish task request to processing queue",
    topic="task-requests",
    message_type="task_request",
    provider="aws",                    # Use specific provider
    priority="normal",
    interrupt_execution=True           # Pause execution after publishing
)
```

### Advanced MessagingAgent Configuration

```python
# Template-based messaging with complex routing
messaging_agent = MessagingAgent(
    name="WorkflowTrigger",
    prompt="Trigger downstream workflow processing",
    topic="workflow-triggers",
    message_type="workflow_trigger",
    template_name="workflow_trigger",  # Use predefined template
    provider="gcp",                    # Use GCP Pub/Sub
    priority="high",
    timeout_seconds=300,               # 5-minute timeout
    wait_for_completion=True,          # Wait for async processing
    
    context={
        # Template variable mapping
        "template_variables": {
            "workflow_name": "target_workflow",
            "trigger_data": "input_data",
            "source_node": "node_name"
        },
        
        # Input field filtering
        "input_fields": ["workflow_id", "parameters", "metadata"]
    }
)
```

### Graph Integration Example

```csv
graph_name,node_name,context,agent_type,input_fields,output_field
ProcessingFlow,PublishTask,"{'topic': 'task-queue', 'template_name': 'task_request'}",messaging,task_data,published
ProcessingFlow,TriggerWorkflow,"{'topic': 'workflows', 'provider': 'gcp', 'priority': 'high'}",messaging,workflow_params,triggered
```

## ⚡ Performance Optimization

### Connection Pooling

```yaml
messaging:
  connection_pool:
    # Global connection settings
    max_connections: 100             # Maximum concurrent connections
    pool_timeout: 30                 # Connection timeout (seconds)
    connection_lifetime: 3600        # Connection lifetime (1 hour)
    keepalive_interval: 60          # Keepalive interval (1 minute)
  
  providers:
    aws:
      enabled: true
      service_type: "sns"
      
      # Provider-specific connection pool
      connection_pool:
        max_connections: 50          # AWS-specific connection limit
        timeout: 15                  # AWS-specific timeout
        retry_attempts: 3            # Connection retry attempts
```

### Batch Processing

```yaml
messaging:
  batch_processing:
    enabled: true                    # Enable message batching
    
    # Batching parameters
    batch_size: 10                   # Messages per batch
    batch_timeout: 1000              # Max batch wait time (milliseconds)
    max_batch_bytes: 262144          # Max batch size (256KB)
    
    # Parallel processing
    parallel_batches: 4              # Number of parallel batch processors
    worker_threads: 8                # Worker threads per batch processor
```

### Caching and Optimization

```yaml
messaging:
  optimization:
    # Topic/queue caching
    topic_cache:
      enabled: true                  # Cache topic/queue references
      ttl: 3600                     # Cache TTL (1 hour)
      max_entries: 1000             # Maximum cached entries
    
    # Connection reuse
    connection_reuse:
      enabled: true                  # Reuse connections across messages
      max_reuse_count: 1000         # Max reuses per connection
      idle_timeout: 300             # Idle connection timeout
    
    # Compression
    compression:
      enabled: true                  # Compress large messages
      algorithm: "gzip"             # Compression algorithm
      min_size: 1024                # Minimum size to compress (1KB)
```

## 🔧 Development and Testing

### Local Development Setup

```yaml
messaging:
  default_provider: "local"
  
  providers:
    local:
      enabled: true
      storage_path: "dev/messages"
      
      # Development features
      development:
        pretty_print: true          # Format JSON for readability
        include_debug_info: true    # Include debug information
        simulate_cloud_behavior: true  # Simulate cloud provider behavior
        
        # Message inspection
        message_inspection:
          enabled: true
          log_published_messages: true
          log_message_content: true  # Log full message content
```

### Testing Configuration

```yaml
messaging:
  testing:
    # Test mode settings
    test_mode:
      enabled: true                  # Enable test mode
      capture_messages: true         # Capture messages for verification
      mock_failures: false          # Mock random failures for testing
      
    # Message verification
    verification:
      enabled: true
      verify_schema: true           # Verify message schemas
      verify_templates: true        # Verify template rendering
      verify_delivery: true         # Verify message delivery
    
    # Test data management
    test_data:
      auto_cleanup: true            # Auto-cleanup test data
      retention_hours: 24           # Test data retention (24 hours)
      isolation: "thread"           # Test isolation level (thread/process)
```

## 🛠️ Troubleshooting Messaging Configuration

### Common Configuration Issues

**Authentication Failures:**
```yaml
# ❌ Missing environment variables
messaging:
  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      # Missing AWS credentials configuration

# ✅ Proper environment variable configuration
messaging:
  providers:
    aws:
      enabled: true
      region_name: "env:AWS_REGION"
      # AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY set via environment
```

**Provider Configuration Issues:**
```yaml
# ❌ Invalid service type
messaging:
  providers:
    aws:
      enabled: true
      service_type: "invalid"      # Should be "sns" or "sqs"

# ✅ Valid service type
messaging:
  providers:
    aws:
      enabled: true
      service_type: "sns"          # Valid AWS service type
```

**Template Configuration Issues:**
```yaml
# ❌ Missing template variables
messaging:
  message_templates:
    task_request:
      payload:
        task_id: "${missing_variable}"  # Variable not provided

# ✅ Proper template with all variables
messaging:
  message_templates:
    task_request:
      payload:
        task_id: "${task_id}"       # Variable will be substituted
```

### Debugging Configuration

```yaml
messaging:
  debugging:
    # Logging configuration
    logging:
      level: "DEBUG"                # DEBUG, INFO, WARN, ERROR
      log_message_content: true     # Log full message content
      log_provider_details: true    # Log provider-specific details
      log_retry_attempts: true      # Log retry attempts
    
    # Health checks
    health_checks:
      enabled: true                 # Enable health monitoring
      check_interval: 60            # Health check interval (seconds)
      timeout: 10                   # Health check timeout
      
      # Provider-specific health checks
      check_providers: true         # Check provider connectivity
      check_topics: false           # Check topic existence (can be slow)
      check_permissions: true       # Check access permissions
    
    # Error reporting
    error_reporting:
      enabled: true
      capture_stack_traces: true    # Capture full stack traces
      report_to_logs: true          # Report errors to logs
      max_error_history: 100        # Keep last 100 errors
```

### Validation and Testing Commands

```bash
# Validate messaging configuration
agentmap validate-config --section messaging

# Test messaging connectivity
agentmap test-messaging --provider aws
agentmap test-messaging --provider gcp
agentmap test-messaging --provider azure
agentmap test-messaging --provider local

# Test message publishing
agentmap test-publish --topic test-topic --message '{"test": "data"}'

# List available providers
agentmap list-messaging-providers

# Show messaging service information
agentmap info messaging
```

## 📖 Next Steps

1. **Set [Environment Variables](./environment-variables)** - Configure messaging credentials
2. **Review [Configuration Examples](./examples)** - See complete messaging setups
3. **Implement MessagingAgent** - Use messaging in your workflows
4. **Test Message Publishing** - Validate your configuration
5. **Monitor Message Delivery** - Set up monitoring and alerting

Ready to set up environment variables for messaging? Continue to the [Environment Variables](./environment-variables) guide for messaging-specific credential configuration.
