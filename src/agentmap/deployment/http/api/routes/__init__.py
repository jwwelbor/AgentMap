"""
FastAPI Routes

This package contains all FastAPI route definitions.
Routes should be thin controllers that delegate to services for business logic.
"""

# Import routers from route modules
from agentmap.deployment.http.api.routes.execution import router as execution_router
from agentmap.deployment.http.api.routes.workflow import router as workflow_router

__all__ = [
    "execution_router",
    "workflow_router",
]
