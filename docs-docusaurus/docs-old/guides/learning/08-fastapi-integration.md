---
sidebar_position: 9
title: "Lesson 8: FastAPI Integration"
description: Integrate AgentMap workflows into existing FastAPI applications with middleware, route configuration, and hybrid API patterns
keywords: [FastAPI integration, middleware, hybrid API, route configuration, existing applications]
---

# Lesson 8: FastAPI Integration

Ready to enhance your existing FastAPI applications with AI capabilities? In this final lesson, you'll learn to seamlessly integrate AgentMap workflows into existing FastAPI applications, creating hybrid APIs that combine traditional endpoints with AI-powered features.

## Learning Objectives

By the end of this lesson, you will:
- ✅ Integrate AgentMap into existing FastAPI applications
- ✅ Configure middleware for seamless AI workflow execution
- ✅ Design hybrid API architectures
- ✅ Implement graceful fallback mechanisms
- ✅ Build scalable integration patterns
- ✅ Create production-ready hybrid applications

## When to Use Integration vs Standalone

Choose **Integration** when you:
- Have existing FastAPI applications to enhance
- Need AI features alongside traditional endpoints
- Want gradual AI adoption in existing systems
- Require backward compatibility
- Have established authentication and middleware

Choose **Standalone** (Lesson 7) when you:
- Building new AI-first applications
- Need simple, focused AI services
- Want minimal dependencies
- Prefer microservice architectures

## Architecture Overview

```
Existing FastAPI App
├── Traditional Endpoints (/api/v1/...)
├── AgentMap Middleware
├── AI-Enhanced Endpoints (/ai/...)
├── Hybrid Endpoints (Traditional + AI)
└── Graceful Fallback System
```

## Integration Patterns

### 1. Middleware Integration

```python
from fastapi import FastAPI, Depends, Request
from agentmap import WorkflowExecutor, WorkflowConfig
import asyncio
import logging

class AgentMapMiddleware:
    def __init__(self, app: FastAPI, config_path: str = None):
        self.app = app
        self.executor: Optional[WorkflowExecutor] = None
        
    async def __call__(self, request: Request, call_next):
        # Add AgentMap context to request
        request.state.agentmap = self.executor
        response = await call_next(request)
        return response
    
    async def initialize(self):
        """Initialize AgentMap on startup."""
        try:
            config = WorkflowConfig.from_file("agentmap_config.yaml")
            self.executor = WorkflowExecutor(config)
            logging.info("AgentMap integration initialized")
        except Exception as e:
            logging.warning(f"AgentMap initialization failed: {e}")
            self.executor = None

# Add to existing app
app = FastAPI(title="My Existing App")
agentmap_middleware = AgentMapMiddleware(app)

@app.on_event("startup")
async def startup_event():
    await agentmap_middleware.initialize()

app.middleware("http")(agentmap_middleware)
```

### 2. Dependency Injection Pattern

```python
from typing import Optional
from fastapi import Depends

class AgentMapIntegration:
    def __init__(self):
        self.executor: Optional[WorkflowExecutor] = None
        self.agents: Dict[str, Agent] = {}
    
    async def get_agent(self, name: str) -> Optional[Agent]:
        if not self.executor:
            return None
        return self.agents.get(name)

# Global instance
agentmap = AgentMapIntegration()

# Dependency functions
async def get_agentmap() -> AgentMapIntegration:
    return agentmap

def require_agent(agent_name: str):
    async def _get_agent(
        integration: AgentMapIntegration = Depends(get_agentmap)
    ) -> Agent:
        agent = await integration.get_agent(agent_name)
        if not agent:
            raise HTTPException(
                status_code=503, 
                detail=f"AI agent '{agent_name}' not available"
            )
        return agent
    return _get_agent

# Usage in endpoints
@app.post("/analyze/sentiment")
async def analyze_sentiment(
    text: str,
    agent: Agent = Depends(require_agent("sentiment_analyzer"))
):
    result = await agent.execute({"text": text})
    return {"sentiment": result.get("sentiment")}
```

### 3. Hybrid Endpoint Pattern

