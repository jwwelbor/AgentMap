---
title: Human Interaction Workflows
sidebar_position: 16
description: Guide to implementing human-in-the-loop workflows, interaction patterns, and workflow pause/resume functionality
keywords: [human-in-the-loop, interaction, workflow pause, resume, thread management, CLI interaction]
---

# Human Interaction Workflows

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <a href="/docs/guides/development">Development</a> → <strong>Human Interaction</strong></span>
</div>

AgentMap provides sophisticated human-in-the-loop (HITL) capabilities that allow workflows to pause execution, request human input, and resume with the provided response. This guide covers the complete human interaction system including interaction types, workflow design patterns, and implementation best practices.

## Human Interaction System Overview

### Core Components

The human interaction system consists of:

1. **Interaction Types**: Five types of human interactions (approval, edit, choice, text input, conversation)
2. **Thread Management**: Execution threads that can pause and resume
3. **CLI Interface**: Command-line interface for human responses
4. **Storage Backend**: Persistent storage for interaction state
5. **Resume Functionality**: Complete workflow resumption capabilities

### Interaction Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Workflow      │    │  Human           │    │  Resume         │
│   Execution     │───▶│  Interaction     │───▶│  Execution      │
│                 │    │  Request         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       ▲
         │              ┌──────────────────┐             │
         │              │  CLI Handler     │             │
         │              │  - Display       │             │
         │              │  - Collect       │             │
         │              │  - Validate      │             │
         │              └──────────────────┘             │
         │                       │                       │
         │              ┌──────────────────┐             │
         │              │  Storage         │             │
         │              │  - Persist       │             │
         │              │  - Retrieve      │             │
         │              │  - Manage        │             │
         │              └──────────────────┘             │
         │                                                │
         └────────────────────────────────────────────────┘
```

## Interaction Types

### 1. Approval Interactions

Used for simple approve/reject decisions:

```python
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType

# Create approval interaction
approval_request = HumanInteractionRequest(
    thread_id="thread_12345",
    node_name="approval_gate",
    interaction_type=InteractionType.APPROVAL,
    prompt="Please review and approve this budget proposal.",
    context={
        "proposal_amount": 50000,
        "department": "Engineering",
        "quarter": "Q1 2024"
    }
)
```

**CLI Resume Commands:**
```bash
# Approve the request
agentmap resume thread_12345 approve

# Reject with reason
agentmap resume thread_12345 reject --data '{"reason": "Budget exceeds allocated amount"}'
```

### 2. Edit Interactions

Used for content editing and correction:

```python
# Create edit interaction
edit_request = HumanInteractionRequest(
    thread_id="thread_12345",
    node_name="content_editor",
    interaction_type=InteractionType.EDIT,
    prompt="Please review and edit this generated content for clarity and accuracy.",
    context={
        "original_content": "The system has detected an anomaly in the data processing pipeline...",
        "content_type": "alert_message",
        "target_audience": "technical_team"
    }
)
```

**CLI Resume Commands:**
```bash
# Edit content
agentmap resume thread_12345 edit --data '{
  "edited": "The data processing pipeline has detected an anomaly that requires immediate attention...",
  "changes": ["Added urgency indicator", "Clarified technical details"]
}'
```

### 3. Choice Interactions

Used for multiple choice selections:

```python
# Create choice interaction
choice_request = HumanInteractionRequest(
    thread_id="thread_12345",
    node_name="deployment_selector",
    interaction_type=InteractionType.CHOICE,
    prompt="Select the deployment environment for this application:",
    options=[
        "Production (us-east-1)",
        "Staging (us-west-2)", 
        "Development (local)",
        "Cancel deployment"
    ],
    context={
        "application": "payment_service",
        "version": "v2.1.0",
        "urgency": "high"
    }
)
```

**CLI Resume Commands:**
```bash
# Choose by option number
agentmap resume thread_12345 choose --data '{"choice": 1}'

