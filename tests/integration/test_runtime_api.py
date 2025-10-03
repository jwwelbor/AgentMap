"""
Unit tests for AgentMap Runtime API.

Tests the facade pattern implementation, error mapping, and RuntimeManager delegation.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from agentmap.runtime import (
    ensure_initialized, get_container,
    run_workflow, resume_workflow, list_graphs, inspect_graph, validate_workflow,
    update_bundle, scaffold_agents,
    refresh_cache, validate_cache, get_config, diagnose_system,
)

from agentmap.runtime.workflow_ops import _resolve_csv_path
from agentmap.runtime.init_ops import  _is_cache_initialized, _refresh_cache

from agentmap.services.workflow_orchestration_service import WorkflowOrchestrationService


from agentmap.exceptions.runtime_exceptions import (
    AgentMapError,
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)


class TestEnsureInitialized:
    """Test the ensure_initialized facade function."""
    
    @patch('agentmap.runtime.init_ops.RuntimeManager')
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
        mock_runtime_manager.initialize.assert_called_once_with(refresh=False, config_file=None)
        mock_runtime_manager.get_container.assert_called_once()
        # The function calls is_initialized twice - once to check if refresh needed, once to verify after
        assert mock_cache_service.is_initialized.call_count >= 1

    @patch('agentmap.runtime.init_ops.RuntimeManager')
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
        mock_runtime_manager.initialize.assert_called_once_with(refresh=True, config_file="test.yaml")
        mock_cache_service.refresh_cache.assert_called_once_with(mock_container)

    @patch('agentmap.runtime.init_ops.RuntimeManager')
    def test_ensure_initialized_cache_missing(self, mock_runtime_manager):
        """Test initialization when cache is missing."""
        # Setup mocks
        mock_container = Mock()
        mock_cache_service = Mock()
        mock_cache_service.is_initialized.side_effect = [False, True]  # First false, then true after refresh
        mock_cache_service.refresh_cache.return_value = None
        mock_container.availability_cache_service.return_value = mock_cache_service
        
        mock_runtime_manager.initialize.return_value = None
        mock_runtime_manager.get_container.return_value = mock_container
        
        # Test
        ensure_initialized()
        
        # Verify
        assert mock_cache_service.is_initialized.call_count == 2
        mock_cache_service.refresh_cache.assert_called_once_with(mock_container)

    @patch('agentmap.runtime.init_ops.RuntimeManager')
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
        with pytest.raises(AgentMapNotInitialized, match="Failed to refresh provider cache"):
            ensure_initialized()

    @patch('agentmap.runtime.init_ops.RuntimeManager')
    def test_ensure_initialized_runtime_manager_fails(self, mock_runtime_manager):
        """Test initialization when RuntimeManager fails."""
        # Setup mocks
        mock_runtime_manager.initialize.side_effect = Exception("DI initialization failed")
        
        # Test
        with pytest.raises(AgentMapNotInitialized, match="Initialization failed"):
            ensure_initialized()


class TestRunWorkflow:
    """Test the run_workflow facade function."""
    
    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
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
        mock_bundle_service.get_or_create_bundle.return_value = mock_bundle
        
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

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
    def test_run_workflow_execution_failure(self, mock_ensure_init, mock_runtime_manager):
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
            mock_bundle_service.get_or_create_bundle.return_value = mock_bundle
            
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

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
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
            
            mock_bundle_service.get_or_create_bundle.side_effect = FileNotFoundError("test.csv not found")
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test
            with pytest.raises(GraphNotFound, match="Workflow file not found"):
                run_workflow("missing_file", {"input": "test"})
        finally:
            # Clean up temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
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
            
            mock_bundle_service.get_or_create_bundle.side_effect = ValueError("Invalid input format")
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
    
    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
    @patch('agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService.resume_workflow')
    def test_resume_workflow_success(self, mock_resume_service, mock_ensure_init, mock_runtime_manager):
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
        resume_token = json.dumps({"thread_id": "thread_123", "response_action": "continue"})
        result = resume_workflow(resume_token)
        
        # Verify
        mock_ensure_init.assert_called_once_with(config_file=None)
        mock_resume_service.assert_called_once_with(
            thread_id="thread_123",
            response_action="continue", 
            response_data=None,
            config_file=None
        )
        assert result["success"] is True
        assert result["metadata"]["thread_id"] == "thread_123"
        assert result["outputs"] == {"resumed": "successfully"}

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
    @patch('agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService.resume_workflow')
    def test_resume_workflow_invalid_token(self, mock_resume_service, mock_ensure_init, mock_runtime_manager):
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
        
        token_with_valid_structure = json.dumps({
            "thread_id": "valid_thread_123",
            "response_action": "continue"
        })
        
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
    
    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
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
            test_csv.write_text("GraphName,NodeType,AgentName\ntest_graph,Start,TestAgent\n")
            
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

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
    @patch('agentmap.runtime.workflow_ops.ensure_initialized')
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
    


    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
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
            csv_path, resolved_graph_name = _resolve_csv_path("test_workflow", mock_container)
            
            # Verify
            assert csv_path == test_csv
            assert resolved_graph_name == "test_workflow"
            assert csv_path.exists()
        finally:
            # Clean up temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch('agentmap.runtime.workflow_ops.RuntimeManager')
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
            csv_path, resolved_graph_name = _resolve_csv_path("nonexistent_workflow", mock_container)
            
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
        mock_container.availability_cache_service.side_effect = Exception("Service error")
        
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
        
        with pytest.raises(AgentMapNotInitialized, match="Failed to refresh provider cache"):
            _refresh_cache(mock_container)


class TestGetContainer:
    """Test the get_container function."""
    
    @patch('agentmap.runtime.init_ops.RuntimeManager')
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


if __name__ == "__main__":
    pytest.main([__file__])
