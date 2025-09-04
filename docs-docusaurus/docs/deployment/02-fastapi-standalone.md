---
sidebar_position: 6
title: FastAPI Standalone Deployment
description: Complete guide to deploying AgentMap workflows as a standalone FastAPI web service with automatic documentation and monitoring
keywords: [FastAPI deployment, web API, REST API, microservice, standalone service, HTTP endpoints]
---

# FastAPI Standalone Deployment

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>FastAPI Standalone</strong></span>
</div>

Deploy AgentMap workflows as a standalone FastAPI web service, providing HTTP endpoints for workflow execution with automatic documentation, monitoring, and production-ready features.

## Quick Start

### 1. Basic FastAPI Service

```python
# main.py
from agentmap.services.fastapi import AgentMapAPI

# Create standalone service
app = AgentMapAPI(
    csv_file="workflows.csv",
    title="My Workflow API",
    description="AgentMap workflows exposed as HTTP API",
    version="1.0.0"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Run the Service

```bash
# Install FastAPI dependencies
pip install agentmap[fastapi]

# Start the service
python main.py

# Or use uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 4. Execute Workflows

```bash
# Execute a workflow via HTTP
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_name": "MyWorkflow",
    "initial_state": {"input": "Hello World"}
  }'
```

## Service Configuration

### 🏗️ Advanced Service Setup

```python
# main.py
from agentmap.services.fastapi import AgentMapAPI
from agentmap.config import AgentMapConfig

# Custom configuration
config = AgentMapConfig(
    csv_path="./workflows/",
    custom_agents_path="./custom_agents/",
    log_level="INFO",
    enable_metrics=True,
    enable_caching=True
)

# Create service with custom configuration
app = AgentMapAPI(
    config=config,
    title="Production Workflow API",
    description="Enterprise AgentMap workflow execution service",
    version="2.0.0",
    
    # API Configuration
    enable_docs=True,
    enable_metrics=True,
    enable_health_checks=True,
    
    # Security
    require_api_key=True,
    allowed_origins=["https://myapp.com"],
    
    # Performance
    max_concurrent_executions=10,
    request_timeout=300,
    enable_response_compression=True
)

# Add custom middleware
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        workers=4,  # Production: multiple workers
        access_log=True,
        log_level="info"
    )
```

### 🔧 Environment Configuration

```bash
# .env file
AGENTMAP_CSV_PATH=./workflows/
AGENTMAP_CUSTOM_AGENTS_PATH=./custom_agents/
AGENTMAP_LOG_LEVEL=INFO
AGENTMAP_API_KEY=your-secure-api-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# Security
AGENTMAP_REQUIRE_API_KEY=true
AGENTMAP_ALLOWED_ORIGINS=https://myapp.com,https://dashboard.myapp.com

# Performance
AGENTMAP_MAX_CONCURRENT=10
AGENTMAP_REQUEST_TIMEOUT=300
AGENTMAP_ENABLE_CACHE=true
AGENTMAP_CACHE_TTL=3600

# Monitoring
AGENTMAP_ENABLE_METRICS=true
AGENTMAP_METRICS_PORT=9090
```

### 📊 Production Configuration