```python
@app.get("/products/{product_id}")
async def get_product_enhanced(
    product_id: int,
    include_ai_insights: bool = False,
    analyzer: Optional[Agent] = Depends(get_agent("product_analyzer"))
):
    # Traditional database lookup
    product = await get_product_from_db(product_id)
    
    response = {
        "product": product,
        "ai_insights": None
    }
    
    # Add AI insights if requested and available
    if include_ai_insights and analyzer:
        try:
            insights = await analyzer.execute({
                "product_data": product,
                "analysis_type": "detailed"
            })
            response["ai_insights"] = insights
        except Exception as e:
            # Graceful degradation
            response["ai_insights"] = {"error": "Analysis unavailable"}
    
    return response
```

## Complete Integration Example

Let's build a complete e-commerce API that enhances existing functionality with AI:

### Step 1: Download the Integration Example

```python title="lesson8.py"
# Download this complete integration example
```

<details>
<summary>📁 View Complete Integration Code (lesson8.py)</summary>

```python
"""
Complete FastAPI + AgentMap Integration Example
E-commerce API with AI-enhanced features
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import logging
from datetime import datetime

# AgentMap imports
from agentmap import WorkflowExecutor, Agent, WorkflowConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str
    inventory: int

class ReviewRequest(BaseModel):
    product_id: int
    user_id: int
    review_text: str
    rating: int

class SupportTicket(BaseModel):
    user_id: int
    subject: str
    message: str
    priority: str = "normal"

# AgentMap Integration Layer
class AgentMapIntegration:
    def __init__(self):
        self.executor: Optional[WorkflowExecutor] = None
        self.agents: Dict[str, Agent] = {}
    
    async def initialize(self):
        """Initialize AgentMap with e-commerce agents."""
        try:
            config = WorkflowConfig(
                agents=[
                    {
                        "name": "product_analyzer",
                        "type": "analysis",
                        "prompt": "Analyze products for insights and recommendations",
                        "model": "gpt-4"
                    },
                    {
                        "name": "review_sentiment",
                        "type": "sentiment",
                        "prompt": "Analyze review sentiment and extract themes",
                        "model": "gpt-3.5-turbo"
                    },
                    {
                        "name": "support_assistant",
                        "type": "customer_support",
                        "prompt": "Analyze support tickets and provide recommendations",
                        "model": "gpt-4"
                    }
                ]
            )
            
            self.executor = WorkflowExecutor(config)
            
            # Cache agents
            for agent_name in ["product_analyzer", "review_sentiment", "support_assistant"]:
                try:
                    self.agents[agent_name] = await self.executor.get_agent(agent_name)
                    logger.info(f"Initialized agent: {agent_name}")
                except Exception as e:
                    logger.warning(f"Failed to initialize agent {agent_name}: {e}")
            
        except Exception as e:
            logger.error(f"AgentMap initialization failed: {e}")
            self.executor = None

# Global instances
agentmap = AgentMapIntegration()
products_db = {}

# Dependencies
async def get_agentmap() -> AgentMapIntegration:
    return agentmap

def get_agent(agent_name: str):
    async def _get_agent(
        integration: AgentMapIntegration = Depends(get_agentmap)
    ) -> Optional[Agent]:
        return integration.agents.get(agent_name)
    return _get_agent

# Security
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != "demo-token":
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

# FastAPI app
app = FastAPI(
    title="E-Commerce API with AgentMap",
    description="Hybrid API with traditional and AI-powered endpoints",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await agentmap.initialize()
    
    # Sample data
    products_db[1] = Product(
        id=1,
        name="Smart Wireless Headphones",
        description="High-quality wireless headphones",
        price=199.99,
        category="electronics",
        inventory=50
    )

# Traditional endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agentmap_status": "available" if agentmap.executor else "unavailable"
    }

@app.get("/products", response_model=List[Product])
async def get_products():
    return list(products_db.values())

# AI-enhanced endpoints
@app.post("/products/{product_id}/analyze")
async def analyze_product(
    product_id: int,
    analyzer: Optional[Agent] = Depends(get_agent("product_analyzer")),
    token: str = Depends(verify_token)
):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = products_db[product_id]
    
    if not analyzer:
        # Fallback analysis
        return {
            "analysis_type": "basic",
            "category": product.category,
            "price_range": "medium"
        }
    
    try:
        result = await analyzer.execute({
            "product_data": product.dict()
        })
        
        return {
            "analysis_type": "ai_powered",
            "insights": result.get("insights", {}),
            "recommendations": result.get("recommendations", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.post("/reviews/analyze")
async def analyze_review(
    review: ReviewRequest,
    analyzer: Optional[Agent] = Depends(get_agent("review_sentiment")),
    token: str = Depends(verify_token)
):
    if not analyzer:
        # Simple sentiment based on rating
        sentiment = "positive" if review.rating >= 4 else "negative" if review.rating <= 2 else "neutral"
        return {"sentiment": sentiment, "confidence": 0.7}
    
    try:
        result = await analyzer.execute({
            "review_text": review.review_text,
            "rating": review.rating
        })
        
        return {
            "sentiment": result.get("sentiment"),
            "confidence": result.get("confidence"),
            "themes": result.get("themes", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Analysis failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("lesson8:app", host="0.0.0.0", port=8000, reload=True)
```

