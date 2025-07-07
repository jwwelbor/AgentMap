---
sidebar_position: 8
title: "Lesson 7: FastAPI Standalone Deployment"
description: Deploy AgentMap workflows as standalone FastAPI web applications with REST APIs, serverless functions, and production-ready architectures
keywords: [FastAPI, standalone deployment, REST API, serverless, web application, production deployment]
---

# Lesson 7: FastAPI Standalone Deployment

Ready to deploy your AI workflows as production web services? In this lesson, you'll learn to package AgentMap workflows as standalone FastAPI applications, complete with REST APIs, automatic documentation, and production-ready deployment patterns.

## Learning Objectives

By the end of this lesson, you will:
- ✅ Create standalone FastAPI applications with AgentMap workflows
- ✅ Design RESTful APIs for workflow execution
- ✅ Implement authentication and rate limiting
- ✅ Add automatic API documentation and OpenAPI specs
- ✅ Deploy to cloud platforms and serverless environments
- ✅ Monitor and scale production deployments
- ✅ Handle file uploads, streaming responses, and async operations

## Overview: What We're Building

We'll create a **Production-Ready AgentMap API Service** that:
1. **Exposes** AgentMap workflows via REST endpoints
2. **Handles** file uploads and multipart data
3. **Provides** real-time progress updates via WebSocket
4. **Implements** authentication and rate limiting
5. **Generates** automatic API documentation
6. **Deploys** to multiple cloud platforms
7. **Monitors** performance and health metrics

```mermaid
flowchart TD
    A[🌐 Client Applications<br/>Web, Mobile, API Consumers] --> B[🔒 API Gateway<br/>Authentication & Rate Limiting]
    B --> C[📋 FastAPI Application<br/>AgentMap Service Layer]
    
    C --> D[🚀 Workflow Endpoints]
    D --> E[📄 Document Processing<br/>/api/v1/process-document]
    D --> F[📊 Data Analysis<br/>/api/v1/analyze-data]
    D --> G[🤖 AI Workflows<br/>/api/v1/run-workflow]
    
    C --> H[📱 Management Endpoints]
    H --> I[💾 Status & Results<br/>/api/v1/status/{job_id}]
    H --> J[📈 Health & Metrics<br/>/api/v1/health]
    H --> K[📚 Documentation<br/>/docs /redoc]
    
    C --> L[🔗 Real-time Features]
    L --> M[📡 WebSocket Updates<br/>/ws/progress]
    L --> N[📤 File Uploads<br/>/api/v1/upload]
    L --> O[📥 Results Download<br/>/api/v1/download/{job_id}]
    
    style C fill:#e3f2fd
    style D fill:#fff3e0
    style H fill:#f3e5f5
    style L fill:#e8f5e8
```

## Step 1: Download the Complete FastAPI Standalone Application

Let's get all the files for our production-ready FastAPI deployment:

import DownloadButton from '@site/src/components/DownloadButton';

### Main FastAPI Application
<DownloadButton 
  filename="lesson7.py"
  contentPath="/downloads/lessons/lesson7/lesson7.py"
/>

### Production Requirements File
<DownloadButton 
  filename="requirements-production.txt"
  contentPath="/downloads/lessons/lesson7/requirements-production.txt"
/>

### Docker Configuration
<DownloadButton 
  filename="Dockerfile"
  contentPath="/downloads/lessons/lesson7/Dockerfile"
/>

### Kubernetes Deployment
<DownloadButton 
  filename="k8s-deployment.yaml"
  contentPath="/downloads/lessons/lesson7/k8s-deployment.yaml"
/>

## Step 2: Understanding FastAPI Standalone Architecture

### Application Structure

```
agentmap-api/
├── lesson7.py              # Main FastAPI application
├── requirements-production.txt  # Production dependencies
├── Dockerfile              # Container configuration
├── k8s-deployment.yaml     # Kubernetes manifests
├── uploads/                # File upload directory
├── results/                # Workflow results directory
└── logs/                   # Application logs
```

### Core Components

#### 1. **Application State Management**
```python
class ApplicationState:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.active_websockets: List[WebSocket] = []
        self.metrics = {
            "total_requests": 0,
            "active_jobs": 0
        }
```

