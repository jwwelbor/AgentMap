"""
Unit tests for AgentMap Runtime API.

Tests the facade pattern implementation, error mapping, and RuntimeManager delegation.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)
from agentmap.runtime import (
    ensure_initialized,
    get_container,
    list_graphs,
    resume_workflow,
    run_workflow,
)
from agentmap.runtime.init_ops import _is_cache_initialized, _refresh_cache
from agentmap.runtime.workflow_ops import _resolve_csv_path


class TestEnsureInitialized:
    """Test the ensure_initialized facade function."""

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_ensure_initialized_success(self, mock_runtime_manager):
        """Test successful initialization."""
        # Setup mocks
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.return_value = True
        mock_container.availability_cache_service.return_value = mock_cache_service

        mock_runtime_manager.initialize.return_value = None
        mock_runtime_manager.get_container.return_value = mock_container

        # Test
        ensure_initialized()

        # Verify
        mock_runtime_manager.initialize.assert_called_once_with(
            refresh=False, config_file=None
        )
        mock_runtime_manager.get_container.assert_called_once()
        # The function calls is_initialized twice - once to check if refresh needed, once to verify after
        assert mock_cache_service.is_initialized.call_count >= 1

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_ensure_initialized_with_refresh(self, mock_runtime_manager):
        """Test initialization with forced refresh."""
        # Setup mocks
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.return_value = True
        mock_cache_service.refresh_cache.return_value = None
        mock_container.availability_cache_service.return_value = mock_cache_service

        mock_runtime_manager.initialize.return_value = None
        mock_runtime_manager.get_container.return_value = mock_container

        # Test
        ensure_initialized(refresh=True, config_file="test.yaml")

        # Verify
        mock_runtime_manager.initialize.assert_called_once_with(
            refresh=True, config_file="test.yaml"
        )
        mock_cache_service.refresh_cache.assert_called_once_with(mock_container)

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_ensure_initialized_cache_missing(self, mock_runtime_manager):
        """Test initialization when cache is missing."""
        # Setup mocks
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.side_effect = [
            False,
            True,
        ]  # First false, then true after refresh
        mock_cache_service.refresh_cache.return_value = None
        mock_container.availability_cache_service.return_value = mock_cache_service

        mock_runtime_manager.initialize.return_value = None
        mock_runtime_manager.get_container.return_value = mock_container

        # Test
        ensure_initialized()

        # Verify
        assert mock_cache_service.is_initialized.call_count == 2
        mock_cache_service.refresh_cache.assert_called_once_with(mock_container)

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_ensure_initialized_cache_refresh_fails(self, mock_runtime_manager):
        """Test initialization when cache refresh fails."""
        # Setup mocks
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.return_value = False
        mock_cache_service.refresh_cache.side_effect = Exception("Cache refresh failed")
        mock_container.availability_cache_service.return_value = mock_cache_service

        mock_runtime_manager.initialize.return_value = None
        mock_runtime_manager.get_container.return_value = mock_container

        # Test
        with pytest.raises(
            AgentMapNotInitialized, match="Failed to refresh provider cache"
        ):
            ensure_initialized()

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_ensure_initialized_runtime_manager_fails(self, mock_runtime_manager):
        """Test initialization when RuntimeManager fails."""
        # Setup mocks
        mock_runtime_manager.initialize.side_effect = Exception(
            "DI initialization failed"
        )

        # Test
        with pytest.raises(AgentMapNotInitialized, match="Initialization failed"):
            ensure_initialized()


class TestRunWorkflow:
    """Test the run_workflow facade function."""

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_run_workflow_success(self, mock_ensure_init, mock_runtime_manager):
        """Test successful workflow execution."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_bundle_service = Mock()
        mock_runner_service = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        # Mock successful execution result
        mock_result = Mock()
        mock_result.success = True
        mock_result.final_state = {"output": "test_result"}
        mock_result.execution_id = "exec_123"

        # Configure container services
        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_runner_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        # Configure bundle creation
        mock_bundle = Mock()
        mock_bundle.graph_name = "test_graph"
        mock_bundle_service.get_or_create_bundle.return_value = (
            mock_bundle,
            False,
        )

        # Configure runner execution
        mock_runner_service.run.return_value = mock_result

        # Setup the RuntimeManager.get_container() static method mock
        mock_runtime_manager.get_container.return_value = mock_container

        # Setup CSV repository path for _resolve_csv_path - persistent temp dir
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            test_csv = csv_repo / "test_graph.csv"
            test_csv.write_text("test content")
            mock_app_config.get_csv_repository_path.return_value = csv_repo

            # Test
            result = run_workflow("test_graph", {"input": "test"})

            # Verify
            mock_ensure_init.assert_called_once_with(config_file=None)
            assert result["success"] is True
            assert result["outputs"] == {"output": "test_result"}
            assert result["execution_id"] == "exec_123"
            assert result["metadata"]["graph_name"] == "test_graph"
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_run_workflow_execution_failure(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """Test workflow execution failure."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_bundle_service = Mock()
        mock_runner_service = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        # Mock failed execution result
        mock_result = Mock()
        mock_result.success = False
        mock_result.error = "Graph not found in CSV"
        mock_result.final_state = {}  # Empty dict to prevent interruption path

        # Configure container services
        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_runner_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        # Setup CSV repository path for _resolve_csv_path
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            test_csv = csv_repo / "missing_graph.csv"
            test_csv.write_text("test content")
            mock_app_config.get_csv_repository_path.return_value = csv_repo

            # Configure bundle creation
            mock_bundle = Mock()
            mock_bundle_service.get_or_create_bundle.return_value = (
                mock_bundle,
                False,
            )

            # Configure runner execution
            mock_runner_service.run.return_value = mock_result

            mock_runtime_manager.get_container.return_value = mock_container

            # Test
            with pytest.raises(GraphNotFound, match="not found"):
                run_workflow("missing_graph", {"input": "test"})
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_run_workflow_file_not_found(self, mock_ensure_init, mock_runtime_manager):
        """Test workflow with missing file."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_bundle_service = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        # Configure container services
        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        # Setup CSV repository path for _resolve_csv_path (file won't exist)
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            mock_app_config.get_csv_repository_path.return_value = csv_repo

            mock_bundle_service.get_or_create_bundle.side_effect = FileNotFoundError(
                "test.csv not found"
            )
            mock_runtime_manager.get_container.return_value = mock_container

            # Test
            with pytest.raises(GraphNotFound, match="Workflow file not found"):
                run_workflow("missing_file", {"input": "test"})
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_run_workflow_invalid_inputs(self, mock_ensure_init, mock_runtime_manager):
        """Test workflow with invalid inputs."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_bundle_service = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        # Configure container services
        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        # Setup CSV repository path for _resolve_csv_path
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            test_csv = csv_repo / "test_graph.csv"
            test_csv.write_text("test content")
            mock_app_config.get_csv_repository_path.return_value = csv_repo

            mock_bundle_service.get_or_create_bundle.side_effect = ValueError(
                "Invalid input format"
            )
            mock_runtime_manager.get_container.return_value = mock_container

            # Test
            with pytest.raises(InvalidInputs, match="Invalid input format"):
                run_workflow("test_graph", {"invalid": "inputs"})
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


class TestResumeWorkflow:
    """Test the resume_workflow facade function."""

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService.resume_workflow"
    )
    def test_resume_workflow_success(
        self, mock_resume_service, mock_ensure_init, mock_runtime_manager
    ):
        """Test successful workflow resume."""
        # Setup mocks
        mock_container = Mock()
        mock_storage_manager = Mock()
        mock_storage_service = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        # Configure container services
        mock_container.system_storage_manager.return_value = mock_storage_manager
        mock_container.logging_service.return_value = mock_logging_service
        mock_container.graph_bundle_service.return_value = Mock()
        mock_container.graph_runner_service.return_value = Mock()
        mock_container.graph_checkpoint_service.return_value = Mock()

        mock_storage_manager.get_service.return_value = mock_storage_service
        mock_logging_service.get_logger.return_value = mock_logger

        mock_runtime_manager.get_container.return_value = mock_container

        # Mock the WorkflowOrchestrationService.resume_workflow to return a successful result
        mock_result = Mock()
        mock_result.final_state = {"resumed": "successfully"}
        mock_result.execution_summary = "Mock execution summary"
        mock_result.graph_name = "test_graph"
        mock_result.total_duration = 1.5
        mock_resume_service.return_value = mock_result

        # Test with JSON token
        resume_token = json.dumps(
            {"thread_id": "thread_123", "response_action": "continue"}
        )
        result = resume_workflow(resume_token)

        # Verify
        mock_ensure_init.assert_called_once_with(config_file=None)
        mock_resume_service.assert_called_once_with(
            thread_id="thread_123",
            response_action="continue",
            response_data=None,
            config_file=None,
        )
        assert result["success"] is True
        assert result["metadata"]["thread_id"] == "thread_123"
        assert result["outputs"] == {"resumed": "successfully"}

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService.resume_workflow"
    )
    def test_resume_workflow_invalid_token(
        self, mock_resume_service, mock_ensure_init, mock_runtime_manager
    ):
        """Test resume with invalid token."""
        # Setup basic mocks for RuntimeManager
        mock_container = Mock()
        mock_storage_manager = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        mock_container.system_storage_manager.return_value = mock_storage_manager
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger
        mock_runtime_manager.get_container.return_value = mock_container

        # Test with valid JSON token structure but make the service fail
        mock_resume_service.side_effect = RuntimeError("Resume service failed")

        token_with_valid_structure = json.dumps(
            {"thread_id": "valid_thread_123", "response_action": "continue"}
        )

        # This should return success: False because the exception is caught
        result = resume_workflow(token_with_valid_structure)
        assert result["success"] is False
        assert "Resume service failed" in result["error"]

        # Test with missing thread_id - this should return success: False because exception is caught
        token = json.dumps({"response_action": "continue"})
        result = resume_workflow(token)
        assert result["success"] is False
        assert "valid thread_id" in result["error"]


class TestListGraphs:
    """Test the list_graphs facade function."""

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_list_graphs_success(self, mock_ensure_init, mock_runtime_manager):
        """Test successful graph listing."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()

        # Create temporary CSV repository path
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)

            # Create test CSV files
            test_csv = csv_repo / "test_workflow.csv"
            test_csv.write_text(
                "GraphName,NodeType,AgentName\ntest_graph,Start,TestAgent\n"
            )

            mock_app_config.get_csv_repository_path.return_value = csv_repo
            mock_container.app_config_service.return_value = mock_app_config
            mock_runtime_manager.get_container.return_value = mock_container

            # Test
            result = list_graphs()

            # Verify
            mock_ensure_init.assert_called_once_with(config_file=None)
            assert result["success"] is True
            assert "outputs" in result
            assert "graphs" in result["outputs"]

            graphs = result["outputs"]["graphs"]
            assert len(graphs) == 1
            assert graphs[0]["name"] == "test_graph"
            assert graphs[0]["workflow"] == "test_workflow"
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_list_graphs_empty_repository(self, mock_ensure_init, mock_runtime_manager):
        """Test listing graphs with empty repository."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()

        # Non-existent path
        mock_app_config.get_csv_repository_path.return_value = Path("/nonexistent")
        mock_container.app_config_service.return_value = mock_app_config
        mock_runtime_manager.get_container.return_value = mock_container

        # Test
        result = list_graphs()

        # Verify
        assert result["success"] is True
        assert "outputs" in result
        assert "graphs" in result["outputs"]

        graphs = result["outputs"]["graphs"]
        assert len(graphs) == 0


class TestHelperFunctions:
    """Test helper functions."""

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    def test_resolve_csv_path_repository_workflow(self, mock_runtime_manager):
        """Test resolving CSV path for repository workflow."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            test_csv = csv_repo / "test_workflow.csv"
            test_csv.write_text("test content")

            mock_app_config.get_csv_repository_path.return_value = csv_repo

            # Test
            csv_path, resolved_graph_name = _resolve_csv_path(
                "test_workflow", mock_container
            )

            # Verify
            assert csv_path == test_csv
            assert resolved_graph_name == "test_workflow"
            assert csv_path.exists()
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    def test_resolve_csv_path_fallback_workflow(self, mock_runtime_manager):
        """Test resolving CSV path for workflow name not in repository."""
        # Setup mocks
        mock_container = Mock()
        mock_app_config = Mock()
        mock_logging_service = Mock()
        mock_logger = Mock()

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.logging_service.return_value = mock_logging_service
        mock_logging_service.get_logger.return_value = mock_logger

        # Mock repository path that doesn't contain the file
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            csv_repo = Path(temp_dir)
            mock_app_config.get_csv_repository_path.return_value = csv_repo

            # Test with workflow name that doesn't exist in repository (fallback to Path)
            csv_path, resolved_graph_name = _resolve_csv_path(
                "nonexistent_workflow", mock_container
            )

            # Verify - should fallback to Path construction
            assert csv_path == Path("nonexistent_workflow")
            assert resolved_graph_name == "nonexistent_workflow"
        finally:
            # Clean up temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_is_cache_initialized_success(self):
        """Test cache initialization check success."""
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.return_value = True
        mock_container.availability_cache_service.return_value = mock_cache_service

        result = _is_cache_initialized(mock_container)
        assert result is True

    def test_is_cache_initialized_failure(self):
        """Test cache initialization check failure."""
        mock_container = Mock()
        mock_container.availability_cache_service.side_effect = Exception(
            "Service error"
        )

        result = _is_cache_initialized(mock_container)
        assert result is False

    def test_refresh_cache_success(self):
        """Test cache refresh success."""
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.refresh_cache.return_value = None
        mock_container.availability_cache_service.return_value = mock_cache_service

        # Should not raise
        _refresh_cache(mock_container)
        mock_cache_service.refresh_cache.assert_called_once_with(mock_container)

    def test_refresh_cache_failure(self):
        """Test cache refresh failure."""
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.refresh_cache.side_effect = Exception("Refresh failed")
        mock_container.availability_cache_service.return_value = mock_cache_service

        with pytest.raises(
            AgentMapNotInitialized, match="Failed to refresh provider cache"
        ):
            _refresh_cache(mock_container)


