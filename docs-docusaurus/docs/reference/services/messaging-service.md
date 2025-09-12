---
sidebar_position: 6
title: MessagingService
description: Cloud-agnostic message publishing service with multi-provider support and intelligent fallback
---

# MessagingService

The `MessagingService` provides a unified interface for publishing messages to cloud message queues and topics across multiple cloud providers. It supports automatic provider detection, intelligent fallback mechanisms, and standardized message formatting.

## Overview

The service abstracts cloud-specific messaging implementations behind a consistent interface, enabling seamless switching between providers and automatic failover when services are unavailable.

### Key Features

- **Multi-Provider Support**: Works with GCP Pub/Sub, AWS SNS/SQS, Azure Service Bus, and local testing
- **Automatic Detection**: Automatically detects available cloud SDKs and configures adapters
- **Intelligent Caching**: Caches provider availability to avoid repeated checks
- **Retry Logic**: Built-in retry mechanism with configurable backoff strategies
- **Message Templates**: Support for reusable message templates with variable substitution
- **Standardized Format**: Consistent message structure across all providers

## Dependencies

The MessagingService requires these services from the DI container:

- **AppConfigService**: For messaging configuration and defaults
- **LoggingService**: For structured logging and debugging
- **AvailabilityCacheService**: For caching provider availability status

## Configuration

### Basic Configuration

```yaml
# config/messaging.yaml
messaging:
  default_provider: "gcp"
  providers:
    gcp:
      enabled: true
      project_id: "my-project"
      credentials_path: "path/to/service-account.json"
    aws:
      enabled: true
      region: "us-east-1"
      access_key_id: "${AWS_ACCESS_KEY_ID}"
      secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    azure:
      enabled: true
      connection_string: "${AZURE_SERVICE_BUS_CONNECTION_STRING}"
    local:
      enabled: true
      storage_path: "data/messages"
  
  retry_policy:
    max_retries: 3
    backoff_seconds: [1, 2, 4]
  
  message_templates:
    task_request:
      message_type: "task_request"
      payload:
        task_id: "${task_id}"
        agent_type: "${agent_type}"
        priority: "${priority}"
      metadata:
        source: "agentmap"
        created_by: "${user_id}"
```

### Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Azure Configuration  
AZURE_SERVICE_BUS_CONNECTION_STRING=your_connection_string

# GCP Configuration (or use service account file)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Usage Examples

### Basic Message Publishing

```python
# Get service from DI container
messaging_service = container.messaging_service()

# Publish a simple message
result = await messaging_service.publish_message(
    topic="workflow_triggers",
    message_type="graph_execution",
    payload={
        "graph_name": "DataProcessing",
        "input_data": {"user_id": "123", "action": "process"}
    },
    metadata={
        "source_node": "trigger_node",
        "workflow_id": "wf_456"
    },
    priority=MessagePriority.HIGH
)

if result.success:
    print(f"Message published successfully: {result.operation}")
else:
    print(f"Failed to publish: {result.error}")
```

### Provider-Specific Publishing

```python
# Publish to specific provider
result = await messaging_service.publish_message(
    topic="critical_alerts",
    message_type="system_alert",
    payload={
        "alert_type": "service_failure",
        "service": "GraphRunnerService",
        "details": "Execution timeout after 300s"
    },
    provider=CloudProvider.GCP,  # Force GCP provider
    priority=MessagePriority.CRITICAL,
    thread_id="alert_thread_789"
)
```

### Using Message Templates

```python
# Apply template with variables
templated_message = messaging_service.apply_template(
    "task_request",
    {
        "task_id": "task_123",
        "agent_type": "LLMAgent", 
        "priority": "high",
        "user_id": "admin"
    }
)

# Publish using template
result = await messaging_service.publish_message(
    topic="agent_tasks",
    message_type=templated_message["message_type"],
    payload=templated_message["payload"],
    metadata=templated_message["metadata"],
    priority=MessagePriority.HIGH
)
```

### Service Monitoring

```python
# Check service status
service_info = messaging_service.get_service_info()
print(f"Available providers: {service_info['available_adapters']}")
print(f"Default provider: {service_info['default_provider']}")

# Get available providers
providers = messaging_service.get_available_providers()
print(f"Active providers: {', '.join(providers)}")
```

