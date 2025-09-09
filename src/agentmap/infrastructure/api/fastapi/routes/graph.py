"""
Graph execution routes for FastAPI server.

This module provides graph-specific API endpoints for execution, validation,
and compilation using the new service architecture.

FIXED: Updated to use correct service interfaces and properly handle return types.
FIXED: Updated to use direct container access instead of Depends() chains.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer

# Import auth decorator
from agentmap.infrastructure.api.fastapi.dependencies import requires_auth
from agentmap.services.auth_service import AuthContext

# Create router
router = APIRouter(prefix="/graph", tags=["Graph Operations"])


@router.get("/status/{graph_name}")
@requires_auth()
async def get_graph_status(
    graph_name: str,
    csv: str,
    request: Request,
):
    """Get status information for a specific graph."""
    try:
        # Get container from request
        container = request.app.state.container

        # ✅ FIXED: Use correct service names and handle Graph object properly
        graph_definition_service = container.graph_definition_service()
        graph_runner_service = container.graph_runner_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_repository_path()

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Build graph to check status
        graph_obj = graph_definition_service.build_from_csv(csv_path, graph_name)

        # ✅ FIXED: Get agent resolution status using existing services
        # Create a mock bundle to get instantiation status
        from agentmap.models.graph_bundle import GraphBundle

        # Create bundle from graph for status checking
        bundle = GraphBundle(
            graph_name=graph_name,
            nodes=graph_obj.nodes if hasattr(graph_obj, "nodes") else {},
            entry_point=getattr(graph_obj, "entry_point", None),
        )

        # Use existing graph_agent_instantiation_service to get agent status
        graph_instantiation_service = container.graph_agent_instantiation_service()
        instantiation_summary = graph_instantiation_service.get_instantiation_summary(
            bundle
        )

        # Transform to expected agent_status format
        agent_status = {
            "resolved_agents": instantiation_summary.get("instantiated", 0),
            "unresolved_agents": instantiation_summary.get("missing", 0),
            "total_agents": instantiation_summary.get("total_nodes", 0),
        }

        # ✅ FIXED: Handle Graph object node count properly
        node_count = 0
        if hasattr(graph_obj, "nodes") and graph_obj.nodes is not None:
            if hasattr(graph_obj.nodes, "__len__"):
                # If nodes has __len__, use it directly
                node_count = len(graph_obj.nodes)
            elif hasattr(graph_obj.nodes, "keys"):
                # If nodes is dict-like, count keys
                node_count = len(list(graph_obj.nodes.keys()))
            else:
                # Try to convert to dict or count iteratively
                try:
                    nodes_dict = dict(graph_obj.nodes) if graph_obj.nodes else {}
                    node_count = len(nodes_dict)
                except (TypeError, ValueError):
                    # Fallback: count by iteration
                    try:
                        node_count = sum(1 for _ in graph_obj.nodes)
                    except (TypeError, AttributeError):
                        node_count = 0

        return {
            "graph_name": graph_name,
            "exists": True,
            "csv_path": str(csv_path),
            "node_count": node_count,
            "entry_point": getattr(graph_obj, "entry_point", None),
            "agent_status": agent_status,
        }

    except ValueError as e:
        if "not found" in str(e).lower():
            return {"graph_name": graph_name, "exists": False, "error": str(e)}
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
@requires_auth()
async def list_graphs(
    request: Request,
    csv: Optional[str] = None,
):
    """List all available graphs in the CSV file."""
    try:
        # Get container from request
        container = request.app.state.container

        # ✅ FIXED: Use correct service names and handle Graph objects properly
        graph_definition_service = container.graph_definition_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_repository_path()

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Build all graphs to get list
        all_graphs = graph_definition_service.build_all_from_csv(csv_path)

        graphs_list = []
        for graph_name, graph_obj in all_graphs.items():
            # ✅ FIXED: Handle Graph object node count properly
            node_count = 0
            if hasattr(graph_obj, "nodes") and graph_obj.nodes is not None:
                if hasattr(graph_obj.nodes, "__len__"):
                    node_count = len(graph_obj.nodes)
                elif hasattr(graph_obj.nodes, "keys"):
                    node_count = len(list(graph_obj.nodes.keys()))
                else:
                    try:
                        nodes_dict = dict(graph_obj.nodes) if graph_obj.nodes else {}
                        node_count = len(nodes_dict)
                    except (TypeError, ValueError):
                        try:
                            node_count = sum(1 for _ in graph_obj.nodes)
                        except (TypeError, AttributeError):
                            node_count = 0

            graphs_list.append(
                {
                    "name": graph_name,
                    "entry_point": getattr(graph_obj, "entry_point", None),
                    "node_count": node_count,
                }
            )

        return {
            "csv_path": str(csv_path),
            "graphs": graphs_list,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
