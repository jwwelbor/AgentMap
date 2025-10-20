# SuspendAgent Messaging Examples

This directory contains example workflows demonstrating the new SuspendAgent messaging features.

## Examples

### 1. Basic Messaging (`suspend_messaging_basic.csv`)

**Purpose**: Simple approval workflow with suspension and resume messaging.

**Features Demonstrated**:
- Suspension message publishing
- Resume message publishing
- Default message templates
- Raw return value handling

**Usage**:
```bash
poetry run AgentMap run suspend_messaging_basic::main --config agentmap_config.yaml
```

**Flow**:
1. Start workflow with request data
2. LLM validates the request
3. SuspendAgent suspends and publishes suspension message
4. External system approves via HTTP API
5. SuspendAgent publishes resume message
6. LLM processes approved request
7. Output final result

---

### 2. Serverless Integration (`suspend_serverless_integration.csv`)

**Purpose**: Event-driven approval workflow that triggers AWS Lambda for external processing.

**Features Demonstrated**:
- Suspension messages
- Resume messages
- Graph messages (triggers serverless function)
- Custom message topics
- Custom message templates

**Prerequisites**:
- AWS Lambda function configured to consume messages from `serverless_triggers` topic
- Messaging service configured with AWS adapter

**Usage**:
```bash
poetry run AgentMap run serverless_approval::main --config agentmap_config.yaml
```

**Flow**:
1. Start approval workflow
2. Validate approval request
3. SuspendAgent suspends and:
   - Publishes graph message to `serverless_triggers` (triggers Lambda)
   - Publishes suspension message to `workflow_events`
4. AWS Lambda processes approval
5. Lambda calls `/resume/{thread_id}` endpoint
6. SuspendAgent publishes resume message
7. Process approval decision
8. Send notifications
9. Complete workflow

**Message Topics**:
- `serverless_triggers` - Triggers Lambda function
- `workflow_events` - Monitoring and observability

---

### 3. API Integration (`suspend_api_integration.csv`)

**Purpose**: Workflow that waits for external API callback.

**Features Demonstrated**:
- API callback pattern
- Custom message topics for API callbacks
- Raw return values (no unwrapping needed)
- Resume message with duration tracking

**Usage**:
```bash
poetry run AgentMap run api_integration::main --config agentmap_config.yaml
```

**Flow**:
1. Start with API request
2. Prepare API request
3. SuspendAgent suspends waiting for callback
4. External API calls `/resume/{thread_id}` with response
5. Process API response (receives raw response data)
6. Store results
7. Complete workflow

**Benefits**:
- No polling needed - external API pushes data
- Clean integration with webhook patterns
- Resume message provides timing data

---

## Configuration

All examples require messaging service configuration in `agentmap_config.yaml`:

```yaml
messaging:
  default_provider: "local"  # or "aws", "gcp", "azure"
  providers:
    local:
      enabled: true
      storage_path: "data/messages"
  message_templates:
    default_suspend:
      event_type: "$event_type"
      thread_id: "$thread_id"
      node_name: "$node_name"
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      inputs: "$inputs"
    default_resume:
      event_type: "$event_type"
      thread_id: "$thread_id"
      node_name: "$node_name"
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      resume_value: "$resume_value"
      suspension_duration_seconds: "$suspension_duration_seconds"
    lambda_trigger:
      trigger_type: "workflow_suspended"
      function_name: "approval-processor"
      thread_id: "$thread_id"
      workflow: "$workflow"
      data: "$inputs"
```

## Testing

You can test these workflows using the HTTP API:

### 1. Execute Workflow
```bash
curl -X POST http://localhost:8000/execute/suspend_messaging_basic/main \
  -H "Content-Type: application/json" \
  -d '{"request_data": {"user": "alice", "amount": 5000}}'
```

### 2. Check Status
```bash
curl http://localhost:8000/status/{thread_id}
```

### 3. Resume Workflow
```bash
curl -X POST http://localhost:8000/resume/{thread_id} \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "approved_by": "manager@example.com"}'
```

## Monitoring Messages

When using local messaging provider, messages are written to `data/messages/`. You can monitor them:

```bash
# Watch for new messages
watch -n 1 'ls -lt data/messages/ | head -20'

# View latest message
cat data/messages/$(ls -t data/messages/ | head -1)
```

## Learn More

- [SuspendAgent Documentation](../docs-docusaurus/docs/agents/suspend-agent-features.md)
- [HTTP API Reference](../docs-docusaurus/docs/http-api/reference.md)
- [Messaging Configuration](../docs-docusaurus/docs/configuration/messaging.md)
- [Serverless Deployment](../docs-docusaurus/docs/deployment/serverless.md)
