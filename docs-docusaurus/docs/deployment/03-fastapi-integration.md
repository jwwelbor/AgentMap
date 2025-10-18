---
sidebar_position: 7
title: FastAPI Integration Guide
description: Integrate AgentMap workflows into existing FastAPI applications with custom routing, middleware, and shared services
keywords: [FastAPI integration, existing application, custom middleware, shared services, workflow integration]
---

# FastAPI Integration Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>FastAPI Integration</strong></span>
</div>

Integrate AgentMap workflows into your existing FastAPI applications, enabling seamless workflow execution alongside your current API endpoints with shared authentication, middleware, and services.

## Quick Integration

### 1. Basic Integration

```python
# main.py - Your existing FastAPI app
from fastapi import FastAPI, Depends
from agentmap.services.fastapi import include_agentmap_routes

# Your existing app
app = FastAPI(title="My Application")

# Your existing routes
@app.get("/")
async def root():
    return {"message": "My existing API"}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id, "name": "John Doe"}

# Add AgentMap workflows
include_agentmap_routes(
    app, 
    prefix="/workflows",
    csv_file="workflows.csv"
)

# Now available:
# POST /workflows/execute
# GET /workflows/list
# GET /workflows/{workflow_name}
```

### 2. With Authentication

```python
# main.py
from fastapi import FastAPI, Depends
from agentmap.services.fastapi import include_agentmap_routes
from your_auth import get_current_user, User

app = FastAPI()

# Add AgentMap with your existing authentication
include_agentmap_routes(
    app,
    prefix="/api/workflows",
    csv_file="workflows.csv",
    dependencies=[Depends(get_current_user)]  # Your auth dependency
)

# All AgentMap endpoints now require authentication
# POST /api/workflows/execute (requires auth)
# GET /api/workflows/list (requires auth)
```

### 3. Test Integration

```bash
# Start your application
uvicorn main:app --reload

# Test existing endpoints
curl http://localhost:8000/
curl http://localhost:8000/users/123

# Test AgentMap endpoints
curl -X POST http://localhost:8000/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{"graph_name": "MyWorkflow", "initial_state": {"input": "test"}}'
```

## Advanced Integration Patterns

### 🔗 Shared Services Integration

```python
# main.py
from fastapi import FastAPI, Depends
from agentmap.services.fastapi import AgentMapService
from agentmap.config import AgentMapConfig
from your_database import get_db_session
from your_redis import get_redis_client
from your_auth import get_current_user

app = FastAPI()

# Your existing services
@app.on_event("startup")
async def startup_event():
    # Initialize your services
    app.state.db_pool = await create_db_pool()
    app.state.redis = await create_redis_client()
    app.state.cache = CacheService(app.state.redis)

# Configure AgentMap to use your services
config = AgentMapConfig(
    csv_path="./workflows/",
    # Use your existing services
    database_session_factory=lambda: get_db_session(app.state.db_pool),
    cache_service=lambda: app.state.cache,
    
    # Custom agent configuration
    custom_services={
        "user_service": lambda: UserService(app.state.db_pool),
        "notification_service": lambda: NotificationService(app.state.redis),
        "analytics_service": lambda: AnalyticsService()
    }
)

# Create AgentMap service with shared configuration
agentmap_service = AgentMapService(config)

# Add routes with shared services
include_agentmap_routes(
    app,
    prefix="/workflows",
    service=agentmap_service,
    dependencies=[Depends(get_current_user)]
)

# Your workflows can now access your services:
# - Database sessions
# - Redis cache
# - User service
# - Notification service
# - Analytics service
```

### 🎛️ Custom Middleware Integration

```python
# middleware.py
from fastapi import Request, Response
from agentmap.services.fastapi import include_agentmap_routes
import time
import logging

logger = logging.getLogger(__name__)

# Your existing middleware
@app.middleware("http")
async def your_existing_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Your existing logic
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host
    
    response = await call_next(request)
    
    # Log all requests (including AgentMap ones)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url} - {response.status_code} - {process_time:.3f}s - {client_ip}")
    
    return response

# Custom AgentMap middleware
@app.middleware("http")
async def agentmap_specific_middleware(request: Request, call_next):
    if request.url.path.startswith("/workflows"):
        # Add workflow-specific headers
        request.state.workflow_context = {
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": getattr(request.state, "user_id", None)
        }
        
        # Add correlation ID for tracking
        response = await call_next(request)
        response.headers["X-Workflow-Request-ID"] = request.state.workflow_context["request_id"]
        
        return response
    else:
        return await call_next(request)

# Add AgentMap routes (will inherit middleware)
include_agentmap_routes(app, prefix="/workflows", csv_file="workflows.csv")
```

