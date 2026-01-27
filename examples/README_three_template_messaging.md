# Three-Template Messaging Examples

This directory contains example workflows demonstrating the three distinct messaging patterns supported by SuspendAgent.

## Overview

SuspendAgent supports three message template types:

1. **Graph Trigger** (`default_graph_trigger`) - Trigger another AgentMap graph via serverless
2. **Node Suspend** (`default_node_suspend`) - Trigger external process/service
3. **Auto-Resume** (`default_auto_resume`) - Serverless function auto-resumes workflow

## Example Files

### 1. Graph Trigger Example (`suspend_graph_trigger.csv`)

**Purpose:** Demonstrates launching a sub-workflow via message broker.

**Use Case:** Main workflow triggers another AgentMap graph to run asynchronously, then resumes when sub-workflow completes.

**Key Configuration:**
```csv
context,"{""send_graph_message"": true, ""graph_message_template"": ""default_graph_trigger"", ""graph_message_topic"": ""graph_triggers""}"
```

**Message Payload:**
```json
{
  "event_type": "workflow_graph_trigger",
  "graph": "sub_workflow",
  "state": {...},  // Inputs for sub-workflow
  "thread_id": "...",
  "context": {...}
}
```

**How It Works:**
1. Workflow suspends at `trigger_sub_workflow` node
2. Graph message published to `graph_triggers` topic with `state` field
3. Serverless handler consumes message, executes sub-graph
4. External system resumes parent workflow when sub-workflow completes

**Run Example:**
```bash
poetry run AgentMap run graph_trigger_example::main --config agentmap_local_config.yaml
```

### 2. Node Suspend Example (`suspend_node_external.csv`)

**Purpose:** Demonstrates triggering an external approval system.

**Use Case:** Workflow suspends and sends message to external system (Lambda, webhook, approval service), which processes the request and resumes the workflow.

**Key Configuration:**
```csv
context,"{""send_suspend_message"": true, ""suspend_message_template"": ""default_node_suspend"", ""suspend_message_topic"": ""approval_events""}"
```

**Message Payload:**
```json
{
  "event_type": "workflow_suspended",
  "thread_id": "...",
  "inputs": {...},  // NOT "state" - for external reference
  "node_name": "wait_external_approval",
  "context": {...}
}
```

**How It Works:**
1. Workflow suspends at `wait_external_approval` node
2. Suspension message published to `approval_events` topic with `inputs` field
3. External approval system (Lambda, webhook) consumes message
4. External system processes approval and calls resume API
5. Workflow continues after resume

**Run Example:**
```bash
poetry run AgentMap run external_processing_example::main --config agentmap_local_config.yaml
```

**Resume via HTTP API:**
```bash
curl -X POST "http://127.0.0.1:8000/resume/<thread_id>" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "data": {
      "approved_by": "manager@example.com",
      "status": "approved"
    }
  }'
```

### 3. Auto-Resume Example (`suspend_auto_resume.csv`)

**Purpose:** Demonstrates chunked serverless execution with automatic resume.

**Use Case:** Long-running workflow splits into chunks, each chunk triggers serverless function that auto-resumes the next chunk. Avoids Lambda/function timeouts.

**Key Configuration:**
```csv
context,"{""send_resume_message"": true, ""resume_message_template"": ""default_auto_resume"", ""resume_message_topic"": ""resume_triggers""}"
```

**Message Payload:**
```json
{
  "event_type": "workflow_resumed",
  "action": "resume",  // Special action for serverless auto-resume
  "thread_id": "...",
  "resume_value": {...},  // Data to pass to resumed workflow
  "suspension_duration_seconds": 5.2,
  "context": {...}
}
```

**How It Works:**
1. Workflow suspends at `chunk_processor_1` node
2. Resume message published to `resume_triggers` topic with `action: "resume"`
3. Serverless handler consumes message, detects `action == "resume"`
4. Handler calls `resume_workflow()` automatically (no manual HTTP API call)
5. Workflow continues to next chunk, repeats process