# Choose with justification
agentmap resume thread_12345 choose --data '{
  "choice": 2,
  "justification": "Staging first for additional testing due to payment system criticality"
}'
```

### 4. Text Input Interactions

Used for free-form text responses:

```python
# Create text input interaction
text_request = HumanInteractionRequest(
    thread_id="thread_12345",
    node_name="requirements_gatherer",
    interaction_type=InteractionType.TEXT_INPUT,
    prompt="Please provide additional requirements for this feature:",
    context={
        "feature_name": "User Authentication",
        "current_requirements": ["OAuth 2.0", "Multi-factor auth"],
        "deadline": "2024-03-15"
    }
)
```

**CLI Resume Commands:**
```bash
# Provide text response
agentmap resume thread_12345 respond --data '{
  "text": "Add support for social login providers (Google, GitHub, Microsoft). Include rate limiting for login attempts and password strength validation."
}'

# Structured text response
agentmap resume thread_12345 respond --data '{
  "response": "Additional security requirements needed",
  "requirements": [
    "Social login integration",
    "Rate limiting",
    "Password strength validation",
    "Session management"
  ],
  "priority": "high"
}'
```

### 5. Conversation Interactions

Used for extended dialog interactions:

```python
# Create conversation interaction
conversation_request = HumanInteractionRequest(
    thread_id="thread_12345",
    node_name="technical_consultant",
    interaction_type=InteractionType.CONVERSATION,
    prompt="Let's discuss the technical architecture for this project. What are your thoughts on the proposed microservices approach?",
    context={
        "project": "E-commerce Platform",
        "current_architecture": "monolithic",
        "team_size": 8,
        "timeline": "6 months"
    }
)
```

**CLI Resume Commands:**
```bash
# Continue conversation
agentmap resume thread_12345 respond --data '{
  "message": "I think microservices would benefit this project given the team size and timeline. We should consider starting with a few core services: user management, product catalog, and order processing.",
  "follow_up_questions": [
    "What database strategy should we use?",
    "How do we handle inter-service communication?"
  ]
}'
```

## Workflow Design Patterns

### Pattern 1: Approval Gates

Use approval interactions at critical decision points:

```csv
graph_name,node_name,agent_type,next_on_success,next_on_failure,prompt,input_fields,output_field,context
ApprovalFlow,start,input,validate,,,user_request,request_data,
ApprovalFlow,validate,validation_agent,approve_gate,reject,Validate request,request_data,validation_result,
ApprovalFlow,approve_gate,approval_interaction,process,end,Please approve this request: {validation_result},validation_result,approval_response,"{""interaction_type"": ""approval""}"
ApprovalFlow,process,processing_agent,end,,Process approved request,request_data,final_result,
ApprovalFlow,reject,output,,,Request rejected due to validation failure,validation_result,rejection_message,
ApprovalFlow,end,output,,,Request completed: {final_result},final_result,completion_message,
```

### Pattern 2: Content Review and Edit

Use edit interactions for content quality assurance:

```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field,context
ContentFlow,start,input,generate,,content_request,request_details,
ContentFlow,generate,content_generator,review,Generate content based on: {request_details},request_details,generated_content,
ContentFlow,review,edit_interaction,finalize,Please review and edit this content: {generated_content},generated_content,edited_content,"{""interaction_type"": ""edit""}"
ContentFlow,finalize,output,,Content finalized: {edited_content},edited_content,final_content,
```

### Pattern 3: Multi-Step Decision Making

Use choice interactions for complex decision trees:

```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field,context
DecisionFlow,start,input,analyze,,problem_description,problem_data,
DecisionFlow,analyze,analysis_agent,choose_approach,Analyze problem: {problem_description},problem_data,analysis_result,
DecisionFlow,choose_approach,choice_interaction,implement,Choose implementation approach,analysis_result,chosen_approach,"{""interaction_type"": ""choice"", ""options"": [""Approach A: Fast implementation"", ""Approach B: Robust solution"", ""Approach C: Hybrid approach""]}"
DecisionFlow,implement,implementation_agent,end,Implement chosen approach: {chosen_approach},chosen_approach,implementation_result,
DecisionFlow,end,output,,Implementation completed: {implementation_result},implementation_result,final_message,
```

### Pattern 4: Requirements Gathering

Use text input interactions for collecting detailed information:

```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field,context
RequirementsFlow,start,input,initial_analysis,,project_brief,project_data,
RequirementsFlow,initial_analysis,analysis_agent,gather_requirements,Analyze project brief: {project_brief},project_data,initial_analysis,
RequirementsFlow,gather_requirements,text_input_interaction,refine,Based on the analysis please provide additional requirements: {initial_analysis},initial_analysis,additional_requirements,"{""interaction_type"": ""text_input""}"
RequirementsFlow,refine,refinement_agent,end,Refine requirements: {additional_requirements},additional_requirements,final_requirements,
RequirementsFlow,end,output,,Requirements gathering completed: {final_requirements},final_requirements,requirements_document,
```

### Pattern 5: Iterative Conversation

Use conversation interactions for complex consultations:

```csv
graph_name,node_name,agent_type,next_on_success,next_on_failure,prompt,input_fields,output_field,context
ConsultationFlow,start,input,initial_consultation,,,consultation_topic,topic_data,
ConsultationFlow,initial_consultation,conversation_interaction,continue_conversation,end,Let's discuss your {consultation_topic}. What specific aspects would you like to explore?,topic_data,conversation_response,"{""interaction_type"": ""conversation""}"
ConsultationFlow,continue_conversation,conversation_agent,next_question,summary,Continue conversation: {conversation_response},conversation_response,next_topic,
ConsultationFlow,next_question,conversation_interaction,continue_conversation,summary,Great insights! Let's dive deeper into {next_topic},next_topic,follow_up_response,"{""interaction_type"": ""conversation""}"
ConsultationFlow,summary,summary_agent,end,,Summarize consultation: {follow_up_response},follow_up_response,consultation_summary,
ConsultationFlow,end,output,,,Consultation completed: {consultation_summary},consultation_summary,final_report,
```

## Implementation Guide

### 1. Creating Interaction Agents

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
from typing import Dict, Any

class ApprovalAgent(BaseAgent):
    \"\"\"Agent that requests human approval before proceeding.\"\"\"
    
    def __init__(self):
        super().__init__()
        self.interaction_handler = None  # Will be injected
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        # Extract data for approval
        approval_data = inputs.get("approval_data", {})
        
        # Create interaction request
        request = HumanInteractionRequest(
            thread_id=self.execution_context.thread_id,
            node_name=self.node_name,
            interaction_type=InteractionType.APPROVAL,
            prompt=f"Please review and approve: {approval_data}",
            context=approval_data,
            timeout_seconds=3600  # 1 hour timeout
        )
        
        # Display interaction request
        if self.interaction_handler:
            self.interaction_handler.display_interaction_request(request)
        
        # Return request ID for tracking
        return {
            "interaction_request_id": str(request.id),
            "status": "pending_approval",
            "message": f"Approval requested. Use: agentmap resume {request.thread_id} approve"
        }
```

