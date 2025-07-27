---
title: Advanced Error Handling
sidebar_position: 15
description: Comprehensive guide to AgentMap's advanced error handling, resume functionality, and error recovery patterns
keywords: [error handling, resume, exceptions, recovery, thread management, workflow interruption]
---

# Advanced Error Handling

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <a href="/docs/guides/development">Development</a> → <strong>Error Handling</strong></span>
</div>

AgentMap provides sophisticated error handling capabilities including workflow resumption, thread management, exception hierarchies, and human-in-the-loop error recovery. This guide covers the complete error handling architecture and best practices for building resilient workflows.

## Error Handling Architecture

### Core Components

AgentMap's error handling system consists of several integrated components:

1. **Exception Hierarchy**: Structured exception classes for different error domains
2. **Thread Management**: Execution threads with state persistence and resumption
3. **Human Interaction System**: Human-in-the-loop workflows for complex error scenarios
4. **Storage-Backed Recovery**: Persistent state management for workflow interruption/resumption
5. **CLI Resume Commands**: Command-line interface for workflow management

### Exception Hierarchy

AgentMap implements a comprehensive exception hierarchy for different error domains:

```python
# Base exception for all AgentMap errors
from agentmap.exceptions.base_exceptions import AgentMapException, ConfigurationException

# Service-specific exceptions
from agentmap.exceptions.service_exceptions import (
    LLMServiceError,
    LLMProviderError,
    LLMConfigurationError,
    LLMDependencyError,
    StorageConfigurationNotAvailableException,
    LoggingNotConfiguredException,
    FunctionResolutionException
)

# Agent-specific exceptions
from agentmap.exceptions.agent_exceptions import AgentError, AgentExecutionError

# Graph execution exceptions
from agentmap.exceptions.graph_exceptions import GraphExecutionError, NodeResolutionError

# Storage exceptions
from agentmap.exceptions.storage_exceptions import StorageError, StorageConnectionError

# Validation exceptions
from agentmap.exceptions.validation_exceptions import ValidationError, SchemaValidationError
```

### Exception Categories

**Configuration Exceptions**
- Missing or invalid configuration files
- Incorrect service configuration
- API key and authentication errors

**Service Exceptions**
- LLM provider connection failures
- Storage service errors
- Dependency resolution problems

**Agent Exceptions**
- Custom agent execution failures
- Agent resolution errors
- Service injection problems

**Graph Exceptions**
- Workflow execution errors
- Node resolution failures
- State transition problems

**Storage Exceptions**
- Database connection issues
- File system access problems
- Data persistence failures

**Validation Exceptions**
- CSV schema validation errors
- Configuration validation problems
- Input/output validation failures

## Thread-Based Error Recovery

### Execution Thread Model

AgentMap uses an execution thread model that supports workflow interruption and resumption:

```python
from agentmap.models.execution_thread import ExecutionThread
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

@dataclass
class ExecutionThread:
    \"\"\"Represents a workflow execution thread that can be paused and resumed.\"\"\"
    
    id: str = ""
    graph_name: str = ""
    status: str = ""  # 'running', 'paused', 'completed', 'failed', 'resuming'
    current_node: str = ""
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    execution_tracker_data: Dict[str, Any] = field(default_factory=dict)
    interaction_request_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

### Thread Status Management

**Thread Statuses:**
- `running`: Thread is actively executing
- `paused`: Thread paused for human interaction or error handling
- `completed`: Thread completed successfully
- `failed`: Thread failed with unrecoverable error
- `resuming`: Thread being resumed after intervention

### State Persistence

Execution threads maintain complete state snapshots including:
- Current execution context
- Variable values at interruption point
- Node execution history
- Error context and recovery information

## Human-in-the-Loop Error Handling

### Interaction Types

AgentMap supports multiple types of human interactions for error recovery:

```python
from agentmap.models.human_interaction import InteractionType

class InteractionType(Enum):
    \"\"\"Types of human interactions supported by the system.\"\"\"
    
    APPROVAL = "approval"        # Simple approve/reject decisions
    EDIT = "edit"               # Content editing and correction
    CHOICE = "choice"           # Multiple choice selections
    TEXT_INPUT = "text_input"   # Free-form text input
    CONVERSATION = "conversation"  # Extended dialog interactions
```

### Interaction Request Model

```python
from agentmap.models.human_interaction import HumanInteractionRequest

@dataclass
class HumanInteractionRequest:
    \"\"\"Represents a request for human interaction in a workflow.\"\"\"
    
    id: UUID = field(default_factory=uuid4)
    thread_id: str = ""
    node_name: str = ""
    interaction_type: InteractionType = InteractionType.TEXT_INPUT
    prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)  # For choice interactions
    timeout_seconds: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