```python
# production.py
import os
from agentmap.services.fastapi import AgentMapAPI
from agentmap.config import AgentMapConfig

# Production configuration
config = AgentMapConfig(
    csv_path=os.getenv("AGENTMAP_CSV_PATH", "/app/workflows/"),
    log_level=os.getenv("AGENTMAP_LOG_LEVEL", "WARNING"),
    enable_metrics=True,
    enable_caching=True,
    cache_ttl=int(os.getenv("AGENTMAP_CACHE_TTL", "3600")),
    
    # Database configuration (if using persistent storage)
    database_url=os.getenv("DATABASE_URL"),
    redis_url=os.getenv("REDIS_URL"),
    
    # LLM Configuration
    llm_providers={
        "openai": {"api_key": os.getenv("OPENAI_API_KEY")},
        "anthropic": {"api_key": os.getenv("ANTHROPIC_API_KEY")}
    }
)

# Production service
app = AgentMapAPI(
    config=config,
    title="Production AgentMap API",
    description="Scalable workflow execution service",
    version="2.0.0",
    
    # Security
    require_api_key=True,
    api_key=os.getenv("AGENTMAP_API_KEY"),
    allowed_origins=os.getenv("AGENTMAP_ALLOWED_ORIGINS", "").split(","),
    
    # Performance
    max_concurrent_executions=int(os.getenv("AGENTMAP_MAX_CONCURRENT", "20")),
    request_timeout=int(os.getenv("AGENTMAP_REQUEST_TIMEOUT", "600")),
    enable_response_compression=True,
    
    # Features
    enable_docs=os.getenv("AGENTMAP_ENABLE_DOCS", "false").lower() == "true",
    enable_metrics=True,
    enable_health_checks=True,
    enable_audit_logging=True
)

# Add production middleware
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log successful response
        logger.info(f"Response: {response.status_code} ({duration:.3f}s)")
        response.headers["X-Process-Time"] = str(duration)
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed: {str(e)} ({duration:.3f}s)")
        
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": str(uuid.uuid4())}
        )

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Comprehensive health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "uptime": time.time() - start_time,
        "workflows_loaded": len(app.get_available_graphs()),
        "agents_available": app.agent_registry.count(),
        "cache_status": "enabled" if config.enable_caching else "disabled"
    }
```

## API Endpoints

### 🚀 Core Endpoints

**Execute Workflow**:
```http
POST /execute
Content-Type: application/json

{
  "graph_name": "MyWorkflow",
  "initial_state": {
    "input": "process this data",
    "config": {"temperature": 0.7}
  },
  "options": {
    "timeout": 300,
    "enable_streaming": false,
    "return_intermediate_states": false
  }
}
```

**Response**:
```json
{
  "success": true,
  "execution_id": "exec_12345",
  "graph_name": "MyWorkflow",
  "result": {
    "output": "processed result",
    "final_state": {"status": "completed"}
  },
  "execution_time": 2.34,
  "nodes_executed": 5,
  "timestamp": "2025-07-04T10:30:00Z"
}
```

**List Available Workflows**:
```http
GET /workflows
```

```json
{
  "workflows": [
    {
      "name": "DataProcessing",
      "description": "Process and analyze data",
      "nodes": 8,
      "estimated_time": "2-5 minutes"
    },
    {
      "name": "CustomerOnboarding", 
      "description": "Automated customer onboarding flow",
      "nodes": 12,
      "estimated_time": "30-60 seconds"
    }
  ]
}
```

**Get Workflow Details**:
```http
GET /workflows/{workflow_name}
```

```json
{
  "name": "DataProcessing",
  "description": "Process and analyze data",
  "nodes": [
    {
      "name": "input_validation",
      "agent_type": "ValidationAgent",
      "description": "Validate input data",
      "required_inputs": ["data", "schema"],
      "output": "validated_data"
    }
  ],
  "execution_stats": {
    "average_duration": 180.5,
    "success_rate": 0.95,
    "last_execution": "2025-07-04T09:15:00Z"
  }
}
```

### 📊 Management Endpoints

**Execution Status**:
```http
GET /executions/{execution_id}
```

**Execution History**:
```http
GET /executions?limit=10&offset=0&status=completed
```

**Validate Workflow**:
```http
POST /validate
{
  "csv_content": "graph_name,node_nameagent_type,..."
}
```

**System Metrics**:
```http
GET /metrics
```

```json
{
  "uptime": 86400,
  "total_executions": 1250,
  "active_executions": 3,
  "average_response_time": 2.1,
  "error_rate": 0.02,
  "workflows": {
    "DataProcessing": {"executions": 800, "avg_time": 180.5},
    "CustomerOnboarding": {"executions": 450, "avg_time": 45.2}
  }
}
```

## Production Deployment

### 🐳 Docker Deployment

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
WORKDIR /app
COPY . .