#### 2. **Asynchronous Workflow Execution**
```python
async def execute_workflow_async(job_id: str, workflow_type: WorkflowType, 
                                input_data: Dict[str, Any]):
    # Background workflow execution
    # Real-time progress updates via WebSocket
    # Result storage and retrieval
```

#### 3. **RESTful API Design**
```python
@app.post("/api/v1/workflows/execute")
@app.get("/api/v1/jobs/{job_id}")
@app.get("/api/v1/health")
@app.post("/api/v1/upload")
```

#### 4. **Authentication and Security**
```python
async def verify_token(credentials: HTTPAuthorizationCredentials):
    # JWT validation
    # API key verification
    # User authorization
```

## Step 3: Running the Standalone Application

### Local Development

1. **Install Dependencies**:
```bash
pip install fastapi uvicorn python-multipart slowapi psutil
```

2. **Run the Application**:
```bash
python lesson7.py
```

3. **Access the API**:
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc docs**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/api/v1/health

### API Usage Examples

#### 1. **Execute a Workflow**
```bash
curl -X POST "http://localhost:8000/api/v1/workflows/execute" \
  -H "Authorization: Bearer demo-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "document_processing",
    "input_data": {
      "document_text": "Sample document content",
      "language": "en"
    },
    "config": {
      "extract_entities": true,
      "generate_summary": true
    },
    "priority": 8
  }'
```

#### 2. **Check Job Status**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/YOUR_JOB_ID" \
  -H "Authorization: Bearer demo-api-key"
```

#### 3. **Upload and Process File**
```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Authorization: Bearer demo-api-key" \
  -F "file=@document.pdf" \
  -F "workflow_type=document_processing"
```

#### 4. **WebSocket Connection for Real-time Updates**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/progress');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Progress update:', data);
};
```

### Production Deployment Options

#### Option 1: Docker Deployment

```bash
# Build image
docker build -t agentmap-api .

# Run container
docker run -p 8000:8000 \
  -e SECRET_KEY="your-production-secret" \
  -e RATE_LIMIT_PER_MINUTE="200/minute" \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/results:/app/results \
  agentmap-api
```

#### Option 2: Kubernetes Deployment

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get pods -l app=agentmap-api
kubectl get service agentmap-api-service
```

#### Option 3: Cloud Platform Deployment

**AWS ECS with Fargate**:
```json
{
  "family": "agentmap-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "agentmap-api",
      "image": "your-registry/agentmap-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "SECRET_KEY",
          "value": "your-production-secret"
        }
      ]
    }
  ]
}
```

**Google Cloud Run**:
```bash
gcloud run deploy agentmap-api \
  --image gcr.io/PROJECT_ID/agentmap-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SECRET_KEY=your-production-secret
```

**Azure Container Apps**:
```bash
az containerapp create \
  --name agentmap-api \
  --resource-group myResourceGroup \
  --environment myEnvironment \
  --image your-registry/agentmap-api:latest \
  --target-port 8000 \
  --env-vars SECRET_KEY=your-production-secret
```

## Step 4: Advanced FastAPI Features

### Feature 1: Background Job Processing with Celery

```python
from celery import Celery