### 🔄 Custom Response Formatting

```python
# response_formatting.py
from fastapi import Response
from agentmap.services.fastapi import include_agentmap_routes, AgentMapService
from typing import Dict, Any

class CustomAgentMapService(AgentMapService):
    """Custom service with your response formatting"""
    
    async def format_execution_response(self, result: Dict[str, Any], request_context: Dict[str, Any]) -> Dict[str, Any]:
        """Format response to match your API standards"""
        
        # Your standard response format
        return {
            "status": "success" if result.get("success") else "error",
            "data": {
                "workflow_name": result.get("graph_name"),
                "result": result.get("result"),
                "execution_time": result.get("execution_time"),
                "nodes_executed": result.get("nodes_executed")
            },
            "metadata": {
                "timestamp": request_context.get("timestamp"),
                "request_id": request_context.get("request_id"),
                "api_version": "v1"
            },
            "links": {
                "self": f"/workflows/executions/{result.get('execution_id')}",
                "workflow": f"/workflows/{result.get('graph_name')}"
            }
        }

# Use custom service
custom_service = CustomAgentMapService(config)
include_agentmap_routes(app, prefix="/api/v1/workflows", service=custom_service)
```

## Real-World Integration Examples

### 🏪 E-commerce Application

```python
# ecommerce_app.py
from fastapi import FastAPI, Depends, HTTPException
from agentmap.services.fastapi import include_agentmap_routes
from your_models import User, Order, Product
from your_auth import get_current_user
from your_database import get_db

app = FastAPI(title="E-commerce API")

# Existing e-commerce endpoints
@app.post("/orders")
async def create_order(order_data: dict, user: User = Depends(get_current_user), db = Depends(get_db)):
    # Create order in database
    order = create_order_in_db(order_data, user.id, db)
    
    # Trigger AgentMap workflow for order processing
    workflow_result = await agentmap_service.execute_workflow(
        "OrderProcessing",
        {
            "order_id": order.id,
            "user_id": user.id,
            "order_data": order_data
        }
    )
    
    return {
        "order": order,
        "processing_status": workflow_result["result"]
    }

@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: int, user: User = Depends(get_current_user)):
    # Get order from database
    order = get_order_by_id(order_id, user.id)
    
    # Check workflow execution status
    execution_status = await agentmap_service.get_execution_status(order.workflow_execution_id)
    
    return {
        "order_id": order.id,
        "status": order.status,
        "workflow_status": execution_status,
        "estimated_completion": execution_status.get("estimated_completion")
    }

# Add AgentMap workflows with authentication
include_agentmap_routes(
    app,
    prefix="/internal/workflows",  # Internal use only
    csv_file="ecommerce_workflows.csv",
    dependencies=[Depends(get_current_user)],
    enable_docs=False  # Hide from public API docs
)

# Workflows available:
# - OrderProcessing: Handle payment, inventory, shipping
# - CustomerOnboarding: Welcome emails, account setup
# - RecommendationEngine: Generate product recommendations
# - InventoryManagement: Stock level monitoring and reordering
```

### 📊 Analytics Dashboard

```python
# analytics_app.py
from fastapi import FastAPI, Depends, BackgroundTasks
from agentmap.services.fastapi import include_agentmap_routes, AgentMapService
from your_analytics import AnalyticsService, get_analytics_service
from your_auth import require_admin_role

app = FastAPI(title="Analytics Dashboard")

# Existing analytics endpoints
@app.get("/dashboard/metrics")
async def get_dashboard_metrics(analytics: AnalyticsService = Depends(get_analytics_service)):
    return analytics.get_real_time_metrics()

@app.post("/reports/generate")
async def generate_report(
    report_config: dict, 
    background_tasks: BackgroundTasks,
    user = Depends(require_admin_role)
):
    # Start background workflow for report generation
    background_tasks.add_task(
        agentmap_service.execute_workflow,
        "ReportGeneration",
        {
            "report_type": report_config["type"],
            "date_range": report_config["date_range"],
            "user_id": user.id,
            "output_format": report_config.get("format", "pdf")
        }
    )
    
    return {"message": "Report generation started", "status": "processing"}

# Custom AgentMap integration
class AnalyticsAgentMapService(AgentMapService):
    def __init__(self, config, analytics_service):
        super().__init__(config)
        self.analytics = analytics_service
    
    async def pre_workflow_execution(self, graph_name: str, initial_state: dict, context: dict):
        """Track workflow executions in analytics"""
        self.analytics.track_event("workflow_started", {
            "workflow": graph_name,
            "user_id": context.get("user_id"),
            "timestamp": datetime.utcnow()
        })
    
    async def post_workflow_execution(self, graph_name: str, result: dict, context: dict):
        """Track workflow completions"""
        self.analytics.track_event("workflow_completed", {
            "workflow": graph_name,
            "success": result.get("success"),
            "duration": result.get("execution_time"),
            "user_id": context.get("user_id")
        })

# Configure with analytics integration
analytics_service = get_analytics_service()
agentmap_service = AnalyticsAgentMapService(config, analytics_service)

include_agentmap_routes(
    app,
    prefix="/workflows",
    service=agentmap_service,
    dependencies=[Depends(require_admin_role)]
)
```

