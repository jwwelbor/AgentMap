---
sidebar_position: 8
title: HTTP API Reference
description: Complete reference for AgentMap HTTP API endpoints, including execution, resume, workflows, and admin operations
keywords: [HTTP API, REST API, API reference, endpoints, suspend resume, workflow execution]
---

# HTTP API Reference

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>HTTP API Reference</strong></span>
</div>

Complete reference for the AgentMap HTTP API, including all endpoints, request/response formats, and authentication methods.

## Base URL

```
http://127.0.0.1:8000
```

## Authentication

The API supports two authentication methods:

### API Key Authentication

```http
X-API-Key: your-api-key-here
```

### Bearer Token Authentication

```http
Authorization: Bearer your-token-here
```

## Core Endpoints

### Execute Workflow

Execute a workflow with initial inputs. Returns execution results or suspension details if the workflow is interrupted.

#### Endpoint (Two-Parameter Format)

```http
POST /execute/{workflow}/{graph}
```

**Path Parameters:**
- `workflow` (string): Workflow name
- `graph` (string): Graph name within the workflow

**Request Body:**
```json
{
  "inputs": {
    "key": "value",
    "nested": {
      "data": "example"
    }
  },
  "force_create": false,
  "execution_id": "optional-tracking-id"
}
```

**Fields:**
- `inputs` (object): Input state passed to the workflow
- `force_create` (boolean, optional): Force recreation of bundle even if cached (default: false)
- `execution_id` (string, optional): Client-supplied tracking identifier

**Response (Completed):**
```json
{
  "success": true,
  "status": "completed",
  "message": "Graph 'workflow::graph' completed successfully",
  "thread_id": null,
  "outputs": {
    "result": "workflow output data"
  },
  "execution_summary": {
    "duration": 2.34,
    "nodes_executed": 5,
    "status": "completed"
  },
  "metadata": {
    "timestamp": "2025-10-17T10:30:00Z"
  },
  "interrupt_info": null,
  "error": null,
  "execution_id": "optional-tracking-id"
}
```

**Response (Suspended):**
```json
{
  "success": false,
  "status": "suspended",
  "message": "Graph 'workflow::graph' suspended awaiting resume",
  "thread_id": "329043ce-577c-4f4d-b4aa-aad033a42171",
  "outputs": null,
  "execution_summary": {
    "status": "suspended",
    "nodes_executed": 3
  },
  "metadata": {
    "timestamp": "2025-10-17T10:30:00Z"
  },
  "interrupt_info": {
    "reason": "human_input_required",
    "prompt": "Please approve the transaction",
    "options": ["approve", "reject"]
  },
  "error": null,
  "execution_id": "optional-tracking-id"
}
```

**Response (Failed):**
```json
{
  "success": false,
  "status": "failed",
  "message": "Graph 'workflow::graph' failed to execute",
  "thread_id": null,
  "outputs": null,
  "execution_summary": null,
  "metadata": null,
  "interrupt_info": null,
  "error": "Error message describing what went wrong",
  "execution_id": "optional-tracking-id"
}
```

**Status Codes:**
- `200 OK`: Workflow executed (check `status` field for completion status)
- `400 Bad Request`: Invalid inputs or graph identifier
- `404 Not Found`: Graph not found
- `503 Service Unavailable`: AgentMap not initialized

#### Example: Execute with API Key

```bash
curl -X POST "http://127.0.0.1:8000/execute/customer_service/support_flow" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "customer_id": "12345",
      "issue": "billing question"
    },
    "execution_id": "support_123"
  }'
```

#### Example: Execute with Bearer Token

```bash
curl -X POST "http://127.0.0.1:8000/execute/data_processing/etl_pipeline" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "data_source": "s3://bucket/data.csv",
      "destination": "database"
    },
    "force_create": true
  }'
```

### Resume Workflow

Resume a suspended workflow execution with a response action and optional data.

#### Endpoint

```http
POST /resume/{thread_id}
```

**Path Parameters:**
- `thread_id` (string): Thread identifier from suspended execution

**Request Body:**
```json
{
  "action": "approve",
  "data": {
    "comments": "Looks good to proceed",
    "approver_id": "user123"
  }
}
```

**Fields:**
- `action` (string, optional): Action to take (e.g., "approve", "reject", "respond", "retry")
- `data` (object, optional): Additional data associated with the resume action

**Response (Success):**
```json
{
  "success": true,
  "status": "completed",
  "message": "Successfully resumed thread '329043ce-577c-4f4d-b4aa-aad033a42171'",
  "thread_id": "329043ce-577c-4f4d-b4aa-aad033a42171",
  "outputs": {
    "final_result": "transaction approved and processed"
  },
  "execution_summary": {
    "status": "completed",
    "total_duration": 5.67,
    "nodes_executed": 8
  },
  "metadata": {
    "resumed_at": "2025-10-17T10:31:00Z"
  },
  "error": null
}
```