### 2. Custom Interaction Handlers

```python
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
from agentmap.models.human_interaction import HumanInteractionResponse
from typing import Optional, Any

class CustomInteractionHandler(CLIInteractionHandler):
    \"\"\"Custom interaction handler with enhanced features.\"\"\"
    
    def __init__(self, storage_service, notification_service=None):
        super().__init__(storage_service)
        self.notification_service = notification_service
    
    def display_interaction_request(self, request: HumanInteractionRequest) -> None:
        # Call parent display method
        super().display_interaction_request(request)
        
        # Send notification if service available
        if self.notification_service:
            self.notification_service.send_notification(
                title=f"Human Input Required: {request.node_name}",
                message=request.prompt,
                thread_id=request.thread_id,
                urgency="normal" if not request.timeout_seconds else "high"
            )
    
    def resume_execution(self, thread_id: str, response_action: str, 
                        response_data: Optional[Any] = None) -> HumanInteractionResponse:
        # Validate response based on interaction type
        self._validate_response(thread_id, response_action, response_data)
        
        # Call parent resume method
        response = super().resume_execution(thread_id, response_action, response_data)
        
        # Log response for audit trail
        self._log_response(response)
        
        return response
    
    def _validate_response(self, thread_id: str, action: str, data: Any) -> None:
        \"\"\"Validate response data based on interaction type.\"\"\"
        # Load interaction request to check type
        thread_data = self.storage_service.read(collection="threads", document_id=thread_id)
        if not thread_data:
            raise ValueError(f"Thread '{thread_id}' not found")
        
        request_id = thread_data.get("pending_interaction_id")
        request_data = self.storage_service.read(
            collection=self.collection_name, 
            document_id=str(request_id)
        )
        
        interaction_type = request_data.get("interaction_type")
        
        # Validate based on type
        if interaction_type == "choice" and action == "choose":
            if not data or "choice" not in data:
                raise ValueError("Choice interaction requires 'choice' in response data")
        elif interaction_type == "edit" and action == "edit":
            if not data or "edited" not in data:
                raise ValueError("Edit interaction requires 'edited' content in response data")
        elif interaction_type == "text_input" and action == "respond":
            if not data or ("text" not in data and "response" not in data):
                raise ValueError("Text input interaction requires 'text' or 'response' in data")
    
    def _log_response(self, response: HumanInteractionResponse) -> None:
        \"\"\"Log response for audit trail.\"\"\"
        audit_entry = {
            "request_id": str(response.request_id),
            "action": response.action,
            "timestamp": response.timestamp.isoformat(),
            "data_keys": list(response.data.keys()) if response.data else []
        }
        
        self.storage_service.write(
            collection="interaction_audit",
            data=audit_entry,
            document_id=f"response_{response.request_id}",
            mode="write"
        )
```