```

### Interaction Response Model

```python
from agentmap.models.human_interaction import HumanInteractionResponse

@dataclass
class HumanInteractionResponse:
    \"\"\"Represents a human's response to an interaction request.\"\"\"
    
    request_id: UUID
    action: str = ""  # 'approve', 'reject', 'choose', 'respond', 'edit'
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

## Resume Command System

### CLI Resume Interface

AgentMap provides a comprehensive CLI interface for resuming interrupted workflows:

```bash
# Basic resume syntax
agentmap resume <thread_id> <action> [OPTIONS]

# Resume with data
agentmap resume <thread_id> <action> --data '<json>'

# Resume with data file
agentmap resume <thread_id> <action> --data-file <file>
```

### Resume Actions

**Approval Actions**
```bash
# Approve pending action
agentmap resume thread_12345 approve

# Reject with reason
agentmap resume thread_12345 reject --data '{"reason": "Budget exceeded"}'
```

**Choice Actions**
```bash
# Select from multiple options
agentmap resume thread_12345 choose --data '{"choice": 1}'

# Choose with context
agentmap resume thread_12345 choose --data '{"choice": "option_b", "notes": "Best performance"}'
```

**Text Response Actions**
```bash
# Provide text response
agentmap resume thread_12345 respond --data '{"text": "Proceed with implementation"}'

# Structured response
agentmap resume thread_12345 respond --data '{
  "response": "Approved with modifications",
  "modifications": ["Add error handling", "Include tests"]
}'
```

**Edit Actions**
```bash
# Edit content
agentmap resume thread_12345 edit --data '{"edited": "Corrected content here"}'

# Edit with metadata
agentmap resume thread_12345 edit --data '{
  "edited": "New content",
  "format": "markdown",
  "reason": "Improved clarity"
}'
```

### Resume Workflow

1. **Thread ID Generation**: Interrupted workflows generate unique thread IDs
2. **State Persistence**: Complete execution state saved to storage
3. **Human Notification**: Interaction request displayed via CLI
4. **Response Collection**: Human provides response via resume command
5. **State Restoration**: Thread state restored from storage
6. **Execution Continuation**: Workflow continues with response data

## Error Recovery Patterns

### Pattern 1: Automatic Retry with Exponential Backoff

```python
import time
from agentmap.exceptions.service_exceptions import LLMServiceError

class ResilientAgent(BaseAgent):
    def process(self, inputs, max_retries=3):
        for attempt in range(max_retries):
            try:
                # Your processing logic here
                result = self.call_external_service(inputs)
                return result
            except LLMServiceError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"All {max_retries} attempts failed: {e}")
                    raise
```

### Pattern 2: Graceful Degradation

```python
from agentmap.exceptions.service_exceptions import LLMProviderError

class GracefulAgent(BaseAgent):
    def process(self, inputs):
        try:
            # Try primary service
            return self.primary_service.process(inputs)
        except LLMProviderError:
            self.logger.warning("Primary service failed, falling back to secondary")
            try:
                # Fall back to secondary service
                return self.secondary_service.process(inputs)
            except LLMProviderError:
                self.logger.warning("Secondary service failed, using default response")
                # Return safe default
                return {"status": "unavailable", "message": "Service temporarily unavailable"}
```

### Pattern 3: Human-in-the-Loop Error Resolution

```python
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType

class InteractiveAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.interaction_handler = CLIInteractionHandler(self.storage_service)
    
    def process(self, inputs):
        try:
            # Attempt automated processing
            return self.automated_process(inputs)
        except ValidationError as e:
            # Request human intervention for validation errors
            request = HumanInteractionRequest(
                thread_id=self.execution_context.thread_id,
                node_name=self.node_name,
                interaction_type=InteractionType.EDIT,
                prompt=f"Validation failed: {e}. Please correct the input.",
                context={"original_input": inputs, "error": str(e)}
            )
            
            # Display request and pause execution
            self.interaction_handler.display_interaction_request(request)
            
            # This would pause execution until resume command is called
            # Implementation depends on graph execution service
            return self.wait_for_human_response(request)
```

