---
title: Messaging Configuration
sidebar_position: 4
description: Configure messaging services to enable workflow events, external integrations, and serverless coordination in AgentMap.
keywords: [messaging configuration, AWS SNS, AWS SQS, Google Cloud Pub/Sub, Azure Service Bus, workflow events, serverless integration]
---

# Messaging Configuration

AgentMap's messaging system enables your workflows to communicate with external systems, trigger serverless functions, and coordinate long-running processes through cloud-native message queues and topics.

## What is Messaging in AgentMap?

Messaging allows your workflows to:
- **Trigger external processes** when a workflow suspends or reaches a checkpoint
- **Launch serverless functions** to execute sub-workflows or process data
- **Send workflow events** to monitoring systems, notification services, or approval systems
- **Coordinate distributed workflows** across multiple systems and environments
- **Enable human-in-the-loop** patterns with approval workflows and callbacks

:::tip When to Use Messaging
Use messaging when your workflow needs to interact with systems outside AgentMap, wait for external events, or trigger asynchronous processing that shouldn't block workflow execution.
:::

## Available Messaging Providers

AgentMap supports four messaging providers:

| Provider | Best For | Requirements |
|----------|----------|--------------|
| **Local** | Development and testing | None - built-in |
| **AWS SNS/SQS** | AWS infrastructure | `boto3` package |
| **Google Cloud Pub/Sub** | GCP infrastructure | `google-cloud-pubsub` package |
| **Azure Service Bus** | Azure infrastructure | `azure-servicebus` package |

:::info Provider Selection
Choose the provider that matches your deployment environment. For local development, use the `local` provider which stores messages as JSON files.
:::

## Quick Start

### Basic Local Configuration

Perfect for development and testing without cloud infrastructure:

```yaml
# agentmap_config.yaml
messaging:
  # Use local file-based messaging (no cloud required)
  default_provider: "local"

  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"
```

This configuration:
- Stores messages as JSON files in `agentmap_data/messages/`
- Requires no external dependencies
- Perfect for testing messaging patterns locally

### Basic Cloud Configuration

For production deployments:

```yaml
messaging:
  default_provider: "aws"

  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"  # or "sqs"
      # AWS credentials via environment variables or IAM roles
```

## Configuration Reference

### Complete Configuration Structure

```yaml
messaging:
  # Which provider to use by default
  default_provider: "local"  # Options: "local", "aws", "gcp", "azure"

  # Provider-specific configurations
  providers:
    # ... see provider sections below

  # Message templates for consistent formatting
  message_templates:
    # ... see templates section below

  # Retry policy for failed message publishing
  retry_policy:
    max_retries: 3
    backoff_seconds: [1, 2, 4]  # Exponential backoff timing
```

## Provider Configuration

### Local Provider (Development/Testing)

The local provider stores messages as JSON files - perfect for development and testing.

**Basic Configuration:**
```yaml
messaging:
  default_provider: "local"

  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"
```

**What You Get:**
- Messages stored as timestamped JSON files
- No external dependencies required
- Easy to inspect and debug messages
- Organized by topic/queue names

**File Organization:**
```
agentmap_data/messages/
├── workflow_events/
│   ├── 2024-01-15T10-30-00-123_abc123def.json
│   └── 2024-01-15T10-31-00-456_def456ghi.json
├── graph_triggers/
│   └── 2024-01-15T10-32-00-789_ghi789jkl.json
└── approval_events/
    └── 2024-01-15T10-33-00-012_jkl012mno.json
```

### AWS Provider (SNS/SQS)

AWS messaging supports both SNS (Simple Notification Service) for pub/sub and SQS (Simple Queue Service) for queues.

**SNS Configuration (Pub/Sub):**
```yaml
messaging:
  default_provider: "aws"

  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"  # Use SNS topics
      profile_name: "default"  # Optional: AWS profile name
```

**SQS Configuration (Queues):**
```yaml
messaging:
  default_provider: "aws"

  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sqs"  # Use SQS queues
```

**Authentication Options:**

1. **Environment Variables (Recommended for Production):**
   ```bash
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_REGION="us-east-1"
   ```
   ```yaml
   messaging:
     providers:
       aws:
         enabled: true
         region_name: "env:AWS_REGION"
         service_type: "sns"
   ```

2. **AWS Profile (Development):**
   ```yaml
   messaging:
     providers:
       aws:
         enabled: true
         region_name: "us-east-1"
         service_type: "sns"
         profile_name: "my-profile"  # From ~/.aws/credentials
   ```