### 🏥 Healthcare Platform

```python
# healthcare_app.py
from fastapi import FastAPI, Depends, HTTPException
from agentmap.services.fastapi import include_agentmap_routes
from your_models import Patient, Doctor, Appointment
from your_auth import get_current_user, require_role
from your_compliance import audit_log, encrypt_phi

app = FastAPI(title="Healthcare Platform")

# Custom middleware for HIPAA compliance
@app.middleware("http")
async def hipaa_compliance_middleware(request: Request, call_next):
    # Log all access for audit trail
    audit_log.log_request(request)
    
    response = await call_next(request)
    
    # Ensure PHI is encrypted in responses
    if request.url.path.startswith("/workflows") and hasattr(response, "body"):
        response.body = encrypt_phi(response.body)
    
    return response

@app.post("/appointments")
async def schedule_appointment(
    appointment_data: dict,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    # Create appointment
    appointment = create_appointment(appointment_data, db)
    
    # Trigger patient care workflow
    care_plan = await agentmap_service.execute_workflow(
        "PatientCareCoordination",
        {
            "appointment_id": appointment.id,
            "patient_id": appointment.patient_id,
            "doctor_id": appointment.doctor_id,
            "appointment_type": appointment_data["type"]
        }
    )
    
    return {
        "appointment": appointment,
        "care_plan": care_plan["result"]
    }

# Compliance-aware AgentMap service
class ComplianceAgentMapService(AgentMapService):
    async def execute_workflow(self, graph_name: str, initial_state: dict, context: dict = None):
        # Audit workflow execution
        audit_log.log_workflow_execution(graph_name, initial_state, context)
        
        # Ensure PHI data is handled properly
        sanitized_state = self.sanitize_phi_data(initial_state)
        
        result = await super().execute_workflow(graph_name, sanitized_state, context)
        
        # Log completion
        audit_log.log_workflow_completion(graph_name, result, context)
        
        return result

# Add AgentMap with healthcare-specific configuration
include_agentmap_routes(
    app,
    prefix="/care/workflows",
    service=ComplianceAgentMapService(config),
    dependencies=[Depends(require_role("healthcare_provider"))],
    enable_audit_logging=True
)
```

## Configuration Patterns

### 🎛️ Environment-Specific Integration

```python
# config.py
from agentmap.config import AgentMapConfig
import os

def get_agentmap_config():
    env = os.getenv("ENVIRONMENT", "development")
    
    base_config = {
        "csv_path": "./workflows/",
        "custom_agents_path": "./custom_agents/"
    }
    
    if env == "development":
        return AgentMapConfig(
            **base_config,
            log_level="DEBUG",
            enable_hot_reload=True,
            enable_docs=True
        )
    elif env == "staging":
        return AgentMapConfig(
            **base_config,
            log_level="INFO",
            enable_metrics=True,
            enable_docs=True
        )
    elif env == "production":
        return AgentMapConfig(
            **base_config,
            log_level="WARNING",
            enable_metrics=True,
            enable_docs=False,
            require_api_key=True,
            enable_audit_logging=True
        )
    
    return AgentMapConfig(**base_config)

# main.py
config = get_agentmap_config()
include_agentmap_routes(app, prefix="/workflows", config=config)
```

### 🔗 Database Integration