</details>

### Step 2: Configuration Setup

Create a configuration file for your AgentMap integration:

```yaml title="agentmap_config.yaml"
agents:
  - name: product_analyzer
    type: analysis
    prompt: |
      You are a product analysis expert. Analyze product information and provide:
      1. Category optimization suggestions
      2. Price recommendations
      3. Inventory insights
      4. Market positioning advice
    model: gpt-4
    
  - name: review_sentiment
    type: sentiment
    prompt: |
      Analyze customer reviews for:
      1. Overall sentiment (positive/negative/neutral)
      2. Key themes and topics
      3. Specific product feedback
      4. Actionable insights for improvement
    model: gpt-3.5-turbo
    
  - name: support_assistant
    type: customer_support
    prompt: |
      Analyze customer support tickets and provide:
      1. Priority classification
      2. Category assignment
      3. Suggested response templates
      4. Escalation recommendations
    model: gpt-4

services:
  - FileService
  - DataProcessingService
  - EmailService
```

### Step 3: Graceful Fallback Implementation

```python
class GracefulFallback:
    @staticmethod
    def product_analysis_fallback(product: Product) -> dict:
        """Traditional product analysis when AI is unavailable."""
        return {
            "analysis_type": "rule_based",
            "category": product.category,
            "price_range": "medium" if 50 <= product.price <= 200 else "high" if product.price > 200 else "low",
            "inventory_status": "adequate" if product.inventory > 20 else "low",
            "recommendations": [
                "Monitor competitor pricing",
                "Track inventory levels",
                "Analyze customer feedback"
            ]
        }
    
    @staticmethod
    def sentiment_analysis_fallback(review: ReviewRequest) -> dict:
        """Simple sentiment analysis based on rating."""
        if review.rating >= 4:
            sentiment = "positive"
        elif review.rating <= 2:
            sentiment = "negative" 
        else:
            sentiment = "neutral"
            
        return {
            "analysis_type": "rule_based",
            "sentiment": sentiment,
            "confidence": 0.7,
            "method": "rating_based"
        }

# Usage in endpoints
@app.post("/products/{product_id}/analyze")
async def analyze_product_with_fallback(
    product_id: int,
    analyzer: Optional[Agent] = Depends(get_agent("product_analyzer"))
):
    product = products_db[product_id]
    
    if analyzer:
        try:
            result = await analyzer.execute({"product_data": product.dict()})
            return {"analysis_type": "ai_powered", **result}
        except Exception as e:
            logger.warning(f"AI analysis failed, using fallback: {e}")
    
    # Fallback to traditional analysis
    return GracefulFallback.product_analysis_fallback(product)
```

## Integration Best Practices

### 1. Startup and Health Checks