3. **IAM Roles (AWS Infrastructure):**
   ```yaml
   messaging:
     providers:
       aws:
         enabled: true
         region_name: "us-east-1"
         service_type: "sns"
         # No credentials needed - uses IAM role attached to instance/function
   ```

**Installing AWS Support:**
```bash
pip install boto3
```

### Google Cloud Provider (Pub/Sub)

Google Cloud Pub/Sub provides scalable messaging with automatic topic creation.

**Basic Configuration:**
```yaml
messaging:
  default_provider: "gcp"

  providers:
    gcp:
      enabled: true
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE"
```

**Authentication Options:**

1. **Service Account File (Recommended):**
   ```bash
   export GCP_PROJECT_ID="my-project"
   export GCP_SERVICE_ACCOUNT_FILE="/path/to/service-account.json"
   ```

2. **Application Default Credentials (Development):**
   ```bash
   gcloud auth application-default login
   ```
   ```yaml
   messaging:
     providers:
       gcp:
         enabled: true
         project_id: "my-project"
         use_default_credentials: true
   ```

3. **Environment Variable (Service Account JSON):**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
   export GCP_PROJECT_ID="my-project"
   ```

**Installing GCP Support:**
```bash
pip install google-cloud-pubsub
```

### Azure Provider (Service Bus)

Azure Service Bus provides enterprise messaging with topics and queues.

**Basic Configuration:**
```yaml
messaging:
  default_provider: "azure"

  providers:
    azure:
      enabled: true
      connection_string: "env:AZURE_SERVICEBUS_CONNECTION_STRING"
      service_type: "topic"  # Options: "topic" or "queue"
```

**Authentication:**

Get your connection string from the Azure Portal and set it as an environment variable:

```bash
export AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://..."
```

**Service Types:**
- **Topics**: Pub/sub pattern with multiple subscribers
- **Queues**: Point-to-point messaging with single consumer

**Installing Azure Support:**
```bash
pip install azure-servicebus
```

## Message Templates

Message templates provide consistent formatting for different types of workflow events.

### Why Use Templates?

Templates allow you to:
- **Standardize message formats** across your organization
- **Reduce configuration duplication** in workflow definitions
- **Separate message structure from workflow logic**
- **Ensure compatibility** with external systems expecting specific formats

### Built-in Templates

AgentMap includes three standard templates for common messaging patterns:

#### 1. Graph Trigger Template

Used to trigger another AgentMap graph execution via serverless:

```yaml
messaging:
  message_templates:
    default_graph_trigger:
      event_type: "$event_type"
      graph: "$graph"              # Which graph to execute
      state: "$inputs"             # Inputs for the graph (serverless compatible)
      thread_id: "$thread_id"      # Parent thread for correlation
      node_name: "$node_name"
      workflow: "$workflow"
      timestamp: "$timestamp"
      context: "$context"
```

**Use Case:** Launch a sub-workflow or trigger a serverless function to execute another graph.

**Key Field:** `state` contains the inputs that the serverless handler will use to execute the graph.

#### 2. Node Suspend Template

Used to trigger external processing when a workflow suspends:

```yaml
messaging:
  message_templates:
    default_node_suspend:
      event_type: "$event_type"
      thread_id: "$thread_id"      # Which workflow suspended
      inputs: "$inputs"            # Data for external reference (NOT for execution)
      node_name: "$node_name"      # Which node suspended
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      context: "$context"
```

**Use Case:** Notify external systems (approval services, webhooks, human operators) that a workflow is waiting.

**Key Field:** `inputs` provides context for the external system (not used for graph execution).

#### 3. Auto-Resume Template

Used by serverless functions to automatically resume a workflow:

```yaml
messaging:
  message_templates:
    default_auto_resume:
      event_type: "$event_type"
      action: "resume"             # Tells serverless to auto-resume
      thread_id: "$thread_id"      # Which workflow to resume
      resume_value: "$resume_value"  # Data to pass to resumed workflow
      node_name: "$node_name"
      workflow: "$workflow"
      graph: "$graph"
      timestamp: "$timestamp"
      suspension_duration_seconds: "$suspension_duration_seconds"
      context: "$context"