### Pattern 4: Circuit Breaker Pattern

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreakerAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = 5
        self.timeout = 60  # seconds
        self.last_failure_time = 0
    
    def process(self, inputs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.logger.info("Circuit breaker moving to half-open state")
            else:
                raise LLMServiceError("Circuit breaker is open")
        
        try:
            result = self.call_external_service(inputs)
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.logger.info("Circuit breaker closed - service recovered")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise
```

## Error Handling Best Practices

### 1. Exception Design

**Use Specific Exceptions**
```python
# Good - specific exception
from agentmap.exceptions.service_exceptions import LLMConfigurationError
raise LLMConfigurationError("OpenAI API key not configured")

# Avoid - generic exception
raise Exception("Configuration error")
```

**Include Context Information**
```python
# Good - detailed context
from agentmap.exceptions.agent_exceptions import AgentExecutionError
raise AgentExecutionError(
    f"Agent '{self.agent_name}' failed to process inputs: {inputs}",
    details={"node": self.node_name, "inputs": inputs, "agent_type": self.agent_type}
)
```

**Chain Exceptions Appropriately**
```python
try:
    result = external_service.call()
except ExternalServiceError as e:
    raise LLMServiceError(f"External service call failed: {e}") from e
```

### 2. Logging and Monitoring

**Structured Logging**
```python
import logging
from agentmap.services.logging_service import LoggingService

class ErrorAwareAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"agentmap.agents.{self.__class__.__name__}")
    
    def process(self, inputs):
        self.logger.info("Starting processing", extra={
            "agent": self.agent_name,
            "node": self.node_name,
            "input_keys": list(inputs.keys())
        })
        
        try:
            result = self.do_processing(inputs)
            self.logger.info("Processing completed successfully", extra={
                "agent": self.agent_name,
                "output_keys": list(result.keys()) if isinstance(result, dict) else None
            })
            return result
        except Exception as e:
            self.logger.error("Processing failed", extra={
                "agent": self.agent_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "inputs": inputs
            }, exc_info=True)
            raise
```

### 3. Timeout Handling

**Request Timeouts**
```python
import asyncio
from agentmap.exceptions.service_exceptions import LLMServiceError