## Core Methods

### publish_message()

Main method for publishing messages to cloud topics.

```python
async def publish_message(
    self,
    topic: str,
    message_type: str,
    payload: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    provider: Optional[CloudProvider] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    thread_id: Optional[str] = None,
) -> StorageResult
```

**Parameters:**
- `topic`: Topic/queue name to publish to
- `message_type`: Type of message (e.g., "task_request", "graph_trigger")
- `payload`: Message payload data
- `metadata`: Optional metadata for the message
- `provider`: Specific provider to use (defaults to configured default)
- `priority`: Message priority (LOW, NORMAL, HIGH, CRITICAL)
- `thread_id`: Thread ID for message correlation

**Returns:** `StorageResult` indicating success/failure with operation details

### apply_template()

Apply message template with variable substitution.

```python
def apply_template(
    self,
    template_name: str,
    variables: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters:**
- `template_name`: Name of the template to apply
- `variables`: Dictionary of variables for substitution

**Returns:** Template with variables substituted

### get_service_info()

Get comprehensive service information for debugging.

```python
def get_service_info(self) -> Dict[str, Any]
```

**Returns:** Dictionary with service status, providers, and configuration

### get_available_providers()

Get list of currently available messaging providers.

```python
def get_available_providers(self) -> List[str]
```

**Returns:** List of provider names that are available and functional

## Message Format

All messages follow a standardized format regardless of provider:

```json
{
  "version": "1.0",
  "message_id": "uuid-generated-id",
  "message_type": "graph_execution",
  "timestamp": "2025-09-10T14:30:00.000Z",
  "thread_id": "optional-thread-id",
  "priority": "high",
  "payload": {
    "graph_name": "DataProcessing",
    "input_data": {"user_id": "123"}
  },
  "metadata": {
    "source_node": "trigger_node",
    "workflow_id": "wf_456"
  },
  "source": {
    "system": "agentmap",
    "version": "0.1.0"
  }
}
```

## Cloud Provider Configuration

### Google Cloud Pub/Sub

Requires the `google-cloud-pubsub` library:

```bash
pip install google-cloud-pubsub
```

Configuration:
```yaml
providers:
  gcp:
    enabled: true
    project_id: "my-gcp-project"
    credentials_path: "path/to/service-account.json"
```

### AWS SNS/SQS

Requires the `boto3` library:

```bash
pip install boto3
```

Configuration:
```yaml
providers:
  aws:
    enabled: true
    region: "us-east-1"
    access_key_id: "${AWS_ACCESS_KEY_ID}"
    secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
```

### Azure Service Bus

Requires the `azure-servicebus` library:

```bash
pip install azure-servicebus
```

Configuration:
```yaml
providers:
  azure:
    enabled: true
    connection_string: "${AZURE_SERVICE_BUS_CONNECTION_STRING}"
```

### Local Provider

Built-in provider for development and testing:

```yaml
providers:
  local:
    enabled: true
    storage_path: "data/messages"
```

## Error Handling

The service uses specific exception types for clear error communication:

- **MessagingServiceUnavailableError**: Thrown when no suitable provider is available
- **MessagingOperationError**: Thrown for general messaging operation failures  
- **MessagingConnectionError**: Thrown for provider connection issues

```python
from agentmap.exceptions import MessagingServiceUnavailableError

try:
    result = await messaging_service.publish_message(
        topic="test_topic",
        message_type="test",
        payload={"data": "test"}
    )