**Run Example:**
```bash
poetry run AgentMap run auto_resume_example::main --config agentmap_local_config.yaml
```

**Note:** This pattern requires serverless deployment with message broker integration. See `src/agentmap/deployment/serverless/base_handler.py` for serverless implementation.

## Configuration

All examples require messaging configuration in your `agentmap_config.yaml`:

```yaml
messaging:
  default_provider: "local"

  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"

  message_templates:
    default_graph_trigger:
      event_type: "$event_type"
      graph: "$graph"
      state: "$inputs"  # For serverless handler
      thread_id: "$thread_id"
      node_name: "$node_name"
      workflow: "$workflow"
      timestamp: "$timestamp"
      context: "$context"

    default_node_suspend:
      event_type: "$event_type"
      thread_id: "$thread_id"
      inputs: "$inputs"  # NOT "state" - for external reference
      node_name: "$node_name"
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      context: "$context"

    default_auto_resume:
      event_type: "$event_type"
      action: "resume"  # Tells serverless to resume
      thread_id: "$thread_id"
      resume_value: "$resume_value"
      node_name: "$node_name"
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      suspension_duration_seconds: "$suspension_duration_seconds"
      context: "$context"
```

## Testing

### Local Testing (Without Serverless)

All examples can run locally with the local messaging provider:

1. Execute workflow and note the thread_id:
   ```bash
   poetry run AgentMap run <workflow>::main --config agentmap_local_config.yaml
   ```

2. Workflow will suspend and publish message to `agentmap_data/messages/`

3. Resume workflow via HTTP API (for node suspend pattern):
   ```bash
   poetry run AgentMap resume <thread_id> "yes" --config agentmap_local_config.yaml
   ```

### Serverless Testing (AWS Lambda)

1. Deploy serverless handler with message broker integration
2. Configure messaging provider (AWS SQS, Azure Service Bus, etc.)
3. Execute workflow - messages automatically trigger serverless functions
4. Monitor execution via CloudWatch/Application Insights

See `docs-docusaurus/docs/agents/suspend-agent-features.md` for full serverless integration guide.

## Key Differences Between Patterns

| Pattern | Message Field | Serverless Behavior | Use Case |
|---------|---------------|---------------------|----------|
| **Graph Trigger** | Uses `state` field | Executes another graph | Sub-workflow orchestration |
| **Node Suspend** | Uses `inputs` field | External processing only | Human approval, API callbacks |
| **Auto-Resume** | Includes `action: "resume"` | Auto-resumes workflow | Chunked serverless execution |

## Troubleshooting

### Messages Not Published

1. Check messaging service configuration in `agentmap_config.yaml`
2. Verify local storage path exists: `agentmap_data/messages/`
3. Enable debug logging to see message publishing attempts

### Resume Not Working

1. Verify thread_id matches suspended workflow
2. Check message template includes required fields
3. For auto-resume: ensure serverless handler has `_handle_resume_action()` support

### Serverless Handler Not Consuming Messages

1. Verify message broker configuration (queue/topic exists)
2. Check serverless function has correct trigger configuration
3. Ensure message payload matches expected format

## Additional Resources

- [SuspendAgent Messaging Features](../docs-docusaurus/docs/agents/suspend-agent-features.md)
- [Three-Template Architecture](../docs/plan/suspend-agent-enhancements/THREE_TEMPLATE_ARCHITECTURE.md)
- [Serverless Deployment Guide](../docs-docusaurus/docs/deployment/serverless-deployment.md)
- [HTTP API Reference](../docs-docusaurus/docs/deployment/06-http-api-reference.md)

## Next Steps

1. Try each example locally to understand the patterns
2. Customize message templates for your use case
3. Deploy serverless handler for production workflows
4. Build your own workflows using these patterns as templates