# Create non-root user
RUN useradd -m -u 1000 agentmap && chown -R agentmap:agentmap /app
USER agentmap

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**requirements.txt**:
```txt
agentmap[fastapi]>=2.0.0
uvicorn[standard]>=0.20.0
gunicorn>=20.1.0
redis>=4.5.0
psycopg2-binary>=2.9.0
prometheus-client>=0.16.0
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  agentmap-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/agentmap
      - REDIS_URL=redis://redis:6379
      - AGENTMAP_LOG_LEVEL=INFO
      - AGENTMAP_ENABLE_METRICS=true
    volumes:
      - ./workflows:/app/workflows:ro
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: agentmap
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    depends_on:
      - agentmap-api
    restart: unless-stopped

volumes:
  postgres_data:
```

### ☁️ Cloud Deployment

**AWS ECS Task Definition**:
```json
{
  "family": "agentmap-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "agentmap-api",
      "image": "your-repo/agentmap-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "AGENTMAP_LOG_LEVEL", "value": "INFO"},
        {"name": "AGENTMAP_ENABLE_METRICS", "value": "true"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agentmap-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

**Kubernetes Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap-api
  labels:
    app: agentmap-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentmap-api
  template:
    metadata:
      labels:
        app: agentmap-api
    spec:
      containers:
      - name: agentmap-api
        image: your-repo/agentmap-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agentmap-secrets
              key: database-url
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: agentmap-api-service
spec:
  selector:
    app: agentmap-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 🔄 Load Balancing & Scaling

**Nginx Configuration**:
```nginx
upstream agentmap_backend {
    server agentmap-api-1:8000;
    server agentmap-api-2:8000;
    server agentmap-api-3:8000;
}

