"""
AgentMap FastAPI Integration Example
Complete e-commerce application with AI-powered features
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import logging
from datetime import datetime

# AgentMap imports
from agentmap import (
    WorkflowExecutor, 
    Agent, 
    ServiceRegistry,
    WorkflowConfig
)

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

class Order(BaseModel):
    id: int
    user_id: int
    products: List[Dict[str, Any]]
    total: float
    status: str
    created_at: datetime

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

class ContentGenerationRequest(BaseModel):
    product_id: int
    content_type: str  # "description", "marketing", "seo"
    target_audience: str
    tone: str = "professional"

# Global state (in production, use proper database and state management)
products_db = {}
orders_db = {}
_workflow_executor: Optional[WorkflowExecutor] = None

# AgentMap Integration Layer
class AgentMapIntegration:
    def __init__(self):
        self.executor: Optional[WorkflowExecutor] = None
        self.agents: Dict[str, Agent] = {}
    
    async def initialize(self, config_path: Optional[str] = None):
        """Initialize AgentMap with e-commerce specific agents."""
        try:
            # Create workflow configuration
            config = WorkflowConfig(
                agents=[
                    {
                        "name": "product_analyzer",
                        "type": "analysis",
                        "prompt": """You are a product analysis expert. Analyze product information and provide:
                        1. Category recommendations
                        2. Price optimization suggestions
                        3. Inventory alerts
                        4. Market insights""",
                        "model": "gpt-4"
                    },
                    {
                        "name": "review_sentiment",
                        "type": "sentiment",
                        "prompt": """Analyze customer reviews for sentiment, key themes, and actionable insights.
                        Provide structured feedback for product improvement.""",
                        "model": "gpt-3.5-turbo"
                    },
                    {
                        "name": "support_assistant",
                        "type": "customer_support",
                        "prompt": """You are a helpful customer support assistant. Analyze support tickets and provide:
                        1. Priority classification
                        2. Suggested responses
                        3. Escalation recommendations
                        4. Related knowledge base articles""",
                        "model": "gpt-4"
                    },
                    {
                        "name": "content_generator",
                        "type": "content",
                        "prompt": """Generate compelling e-commerce content including:
                        1. Product descriptions
                        2. Marketing copy
                        3. SEO content
                        4. Email campaigns""",
                        "model": "gpt-4"
                    },
                    {
                        "name": "order_optimizer",
                        "type": "optimization",
                        "prompt": """Analyze order patterns and provide recommendations for:
                        1. Inventory management
                        2. Cross-selling opportunities
                        3. Shipping optimization
                        4. Customer retention strategies""",
                        "model": "gpt-4"
                    }
                ],
                services=[
                    "FileService",
                    "DataProcessingService",
                    "EmailService"
                ]
            )
            
            self.executor = WorkflowExecutor(config)
            
            # Cache frequently used agents
            agent_names = ["product_analyzer", "review_sentiment", "support_assistant", 
                          "content_generator", "order_optimizer"]
            
            for agent_name in agent_names:
                try:
                    self.agents[agent_name] = await self.executor.get_agent(agent_name)
                    logger.info(f"Initialized agent: {agent_name}")
                except Exception as e:
                    logger.warning(f"Failed to initialize agent {agent_name}: {e}")
            
            logger.info("AgentMap integration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentMap: {e}")
            # Continue without AgentMap (graceful degradation)
            self.executor = None

# Global AgentMap instance
agentmap = AgentMapIntegration()

# Dependency functions
async def get_agentmap() -> AgentMapIntegration:
    """Get AgentMap integration instance."""
    return agentmap

def get_agent(agent_name: str):
    """Dependency to get specific AgentMap agent."""
    async def _get_agent(integration: AgentMapIntegration = Depends(get_agentmap)) -> Optional[Agent]:
        return integration.agents.get(agent_name)
    return _get_agent

# Security
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Simple token verification (replace with proper auth)."""
    if credentials.credentials != "demo-token":
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

# FastAPI app initialization
app = FastAPI(
    title="E-Commerce API with AgentMap",
    description="Hybrid API combining traditional e-commerce endpoints with AI-powered features",
    version="1.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize AgentMap on startup."""
    await agentmap.initialize()
    
    # Populate sample data
    products_db[1] = Product(
        id=1,
        name="Smart Wireless Headphones",
        description="High-quality wireless headphones with noise cancellation",
        price=199.99,
        category="electronics",
        inventory=50
    )

# Traditional e-commerce endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    agentmap_status = "available" if agentmap.executor else "unavailable"
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agentmap_status": agentmap_status
    }

@app.get("/products", response_model=List[Product])
async def get_products():
    """Get all products."""
    return list(products_db.values())

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    """Get specific product."""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return products_db[product_id]

# AI-Enhanced Endpoints

