"""
FastAPI Routes

This package contains all FastAPI route definitions.
Routes should be thin controllers that delegate to services for business logic.
"""

from agentmap.deployment.http.api.routes.admin import router as admin_router

# Import routers from route modules
from agentmap.deployment.http.api.routes.execute import router as execution_router
from agentmap.deployment.http.api.routes.workflows import router as workflow_router

__all__ = [
    "execution_router",
    "workflow_router",
    "admin_router",
]