```

**Use Case:** Enable chunked serverless execution where one function triggers the next automatically.

**Key Field:** `action: "resume"` signals the serverless handler to resume (not execute a new graph).

### Template Variables

Templates use `$variable_name` syntax. Available variables depend on the message type:

| Variable | Description | Available In |
|----------|-------------|--------------|
| `$event_type` | Type of event (e.g., "workflow_suspended") | All templates |
| `$thread_id` | Thread identifier for workflow correlation | All templates |
| `$node_name` | Name of the node that triggered the message | All templates |
| `$workflow` | Workflow name from CSV | All templates |
| `$graph` | Graph name for execution | All templates |
| `$timestamp` | ISO timestamp when message was created | All templates |
| `$inputs` | Node inputs (for context/reference) | Suspend, Graph |
| `$state` | Inputs formatted for graph execution | Graph only |
| `$resume_value` | Value passed to resumed workflow | Resume only |
| `$suspension_duration_seconds` | How long workflow was suspended | Resume only |
| `$context` | Agent context configuration | All templates |

### Custom Templates

Create custom templates for your specific integrations:

```yaml
messaging:
  message_templates:
    # Custom approval request template
    approval_request:
      event_type: "approval_required"
      request_id: "$thread_id"
      requester: "$context.requester_email"
      approval_type: "$context.approval_type"
      amount: "$inputs.amount"
      description: "$inputs.description"
      callback_url: "https://api.example.com/resume/$thread_id"

    # Custom notification template
    status_notification:
      event_type: "workflow_status_update"
      workflow_id: "$thread_id"
      status: "$event_type"
      details: "$inputs"
      timestamp: "$timestamp"
      notification_channels: ["email", "slack"]
```

## Using Messaging in Workflows

### SuspendAgent with Messaging

The SuspendAgent is the primary way to use messaging in workflows. It can publish up to three different message types when it suspends and resumes.

**CSV Configuration:**
```csv
graph_name,node_name,agent_type,context
MyWorkflow,wait_approval,suspend,"{""send_suspend_message"": true, ""suspend_message_template"": ""default_node_suspend"", ""suspend_message_topic"": ""approval_events""}"
```

**What This Does:**
1. Workflow reaches `wait_approval` node
2. SuspendAgent suspends execution
3. Publishes suspension message to `approval_events` topic
4. External system consumes message and processes approval
5. External system calls resume API
6. Workflow continues execution

### Message Type Combinations

You can configure up to three message types per SuspendAgent:

```csv
context,"{
  ""send_graph_message"": true,
  ""graph_message_template"": ""default_graph_trigger"",
  ""graph_message_topic"": ""serverless_triggers"",
  ""send_suspend_message"": true,
  ""suspend_message_template"": ""default_node_suspend"",
  ""suspend_message_topic"": ""monitoring_events"",
  ""send_resume_message"": true,
  ""resume_message_template"": ""default_auto_resume"",
  ""resume_message_topic"": ""resume_triggers""
}"
```

**Publishing Sequence:**
1. **On Suspend:** Graph message published (if configured)
2. **On Suspend:** Suspend message published (if configured)
3. **On Resume:** Resume message published (if configured)

### Configuration Options

| Context Key | Description | Default |
|-------------|-------------|---------|
| `send_graph_message` | Publish message to trigger graph execution | `false` |
| `graph_message_template` | Template name for graph messages | `"default_graph_trigger"` |
| `graph_message_topic` | Topic/queue for graph messages | `"workflow_events"` |
| `send_suspend_message` | Publish message when suspending | `false` |
| `suspend_message_template` | Template name for suspend messages | `"default_node_suspend"` |
| `suspend_message_topic` | Topic/queue for suspend messages | `"workflow_events"` |
| `send_resume_message` | Publish message when resuming | `false` |
| `resume_message_template` | Template name for resume messages | `"default_auto_resume"` |
| `resume_message_topic` | Topic/queue for resume messages | `"workflow_events"` |

## Common Use Cases

### Use Case 1: Human Approval Workflow

**Scenario:** Workflow needs human approval before continuing.

**Configuration:**
```yaml
# agentmap_config.yaml
messaging:
  default_provider: "aws"
  providers:
    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"

  message_templates:
    approval_request:
      event_type: "approval_required"
      thread_id: "$thread_id"
      approval_data: "$inputs"
      resume_url: "https://api.example.com/approve/$thread_id"
```

**Workflow CSV:**
```csv
graph_name,node_name,agent_type,context
ApprovalFlow,request_approval,suspend,"{""send_suspend_message"": true, ""suspend_message_template"": ""approval_request"", ""suspend_message_topic"": ""approvals""}"
```

**Flow:**
1. Workflow suspends at `request_approval`
2. Message published to SNS `approvals` topic
3. Approval service receives message
4. Human reviews and approves
5. Service calls AgentMap resume API
6. Workflow continues with approval data

### Use Case 2: Serverless Sub-Workflow

**Scenario:** Trigger a serverless function to run a sub-workflow asynchronously.

**Configuration:**
```yaml
messaging:
  default_provider: "gcp"
  providers:
    gcp:
      enabled: true
      project_id: "my-project"

  message_templates:
    lambda_trigger:
      event_type: "workflow_graph_trigger"
      graph: "$graph"
      state: "$inputs"  # For serverless execution
      thread_id: "$thread_id"