### 3. Timeout Handling

```python
from datetime import datetime, timedelta
from agentmap.models.human_interaction import HumanInteractionRequest

class TimeoutInteractionHandler(CLIInteractionHandler):
    \"\"\"Interaction handler with timeout management.\"\"\"
    
    def check_timeouts(self) -> list:
        \"\"\"Check for timed out interactions and handle them.\"\"\"
        timed_out_interactions = []
        
        # Get all pending interactions
        pending_threads = self.storage_service.list(
            collection="threads",
            filter_criteria={"status": "paused"}
        )
        
        for thread_data in pending_threads:
            request_id = thread_data.get("pending_interaction_id")
            if not request_id:
                continue
            
            # Load interaction request
            request_data = self.storage_service.read(
                collection=self.collection_name,
                document_id=str(request_id)
            )
            
            if not request_data or not request_data.get("timeout_seconds"):
                continue
            
            # Check if timed out
            created_at = datetime.fromisoformat(request_data["created_at"])
            timeout_duration = timedelta(seconds=request_data["timeout_seconds"])
            
            if datetime.utcnow() > created_at + timeout_duration:
                timed_out_interactions.append({
                    "thread_id": thread_data["id"],
                    "request_id": request_id,
                    "timeout_duration": request_data["timeout_seconds"]
                })
                
                # Handle timeout
                self._handle_timeout(thread_data["id"], request_id)
        
        return timed_out_interactions
    
    def _handle_timeout(self, thread_id: str, request_id: str) -> None:
        \"\"\"Handle a timed out interaction.\"\"\"
        # Create default timeout response
        default_response = HumanInteractionResponse(
            request_id=request_id,
            action="timeout",
            data={"reason": "Interaction timed out"}
        )
        
        # Update thread status
        self.storage_service.write(
            collection="threads",
            data={
                "status": "timed_out",
                "pending_interaction_id": None,
                "timeout_response_id": str(request_id)
            },
            document_id=thread_id,
            mode="update"
        )
        
        # Log timeout
        self.logger.warning(f"Interaction {request_id} for thread {thread_id} timed out")
```

## Advanced Features

### Conditional Interactions

