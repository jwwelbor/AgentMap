"""
Tests for HTTP route migration to async runtime facade.

TC-001: POST /execute/{graph_id} awaits run_workflow_async (REQ-AC-001)
TC-002A: GET /workflows awaits list_graphs_async (REQ-AC-002)
TC-002B: GET /workflows/{graph_id} awaits inspect_graph_async (REQ-AC-002)

Caller-Path Contracts (from test-plan.md):
- TC-001: entrypoint execute_workflow(...), mock seam run_workflow_async,
          forbidden: run_workflow, _execute_workflow_internal, _build_execute_response
- TC-002A: entrypoint list_workflows(...), mock seam list_graphs_async,
           forbidden: list_graphs, WorkflowListResponse/WorkflowSummary helpers
- TC-002B: entrypoint get_workflow_details(...), mock seam inspect_graph_async,
           forbidden: inspect_graph, WorkflowDetailResponse/NodeInfo helpers
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_app_with_auth_disabled(router):
    """Create a minimal FastAPI app with the given router and auth disabled."""
    app = FastAPI()
    app.include_router(router)

    mock_container = MagicMock()
    mock_auth_service = MagicMock()
    mock_auth_service.is_authentication_enabled.return_value = False
    mock_container.auth_service.return_value = mock_auth_service
    app.state.container = mock_container

    return app


def _make_execute_success_payload(interrupted: bool = False, thread_id: str = None):
    """Return a representative async runtime payload for execute routes."""
    if interrupted:
        return {
            "success": False,
            "interrupted": True,
            "thread_id": thread_id or "thread-abc-123",
            "interrupt_info": {"type": "human", "node_name": "approve_node"},
            "execution_summary": None,
            "metadata": {"graph_name": "customer_service::support_flow"},
        }
    return {
        "success": True,
        "outputs": {"result": "test_output"},
        "execution_id": None,
        "execution_summary": None,
        "metadata": {"graph_name": "customer_service::support_flow", "profile": None},
    }


def _make_list_graphs_payload(empty: bool = False):
    """Return a representative async runtime payload for list_graphs_async."""
    if empty:
        return {
            "success": True,
            "outputs": {"graphs": [], "total_count": 0},
            "metadata": {"profile": None, "repository_path": "/repo/csv"},
        }
    return {
        "success": True,
        "outputs": {
            "graphs": [
                {
                    "name": "graph_a",
                    "workflow": "customer_service",
                    "filename": "customer_service.csv",
                    "file_path": "/repo/csv/customer_service.csv",
                    "file_size": 1024,
                    "last_modified": 1700000000.0,
                    "total_nodes": 3,
                    "graph_count_in_workflow": 2,
                    "meta": {
                        "type": "csv_workflow",
                        "repository_path": "/repo/csv",
                        "profile": None,
                    },
                },
                {
                    "name": "graph_b",
                    "workflow": "customer_service",
                    "filename": "customer_service.csv",
                    "file_path": "/repo/csv/customer_service.csv",
                    "file_size": 1024,
                    "last_modified": 1700000000.0,
                    "total_nodes": 2,
                    "graph_count_in_workflow": 2,
                    "meta": {
                        "type": "csv_workflow",
                        "repository_path": "/repo/csv",
                        "profile": None,
                    },
                },
            ],
            "total_count": 2,
        },
        "metadata": {"profile": None, "repository_path": "/repo/csv"},
    }


def _make_inspect_graph_payload(not_found: bool = False):
    """Return a representative async runtime payload for inspect_graph_async."""
    return {
        "success": True,
        "outputs": {
            "resolved_name": "support_flow",
            "total_nodes": 2,
            "unique_agent_types": 1,
            "all_resolvable": True,
            "resolution_rate": 1.0,
            "structure": {
                "nodes": [
                    {"name": "start_node", "agent_type": "default", "description": ""},
                    {"name": "end_node", "agent_type": "default", "description": ""},
                ],
                "entry_point": "start_node",
            },
            "issues": [],
        },
        "metadata": {
            "graph_name": "support_flow",
            "csv_file": "/repo/csv/customer_service.csv",
            "inspected_node": None,
        },
    }


# ---------------------------------------------------------------------------
# TC-001: POST /execute/{graph_id} awaits run_workflow_async
# ---------------------------------------------------------------------------


class TestExecuteRouteAwaitsAsyncFacade:
    """TC-001: execute route uses run_workflow_async, not run_workflow."""

    def _make_client(self):
        from agentmap.deployment.http.api.routes.execute import router

        return TestClient(_make_app_with_auth_disabled(router))

    @patch("agentmap.deployment.http.api.routes.execute.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.execute.run_workflow_async",
        new_callable=AsyncMock,
    )
    def test_execute_route_awaits_run_workflow_async_on_success(
        self, mock_run_workflow_async, mock_ensure_initialized
    ):
        """TC-001 happy path: route calls run_workflow_async and returns ExecuteResponse."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_execute_success_payload()

        client = self._make_client()
        response = client.post(
            "/execute/customer_service::support_flow",
            json={
                "inputs": {"input": "test"},
                "execution_id": "exec-123",
                "force_create": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # ExecuteResponse schema must be present
        for field in (
            "success",
            "status",
            "message",
            "thread_id",
            "outputs",
            "execution_summary",
            "metadata",
            "interrupt_info",
            "error",
            "execution_id",
        ):
            assert field in data, f"Missing field: {field}"

        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["execution_id"] == "exec-123"

        # Counter-factual: run_workflow_async must be called, run_workflow must NOT be called
        mock_run_workflow_async.assert_awaited_once()
        mock_ensure_initialized.assert_called_once()

    def test_execute_route_does_not_import_sync_run_workflow(self):
        """TC-001 counter-factual: run_workflow (sync) must not be in the route module namespace."""
        import agentmap.deployment.http.api.routes.execute as execute_module

        # The sync facade must not be imported into the route module namespace.
        # The route now uses run_workflow_async exclusively.
        assert not hasattr(
            execute_module, "run_workflow"
        ), "sync run_workflow is still imported in execute.py — route regression"

    @patch("agentmap.deployment.http.api.routes.execute.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.execute.run_workflow_async",
        new_callable=AsyncMock,
    )
    def test_execute_route_maps_interrupted_payload_to_suspended_status(
        self, mock_run_workflow_async, mock_ensure_initialized
    ):
        """TC-001 edge case: interrupted payload maps to status='suspended' with thread_id."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_execute_success_payload(
            interrupted=True, thread_id="thread-xyz-999"
        )

        client = self._make_client()
        response = client.post(
            "/execute/customer_service::support_flow",
            json={"inputs": {}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "suspended"
        assert data["thread_id"] == "thread-xyz-999"
        mock_run_workflow_async.assert_awaited_once()

    @patch("agentmap.deployment.http.api.routes.execute.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.execute.run_workflow_async",
        new_callable=AsyncMock,
    )
    def test_execute_route_double_colon_graph_id_passes_through(
        self, mock_run_workflow_async, mock_ensure_initialized
    ):
        """TC-001 edge case: workflow::graph form passes the correct identifier to the facade."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_execute_success_payload()

        client = self._make_client()
        response = client.post(
            "/execute/customer_service::support_flow",
            json={"inputs": {}},
        )

        assert response.status_code == 200
        call_kwargs = mock_run_workflow_async.call_args
        assert "customer_service::support_flow" in str(call_kwargs)

    @patch("agentmap.deployment.http.api.routes.execute.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.execute.run_workflow_async",
        new_callable=AsyncMock,
    )
    def test_execute_route_slash_separated_graph_id_normalised(
        self, mock_run_workflow_async, mock_ensure_initialized
    ):
        """TC-001 edge case: workflow/graph path form converts to workflow::graph identifier."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_execute_success_payload()

        client = self._make_client()
        response = client.post(
            "/execute/customer_service/support_flow",
            json={"inputs": {}},
        )

        assert response.status_code == 200
        # The handler must pass the :: form to the async facade
        call_kwargs = mock_run_workflow_async.call_args
        assert "customer_service::support_flow" in str(call_kwargs)


# ---------------------------------------------------------------------------
# TC-001 resume route: resume_workflow_async
# ---------------------------------------------------------------------------


class TestResumeRouteAwaitsAsyncFacade:
    """TC-001 resume: /resume/{thread_id} uses resume_workflow_async, not resume_workflow."""

    def _make_client(self):
        from agentmap.deployment.http.api.routes.execute import router

        return TestClient(_make_app_with_auth_disabled(router))

    @patch("agentmap.deployment.http.api.routes.execute.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.execute.resume_workflow_async",
        new_callable=AsyncMock,
    )
    def test_resume_route_awaits_resume_workflow_async(
        self, mock_resume_workflow_async, mock_ensure_initialized
    ):
        """Resume route must await resume_workflow_async and return ResumeResponse."""
        mock_ensure_initialized.return_value = None
        mock_resume_workflow_async.return_value = {
            "success": True,
            "outputs": {"resumed": "result"},
            "execution_summary": None,
            "metadata": {
                "thread_id": "thread-resume-001",
                "response_action": "approve",
            },
        }

        client = self._make_client()
        response = client.post(
            "/resume/thread-resume-001",
            json={"action": "approve", "data": {"comment": "looks good"}},
        )

        assert response.status_code == 200
        data = response.json()
        for field in (
            "success",
            "status",
            "message",
            "thread_id",
            "outputs",
            "execution_summary",
            "metadata",
            "error",
        ):
            assert field in data, f"Missing field: {field}"
        assert data["success"] is True
        mock_resume_workflow_async.assert_awaited_once()

    def test_resume_route_does_not_import_sync_resume_workflow(self):
        """Counter-factual: sync resume_workflow must not be in the route module namespace."""
        import agentmap.deployment.http.api.routes.execute as execute_module

        assert not hasattr(
            execute_module, "resume_workflow"
        ), "sync resume_workflow is still imported in execute.py — route regression"


# ---------------------------------------------------------------------------
# TC-002A: GET /workflows awaits list_graphs_async
# ---------------------------------------------------------------------------


class TestListWorkflowsAwaitsAsyncFacade:
    """TC-002A: list_workflows handler awaits list_graphs_async, not list_graphs."""

    def _make_client(self):
        from agentmap.deployment.http.api.routes.workflows import router

        return TestClient(_make_app_with_auth_disabled(router))

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.list_graphs_async",
        new_callable=AsyncMock,
    )
    def test_list_workflows_awaits_list_graphs_async(
        self, mock_list_graphs_async, mock_ensure_initialized
    ):
        """TC-002A: route returns WorkflowListResponse via list_graphs_async."""
        mock_ensure_initialized.return_value = None
        mock_list_graphs_async.return_value = _make_list_graphs_payload()

        client = self._make_client()
        response = client.get("/workflows")

        assert response.status_code == 200
        data = response.json()
        for field in ("repository_path", "workflows", "total_count"):
            assert field in data, f"Missing field: {field}"
        assert data["total_count"] >= 1
        assert isinstance(data["workflows"], list)
        mock_list_graphs_async.assert_awaited_once()
        mock_ensure_initialized.assert_called_once()

    def test_list_workflows_does_not_import_sync_list_graphs(self):
        """TC-002A counter-factual: sync list_graphs must not be in the route module namespace."""
        import agentmap.deployment.http.api.routes.workflows as workflows_module

        assert not hasattr(
            workflows_module, "list_graphs"
        ), "sync list_graphs is still imported in workflows.py — route regression"

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.list_graphs_async",
        new_callable=AsyncMock,
    )
    def test_list_workflows_empty_repository(
        self, mock_list_graphs_async, mock_ensure_initialized
    ):
        """TC-002A edge case: empty repository returns workflows=[] and total_count=0."""
        mock_ensure_initialized.return_value = None
        mock_list_graphs_async.return_value = _make_list_graphs_payload(empty=True)

        client = self._make_client()
        response = client.get("/workflows")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["workflows"] == []
        mock_list_graphs_async.assert_awaited_once()

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.list_graphs_async",
        new_callable=AsyncMock,
    )
    def test_list_workflows_preserves_workflow_ordering_and_schema(
        self, mock_list_graphs_async, mock_ensure_initialized
    ):
        """TC-002A: response field names and derived workflow ordering match sync contract."""
        mock_ensure_initialized.return_value = None
        mock_list_graphs_async.return_value = _make_list_graphs_payload()

        client = self._make_client()
        response = client.get("/workflows")

        assert response.status_code == 200
        data = response.json()
        for wf in data["workflows"]:
            for field in (
                "name",
                "filename",
                "file_path",
                "file_size",
                "last_modified",
                "graph_count",
                "total_nodes",
            ):
                assert field in wf, f"WorkflowSummary missing field: {field}"


# ---------------------------------------------------------------------------
# TC-002B: GET /workflows/{graph_id} awaits inspect_graph_async
# ---------------------------------------------------------------------------


class TestGetWorkflowDetailsAwaitsAsyncFacade:
    """TC-002B: get_workflow_details handler awaits inspect_graph_async, not inspect_graph."""

    def _make_client(self):
        from agentmap.deployment.http.api.routes.workflows import router

        return TestClient(_make_app_with_auth_disabled(router))

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.inspect_graph_async",
        new_callable=AsyncMock,
    )
    def test_get_workflow_details_awaits_inspect_graph_async(
        self, mock_inspect_graph_async, mock_ensure_initialized
    ):
        """TC-002B: route returns WorkflowDetailResponse via inspect_graph_async."""
        mock_ensure_initialized.return_value = None
        mock_inspect_graph_async.return_value = _make_inspect_graph_payload()

        client = self._make_client()
        response = client.get("/workflows/customer_service::support_flow")

        assert response.status_code == 200
        data = response.json()
        for field in (
            "graph_id",
            "workflow",
            "graph",
            "nodes",
            "node_count",
            "entry_point",
        ):
            assert field in data, f"Missing field: {field}"
        assert data["graph_id"] == "customer_service::support_flow"
        assert data["workflow"] == "customer_service"
        assert data["graph"] == "support_flow"
        assert isinstance(data["nodes"], list)
        mock_inspect_graph_async.assert_awaited_once()
        mock_ensure_initialized.assert_called_once()

    def test_get_workflow_details_does_not_import_sync_inspect_graph(self):
        """TC-002B counter-factual: sync inspect_graph must not be in the route module namespace."""
        import agentmap.deployment.http.api.routes.workflows as workflows_module

        assert not hasattr(
            workflows_module, "inspect_graph"
        ), "sync inspect_graph is still imported in workflows.py — route regression"

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.inspect_graph_async",
        new_callable=AsyncMock,
    )
    def test_get_workflow_details_graph_not_found_returns_404(
        self, mock_inspect_graph_async, mock_ensure_initialized
    ):
        """TC-002B edge case: graph-not-found result maps to 404."""
        from agentmap.exceptions.runtime_exceptions import GraphNotFound

        mock_ensure_initialized.return_value = None
        mock_inspect_graph_async.side_effect = GraphNotFound(
            "nonexistent::graph", "Graph not found"
        )

        client = self._make_client()
        response = client.get("/workflows/nonexistent::graph")

        assert response.status_code == 404

    @patch("agentmap.deployment.http.api.routes.workflows.ensure_initialized")
    @patch(
        "agentmap.deployment.http.api.routes.workflows.inspect_graph_async",
        new_callable=AsyncMock,
    )
    def test_get_workflow_details_slash_separated_graph_id(
        self, mock_inspect_graph_async, mock_ensure_initialized
    ):
        """TC-002B edge case: path-separator form still normalises correctly."""
        mock_ensure_initialized.return_value = None
        mock_inspect_graph_async.return_value = _make_inspect_graph_payload()

        client = self._make_client()
        response = client.get("/workflows/customer_service/support_flow")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow"] == "customer_service"
        assert data["graph"] == "support_flow"