```

**Workflow CSV:**
```csv
graph_name,node_name,agent_type,context
MainWorkflow,trigger_processing,suspend,"{""send_graph_message"": true, ""graph_message_template"": ""lambda_trigger"", ""graph_message_topic"": ""serverless_triggers""}"
```

**Flow:**
1. Workflow suspends at `trigger_processing`
2. Graph message published to Pub/Sub
3. Cloud Function consumes message
4. Function executes sub-workflow using `state` data
5. Function calls resume API when complete
6. Main workflow continues

### Use Case 3: API Callback Pattern

**Scenario:** Wait for external API to process data and call back.

**Configuration:**
```yaml
messaging:
  default_provider: "local"  # For development
  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"
```

**Workflow CSV:**
```csv
graph_name,node_name,agent_type,prompt,context
ApiFlow,wait_callback,suspend,Waiting for API callback,"{""send_suspend_message"": true, ""suspend_message_topic"": ""api_callbacks""}"
```

**Flow:**
1. Workflow suspends at `wait_callback`
2. Message published with thread_id
3. External API retrieves thread_id from message
4. API processes data asynchronously
5. API calls `/resume/{thread_id}` with results
6. Workflow receives results and continues

### Use Case 4: Multi-Environment Development

**Scenario:** Use local messaging in development, cloud in production.

**Configuration:**
```yaml
messaging:
  # Override default_provider with environment variable
  default_provider: "local"  # Development default

  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"

    aws:
      enabled: true
      region_name: "us-east-1"
      service_type: "sns"
      # Only used when explicitly selected or in production
```

**Usage:**
```bash
# Development - uses local provider
poetry run AgentMap run workflow::main

# Production - override provider via environment
export AGENTMAP_MESSAGING_PROVIDER=aws
poetry run AgentMap run workflow::main
```

## Retry Configuration

Configure how AgentMap handles message publishing failures:

```yaml
messaging:
  retry_policy:
    max_retries: 3               # Maximum retry attempts
    backoff_seconds: [1, 2, 4]   # Wait time between retries (exponential)
```

**How It Works:**
- Attempt 1 fails → Wait 1 second → Retry
- Attempt 2 fails → Wait 2 seconds → Retry
- Attempt 3 fails → Wait 4 seconds → Final retry
- All retries fail → Log error (workflow continues)

:::info Retry Behavior
Message publishing failures are logged but **do not stop workflow execution**. Workflows will suspend/resume correctly even if messaging fails.
:::

## Troubleshooting

### Messages Not Being Published

**Symptoms:** SuspendAgent suspends but no messages appear

**Solutions:**

1. **Check provider configuration:**
   ```bash
   # Verify provider is enabled and configured
   cat agentmap_config.yaml | grep -A 10 "messaging:"
   ```

2. **Verify context configuration:**
   ```csv
   # Ensure send_*_message is true
   context,"{""send_suspend_message"": true, ...}"
   ```

3. **Check logs for errors:**
   ```bash
   # Look for messaging service errors
   poetry run AgentMap run workflow::main --log-level DEBUG
   ```

4. **Verify provider dependencies:**
   ```bash
   # For AWS
   pip show boto3

   # For GCP
   pip show google-cloud-pubsub

   # For Azure
   pip show azure-servicebus
   ```

### Authentication Failures

**Symptoms:** "Authentication failed" or "Unable to connect" errors

**AWS Solutions:**
```bash
# Verify credentials are set
aws sts get-caller-identity

# Check AWS profile
cat ~/.aws/credentials

# Test with AWS CLI
aws sns list-topics --region us-east-1
```

**GCP Solutions:**
```bash
# Verify credentials
gcloud auth application-default print-access-token

# Check service account
cat $GCP_SERVICE_ACCOUNT_FILE

# Test with gcloud
gcloud pubsub topics list --project=my-project
```

**Azure Solutions:**
```bash
# Verify connection string format
echo $AZURE_SERVICEBUS_CONNECTION_STRING