```python
class ConditionalInteractionAgent(BaseAgent):
    \"\"\"Agent that conditionally requests human input based on criteria.\"\"\"
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        risk_score = self.calculate_risk_score(inputs)
        
        # Only request human approval for high-risk operations
        if risk_score > 0.8:
            return self.request_approval(inputs, risk_score)
        else:
            return self.auto_approve(inputs)
    
    def calculate_risk_score(self, inputs: Dict[str, Any]) -> float:
        # Example risk calculation
        amount = inputs.get("amount", 0)
        user_tier = inputs.get("user_tier", "basic")
        
        score = 0.0
        if amount > 10000:
            score += 0.5
        if user_tier == "basic":
            score += 0.3
        
        return min(score, 1.0)
    
    def request_approval(self, inputs: Dict[str, Any], risk_score: float) -> Dict[str, Any]:
        request = HumanInteractionRequest(
            thread_id=self.execution_context.thread_id,
            node_name=self.node_name,
            interaction_type=InteractionType.APPROVAL,
            prompt=f"High-risk operation detected (risk score: {risk_score:.2f}). Please review and approve.",
            context={
                "risk_score": risk_score,
                "operation_details": inputs,
                "recommendation": "manual_review_required"
            }
        )
        
        self.interaction_handler.display_interaction_request(request)
        
        return {
            "status": "pending_approval",
            "risk_score": risk_score,
            "interaction_id": str(request.id)
        }
    
    def auto_approve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "auto_approved",
            "operation_result": self.process_operation(inputs)
        }
```

### Batch Interactions

```python
class BatchInteractionAgent(BaseAgent):
    \"\"\"Agent that handles multiple interactions in a batch.\"\"\"
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        items = inputs.get("items", [])
        
        # Process items in batches
        batch_size = 5
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        
        batch_results = []
        
        for batch_num, batch in enumerate(batches):
            request = HumanInteractionRequest(
                thread_id=f"{self.execution_context.thread_id}_batch_{batch_num}",
                node_name=f"{self.node_name}_batch_{batch_num}",
                interaction_type=InteractionType.CHOICE,
                prompt=f"Please review batch {batch_num + 1} of {len(batches)}:",
                options=[
                    "Approve all items in batch",
                    "Review items individually", 
                    "Reject entire batch",
                    "Pause for later review"
                ],
                context={
                    "batch_number": batch_num + 1,
                    "total_batches": len(batches),
                    "batch_items": batch,
                    "items_count": len(batch)
                }
            )
            
            self.interaction_handler.display_interaction_request(request)
            batch_results.append({
                "batch_id": batch_num,
                "status": "pending_review",
                "interaction_id": str(request.id)
            })
        
        return {
            "batch_processing": "initiated",
            "total_batches": len(batches),
            "batch_results": batch_results
        }
```

## Best Practices

### 1. Interaction Design

**Clear and Specific Prompts**
```python
# Good - specific and actionable
prompt = "Please review the deployment plan for the payment service v2.1.0 to production. Check the rollback strategy and database migration scripts."

# Avoid - vague and unclear
prompt = "Please review this."
```

**Provide Sufficient Context**
```python
context = {
    "service_name": "payment_service",
    "version": "v2.1.0",
    "environment": "production",
    "deployment_time": "2024-03-15T14:00:00Z",
    "rollback_strategy": "blue_green",
    "database_changes": True,
    "risk_level": "medium",
    "estimated_downtime": "5 minutes"
}
```

**Set Appropriate Timeouts**
```python
# Different timeouts for different interaction types
approval_timeout = 24 * 3600      # 24 hours for approvals
edit_timeout = 2 * 3600           # 2 hours for content editing
choice_timeout = 30 * 60          # 30 minutes for simple choices
conversation_timeout = None        # No timeout for conversations
```

### 2. Error Handling in Interactions