@app.post("/products/{product_id}/analyze")
async def analyze_product(
    product_id: int,
    analyzer: Optional[Agent] = Depends(get_agent("product_analyzer")),
    token: str = Depends(verify_token)
):
    """AI-powered product analysis."""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = products_db[product_id]
    
    if not analyzer:
        # Fallback to traditional analysis
        return {
            "analysis_type": "traditional",
            "category": product.category,
            "price_range": "medium",
            "inventory_status": "adequate" if product.inventory > 20 else "low"
        }
    
    try:
        result = await analyzer.execute({
            "product_data": product.dict(),
            "market_context": "consumer_electronics",
            "analysis_date": datetime.now().isoformat()
        })
        
        return {
            "analysis_type": "ai_powered",
            "insights": result.get("insights", {}),
            "recommendations": result.get("recommendations", []),
            "confidence_score": result.get("confidence", 0.0)
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.post("/reviews/analyze")
async def analyze_review(
    review: ReviewRequest,
    sentiment_analyzer: Optional[Agent] = Depends(get_agent("review_sentiment")),
    token: str = Depends(verify_token)
):
    """AI-powered review sentiment analysis."""
    if not sentiment_analyzer:
        # Simple fallback sentiment analysis
        score = 1.0 if review.rating >= 4 else 0.0 if review.rating <= 2 else 0.5
        return {
            "analysis_type": "rule_based",
            "sentiment": "positive" if score > 0.5 else "negative" if score < 0.5 else "neutral",
            "score": score
        }
    
    try:
        result = await sentiment_analyzer.execute({
            "review_text": review.review_text,
            "rating": review.rating,
            "product_id": review.product_id
        })
        
        return {
            "analysis_type": "ai_powered",
            "sentiment": result.get("sentiment"),
            "score": result.get("sentiment_score"),
            "themes": result.get("key_themes", []),
            "actionable_insights": result.get("insights", [])
        }
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.post("/support/tickets")
async def create_support_ticket(
    ticket: SupportTicket,
    support_agent: Optional[Agent] = Depends(get_agent("support_assistant")),
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Create support ticket with AI triage."""
    ticket_id = len(orders_db) + 1
    
    if not support_agent:
        # Traditional ticket creation
        return {
            "ticket_id": ticket_id,
            "status": "created",
            "priority": ticket.priority,
            "estimated_response": "24 hours"
        }
    
    # AI-powered ticket analysis
    background_tasks.add_task(analyze_ticket_async, ticket_id, ticket, support_agent)
    
    return {
        "ticket_id": ticket_id,
        "status": "created_with_ai_analysis",
        "message": "Ticket created. AI analysis in progress."
    }

async def analyze_ticket_async(ticket_id: int, ticket: SupportTicket, agent: Agent):
    """Background task for ticket analysis."""
    try:
        result = await agent.execute({
            "subject": ticket.subject,
            "message": ticket.message,
            "user_id": ticket.user_id,
            "priority": ticket.priority
        })
        
        # Store analysis results (in production, save to database)
        logger.info(f"Ticket {ticket_id} analysis: {result}")
        
    except Exception as e:
        logger.error(f"Background ticket analysis failed: {e}")

@app.post("/content/generate")
async def generate_content(
    request: ContentGenerationRequest,
    content_generator: Optional[Agent] = Depends(get_agent("content_generator")),
    token: str = Depends(verify_token)
):
    """AI-powered content generation for products."""
    if request.product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = products_db[request.product_id]
    
    if not content_generator:
        # Template-based fallback
        templates = {
            "description": f"High-quality {product.name} featuring excellent performance and reliability.",
            "marketing": f"Don't miss out on our amazing {product.name}! Limited time offer!",
            "seo": f"{product.name} - Best {product.category} for {request.target_audience}"
        }
        return {
            "content": templates.get(request.content_type, templates["description"]),
            "generation_method": "template"
        }
    
    try:
        result = await content_generator.execute({
            "product": product.dict(),
            "content_type": request.content_type,
            "target_audience": request.target_audience,
            "tone": request.tone
        })
        
        return {
            "content": result.get("generated_content"),
            "generation_method": "ai_powered",
            "quality_score": result.get("quality_score"),
            "alternatives": result.get("alternatives", [])
        }
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(status_code=500, detail="Content generation failed")

@app.post("/orders/optimize")
async def optimize_orders(
    optimizer: Optional[Agent] = Depends(get_agent("order_optimizer")),
    token: str = Depends(verify_token)
):
    """AI-powered order and inventory optimization."""
    if not optimizer:
        return {
            "optimization_type": "rule_based",
            "recommendations": ["Monitor inventory levels", "Review pricing strategy"]
        }
    
    try:
        # Get recent order data (simplified)
        order_data = {
            "recent_orders": list(orders_db.values())[-10:],  # Last 10 orders
            "product_inventory": {pid: p.inventory for pid, p in products_db.items()},
            "analysis_date": datetime.now().isoformat()
        }
        
        result = await optimizer.execute(order_data)
        
        return {
            "optimization_type": "ai_powered",
            "inventory_recommendations": result.get("inventory_actions", []),
            "cross_sell_opportunities": result.get("cross_sell", []),
            "shipping_optimizations": result.get("shipping", []),
            "retention_strategies": result.get("retention", [])
        }
    except Exception as e:
        logger.error(f"Order optimization failed: {e}")
        raise HTTPException(status_code=500, detail="Optimization failed")

# Batch processing endpoint
@app.post("/batch/process")
async def batch_process(
    file: UploadFile = File(...),
    process_type: str = "product_analysis",
    integration: AgentMapIntegration = Depends(get_agentmap),
    token: str = Depends(verify_token)
):
    """Batch process uploaded data through AgentMap."""
    if not integration.executor:
        raise HTTPException(status_code=503, detail="AgentMap not available")
    
    try:
        content = await file.read()
        
        # Process based on type
        if process_type == "product_analysis":
            agent = integration.agents.get("product_analyzer")
        elif process_type == "review_sentiment":
            agent = integration.agents.get("review_sentiment")
        else:
            raise HTTPException(status_code=400, detail="Invalid process type")
        
        if not agent:
            raise HTTPException(status_code=503, detail=f"Agent for {process_type} not available")
        
        result = await agent.execute({
            "batch_data": content.decode(),
            "file_name": file.filename,
            "process_type": process_type
        })
        
        return {
            "status": "processed",
            "results": result.get("batch_results", []),
            "summary": result.get("summary", {}),
            "processing_time": result.get("processing_time")
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "lesson8:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