```python
@app.on_event("startup")
async def startup_event():
    """Initialize services with proper error handling."""
    # Initialize database connections
    await init_database()
    
    # Initialize AgentMap (non-blocking)
    try:
        await agentmap.initialize()
        logger.info("AgentMap integration successful")
    except Exception as e:
        logger.warning(f"AgentMap initialization failed: {e}")
        # Application continues without AI features

@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check including AI status."""
    health_status = {
        "app": "healthy",
        "database": await check_database_health(),
        "agentmap": {
            "status": "available" if agentmap.executor else "unavailable",
            "agents": list(agentmap.agents.keys()) if agentmap.agents else []
        }
    }
    
    overall_healthy = all([
        health_status["app"] == "healthy",
        health_status["database"] == "healthy"
        # Note: AgentMap is optional, don't fail health check if unavailable
    ])
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "details": health_status
    }
```

### 2. Background Processing

```python
from fastapi import BackgroundTasks

@app.post("/support/tickets")
async def create_support_ticket(
    ticket: SupportTicket,
    background_tasks: BackgroundTasks,
    support_agent: Optional[Agent] = Depends(get_agent("support_assistant"))
):
    # Create ticket immediately
    ticket_id = await create_ticket_in_db(ticket)
    
    # Process with AI in background
    if support_agent:
        background_tasks.add_task(
            process_ticket_with_ai,
            ticket_id,
            ticket,
            support_agent
        )
    
    return {
        "ticket_id": ticket_id,
        "status": "created",
        "ai_processing": support_agent is not None
    }

async def process_ticket_with_ai(ticket_id: int, ticket: SupportTicket, agent: Agent):
    """Background AI processing of support ticket."""
    try:
        analysis = await agent.execute({
            "subject": ticket.subject,
            "message": ticket.message,
            "priority": ticket.priority
        })
        
        await update_ticket_analysis(ticket_id, analysis)
        logger.info(f"AI analysis completed for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Background AI processing failed for ticket {ticket_id}: {e}")
```

### 3. Route Organization

```python
from fastapi import APIRouter

# Traditional API routes
api_router = APIRouter(prefix="/api/v1")

@api_router.get("/products")
async def get_products_traditional():
    """Traditional product listing."""
    return await get_products_from_db()

# AI-enhanced routes  
ai_router = APIRouter(prefix="/ai/v1")

@ai_router.post("/products/analyze")
async def analyze_products_batch(
    products: List[int],
    analyzer: Agent = Depends(require_agent("product_analyzer"))
):
    """Batch AI analysis of products."""
    results = []
    for product_id in products:
        result = await analyzer.execute({"product_id": product_id})
        results.append({"product_id": product_id, "analysis": result})
    return {"batch_results": results}

# Include routers
app.include_router(api_router, tags=["traditional"])
app.include_router(ai_router, tags=["ai-powered"])
```

## Testing Your Integration

### 1. Basic Integration Test

```bash
# Test traditional endpoint
curl http://localhost:8000/products

# Test AI-enhanced endpoint
curl -X POST "http://localhost:8000/products/1/analyze" \
  -H "Authorization: Bearer demo-token"

# Test health check
curl http://localhost:8000/health/detailed
```

### 2. Graceful Degradation Test

```python
# Simulate AgentMap failure
@app.post("/admin/simulate-ai-failure")
async def simulate_ai_failure():
    """Admin endpoint to test graceful degradation."""
    agentmap.executor = None
    agentmap.agents.clear()
    return {"message": "AI services disabled for testing"}

@app.post("/admin/restore-ai")
async def restore_ai():
    """Admin endpoint to restore AI services."""
    await agentmap.initialize()
    return {"message": "AI services restored"}
```

### 3. Load Testing

```python
import asyncio
import aiohttp
import time

async def test_hybrid_load():
    """Test both traditional and AI endpoints under load."""
    async with aiohttp.ClientSession() as session:
        # Test traditional endpoints
        traditional_tasks = [
            session.get("http://localhost:8000/products")
            for _ in range(100)
        ]
        
        # Test AI endpoints  
        ai_tasks = [
            session.post(
                "http://localhost:8000/products/1/analyze",
                headers={"Authorization": "Bearer demo-token"}
            )
            for _ in range(20)  # Fewer AI calls due to higher latency
        ]
        
        start_time = time.time()
        
        # Run concurrently
        results = await asyncio.gather(
            *traditional_tasks, 
            *ai_tasks, 
            return_exceptions=True
        )
        
        end_time = time.time()
        
        print(f"Total time: {end_time - start_time:.2f}s")
        print(f"Success rate: {len([r for r in results if not isinstance(r, Exception)]) / len(results) * 100:.1f}%")

# Run: asyncio.run(test_hybrid_load())
```