```python
class RobustInteractionAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        try:
            return self.create_interaction(inputs)
        except Exception as e:
            self.logger.error(f"Failed to create interaction: {e}")
            
            # Fallback to automated processing
            self.logger.info("Falling back to automated processing")
            return self.automated_fallback(inputs)
    
    def create_interaction(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Validate inputs before creating interaction
        if not self.validate_inputs(inputs):
            raise ValueError("Invalid inputs for interaction")
        
        # Create and display interaction
        request = self.build_interaction_request(inputs)
        self.interaction_handler.display_interaction_request(request)
        
        return {"status": "interaction_created", "request_id": str(request.id)}
    
    def automated_fallback(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Implement safe automated processing
        return {
            "status": "automated_processing",
            "result": self.safe_automatic_process(inputs),
            "note": "Human interaction unavailable, used automated fallback"
        }
```

### 3. Testing Interaction Workflows

```python
import pytest
from unittest.mock import Mock, patch
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType

class TestInteractionWorkflows:
    def setup_method(self):
        self.mock_storage = Mock()
        self.mock_handler = Mock()
        self.agent = InteractionAgent()
        self.agent.interaction_handler = self.mock_handler
    
    def test_approval_interaction_created(self):
        inputs = {"approval_data": {"amount": 5000, "type": "expense"}}
        
        result = self.agent.process(inputs)
        
        assert result["status"] == "pending_approval"
        assert "interaction_request_id" in result
        self.mock_handler.display_interaction_request.assert_called_once()
    
    def test_timeout_handling(self):
        # Test that interactions handle timeouts appropriately
        with patch('datetime.datetime') as mock_datetime:
            # Set up timeout scenario
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
            
            # Create interaction with timeout
            result = self.agent.process_with_timeout({"data": "test"}, timeout=30)
            
            # Verify timeout was set
            assert result["timeout_seconds"] == 30
    
    def test_interaction_validation(self):
        # Test that invalid interactions are rejected
        with pytest.raises(ValueError):
            self.agent.process({"invalid": "data"})
```

### 4. Monitoring and Analytics

```python
class InteractionAnalytics:
    \"\"\"Track and analyze human interaction patterns.\"\"\"
    
    def __init__(self, storage_service):
        self.storage_service = storage_service
    
    def track_interaction_metrics(self) -> Dict[str, Any]:
        \"\"\"Collect interaction metrics for analysis.\"\"\"
        # Get all interactions from last 30 days
        interactions = self.get_recent_interactions(days=30)
        
        metrics = {
            "total_interactions": len(interactions),
            "by_type": self.count_by_type(interactions),
            "avg_response_time": self.calculate_avg_response_time(interactions),
            "timeout_rate": self.calculate_timeout_rate(interactions),
            "approval_rate": self.calculate_approval_rate(interactions)
        }
        
        return metrics
    
    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        \"\"\"Identify interaction bottlenecks and patterns.\"\"\"
        interactions = self.get_recent_interactions(days=7)
        
        bottlenecks = []
        
        # Find nodes with many interactions
        node_counts = {}
        for interaction in interactions:
            node = interaction["node_name"]
            node_counts[node] = node_counts.get(node, 0) + 1
        
        # Identify high-interaction nodes
        for node, count in node_counts.items():
            if count > 10:  # Threshold for bottleneck
                bottlenecks.append({
                    "node": node,
                    "interaction_count": count,
                    "type": "high_interaction_volume"
                })
        
        return bottlenecks
```

## Related Documentation

### 🔧 **Interaction Tools**
- **[CLI Resume Commands](/docs/deployment/cli-resume)**: Command-line workflow resumption
- **[Advanced Error Handling](/docs/guides/development/error-handling)**: Error handling with interactions
- **[Thread Management](/docs/guides/development/thread-management)**: Execution thread lifecycle

### 🏗️ **Development Guides**
- **[Workflow Design](/docs/guides/development/workflow-design)**: Designing effective workflows
- **[Agent Development](/docs/guides/development/agents/)**: Building interactive agents
- **[Testing Patterns](/docs/guides/development/testing)**: Testing interaction workflows

### 🚀 **Production Patterns**
- **[Approval Workflows](/docs/examples/approval-workflows)**: Production approval patterns
- **[Content Review Systems](/docs/examples/content-review)**: Editorial workflow examples
- **[Decision Support Systems](/docs/examples/decision-support)**: Complex decision workflows