# Test with Azure CLI
az servicebus namespace list
```

### Template Variables Not Substituting

**Symptoms:** Messages contain literal `$variable_name` instead of values

**Causes & Solutions:**

1. **Wrong template syntax:**
   ```yaml
   # ❌ Wrong - using {{variable}}
   template: "{{thread_id}}"

   # ✅ Correct - using $variable
   template: "$thread_id"
   ```

2. **Variable not available in context:**
   ```yaml
   # ❌ Wrong - $custom_field not provided
   template: "$custom_field"

   # ✅ Correct - use available variables
   template: "$inputs"
   ```

3. **Check template is being applied:**
   ```csv
   # Ensure template name matches configuration
   context,"{""suspend_message_template"": ""default_node_suspend""}"
   ```

### Local Messages Not Appearing

**Symptoms:** Using local provider but no files created

**Solutions:**

1. **Check storage path exists:**
   ```bash
   mkdir -p agentmap_data/messages
   ```

2. **Verify permissions:**
   ```bash
   ls -ld agentmap_data/messages
   # Should be writable
   ```

3. **Check configuration:**
   ```yaml
   messaging:
     providers:
       local:
         storage_path: "agentmap_data/messages"  # Correct path
   ```

### Provider Not Available

**Symptoms:** "No adapter available for provider" error

**Solutions:**

1. **Install required package:**
   ```bash
   # AWS
   pip install boto3

   # GCP
   pip install google-cloud-pubsub

   # Azure
   pip install azure-servicebus
   ```

2. **Verify installation:**
   ```bash
   python -c "import boto3; print('AWS available')"
   python -c "import google.cloud.pubsub_v1; print('GCP available')"
   python -c "import azure.servicebus; print('Azure available')"
   ```

3. **Check enabled flag:**
   ```yaml
   messaging:
     providers:
       aws:
         enabled: true  # Must be true
   ```

## Best Practices

### 1. Use Local Provider for Development

Always test messaging patterns locally before deploying to cloud:

```yaml
# Development config
messaging:
  default_provider: "local"
  providers:
    local:
      enabled: true
      storage_path: "agentmap_data/messages"
```

Benefits:
- No cloud costs during development
- Easy to inspect and debug messages
- Fast iteration without network delays

### 2. Separate Topics by Purpose

Use different topics for different types of events:

```csv
# Approval events
context,"{""suspend_message_topic"": ""approvals""}"

# Monitoring events
context,"{""suspend_message_topic"": ""monitoring""}"

# Serverless triggers
context,"{""graph_message_topic"": ""serverless_triggers""}"
```

### 3. Include Correlation IDs

Always use thread_id for correlating messages with workflows:

```yaml
message_templates:
  custom_template:
    correlation_id: "$thread_id"  # Essential for matching responses
    workflow: "$workflow"
    timestamp: "$timestamp"
```

### 4. Use Descriptive Template Names

Name templates after their purpose, not their structure:

```yaml
message_templates:
  approval_request:      # ✅ Clear purpose
    ...
  notification_alert:    # ✅ Clear purpose
    ...
  template_1:            # ❌ Unclear purpose
    ...
```

### 5. Configure Appropriate Retry Policies

Balance reliability with performance:

```yaml
# For critical messages
retry_policy:
  max_retries: 5
  backoff_seconds: [1, 2, 4, 8, 16]

# For non-critical notifications
retry_policy:
  max_retries: 2
  backoff_seconds: [1, 2]
```

### 6. Document Your Message Formats

When creating custom templates, document the expected format for consumers:

```yaml
# Custom approval template
# Consumer: Approval Lambda function (approval-processor)
# Expected response: POST /resume/{thread_id} with {"action": "approve"|"reject"}
message_templates:
  approval_request:
    thread_id: "$thread_id"
    approval_type: "$inputs.type"
    resume_endpoint: "https://api.example.com/resume/$thread_id"
```

### 7. Monitor Message Publishing

Enable appropriate logging to track message publishing:

```yaml
logging:
  root:
    level: INFO  # Will log successful message publishing
```

Look for log messages:
```
[INFO] Published suspension message for thread abc-123
[INFO] Published graph message for thread abc-123
```

## Next Steps

Now that you have messaging configured:

1. **Create workflows with SuspendAgent** - Use messaging to coordinate with external systems
2. **Set up serverless handlers** - Deploy functions to consume messages and trigger workflows
3. **Configure monitoring** - Track message publishing and workflow coordination
4. **Build approval workflows** - Implement human-in-the-loop patterns
5. **Test locally first** - Use local provider to validate your messaging patterns

### Related Documentation

- [SuspendAgent Guide](/docs/agents/suspend-agent) - How to use suspension and messaging in workflows
- [Serverless Deployment](/docs/deployment/serverless) - Deploy message-driven workflows
- [HTTP API Reference](/docs/http-api/reference) - Resume endpoints for callbacks
- [Environment Variables](/docs/configuration/environment-variables) - Secure credential management