```python
# database_integration.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from agentmap.services.fastapi import AgentMapService

Base = declarative_base()

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True)
    graph_name = Column(String)
    initial_state = Column(JSON)
    result = Column(JSON)
    status = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    user_id = Column(Integer)

class DatabaseIntegratedAgentMapService(AgentMapService):
    def __init__(self, config, db_session_factory):
        super().__init__(config)
        self.get_db = db_session_factory
    
    async def execute_workflow(self, graph_name: str, initial_state: dict, context: dict = None):
        # Store execution in database
        db = self.get_db()
        execution = WorkflowExecution(
            graph_name=graph_name,
            initial_state=initial_state,
            status="running",
            started_at=datetime.utcnow(),
            user_id=context.get("user_id") if context else None
        )
        db.add(execution)
        db.commit()
        
        try:
            # Execute workflow
            result = await super().execute_workflow(graph_name, initial_state, context)
            
            # Update database with result
            execution.result = result
            execution.status = "completed" if result.get("success") else "failed"
            execution.completed_at = datetime.utcnow()
            db.commit()
            
            return result
            
        except Exception as e:
            # Update database with error
            execution.status = "error"
            execution.result = {"error": str(e)}
            execution.completed_at = datetime.utcnow()
            db.commit()
            raise

# Integration
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

agentmap_service = DatabaseIntegratedAgentMapService(config, get_db)
include_agentmap_routes(app, prefix="/workflows", service=agentmap_service)
```

## Testing Integration

### 🧪 Testing with Existing Test Suite

```python
# test_integration.py
import pytest
from fastapi.testclient import TestClient
from main import app
from your_tests.fixtures import authenticated_client, mock_db

client = TestClient(app)

def test_existing_endpoint_still_works():
    """Ensure existing endpoints work after AgentMap integration"""
    response = client.get("/users/123")
    assert response.status_code == 200

def test_agentmap_endpoints_added():
    """Verify AgentMap endpoints are available"""
    response = client.get("/workflows/list")
    assert response.status_code == 200

def test_shared_authentication():
    """Test that AgentMap uses your existing authentication"""
    # Without auth - should fail
    response = client.post("/workflows/execute", json={
        "graph_name": "TestWorkflow",
        "initial_state": {"input": "test"}
    })
    assert response.status_code == 401
    
    # With auth - should work
    with authenticated_client() as auth_client:
        response = auth_client.post("/workflows/execute", json={
            "graph_name": "TestWorkflow", 
            "initial_state": {"input": "test"}
        })
        assert response.status_code == 200

def test_shared_database():
    """Test that workflows can access your database"""
    with mock_db() as db:
        # Create test data in your database
        test_user = create_test_user(db)
        
        # Execute workflow that uses the database
        response = client.post("/workflows/execute", json={
            "graph_name": "UserWorkflow",
            "initial_state": {"user_id": test_user.id}
        })
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        
        # Verify workflow could access database
        assert "user_name" in result["result"]
        assert result["result"]["user_name"] == test_user.name
```

### 🔄 End-to-End Testing

```python
# test_e2e_integration.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_complete_user_journey():
    """Test complete user journey including workflows"""
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. User login (your existing endpoint)
        login_response = await ac.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. User creates something (your existing endpoint)
        create_response = await ac.post("/items", 
            json={"name": "Test Item", "description": "Test"},
            headers=headers
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]
        
        # 3. Trigger workflow to process the item
        workflow_response = await ac.post("/workflows/execute",
            json={
                "graph_name": "ItemProcessing",
                "initial_state": {"item_id": item_id}
            },
            headers=headers
        )
        assert workflow_response.status_code == 200
        assert workflow_response.json()["success"] == True
        
        # 4. Verify item was processed (your existing endpoint)
        item_response = await ac.get(f"/items/{item_id}", headers=headers)
        assert item_response.status_code == 200
        assert item_response.json()["status"] == "processed"
```

## Migration Strategies

### 🔄 Gradual Migration

```python
# Phase 1: Add AgentMap alongside existing logic
@app.post("/orders")
async def create_order_v1(order_data: dict, user = Depends(get_current_user)):
    # Existing order processing logic
    order = process_order_legacy(order_data, user)
    
    # Optional: Also run new AgentMap workflow
    try:
        workflow_result = await agentmap_service.execute_workflow(
            "OrderProcessing",
            {"order_id": order.id, "user_id": user.id}
        )
        order.workflow_result = workflow_result
    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Workflow execution failed: {e}")
    
    return order

# Phase 2: Feature flag migration
@app.post("/orders")
async def create_order_v2(order_data: dict, user = Depends(get_current_user)):
    use_agentmap = get_feature_flag("use_agentmap_for_orders", user.id)
    
    if use_agentmap:
        # New AgentMap workflow
        workflow_result = await agentmap_service.execute_workflow(
            "OrderProcessing",
            {"order_data": order_data, "user_id": user.id}
        )
        return workflow_result["result"]
    else:
        # Legacy processing
        return process_order_legacy(order_data, user)

# Phase 3: Full migration
@app.post("/orders")
async def create_order_v3(order_data: dict, user = Depends(get_current_user)):
    # Fully migrated to AgentMap
    workflow_result = await agentmap_service.execute_workflow(
        "OrderProcessing",
        {"order_data": order_data, "user_id": user.id}
    )
    return workflow_result["result"]
```