except MessagingServiceUnavailableError as e:
    print(f"No messaging providers available: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Integration with Agents

Agents can receive messaging capabilities through the dependency injection system:

### Agent Protocol

```python
@runtime_checkable
class MessagingCapableAgent(Protocol):
    """Protocol for agents that can use messaging services."""
    
    def configure_messaging_service(
        self, messaging_service: MessagingServiceProtocol
    ) -> None:
        """Configure messaging service for this agent."""
        ...
```

### Agent Implementation

```python
class NotificationAgent:
    def __init__(self):
        self.messaging_service = None
    
    def configure_messaging_service(
        self, messaging_service: MessagingServiceProtocol
    ) -> None:
        """Configure messaging service for this agent."""
        self.messaging_service = messaging_service
    
    async def send_notification(self, user_id: str, message: str):
        """Send notification via messaging service."""
        if self.messaging_service:
            await self.messaging_service.publish_message(
                topic="user_notifications",
                message_type="notification",
                payload={"user_id": user_id, "message": message},
                priority=MessagePriority.NORMAL
            )
```

## Performance Considerations

### Provider Selection Strategy

1. **Availability Caching**: Provider availability is cached to avoid repeated SDK checks
2. **Graceful Fallback**: Service gracefully falls back to alternative providers
3. **Connection Pooling**: Adapters maintain connection pools for efficiency
4. **Retry Logic**: Built-in retry with exponential backoff reduces transient failures

### Monitoring

Monitor service performance using the logging output:

```python
# Enable debug logging to see provider selection and retry attempts
logging_service.set_level("DEBUG")

# Check service health
info = messaging_service.get_service_info()
print(f"Available providers: {info['available_adapters']}")
```

## Best Practices

### 1. Configure Multiple Providers

```yaml
# Configure multiple providers for redundancy
providers:
  gcp:
    enabled: true
    # GCP config
  aws:
    enabled: true  
    # AWS config as fallback
  local:
    enabled: true  # For development
```

### 2. Use Appropriate Message Priorities

```python
# Critical system alerts
priority=MessagePriority.CRITICAL

# Normal workflow triggers  
priority=MessagePriority.NORMAL

# Background processing
priority=MessagePriority.LOW
```

### 3. Include Thread IDs for Correlation

```python
# Use thread IDs to correlate related messages
thread_id = f"workflow_{workflow_id}_{timestamp}"

await messaging_service.publish_message(
    topic="workflow_events",
    message_type="node_completed",
    payload=payload,
    thread_id=thread_id
)
```

### 4. Leverage Message Templates

```yaml
# Define reusable templates
message_templates:
  error_alert:
    message_type: "error_alert"
    payload:
      error_type: "${error_type}"
      service: "${service_name}"
      timestamp: "${timestamp}"
      details: "${error_details}"
    metadata:
      severity: "${severity}"
      component: "agentmap"
```

### 5. Handle Failures Gracefully

```python
result = await messaging_service.publish_message(
    topic="important_events",
    message_type="user_action",
    payload=event_data
)

if not result.success:
    # Log the failure but continue processing
    logger.warning(f"Failed to publish event: {result.error}")
    # Consider alternative notification methods
    await send_email_notification(event_data)
```

## Troubleshooting

### Common Issues

**No providers available:**
```
MessagingServiceUnavailableError: No adapter available for provider: gcp
```
- Check that required SDK libraries are installed
- Verify cloud credentials are properly configured
- Check availability cache for cached failures

**Authentication failures:**
```
MessagingConnectionError: Failed to authenticate with provider
```
- Verify credentials (service accounts, access keys, connection strings)
- Check IAM permissions for messaging services
- Ensure environment variables are set correctly

**Topic not found:**
```
MessagingOperationError: Topic 'unknown_topic' does not exist
```
- Create topics before publishing (most providers support auto-creation)
- Check topic naming conventions for the provider
- Verify project/account permissions

### Debug Steps

1. **Check Service Status:**
   ```python
   info = messaging_service.get_service_info()
   print(json.dumps(info, indent=2))
   ```

2. **Verify Provider Configuration:**
   ```python
   providers = messaging_service.get_available_providers()
   print(f"Available: {providers}")
   ```

3. **Enable Debug Logging:**
   ```python
   logging_service.set_level("DEBUG")
   # Now see detailed provider selection and retry logs
   ```

4. **Test Local Provider:**
   ```yaml
   # Use local provider for testing
   messaging:
     default_provider: "local"
     providers:
       local:
         enabled: true
         storage_path: "test/messages"
   ```

The MessagingService provides a robust, cloud-agnostic messaging solution that seamlessly integrates with AgentMap's workflow system while maintaining high availability and performance across multiple cloud providers.