# Configure Celery for distributed task processing
celery_app = Celery(
    "agentmap_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def execute_workflow_celery(job_id: str, workflow_type: str, input_data: dict):
    """Execute workflow as Celery task."""
    # Long-running workflow execution
    # Update job status in database
    # Send notifications on completion
    pass

@app.post("/api/v1/workflows/execute-async")
async def execute_workflow_celery_endpoint(request: WorkflowRequest):
    """Execute workflow using Celery for distributed processing."""
    job_id = str(uuid.uuid4())
    
    # Start Celery task
    task = execute_workflow_celery.delay(
        job_id, 
        request.workflow_type, 
        request.input_data
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "queued"
    }
```

### Feature 2: Database Integration with SQLAlchemy

```python
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True)
    workflow_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    input_data = Column(JSON)
    result = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    progress = Column(Float, default=0.0)

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/v1/jobs/{job_id}")
async def get_job_from_db(job_id: str, db: Session = Depends(get_db)):
    """Get job from database."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

### Feature 3: Monitoring and Metrics

```python
from prometheus_fastapi_instrumentator import Instrumentator

# Add Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app)

@app.on_event("startup")
async def startup():
    instrumentator.expose(app)

# Custom metrics
from prometheus_client import Counter, Histogram, Gauge

workflow_counter = Counter(
    'agentmap_workflows_total', 
    'Total number of workflows executed',
    ['workflow_type', 'status']
)

workflow_duration = Histogram(
    'agentmap_workflow_duration_seconds',
    'Workflow execution duration',
    ['workflow_type']
)

active_jobs_gauge = Gauge(
    'agentmap_active_jobs',
    'Number of currently active jobs'
)

# Use metrics in endpoints
@app.post("/api/v1/workflows/execute")
async def execute_workflow_with_metrics(request: WorkflowRequest):
    workflow_counter.labels(
        workflow_type=request.workflow_type,
        status='started'
    ).inc()
    
    active_jobs_gauge.inc()
    
    start_time = time.time()
    
    try:
        # Execute workflow
        result = await execute_workflow(request)
        
        workflow_counter.labels(
            workflow_type=request.workflow_type,
            status='completed'
        ).inc()
        
        return result
        
    except Exception as e:
        workflow_counter.labels(
            workflow_type=request.workflow_type,
            status='failed'
        ).inc()
        raise e
        
    finally:
        duration = time.time() - start_time
        workflow_duration.labels(
            workflow_type=request.workflow_type
        ).observe(duration)
        
        active_jobs_gauge.dec()
```

### Feature 4: Advanced Security

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

@app.on_event("startup")
async def startup():
    redis_client = redis.from_url("redis://localhost:6379", encoding="utf-8")
    await FastAPILimiter.init(redis_client)

# Advanced rate limiting
@app.post("/api/v1/workflows/execute")
@app.dependencies([Depends(RateLimiter(times=10, seconds=60))])
async def execute_workflow_limited(request: WorkflowRequest):
    """Execute workflow with advanced rate limiting."""
    pass

# API key management
class APIKeyManager:
    def __init__(self):
        self.keys = {}  # In production, use database
    
    def create_key(self, user_id: str, scopes: List[str]) -> str:
        api_key = secrets.token_urlsafe(32)
        self.keys[api_key] = {
            "user_id": user_id,
            "scopes": scopes,
            "created_at": datetime.now(),
            "last_used": None
        }
        return api_key
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        if api_key in self.keys:
            key_info = self.keys[api_key]
            key_info["last_used"] = datetime.now()
            return key_info
        return None

# Request validation middleware
@app.middleware("http")
async def validate_request_size(request: Request, call_next):
    """Limit request size to prevent DoS attacks."""
    max_size = 10 * 1024 * 1024  # 10MB
    
    if "content-length" in request.headers:
        content_length = int(request.headers["content-length"])
        if content_length > max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request too large"}
            )
    
    response = await call_next(request)
    return response
```

## Step 5: Testing the Standalone Application

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient
from lesson7 import app

client = TestClient(app)

def test_health_check():
    """Test health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_execute_workflow():
    """Test workflow execution."""
    response = client.post(
        "/api/v1/workflows/execute",
        headers={"Authorization": "Bearer demo-api-key"},
        json={
            "workflow_type": "document_processing",
            "input_data": {"text": "sample"},
            "config": {}
        }
    )
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connection."""
    with client.websocket_connect("/ws/progress") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "heartbeat"

def test_file_upload():
    """Test file upload endpoint."""
    with open("test_file.txt", "w") as f:
        f.write("test content")
    
    with open("test_file.txt", "rb") as f:
        response = client.post(
            "/api/v1/upload",
            headers={"Authorization": "Bearer demo-api-key"},
            files={"file": ("test_file.txt", f, "text/plain")}
        )
    
    assert response.status_code == 200
    assert "file_id" in response.json()

def test_unauthorized_access():
    """Test authentication requirement."""
    response = client.post("/api/v1/workflows/execute")
    assert response.status_code == 403  # Forbidden
```

### Load Testing

```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test_workflow_execution():
    """Load test workflow execution endpoint."""
    
    async def make_request(session, request_id):
        async with session.post(
            "http://localhost:8000/api/v1/workflows/execute",
            headers={"Authorization": "Bearer demo-api-key"},
            json={
                "workflow_type": "document_processing",
                "input_data": {"text": f"request {request_id}"},
                "config": {}
            }
        ) as response:
            return await response.json()
    
    # Test with 100 concurrent requests
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        
        tasks = [
            make_request(session, i) 
            for i in range(100)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        
        successful = len([r for r in results if not isinstance(r, Exception)])
        failed = len(results) - successful
        
        print(f"Load test results:")
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Duration: {end_time - start_time:.2f}s")
        print(f"  Requests/second: {len(results) / (end_time - start_time):.2f}")

# Run load test
if __name__ == "__main__":
    asyncio.run(load_test_workflow_execution())
```

## Step 6: Monitoring and Observability

### Application Logging

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests with structured data."""
    start_time = time.time()
    
    # Log request
    logger.info(
        "request_started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    logger.info(
        "request_completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration=duration
    )
    
    return response