## Production Deployment

### 1. Environment Configuration

```python
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # App settings
    app_name: str = "E-Commerce API"
    debug: bool = False
    
    # Database
    database_url: str
    
    # AgentMap settings
    agentmap_config_path: str = "config/agentmap.yaml"
    agentmap_enabled: bool = True
    agentmap_timeout: float = 30.0
    
    # AI fallback settings
    enable_fallback: bool = True
    fallback_cache_ttl: int = 3600
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 2. Docker Configuration

```dockerfile title="Dockerfile"
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "lesson8:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Production Configuration

```yaml title="docker-compose.yml"
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/ecommerce
      - AGENTMAP_ENABLED=true
      - ENABLE_FALLBACK=true
    depends_on:
      - db
      - redis
    
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ecommerce
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7-alpine
    
volumes:
  postgres_data:
```

## Performance Optimization

### 1. Agent Caching

```python
import asyncio
from datetime import datetime, timedelta

class AgentCache:
    def __init__(self, ttl_minutes: int = 30):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    async def get_or_create_agent(self, name: str, executor: WorkflowExecutor) -> Agent:
        now = datetime.now()
        
        if name in self.cache:
            agent, timestamp = self.cache[name]
            if now - timestamp < self.ttl:
                return agent
        
        # Create new agent
        agent = await executor.get_agent(name)
        self.cache[name] = (agent, now)
        return agent

# Use in integration
agent_cache = AgentCache(ttl_minutes=60)

async def get_cached_agent(name: str) -> Optional[Agent]:
    if not agentmap.executor:
        return None
    return await agent_cache.get_or_create_agent(name, agentmap.executor)
```

### 2. Response Caching

```python
from functools import wraps
import json
import hashlib

def cache_ai_response(ttl_seconds: int = 300):
    def decorator(func):
        cache = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from arguments
            cache_key = hashlib.md5(
                json.dumps(str(args) + str(kwargs), sort_keys=True).encode()
            ).hexdigest()
            
            # Check cache
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            # Execute and cache
            result = await func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            return result
            
        return wrapper
    return decorator

@cache_ai_response(ttl_seconds=600)  # Cache for 10 minutes
async def cached_product_analysis(product_data: dict, agent: Agent):
    return await agent.execute(product_data)
```

## Monitoring and Observability

### 1. Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
ai_requests_total = Counter('ai_requests_total', 'Total AI requests', ['agent_name', 'status'])
ai_request_duration = Histogram('ai_request_duration_seconds', 'AI request duration')
ai_agents_available = Gauge('ai_agents_available', 'Number of available AI agents')

async def execute_with_metrics(agent: Agent, data: dict, agent_name: str):
    """Execute agent with metrics collection."""
    start_time = time.time()
    
    try:
        result = await agent.execute(data)
        ai_requests_total.labels(agent_name=agent_name, status='success').inc()
        return result
    except Exception as e:
        ai_requests_total.labels(agent_name=agent_name, status='error').inc()
        raise
    finally:
        ai_request_duration.observe(time.time() - start_time)

# Update agent availability
@app.on_event("startup")
async def update_metrics():
    ai_agents_available.set(len(agentmap.agents))
```

### 2. Logging Configuration

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def log_ai_request(self, agent_name: str, request_data: dict, response_data: dict = None, error: str = None):
        """Log AI requests in structured format."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "ai_request",
            "agent_name": agent_name,
            "request_id": getattr(request_data, 'request_id', None),
            "status": "error" if error else "success",
            "error": error,
            "duration_ms": getattr(response_data, 'duration_ms', None)
        }
        
        if error:
            self.logger.error(json.dumps(log_entry))
        else:
            self.logger.info(json.dumps(log_entry))

ai_logger = StructuredLogger("agentmap.integration")
```

## Advanced Integration Patterns

### 1. Event-Driven Integration