class TimeoutAgent(BaseAgent):
    async def process_with_timeout(self, inputs, timeout=30):
        try:
            return await asyncio.wait_for(
                self.async_process(inputs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise LLMServiceError(f"Processing timed out after {timeout} seconds")
```

### 4. Resource Cleanup

**Context Managers for Resources**
```python
from contextlib import contextmanager
from agentmap.exceptions.storage_exceptions import StorageConnectionError

class ResourceAgent(BaseAgent):
    @contextmanager
    def database_connection(self):
        conn = None
        try:
            conn = self.get_database_connection()
            yield conn
        except Exception as e:
            raise StorageConnectionError(f"Database connection failed: {e}")
        finally:
            if conn:
                conn.close()
    
    def process(self, inputs):
        with self.database_connection() as conn:
            # Use connection safely
            return self.query_database(conn, inputs)
```

### 5. Error Reporting and Alerts

**Error Context Collection**
```python
class DiagnosticAgent(BaseAgent):
    def collect_error_context(self, error: Exception) -> dict:
        return {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "agent_name": self.agent_name,
            "node_name": self.node_name,
            "thread_id": getattr(self.execution_context, 'thread_id', None),
            "timestamp": datetime.utcnow().isoformat(),
            "system_info": {
                "python_version": sys.version,
                "agentmap_version": self.get_agentmap_version(),
                "memory_usage": self.get_memory_usage()
            }
        }
    
    def handle_error(self, error: Exception):
        context = self.collect_error_context(error)
        
        # Log detailed error context
        self.logger.error("Agent execution failed", extra=context)
        
        # Send alert for critical errors
        if isinstance(error, (LLMServiceError, StorageConnectionError)):
            self.send_alert(context)
        
        # Store error for analysis
        self.store_error_report(context)
```

## Production Error Handling

### Error Monitoring Setup

**Health Check Integration**
```python
# Include error metrics in health checks
from agentmap.core.cli.diagnostic_commands import diagnose_command

def health_check_with_error_tracking():
    try:
        # Run diagnostics
        diagnostic_data = diagnose_command()
        
        # Check for recent errors
        error_count = get_recent_error_count(hours=1)
        critical_errors = get_critical_errors(hours=24)
        
        return {
            "status": "healthy" if error_count < 10 else "degraded",
            "error_count_1h": error_count,
            "critical_errors_24h": len(critical_errors),
            "diagnostic_status": diagnostic_data
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

**Error Alerting**
```python
# Set up error alerting
class ErrorAlertManager:
    def __init__(self, slack_webhook=None, email_config=None):
        self.slack_webhook = slack_webhook
        self.email_config = email_config
    
    def alert_on_error(self, error_context: dict):
        severity = self.determine_severity(error_context)
        
        if severity == "critical":
            self.send_immediate_alert(error_context)
        elif severity == "warning":
            self.queue_alert_summary(error_context)
    
    def determine_severity(self, error_context: dict) -> str:
        error_type = error_context.get("error_type", "")
        
        critical_errors = [
            "LLMServiceError",
            "StorageConnectionError", 
            "ConfigurationException"
        ]
        
        if error_type in critical_errors:
            return "critical"
        else:
            return "warning"
```

### Error Recovery Automation

**Automatic Recovery Scripts**
```bash
#!/bin/bash
# auto_recovery.sh - Automatic error recovery

LOG_FILE="/var/log/agentmap/auto_recovery.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting automatic error recovery..." >> "$LOG_FILE"

# Check for failed threads
failed_threads=$(agentmap threads --status failed --format json | jq -r '.[].id')

for thread_id in $failed_threads; do
    echo "[$TIMESTAMP] Processing failed thread: $thread_id" >> "$LOG_FILE"
    
    # Get thread details
    thread_info=$(agentmap thread-info "$thread_id" --format json)
    error_type=$(echo "$thread_info" | jq -r '.error.type')
    
    case "$error_type" in
        "LLMServiceError")
            echo "[$TIMESTAMP] Retrying LLM service error for thread $thread_id" >> "$LOG_FILE"
            agentmap retry-thread "$thread_id" --max-attempts 3
            ;;
        "ValidationError")
            echo "[$TIMESTAMP] Requesting human intervention for thread $thread_id" >> "$LOG_FILE"
            agentmap request-intervention "$thread_id" --type validation
            ;;
        *)
            echo "[$TIMESTAMP] Unknown error type for thread $thread_id: $error_type" >> "$LOG_FILE"
            ;;
    esac
done

echo "[$TIMESTAMP] Automatic error recovery completed" >> "$LOG_FILE"
```

## Testing Error Handling

### Unit Testing Exceptions

```python
import pytest
from agentmap.exceptions.service_exceptions import LLMServiceError
from agentmap.agents.your_agent import YourAgent

class TestYourAgent:
    def test_handles_llm_service_error(self):
        agent = YourAgent()
        
        # Mock the LLM service to raise an error
        with patch.object(agent, 'llm_service') as mock_llm:
            mock_llm.call_llm.side_effect = LLMServiceError("API rate limit exceeded")
            
            # Verify the agent handles the error appropriately
            with pytest.raises(LLMServiceError):
                agent.process({"input": "test"})
            
            # Verify retry logic was attempted
            assert mock_llm.call_llm.call_count == 3  # Assuming 3 retries
    
    def test_graceful_degradation(self):
        agent = YourAgent()
        
        # Mock primary service failure
        with patch.object(agent, 'primary_service') as mock_primary, \
             patch.object(agent, 'fallback_service') as mock_fallback:
            
            mock_primary.process.side_effect = LLMServiceError("Primary service down")
            mock_fallback.process.return_value = {"status": "fallback_used"}
            
            result = agent.process({"input": "test"})
            
            assert result["status"] == "fallback_used"
            assert mock_fallback.process.called
```

### Integration Testing Resume Functionality

```python
import pytest
from agentmap.testing.test_helpers import create_test_thread, create_test_interaction

class TestResumeWorkflow:
    def test_resume_with_approval(self):
        # Create a paused thread
        thread_id = create_test_thread(
            graph_name="TestGraph",
            status="paused",
            current_node="approval_node"
        )
        
        # Create interaction request
        interaction_id = create_test_interaction(
            thread_id=thread_id,
            interaction_type=InteractionType.APPROVAL,
            prompt="Approve this action?"
        )
        
        # Resume with approval
        response = self.cli_handler.resume_execution(
            thread_id=thread_id,
            response_action="approve",
            response_data={}
        )
        
        assert response.action == "approve"
        
        # Verify thread status updated
        thread = self.get_thread(thread_id)
        assert thread.status == "resuming"
    
    def test_resume_with_invalid_thread(self):
        with pytest.raises(ValueError, match="Thread 'invalid_id' not found"):
            self.cli_handler.resume_execution(
                thread_id="invalid_id",
                response_action="approve"
            )
```

## Related Documentation

### 🔧 **Error Handling Tools**
- **[CLI Resume Commands](/docs/deployment/cli-resume)**: Command-line workflow resumption
- **[Diagnostic Commands](/docs/deployment/cli-diagnostics)**: System health and error diagnosis
- **[Troubleshooting Guide](/docs/guides/troubleshooting)**: Step-by-step error resolution

### 🏗️ **Development Guides**
- **[Human Interaction Workflows](/docs/guides/development/human-interaction)**: Human-in-the-loop patterns
- **[Testing Patterns](/docs/guides/development/testing)**: Testing error handling logic
- **[Service Integration](/docs/guides/development/service-integration)**: Robust service integration

### 🚀 **Production Operations**
- **[System Health Monitoring](/docs/guides/system-health)**: Production monitoring setup
- **[Dependency Management](/docs/guides/dependency-management)**: Dependency error handling
- **[Configuration Reference](/docs/reference/configuration/)**: Error-prone configuration areas
