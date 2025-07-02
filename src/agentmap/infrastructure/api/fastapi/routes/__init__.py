"""
FastAPI Routes

This package contains all FastAPI route definitions.
Routes should be thin controllers that delegate to services for business logic.
"""

# Import routers from route modules
from agentmap.infrastructure.api.fastapi.routes.execution import (
    router as execution_router,
)
from agentmap.infrastructure.api.fastapi.routes.graph import router as graph_router
from agentmap.infrastructure.api.fastapi.routes.info import router as info_router
from agentmap.infrastructure.api.fastapi.routes.validation import (
    router as validation_router,
)
from agentmap.infrastructure.api.fastapi.routes.workflow import (
    router as workflow_router,
)

__all__ = [
    "execution_router",
    "workflow_router",
    "validation_router",
    "graph_router",
    "info_router",
]