**Response (Re-suspended):**
```json
{
  "success": false,
  "status": "suspended",
  "message": "Successfully resumed thread but workflow suspended again",
  "thread_id": "329043ce-577c-4f4d-b4aa-aad033a42171",
  "outputs": null,
  "execution_summary": {
    "status": "suspended",
    "nodes_executed": 6
  },
  "metadata": null,
  "error": null
}
```

**Status Codes:**
- `200 OK`: Resume processed (check `status` field for completion status)
- `400 Bad Request`: Invalid thread ID or request data
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Resume operation failed

#### Example: Resume with Approval

```bash
curl -X POST "http://127.0.0.1:8000/resume/329043ce-577c-4f4d-b4aa-aad033a42171" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "data": {
      "approved_by": "manager@company.com",
      "timestamp": "2025-10-17T10:31:00Z"
    }
  }'
```

#### Example: Resume with Rejection

```bash
curl -X POST "http://127.0.0.1:8000/resume/329043ce-577c-4f4d-b4aa-aad033a42171" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "data": {
      "reason": "Insufficient documentation provided"
    }
  }'
```

## Workflow Endpoints

### List Workflows

Get a list of all available workflows with metadata.

#### Endpoint

```http
GET /workflows
```

**Response:**
```json
{
  "repository_path": "/path/to/workflows",
  "workflows": [
    {
      "name": "customer_service",
      "filename": "customer_service.csv",
      "file_path": "/path/to/workflows/customer_service.csv",
      "file_size": 2048,
      "last_modified": 1729161600.0,
      "graph_count": 3,
      "total_nodes": 15
    },
    {
      "name": "data_processing",
      "filename": "data_processing.csv",
      "file_path": "/path/to/workflows/data_processing.csv",
      "file_size": 4096,
      "last_modified": 1729161600.0,
      "graph_count": 5,
      "total_nodes": 28
    }
  ],
  "total_count": 2
}
```

**Status Codes:**
- `200 OK`: Workflows listed successfully
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Failed to list workflows

#### Example: List All Workflows

```bash
curl -X GET "http://127.0.0.1:8000/workflows" \
  -H "X-API-Key: your-api-key"
```

### Get Workflow Details

Get detailed information about a specific workflow including its nodes and structure.

#### Endpoint

```http
GET /workflows/{graph_id}
```

**Path Parameters:**
- `graph_id` (string): Graph identifier in format `workflow::graph` or `workflow/graph`

**Response:**
```json
{
  "graph_id": "customer_service::support_flow",
  "workflow": "customer_service",
  "graph": "support_flow",
  "nodes": [
    {
      "name": "intake",
      "agent_type": "InputAgent",
      "description": "Collect customer information"
    },
    {
      "name": "classify",
      "agent_type": "LLMAgent",
      "description": "Classify the support request"
    },
    {
      "name": "route",
      "agent_type": "RouterAgent",
      "description": "Route to appropriate handler"
    }
  ],
  "node_count": 3,
  "entry_point": "intake"
}
```

**Status Codes:**
- `200 OK`: Workflow details retrieved
- `404 Not Found`: Workflow not found
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Failed to retrieve details

#### Example: Get Workflow Details

```bash
curl -X GET "http://127.0.0.1:8000/workflows/customer_service::support_flow" \
  -H "X-API-Key: your-api-key"
```

#### Example: Get Workflow Details (Path Format)

```bash
# Alternative format using /
curl -X GET "http://127.0.0.1:8000/workflows/customer_service/support_flow" \
  -H "X-API-Key: your-api-key"
```

## Health & Admin Endpoints

### Health Check

Basic health check endpoint for monitoring and load balancing.

#### Endpoint

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "agentmap-api",
  "timestamp": "2025-10-17T10:30:00.123456",
  "version": "2.0"
}
```

**Status Codes:**
- `200 OK`: Service is healthy

#### Example

```bash
curl -X GET "http://127.0.0.1:8000/health"
```

### Get Diagnostics

Get comprehensive system diagnostics information.

#### Endpoint

```http
GET /admin/diagnostics
```

**Response:**
```json
{
  "overall_status": "healthy",
  "llm_ready": true,
  "storage_ready": true,
  "features": {
    "llm_agents": {
      "available": true,
      "providers": ["openai", "anthropic"]
    },
    "storage": {
      "available": true,
      "backend": "sqlite"
    }
  },
  "suggestions": []
}
```

**Status Codes:**
- `200 OK`: Diagnostics retrieved
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Diagnostics failed

#### Example

```bash
curl -X GET "http://127.0.0.1:8000/admin/diagnostics" \
  -H "X-API-Key: your-api-key"