server {
    listen 80;
    server_name api.yourcompany.com;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Proxy settings
    location / {
        proxy_pass http://agentmap_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://agentmap_backend/health;
        access_log off;
    }

    # Static files
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**Auto-scaling Configuration (K8s HPA)**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentmap-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentmap-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

## Monitoring & Observability

### 📊 Metrics Integration

**Prometheus Configuration**:
```python
# main.py
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Metrics
execution_counter = Counter('agentmap_executions_total', 'Total executions', ['graph_name', 'status'])
execution_duration = Histogram('agentmap_execution_duration_seconds', 'Execution duration', ['graph_name'])

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path.startswith("/execute"):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        graph_name = request.json().get('graph_name', 'unknown') if hasattr(request, 'json') else 'unknown'
        status = 'success' if 200 <= response.status_code < 300 else 'error'
        
        execution_counter.labels(graph_name=graph_name, status=status).inc()
        execution_duration.labels(graph_name=graph_name).observe(duration)
        
        return response
    else:
        return await call_next(request)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")
```

### 🔍 Logging Configuration

```python
# logging_config.py
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s", "execution_id": "%(execution_id)s"}',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'json',
            'filename': '/app/logs/agentmap.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        },
    },
    'loggers': {
        'agentmap': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False
        },
        'uvicorn': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

## Security Best Practices

### 🔐 Authentication & Authorization

```python
# security.py
from fastapi import HTTPException, Depends, Header
from fastapi.security import APIKeyHeader
import jwt
from datetime import datetime, timedelta

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != os.getenv("AGENTMAP_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# JWT token authentication
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

async def verify_jwt_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply security to endpoints
@app.post("/execute", dependencies=[Depends(verify_api_key)])
async def execute_workflow(request: ExecuteRequest):
    # Secured endpoint
    pass
```

### 🛡️ Input Validation & Sanitization

```python
# validation.py
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional

class ExecuteRequest(BaseModel):
    graph_name: str = Field(..., regex="^[a-zA-Z0-9_-]+$", max_length=100)
    initial_state: Dict[str, Any] = Field(..., max_length=10000)
    options: Optional[Dict[str, Any]] = Field(default={}, max_length=1000)
    
    @validator('graph_name')
    def validate_graph_name(cls, v):
        # Additional validation logic
        if v.startswith('_'):
            raise ValueError('Graph name cannot start with underscore')
        return v
    
    @validator('initial_state')
    def validate_initial_state(cls, v):
        # Prevent code injection
        if any(isinstance(value, str) and 'exec(' in value for value in v.values()):
            raise ValueError('Potentially dangerous content detected')
        return v

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/execute")
@limiter.limit("10/minute")
async def execute_workflow(request: Request, execute_request: ExecuteRequest):
    # Rate-limited endpoint
    pass
```

## Testing

### 🧪 Unit Tests

```python
# test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_workflows():
    response = client.get("/workflows")
    assert response.status_code == 200
    assert "workflows" in response.json()

def test_execute_workflow():
    response = client.post("/execute", json={
        "graph_name": "TestWorkflow",
        "initial_state": {"input": "test"}
    })
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_invalid_graph_name():
    response = client.post("/execute", json={
        "graph_name": "Invalid/Graph",
        "initial_state": {"input": "test"}
    })
    assert response.status_code == 422  # Validation error

def test_api_key_required():
    # Test without API key
    response = client.post("/execute", json={
        "graph_name": "TestWorkflow",
        "initial_state": {"input": "test"}
    })
    assert response.status_code == 401
```

### 🔄 Integration Tests

```python
# test_integration.py
import pytest
import asyncio
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_concurrent_executions():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        tasks = []
        for i in range(5):
            task = ac.post("/execute", json={
                "graph_name": "TestWorkflow",
                "initial_state": {"input": f"test_{i}"}
            })
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.status_code == 200
            assert response.json()["success"] == True

@pytest.mark.asyncio
async def test_workflow_execution_end_to_end():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Test complete workflow execution
        response = await ac.post("/execute", json={
            "graph_name": "DataProcessing",
            "initial_state": {
                "input_data": "sample data",
                "config": {"temperature": 0.7}
            }
        })
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] == True
        assert "execution_id" in result
        assert "result" in result
        assert result["execution_time"] > 0
```

### 🚀 Load Testing

```python
# load_test.py
import asyncio
import aiohttp
import time
from statistics import mean, median

async def execute_workflow(session, graph_name, input_data):
    start_time = time.time()
    
    async with session.post("/execute", json={
        "graph_name": graph_name,
        "initial_state": {"input": input_data}
    }) as response:
        result = await response.json()
        duration = time.time() - start_time
        
        return {
            "success": response.status == 200,
            "duration": duration,
            "result": result
        }

async def load_test(concurrent_users=10, requests_per_user=10):
    async with aiohttp.ClientSession("http://localhost:8000") as session:
        tasks = []
        
        for user in range(concurrent_users):
            for request in range(requests_per_user):
                task = execute_workflow(session, "TestWorkflow", f"user_{user}_req_{request}")
                tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        durations = [r["duration"] for r in successful]
        
        print(f"Total requests: {len(results)}")
        print(f"Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
        print(f"Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
        
        if durations:
            print(f"Average response time: {mean(durations):.3f}s")
            print(f"Median response time: {median(durations):.3f}s")
            print(f"Min response time: {min(durations):.3f}s")
            print(f"Max response time: {max(durations):.3f}s")

if __name__ == "__main__":
    asyncio.run(load_test(concurrent_users=20, requests_per_user=50))
```

## Next Steps

- **[FastAPI Integration](./fastapi-integration)**: Integrate with existing applications
- **[Configuration Reference](./configuration)**: Advanced configuration options
- **[Monitoring Guide](./monitoring)**: Production monitoring and observability
- **[Performance Tuning](./performance)**: Optimization best practices
- **[Security Guide](./security)**: Comprehensive security implementation

## Related Resources

- **[CLI Deployment](./cli-deployment)**: Command-line deployment option
- **[Example Workflows](/docs/templates/)**: Real-world usage patterns
- **[API Documentation](/docs/reference/api)**: Complete API reference
- **[Troubleshooting](./troubleshooting)**: Common issues and solutions

---

**Quick Links:**
- [Deployment Overview](./index) | [CLI Deployment](./cli-deployment) | [Integration Guide](./fastapi-integration)
- [Configuration](./configuration) | [Monitoring](./monitoring) | [Troubleshooting](./troubleshooting)