```python
from typing import Callable
import asyncio

class EventDrivenIntegration:
    def __init__(self):
        self.event_handlers = {}
    
    def on_event(self, event_type: str):
        def decorator(func: Callable):
            self.event_handlers[event_type] = func
            return func
        return decorator
    
    async def emit_event(self, event_type: str, data: dict):
        if event_type in self.event_handlers:
            await self.event_handlers[event_type](data)

events = EventDrivenIntegration()

@events.on_event("product_created")
async def analyze_new_product(data: dict):
    """Automatically analyze new products."""
    if analyzer := agentmap.agents.get("product_analyzer"):
        analysis = await analyzer.execute(data)
        await store_product_analysis(data["product_id"], analysis)

# Trigger events in endpoints
@app.post("/products")
async def create_product(product: Product):
    saved_product = await save_product(product)
    
    # Trigger AI analysis
    await events.emit_event("product_created", {
        "product_id": saved_product.id,
        "product_data": saved_product.dict()
    })
    
    return saved_product
```

### 2. Multi-Model Integration

```python
class MultiModelIntegration:
    def __init__(self):
        self.model_configs = {
            "fast": {"model": "gpt-3.5-turbo", "timeout": 10},
            "accurate": {"model": "gpt-4", "timeout": 30},
            "specialized": {"model": "gpt-4-turbo", "timeout": 45}
        }
    
    async def execute_with_strategy(self, agent_name: str, data: dict, strategy: str = "fast"):
        """Execute with different model strategies."""
        config = self.model_configs.get(strategy, self.model_configs["fast"])
        
        # Get agent with specific model config
        agent = await self.get_agent_with_config(agent_name, config)
        
        try:
            return await asyncio.wait_for(
                agent.execute(data),
                timeout=config["timeout"]
            )
        except asyncio.TimeoutError:
            if strategy != "fast":
                # Fallback to faster model
                return await self.execute_with_strategy(agent_name, data, "fast")
            raise

multi_model = MultiModelIntegration()

@app.post("/analyze/advanced")
async def advanced_analysis(
    data: dict,
    strategy: str = "fast"  # "fast", "accurate", "specialized"
):
    """Analysis with different model strategies."""
    result = await multi_model.execute_with_strategy(
        "product_analyzer", 
        data, 
        strategy
    )
    return {"strategy_used": strategy, "result": result}
```

## Summary

In this lesson, you've learned to:

✅ **Integrate AgentMap into existing FastAPI applications** using middleware and dependency injection

✅ **Build hybrid APIs** that combine traditional endpoints with AI-powered features

✅ **Implement graceful fallback mechanisms** for robust production deployments

✅ **Design scalable integration patterns** for enterprise applications

✅ **Create production-ready configurations** with monitoring and observability

✅ **Master advanced patterns** like event-driven integration and multi-model strategies

### Key Takeaways

1. **Gradual Enhancement**: Start with basic integration and gradually add AI features
2. **Graceful Degradation**: Always provide fallback mechanisms when AI services are unavailable
3. **Performance Optimization**: Use caching, background processing, and appropriate timeouts
4. **Monitoring**: Implement comprehensive logging and metrics for production visibility
5. **Flexibility**: Design integrations that can adapt to changing requirements

### Next Steps

🎯 **Production Deployment**: Deploy your hybrid application to production with proper monitoring

🔄 **Continuous Integration**: Set up CI/CD pipelines that test both traditional and AI features

📈 **Scaling**: Implement horizontal scaling patterns for high-traffic applications

🔐 **Security**: Add comprehensive authentication, authorization, and input validation

🚀 **Advanced Features**: Explore streaming responses, real-time AI, and advanced orchestration patterns

Congratulations! You've completed the AgentMap Learning Guide and are now equipped to build sophisticated, production-ready applications that seamlessly blend traditional APIs with cutting-edge AI capabilities.

## Practice Exercises

1. **Integration Challenge**: Add AgentMap to an existing FastAPI project
2. **Fallback Testing**: Implement and test graceful degradation scenarios
3. **Performance Optimization**: Add caching and background processing
4. **Monitoring Setup**: Implement metrics collection and structured logging
5. **Advanced Patterns**: Build an event-driven AI integration system

Ready to revolutionize your applications with AI? Start integrating! 🚀
