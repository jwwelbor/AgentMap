"""
RETIRED PROTOTYPE — do not use as a production route surface.

This module was a prototype async workflow router. The canonical production
surfaces are:

  HTTP routes : agentmap.deployment.http.api.routes.workflows
                agentmap.deployment.http.api.routes.execute
  Runtime API : agentmap.runtime_api
  CLI         : agentmap.cli

The create_workflow_router() and integrate_workflow_routes() functions below
are tombstoned. Calling them raises RuntimeError so that any accidental
re-registration is caught immediately rather than silently adding a
duplicate /workflow surface to the app.

Data-model classes (WorkflowExecutionRequest, WorkflowExecutionResponse, etc.)
are preserved for reference but are not required by any canonical entrypoint.
"""

import warnings
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

warnings.warn(
    "agentmap.models.workflow_execution_models is a retired prototype module. "
    "Use agentmap.deployment.http.api.routes.workflows or agentmap.runtime_api instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ==========================================
# Request/Response Models
# ==========================================


class WorkflowExecutionRequest(BaseModel):
    """Request model for workflow execution."""

    state: Dict[str, Any] = {}
    config: Optional[Dict[str, Any]] = None
    validate: bool = False


class WorkflowExecutionResponse(BaseModel):
    """Response model for workflow execution."""

    success: bool
    graph_name: str
    workflow_name: str
    final_state: Dict[str, Any]
    error: Optional[str] = None
    bundle_cached: bool = False
    execution_time: Optional[float] = None


class WorkflowInfo(BaseModel):
    """Information about available workflows."""

    name: str
    path: str
    graphs: List[str]
    size_bytes: int


class WorkflowListResponse(BaseModel):
    """Response for listing available workflows."""

    workflows: List[WorkflowInfo]
    repository_path: str


# ==========================================
# API Router Implementation
# ==========================================


def create_workflow_router(container=None):  # type: ignore[return]
    """
    TOMBSTONED — this prototype router is retired.

    The /workflow route surface is no longer a supported production entrypoint.
    Use the canonical routes instead:

      agentmap.deployment.http.api.routes.workflows  (GET /workflows/*)
      agentmap.deployment.http.api.routes.execute    (POST /execute/*)

    Raises:
        RuntimeError: Always, to prevent accidental re-registration of the
                      prototype /workflow route surface.
    """
    raise RuntimeError(
        "create_workflow_router() is retired. "
        "Register agentmap.deployment.http.api.routes.workflows and "
        "agentmap.deployment.http.api.routes.execute instead."
    )


# ==========================================
# TOMBSTONED helper functions
# ==========================================


def execute_workflow_from_cli_pattern(  # type: ignore[return]
    workflow_name: str,
    graph_name: str,
    initial_state: Dict[str, Any],
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    TOMBSTONED — use agentmap.runtime_api.run_workflow or the CLI instead.

    Raises:
        RuntimeError: Always.
    """
    raise RuntimeError(
        "execute_workflow_from_cli_pattern() is retired. "
        "Use agentmap.runtime_api or the agentmap CLI instead."
    )


def integrate_workflow_routes(app, container=None) -> None:  # type: ignore[return]
    """
    TOMBSTONED — do not call this function.

    The /workflow prototype surface is retired. Register the canonical routes:

      agentmap.deployment.http.api.routes.workflows
      agentmap.deployment.http.api.routes.execute

    Raises:
        RuntimeError: Always.
    """
    raise RuntimeError(
        "integrate_workflow_routes() is retired. "
        "Use the canonical route modules in agentmap.deployment.http.api.routes instead."
    )