### 🚀 Migration Tools

```python
# migration_helper.py
from agentmap.services.fastapi import AgentMapService
from typing import Callable, Any

class MigrationHelper:
    def __init__(self, agentmap_service: AgentMapService):
        self.agentmap_service = agentmap_service
        self.fallback_handlers = {}
    
    def register_fallback(self, workflow_name: str, handler: Callable):
        """Register fallback handler for when workflow fails"""
        self.fallback_handlers[workflow_name] = handler
    
    async def execute_with_fallback(self, workflow_name: str, data: dict, context: dict = None):
        """Execute workflow with automatic fallback to legacy code"""
        try:
            result = await self.agentmap_service.execute_workflow(workflow_name, data, context)
            
            if result.get("success"):
                return {"source": "agentmap", "result": result["result"]}
            else:
                raise Exception(f"Workflow failed: {result.get('error')}")
                
        except Exception as e:
            logger.warning(f"AgentMap workflow {workflow_name} failed: {e}")
            
            if workflow_name in self.fallback_handlers:
                fallback_result = await self.fallback_handlers[workflow_name](data, context)
                return {"source": "fallback", "result": fallback_result}
            else:
                raise

# Usage
migration_helper = MigrationHelper(agentmap_service)

# Register fallback handlers
migration_helper.register_fallback("OrderProcessing", process_order_legacy)
migration_helper.register_fallback("UserOnboarding", onboard_user_legacy)

@app.post("/orders")
async def create_order(order_data: dict, user = Depends(get_current_user)):
    result = await migration_helper.execute_with_fallback(
        "OrderProcessing",
        {"order_data": order_data, "user_id": user.id}
    )
    
    # Log which system was used
    logger.info(f"Order processed via: {result['source']}")
    
    return result["result"]
```

## Performance Considerations

### ⚡ Optimization for Integration

```python
# performance_optimization.py
from agentmap.services.fastapi import AgentMapService
from functools import lru_cache
import asyncio

class OptimizedAgentMapService(AgentMapService):
    def __init__(self, config):
        super().__init__(config)
        self._workflow_cache = {}
        self._execution_semaphore = asyncio.Semaphore(10)  # Limit concurrent executions
    
    @lru_cache(maxsize=100)
    def get_workflow_definition(self, graph_name: str):
        """Cache workflow definitions"""
        return super().get_workflow_definition(graph_name)
    
    async def execute_workflow(self, graph_name: str, initial_state: dict, context: dict = None):
        """Execute workflow with concurrency limiting"""
        async with self._execution_semaphore:
            return await super().execute_workflow(graph_name, initial_state, context)
    
    async def batch_execute_workflows(self, executions: list):
        """Execute multiple workflows efficiently"""
        tasks = []
        for execution in executions:
            task = self.execute_workflow(
                execution["graph_name"],
                execution["initial_state"],
                execution.get("context")
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)

# Connection pooling for shared resources
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600
)
```

## Next Steps

- **[HTTP API Reference](./http-api-reference)**: Complete REST API endpoint documentation
- **[Configuration Reference](./configuration)**: Advanced configuration options
- **[Monitoring Guide](./monitoring)**: Production monitoring and observability
- **[Performance Tuning](./performance)**: Optimization best practices
- **[Security Guide](./security)**: Comprehensive security implementation
- **[CLI Deployment](./cli-deployment)**: Alternative deployment option

## Related Resources

- **[FastAPI Standalone](./fastapi-standalone)**: Standalone service deployment
- **[HTTP API Reference](./http-api-reference)**: Complete API reference
- **[Agent Development](/docs/guides/development/agents/agent-development)**: Custom agent creation
- **[Example Workflows](/docs/templates/)**: Real-world usage patterns
- **[Troubleshooting](./troubleshooting)**: Common issues and solutions

---

**Quick Links:**
- [Deployment Overview](./index) | [CLI Deployment](./cli-deployment) | [FastAPI Standalone](./fastapi-standalone)
- [HTTP API Reference](./http-api-reference) | [Configuration](./configuration) | [Monitoring](./monitoring) | [Troubleshooting](./troubleshooting)