```

### Health Checks and Readiness Probes

```python
@app.get("/api/v1/health/live")
async def liveness_probe():
    """Liveness probe for Kubernetes."""
    return {"status": "alive", "timestamp": datetime.now()}

@app.get("/api/v1/health/ready")
async def readiness_probe():
    """Readiness probe for Kubernetes."""
    # Check database connection
    # Check external service dependencies
    # Check resource availability
    
    checks = {
        "database": True,  # Replace with actual check
        "redis": True,     # Replace with actual check
        "disk_space": True  # Replace with actual check
    }
    
    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now()
    }

@app.get("/api/v1/metrics")
async def metrics_endpoint():
    """Custom metrics endpoint."""
    return {
        "application_metrics": {
            "total_requests": app_state.metrics["total_requests"],
            "active_jobs": app_state.metrics["active_jobs"],
            "completed_jobs": app_state.metrics["completed_jobs"],
            "failed_jobs": app_state.metrics["failed_jobs"]
        },
        "system_metrics": {
            "uptime_seconds": time.time() - app_state.start_time,
            "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
            "cpu_percent": psutil.Process().cpu_percent()
        }
    }
```

## Key Concepts Mastered

### 1. **Standalone API Architecture**
- FastAPI application structure and configuration
- RESTful API design with proper HTTP methods
- Asynchronous request handling and background tasks
- Request/response models with Pydantic validation

### 2. **Production-Ready Features**
- Authentication and authorization mechanisms
- Rate limiting and request validation
- File upload and download handling
- WebSocket real-time communication

### 3. **Deployment Strategies**
- Docker containerization and multi-stage builds
- Kubernetes deployment with health checks
- Cloud platform deployment (AWS, GCP, Azure)
- Serverless deployment patterns

### 4. **Monitoring and Observability**
- Structured logging with correlation IDs
- Prometheus metrics and health endpoints
- Load testing and performance validation
- Error handling and graceful degradation

## Troubleshooting Production Deployment

### Common Issues and Solutions

#### Issue: High memory usage
**Symptoms**: OOM kills, slow response times
**Solutions**:
- Implement proper request streaming
- Add memory limits to containers
- Use connection pooling for databases
- Monitor and profile memory usage

#### Issue: Rate limiting not working
**Symptoms**: API abuse, high server load
**Solutions**:
- Verify Redis connection for rate limiting
- Check rate limiter configuration
- Implement multiple rate limiting tiers
- Add IP-based blocking for persistent abuse

#### Issue: WebSocket connections dropping
**Symptoms**: Lost real-time updates
**Solutions**:
- Implement WebSocket heartbeat/ping
- Add connection pooling and reconnection logic
- Check load balancer WebSocket support
- Monitor WebSocket connection metrics

#### Issue: File upload failures
**Symptoms**: Large file upload timeouts
**Solutions**:
- Increase client and server timeouts
- Implement chunked upload support
- Add file validation and virus scanning
- Use cloud storage for large files

## Congratulations!

You've mastered FastAPI standalone deployment! You can now:

- ✅ **Build Production APIs** - Create robust, scalable web services
- ✅ **Handle Authentication** - Implement secure access control
- ✅ **Deploy Anywhere** - Docker, Kubernetes, cloud platforms
- ✅ **Monitor Performance** - Metrics, logging, and health checks
- ✅ **Scale Applications** - Load balancing and horizontal scaling

### What's Next?

Ready to integrate AgentMap into existing applications? Continue with:
- **[Lesson 8: FastAPI Integration](/docs/guides/learning/08-fastapi-integration)** - Add AgentMap to existing FastAPI apps

---

*🚀 **You're now equipped to deploy AgentMap workflows as production-ready web services** - scale your AI automation to serve thousands of users with enterprise-grade reliability and performance!*