class TestGetContainer:
    """Test the get_container function."""

    @patch("agentmap.runtime.init_ops.RuntimeManager")
    def test_get_container(self, mock_runtime_manager):
        """Test getting the DI container."""
        mock_container = Mock()
        mock_runtime_manager.get_container.return_value = mock_container

        result = get_container()

        assert result is mock_container
        mock_runtime_manager.get_container.assert_called_once()

    # Integration test placeholder for end-to-end facade behavior
    # class TestRuntimeAPIIntegration:
    """Integration tests for runtime API facade patterns."""

    # def test_runtime_api_facade_contract(self):
    #     """Test that runtime API follows facade contract properly."""
    #     # This would be an integration test that verifies:
    #     # 1. Runtime API only calls RuntimeManager methods
    #     # 2. All exceptions are properly mapped to canonical types
    #     # 3. No direct service/DI access in runtime API
    #     # 4. Consistent behavior across all facade functions
    #     pass


class TestAsyncFacadeExports:
    """
    TC-005 / TC-006 (REQ-AC-005, REQ-AC-006):
    Async runtime facade — argument and payload shape parity with sync siblings.
    """

    @pytest.fixture(autouse=True)
    def csv_tmp(self, tmp_path):
        """Shared temp directory with a minimal test_graph.csv."""
        csv_file = tmp_path / "test_graph.csv"
        csv_file.write_text(
            "GraphName,NodeType,AgentName\ntest_graph,Start,TestAgent\n"
        )
        self._csv_repo = tmp_path
        self._csv_file = csv_file

    # ------------------------------------------------------------------
    # TC-005: run_workflow_async preserves sync facade argument shape
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    async def test_run_workflow_async_success_preserves_envelope(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """AC-T1: run_workflow_async returns the same response envelope as run_workflow."""
        from agentmap.runtime.workflow_ops import run_workflow_async

        mock_container = Mock()
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = self._csv_repo
        mock_bundle_service = Mock()
        mock_runner_service = Mock()
        mock_logging_service = Mock()
        mock_logging_service.get_logger.return_value = Mock()

        mock_result = Mock()
        mock_result.success = True
        mock_result.final_state = {"output": "async_result"}
        mock_result.execution_id = "exec_async_001"
        mock_result.execution_summary = "Async run complete"

        mock_bundle = Mock()
        mock_bundle.graph_name = "test_graph"
        mock_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)
        # T-E04-F04-004: run_workflow_async now awaits run_async, not run
        mock_runner_service.run_async = AsyncMock(return_value=mock_result)

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_runner_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_runtime_manager.get_container.return_value = mock_container

        result = await run_workflow_async("test_graph", {"input": "data"})

        mock_ensure_init.assert_called_once_with(config_file=None)
        assert result["success"] is True
        assert result["outputs"] == {"output": "async_result"}
        assert result["execution_id"] == "exec_async_001"
        assert result["metadata"]["graph_name"] == "test_graph"

    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    async def test_run_workflow_async_propagates_graph_not_found(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """AC-T1: run_workflow_async raises GraphNotFound same as sync sibling."""
        from agentmap.runtime.workflow_ops import run_workflow_async

        mock_container = Mock()
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = self._csv_repo
        mock_bundle_service = Mock()
        mock_runner_service = Mock()
        mock_logging_service = Mock()
        mock_logging_service.get_logger.return_value = Mock()

        mock_result = Mock()
        mock_result.success = False
        mock_result.error = "Graph not found in CSV"
        mock_result.final_state = {}

        mock_bundle = Mock()
        mock_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)
        # T-E04-F04-004: run_workflow_async now awaits run_async, not run
        mock_runner_service.run_async = AsyncMock(return_value=mock_result)

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_runner_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_runtime_manager.get_container.return_value = mock_container

        with pytest.raises(GraphNotFound):
            await run_workflow_async("test_graph", {"input": "data"})

    # ------------------------------------------------------------------
    # TC-006: resume_workflow_async preserves suspend/human-response parity
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch(
        "agentmap.services.workflow_orchestration_service._rehydrate_bundle_from_metadata"
    )
    async def test_resume_workflow_async_suspend_style(
        self, mock_rehydrate, mock_runtime_manager, mock_ensure_init
    ):
        """AC-T1/TC-006: resume_workflow_async preserves suspend-style response envelope.

        T-E04-F04-004: resume_workflow_async now inlines the orchestration logic and
        awaits GraphRunnerService.resume_from_checkpoint_async directly.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.runtime.workflow_ops import resume_workflow_async

        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={"resumed": True},
            execution_summary=None,
            success=True,
            total_duration=3.2,
        )

        mock_bundle = Mock()
        mock_rehydrate.return_value = mock_bundle

        mock_interaction_handler = Mock()
        mock_interaction_handler.get_thread_metadata.return_value = {
            "graph_name": "test_graph",
            "bundle_info": {"csv_path": "/fake/path.csv"},
            "checkpoint_data": {"state": "paused"},
            "pending_interaction_id": None,
            "node_name": "suspend_node",
        }
        mock_interaction_handler.mark_thread_resuming.return_value = True

        mock_graph_runner = Mock()
        mock_graph_runner.resume_from_checkpoint_async = AsyncMock(
            return_value=mock_result
        )

        mock_bundle_service = Mock()
        mock_container = Mock()
        mock_container.interaction_handler_service.return_value = (
            mock_interaction_handler
        )
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_graph_runner
        mock_runtime_manager.get_container.return_value = mock_container

        resume_token = json.dumps(
            {"thread_id": "thread_async_001", "response_action": "continue"}
        )

        result = await resume_workflow_async(resume_token, profile="dev")

        assert result["success"] is True
        assert result["outputs"] == {"resumed": True}
        assert result["metadata"]["thread_id"] == "thread_async_001"
        assert result["metadata"]["graph_name"] == "test_graph"
        assert result["metadata"]["profile"] == "dev"
        mock_graph_runner.resume_from_checkpoint_async.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch(
        "agentmap.services.workflow_orchestration_service._rehydrate_bundle_from_metadata"
    )
    async def test_resume_workflow_async_human_response(
        self, mock_rehydrate, mock_runtime_manager, mock_ensure_init
    ):
        """AC-T1/TC-006: resume_workflow_async preserves human-response payload.

        T-E04-F04-004: resume_workflow_async now inlines the orchestration logic and
        awaits GraphRunnerService.resume_from_checkpoint_async directly.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.runtime.workflow_ops import resume_workflow_async

        mock_result = ExecutionResult(
            graph_name="approval_flow",
            final_state={"approved": True, "__human_response": "yes"},
            execution_summary=None,
            success=True,
            total_duration=5.0,
        )

        mock_bundle = Mock()
        mock_rehydrate.return_value = mock_bundle

        mock_interaction_handler = Mock()
        mock_interaction_handler.get_thread_metadata.return_value = {
            "graph_name": "approval_flow",
            "bundle_info": {"csv_path": "/fake/approval.csv"},
            "checkpoint_data": {"state": "waiting_human"},
            "pending_interaction_id": "11111111-1111-1111-1111-111111111111",
            "node_name": "approve_node",
        }
        mock_interaction_handler.save_interaction_response.return_value = True
        mock_interaction_handler.mark_thread_resuming.return_value = True

        mock_graph_runner = Mock()
        mock_graph_runner.resume_from_checkpoint_async = AsyncMock(
            return_value=mock_result
        )

        mock_bundle_service = Mock()
        mock_container = Mock()
        mock_container.interaction_handler_service.return_value = (
            mock_interaction_handler
        )
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_runner_service.return_value = mock_graph_runner
        mock_runtime_manager.get_container.return_value = mock_container

        resume_token = json.dumps(
            {
                "thread_id": "thread_human_001",
                "response_action": "approve",
                "response_data": {"decision": "yes"},
            }
        )

        result = await resume_workflow_async(resume_token)

        assert result["success"] is True
        assert result["outputs"]["approved"] is True
        mock_graph_runner.resume_from_checkpoint_async.assert_awaited_once()
        # Verify the human response was saved
        mock_interaction_handler.save_interaction_response.assert_called_once()

    # ------------------------------------------------------------------
    # AC-T2: list_graphs_async does not block event loop
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    async def test_list_graphs_async_returns_same_envelope(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """AC-T1: list_graphs_async returns the same envelope as list_graphs."""
        from agentmap.runtime.workflow_ops import list_graphs_async

        mock_container = Mock()
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = self._csv_repo
        mock_container.app_config_service.return_value = mock_app_config
        mock_runtime_manager.get_container.return_value = mock_container

        result = await list_graphs_async()

        mock_ensure_init.assert_called_once_with(config_file=None)
        assert result["success"] is True
        assert "graphs" in result["outputs"]

    # ------------------------------------------------------------------
    # AC-T1: inspect_graph_async preserves argument shape
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    async def test_inspect_graph_async_preserves_argument_shape(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """AC-T1: inspect_graph_async accepts same kwargs as inspect_graph."""
        from agentmap.runtime.workflow_ops import inspect_graph_async

        mock_container = Mock()
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = self._csv_repo
        mock_bundle_service = Mock()
        mock_logging_service = Mock()
        mock_logging_service.get_logger.return_value = Mock()

        mock_bundle = Mock()
        mock_bundle.graph_name = "test_graph"
        mock_bundle.nodes = {"NodeA": Mock(agent_type="default", description="")}
        mock_bundle.entry_point = "NodeA"
        mock_bundle.required_agents = {"default"}
        mock_bundle.required_services = set()
        mock_bundle.missing_declarations = set()
        mock_bundle.csv_hash = "abc123"
        mock_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_runtime_manager.get_container.return_value = mock_container

        result = await inspect_graph_async("test_graph")

        assert result["success"] is True
        assert "resolved_name" in result["outputs"]

    # ------------------------------------------------------------------
    # AC-T1: validate_workflow_async preserves argument shape
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    @patch("agentmap.runtime.workflow_ops.RuntimeManager")
    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    async def test_validate_workflow_async_preserves_argument_shape(
        self, mock_ensure_init, mock_runtime_manager
    ):
        """AC-T1: validate_workflow_async accepts same kwargs as validate_workflow."""
        from agentmap.runtime.workflow_ops import validate_workflow_async

        mock_container = Mock()
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = self._csv_repo
        mock_bundle_service = Mock()
        mock_validation_service = Mock()
        mock_logging_service = Mock()
        mock_logging_service.get_logger.return_value = Mock()

        mock_bundle = Mock()
        mock_bundle.graph_name = "test_graph"
        mock_bundle.nodes = {"NodeA": Mock()}
        mock_bundle.edges = []
        mock_bundle.missing_declarations = set()
        mock_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)

        mock_container.app_config_service.return_value = mock_app_config
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.validation_service.return_value = mock_validation_service
        mock_container.logging_service.return_value = mock_logging_service
        mock_runtime_manager.get_container.return_value = mock_container

        result = await validate_workflow_async("test_graph")

        assert result["success"] is True
        assert result["outputs"]["csv_structure_valid"] is True

    # ------------------------------------------------------------------
    # Export surface: async names reachable from agentmap.runtime and
    # agentmap.runtime_api without import-path changes (AC-T1)
    # ------------------------------------------------------------------
    def test_async_functions_exported_from_runtime_package(self):
        """AC-T1: async callables are accessible via agentmap.runtime.*"""
        import agentmap.runtime as rt

        for name in (
            "run_workflow_async",
            "resume_workflow_async",
            "list_graphs_async",
            "inspect_graph_async",
            "validate_workflow_async",
        ):
            assert hasattr(rt, name), f"agentmap.runtime missing {name}"
            assert callable(getattr(rt, name)), f"{name} is not callable"

    def test_async_functions_exported_from_runtime_api(self):
        """AC-T1: async callables are accessible via agentmap.runtime_api.*"""
        import agentmap.runtime_api as rapi

        for name in (
            "run_workflow_async",
            "resume_workflow_async",
            "list_graphs_async",
            "inspect_graph_async",
            "validate_workflow_async",
        ):
            assert hasattr(rapi, name), f"agentmap.runtime_api missing {name}"
            assert callable(getattr(rapi, name)), f"{name} is not callable"

    def test_sync_siblings_still_callable_without_import_path_change(self):
        """AC-T1: sync siblings remain importable from both surfaces unchanged."""
        import agentmap.runtime as rt
        import agentmap.runtime_api as rapi

        for name in (
            "run_workflow",
            "resume_workflow",
            "list_graphs",
            "inspect_graph",
            "validate_workflow",
        ):
            assert callable(getattr(rt, name)), f"agentmap.runtime.{name} not callable"
            assert callable(
                getattr(rapi, name)
            ), f"agentmap.runtime_api.{name} not callable"


class TestAsyncWrapperNonBlocking:
    """
    AC-T2: Async wrappers isolate sync-only internals behind asyncio.to_thread.
    """

    @pytest.mark.asyncio
    async def test_list_graphs_async_uses_thread_for_sync_io(self):
        """AC-T2: list_graphs_async isolates sync filesystem work via to_thread."""
        import asyncio

        from agentmap.runtime.workflow_ops import list_graphs_async

        calls = []

        original_to_thread = asyncio.to_thread

        async def spy_to_thread(fn, *args, **kwargs):
            calls.append(fn.__name__ if hasattr(fn, "__name__") else str(fn))
            return await original_to_thread(fn, *args, **kwargs)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch("agentmap.runtime.workflow_ops.RuntimeManager") as mock_rm,
            patch("asyncio.to_thread", side_effect=spy_to_thread),
        ):
            mock_container = Mock()
            mock_app_config = Mock()
            mock_app_config.get_csv_repository_path.return_value = Path(
                "/nonexistent_repo"
            )
            mock_container.app_config_service.return_value = mock_app_config
            mock_rm.get_container.return_value = mock_container

            await list_graphs_async()

        assert len(calls) > 0, "list_graphs_async must delegate to asyncio.to_thread"

    @pytest.mark.asyncio
    async def test_run_workflow_async_uses_native_run_async(self):
        """AC-T2 (T-E04-F04-004): run_workflow_async awaits run_async, not asyncio.to_thread.

        Counter-factual: if to_thread were still used, run_async would never be awaited.
        """
        from agentmap.runtime.workflow_ops import run_workflow_async

        tmp = tempfile.mkdtemp()
        try:
            csv_file = Path(tmp) / "test_graph.csv"
            csv_file.write_text(
                "GraphName,NodeType,AgentName\ntest_graph,Start,TestAgent\n"
            )

            mock_container = Mock()
            mock_app_config = Mock()
            mock_app_config.get_csv_repository_path.return_value = Path(tmp)
            mock_runner_service = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.final_state = {}
            mock_result.execution_id = None
            mock_result.execution_summary = ""
            # T-E04-F04-004: native async runner, not sync run
            mock_runner_service.run_async = AsyncMock(return_value=mock_result)
            mock_bundle_service = Mock()
            mock_bundle = Mock()
            mock_bundle.graph_name = "test_graph"
            mock_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)
            mock_logging_service = Mock()
            mock_logging_service.get_logger.return_value = Mock()

            mock_container.app_config_service.return_value = mock_app_config
            mock_container.graph_runner_service.return_value = mock_runner_service
            mock_container.graph_bundle_service.return_value = mock_bundle_service
            mock_container.logging_service.return_value = mock_logging_service

            with (
                patch("agentmap.runtime.workflow_ops.ensure_initialized"),
                patch("agentmap.runtime.workflow_ops.RuntimeManager") as mock_rm,
            ):
                mock_rm.get_container.return_value = mock_container
                await run_workflow_async("test_graph", {})

            # The native async runner must have been awaited (not just called)
            mock_runner_service.run_async.assert_awaited_once()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__])