```

### Get Configuration

Get current system configuration.

#### Endpoint

```http
GET /admin/config
```

**Response:**
```json
{
  "configuration": {
    "csv_repository_path": "/path/to/workflows",
    "custom_agents_path": "/path/to/agents",
    "functions_path": "/path/to/functions",
    "log_level": "INFO",
    "storage_backend": "sqlite"
  }
}
```

**Status Codes:**
- `200 OK`: Configuration retrieved
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Failed to get configuration

#### Example

```bash
curl -X GET "http://127.0.0.1:8000/admin/config" \
  -H "X-API-Key: your-api-key"
```

### Get Cache Statistics

Get cache statistics and information.

#### Endpoint

```http
GET /admin/cache
```

**Response:**
```json
{
  "action": "stats",
  "stats": {
    "total_entries": 42,
    "cache_size_bytes": 102400,
    "hit_rate": 0.85
  },
  "removed_entries": null
}
```

**Status Codes:**
- `200 OK`: Cache stats retrieved
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Failed to get cache stats

#### Example

```bash
curl -X GET "http://127.0.0.1:8000/admin/cache" \
  -H "X-API-Key: your-api-key"
```

### Clear Cache

Clear validation cache.

#### Endpoint

```http
POST /admin/cache/clear
```

**Query Parameters:**
- `file_path` (string, optional): Clear cache for specific file only

**Response:**
```json
{
  "action": "clear",
  "stats": null,
  "removed_entries": 15
}
```

**Status Codes:**
- `200 OK`: Cache cleared
- `503 Service Unavailable`: AgentMap not initialized
- `500 Internal Server Error`: Failed to clear cache

#### Example: Clear All Cache

```bash
curl -X POST "http://127.0.0.1:8000/admin/cache/clear" \
  -H "X-API-Key: your-api-key"
```

#### Example: Clear Specific File Cache

```bash
curl -X POST "http://127.0.0.1:8000/admin/cache/clear?file_path=/path/to/workflow.csv" \
  -H "X-API-Key: your-api-key"
```

### Get Version

Get version information (no authentication required).

#### Endpoint

```http
GET /admin/version
```

**Response:**
```json
{
  "agentmap_version": "2.0.0",
  "api_version": "2.0"
}
```

**Status Codes:**
- `200 OK`: Version information retrieved

#### Example

```bash
curl -X GET "http://127.0.0.1:8000/admin/version"
```

## Complete Suspend/Resume Workflow Example

This example demonstrates a complete suspend/resume cycle with a workflow that requires human approval.

### Step 1: Execute Workflow

```bash
curl -X POST "http://127.0.0.1:8000/execute/suspend_agent_examples/APIIntegration" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "task": "Process high-value transaction",
      "amount": 50000,
      "customer_id": "CUST-12345"
    },
    "execution_id": "txn_20251017_001"
  }'
```

### Response: Workflow Suspended

```json
{
  "success": false,
  "status": "suspended",
  "message": "Graph 'suspend_agent_examples::APIIntegration' suspended awaiting resume",
  "thread_id": "3a1a9c33-f219-4eb9-af75-8ad7e5831bf0",
  "outputs": null,
  "execution_summary": {
    "status": "suspended",
    "nodes_executed": 2
  },
  "metadata": {
    "timestamp": "2025-10-17T14:30:00Z"
  },
  "interrupt_info": {
    "reason": "approval_required",
    "prompt": "High-value transaction requires manager approval",
    "amount": 50000,
    "options": ["approve", "reject", "escalate"]
  },
  "error": null,
  "execution_id": "txn_20251017_001"
}
```

### Step 2: Resume Workflow (After Human Review)

```bash
curl -X POST "http://127.0.0.1:8000/resume/3a1a9c33-f219-4eb9-af75-8ad7e5831bf0" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "data": {
      "approved_by": "manager@company.com",
      "approval_timestamp": "2025-10-17T14:35:00Z",
      "comments": "Verified with customer, transaction is legitimate"
    }
  }'
```

### Response: Workflow Completed

```json
{
  "success": true,
  "status": "completed",
  "message": "Successfully resumed thread '3a1a9c33-f219-4eb9-af75-8ad7e5831bf0'",
  "thread_id": "3a1a9c33-f219-4eb9-af75-8ad7e5831bf0",
  "outputs": {
    "transaction_status": "approved",
    "transaction_id": "TXN-20251017-12345",
    "confirmation_number": "CONF-987654",
    "processing_result": "Transaction completed successfully"
  },
  "execution_summary": {
    "status": "completed",
    "total_duration": 305.23,
    "nodes_executed": 5,
    "approval_delay": 300
  },
  "metadata": {
    "resumed_at": "2025-10-17T14:35:00Z",
    "completed_at": "2025-10-17T14:35:05Z"
  },
  "error": null
}
```

## Error Responses

All endpoints follow a consistent error response format:

### 400 Bad Request

```json
{
  "detail": "Invalid graph identifier format: invalid/format/here"
}
```

### 404 Not Found

```json
{
  "error": "Graph not found",
  "message": "Graph 'nonexistent::workflow' not found",
  "type": "GraphNotFound"
}
```

### 503 Service Unavailable

```json
{
  "error": "Service unavailable",
  "message": "AgentMap runtime not initialized",
  "type": "AgentMapNotInitialized"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error occurred during workflow execution"
}
```

## Python Client Example

Here's a complete Python client for the AgentMap HTTP API:

```python
import requests
import json
import time
from typing import Dict, Any, Optional


class AgentMapClient:
    """Client for AgentMap HTTP API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        auth_method: str = "x-api-key"
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.auth_method = auth_method
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            if self.auth_method == "bearer":
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers["X-API-Key"] = self.api_key

        return headers

    def execute(
        self,
        workflow: str,
        graph: str,
        inputs: Dict[str, Any],
        execution_id: Optional[str] = None,
        force_create: bool = False
    ) -> Dict[str, Any]:
        """Execute a workflow."""
        url = f"{self.base_url}/execute/{workflow}/{graph}"

        payload = {
            "inputs": inputs,
            "force_create": force_create
        }

        if execution_id:
            payload["execution_id"] = execution_id

        response = self.session.post(
            url,
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def resume(
        self,
        thread_id: str,
        action: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resume a suspended workflow."""
        url = f"{self.base_url}/resume/{thread_id}"

        payload = {
            "action": action,
            "data": data or {}
        }

        response = self.session.post(
            url,
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def list_workflows(self) -> Dict[str, Any]:
        """List all available workflows."""
        url = f"{self.base_url}/workflows"

        response = self.session.get(
            url,
            headers=self._get_headers(),
            timeout=10
        )

        response.raise_for_status()
        return response.json()

    def get_workflow_details(self, graph_id: str) -> Dict[str, Any]:
        """Get details for a specific workflow."""
        url = f"{self.base_url}/workflows/{graph_id}"

        response = self.session.get(
            url,
            headers=self._get_headers(),
            timeout=10
        )

        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        url = f"{self.base_url}/health"

        response = self.session.get(url, timeout=5)
        response.raise_for_status()
        return response.json()


# Usage Example
if __name__ == "__main__":
    # Initialize client
    client = AgentMapClient(
        base_url="http://127.0.0.1:8000",
        api_key="your-api-key",
        auth_method="x-api-key"
    )

    # Check health
    health = client.health_check()
    print(f"Service status: {health['status']}")

    # List workflows
    workflows = client.list_workflows()
    print(f"Available workflows: {len(workflows['workflows'])}")

    # Execute workflow
    result = client.execute(
        workflow="customer_service",
        graph="support_flow",
        inputs={
            "customer_id": "12345",
            "issue": "billing question"
        },
        execution_id="test_001"
    )

    # Check if suspended
    if result["status"] == "suspended":
        thread_id = result["thread_id"]
        print(f"Workflow suspended: {result['interrupt_info']['prompt']}")

        # Wait for human input (in real scenario)
        time.sleep(5)

        # Resume workflow
        resume_result = client.resume(
            thread_id=thread_id,
            action="approve",
            data={"approved_by": "user@example.com"}
        )

        print(f"Resume status: {resume_result['status']}")

    elif result["status"] == "completed":
        print(f"Workflow completed: {result['outputs']}")

    else:
        print(f"Workflow failed: {result['error']}")
```

## Next Steps

- **[FastAPI Standalone Deployment](./fastapi-standalone)**: Deploy AgentMap as a standalone service
- **[FastAPI Integration](./fastapi-integration)**: Integrate with existing FastAPI apps
- **[CLI Commands](./cli-commands)**: Command-line interface reference
- **[CLI Resume](./cli-resume)**: Using resume functionality via CLI

---

**Quick Links:**
- [Deployment Overview](./index) | [FastAPI Standalone](./fastapi-standalone) | [Integration Guide](./fastapi-integration)
- [Configuration](./configuration) | [Monitoring](./monitoring) | [Troubleshooting](./troubleshooting)
