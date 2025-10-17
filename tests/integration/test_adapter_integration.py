"""
Integration tests for adapter facade patterns.

Tests that CLI/HTTP/Serverless adapters show identical behavior and error semantics
for the same graph and inputs, ensuring the facade pattern works consistently.
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, Mock

from agentmap.runtime_api import (
    run_workflow,
    list_graphs,
    diagnose_system,
    validate_workflow,
    ensure_initialized,
)
from agentmap.exceptions.runtime_exceptions import (
    GraphNotFound,
    InvalidInputs,
    AgentMapNotInitialized,
)


class TestAdapterIntegration:
    """Integration tests verifying consistent behavior across adapters."""
    
    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing."""
        return """GraphName,NodeType,AgentName,Description,Dependencies
test_graph,Start,StartAgent,Initial node,
test_graph,Process,ProcessAgent,Processing node,StartAgent
test_graph,End,EndAgent,Final node,ProcessAgent"""
    
    @pytest.fixture
    def temp_csv_file(self, sample_csv_content):
        """Create a temporary CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(sample_csv_content)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        try:
            Path(temp_path).unlink()
        except FileNotFoundError:
            pass

    def test_runtime_api_initialization(self):
        """Test that runtime API initialization works consistently."""
        with patch('agentmap.runtime.init_ops.RuntimeManager') as mock_runtime_manager:
            mock_container = Mock()
            mock_cache_service = Mock()
            mock_cache_service.is_initialized.return_value = True
            mock_container.availability_cache_service.return_value = mock_cache_service
            
            mock_runtime_manager.initialize.return_value = None
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test initialization
            ensure_initialized()
            
            # Verify consistent behavior
            mock_runtime_manager.initialize.assert_called_once_with(refresh=False, config_file=None)
            mock_runtime_manager.get_container.assert_called_once()

    def test_workflow_execution_consistent_responses(self):
        """Test that workflow execution returns consistent response formats."""
        with patch('agentmap.runtime.ensure_initialized'), \
             patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
             patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
            
            # Setup mocks
            mock_container = Mock()
            mock_bundle_service = Mock()
            mock_runner_service = Mock()
            
            # Mock successful execution result
            mock_result = Mock()
            mock_result.success = True
            mock_result.final_state = {"output": "test_result"}
            mock_result.execution_id = "exec_123"
            
            # Configure mocks
            mock_resolve_path.return_value = (Path("/test/test_graph.csv"), "test_graph")
            mock_container.graph_bundle_service.return_value = mock_bundle_service
            mock_container.graph_runner_service.return_value = mock_runner_service
            
            mock_bundle = Mock()
            mock_bundle.graph_name = "test_graph"
            mock_bundle_service.get_or_create_bundle.return_value = (
                mock_bundle,
                False,
            )
            mock_runner_service.run.return_value = mock_result
            
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test execution
            result = run_workflow("test_graph", {"input": "test"})
            
            # Verify consistent response format
            assert result["success"] is True
            assert "outputs" in result
            assert "metadata" in result
            assert result["outputs"]["output"] == "test_result"
            assert result["execution_id"] == "exec_123"
            assert result["metadata"]["graph_name"] == "test_graph"

    def test_error_mapping_consistency(self):
        """Test that error mapping is consistent across facade functions."""
        with patch('agentmap.runtime.ensure_initialized'), \
             patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
             patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
            
            mock_container = Mock()
            mock_bundle_service = Mock()
            
            # Test GraphNotFound mapping
            mock_bundle_service.get_or_create_bundle.side_effect = FileNotFoundError("test.csv not found")
            mock_container.graph_bundle_service.return_value = mock_bundle_service
            mock_resolve_path.return_value = (Path("/test/missing.csv"), "missing_graph")
            mock_runtime_manager.get_container.return_value = mock_container
            
            with pytest.raises(GraphNotFound, match="Workflow file not found"):
                run_workflow("missing_graph", {"input": "test"})
            
            # Test InvalidInputs mapping
            mock_bundle_service.get_or_create_bundle.side_effect = ValueError("Invalid input format")
            
            with pytest.raises(InvalidInputs, match="Invalid input format"):
                run_workflow("test_graph", {"invalid": "inputs"})

    def test_list_graphs_consistent_format(self):
        """Test that list_graphs returns consistent format."""
        with patch('agentmap.runtime.ensure_initialized'), \
             patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
             tempfile.TemporaryDirectory() as temp_dir:
            
            # Setup mock container
            mock_container = Mock()
            mock_app_config = Mock()
            
            # Create test CSV files
            csv_repo = Path(temp_dir)
            test_csv = csv_repo / "test_workflow.csv"
            test_csv.write_text("GraphName,NodeType,AgentName\ntest_graph,Start,TestAgent\n")
            
            mock_app_config.get_csv_repository_path.return_value = csv_repo
            mock_container.app_config_service.return_value = mock_app_config
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test list_graphs
            result = list_graphs()
            
            # Verify consistent response format
            assert result["success"] is True
            assert "outputs" in result
            assert "metadata" in result
            
            graphs = result["outputs"]["graphs"]
            assert len(graphs) == 1
            graph = graphs[0]
            assert "name" in graph
            assert "workflow" in graph
            assert "filename" in graph
            assert "meta" in graph
            assert graph["name"] == "test_graph"
            assert graph["workflow"] == "test_workflow"

    def test_diagnose_system_consistent_format(self):
        """Test that diagnose_system returns consistent format."""
        with patch('agentmap.runtime.ensure_initialized'), \
             patch('agentmap.runtime.RuntimeManager') as mock_runtime_manager:
            
            # Setup mocks
            mock_container = Mock()
            mock_features_service = Mock()
            mock_dependency_checker = Mock()
            
            # Mock services
            mock_container.features_registry_service.return_value = mock_features_service
            mock_container.dependency_checker_service.return_value = mock_dependency_checker
            
            # Mock discovery results
            mock_dependency_checker.discover_and_validate_providers.side_effect = [
                {"openai": True, "anthropic": False, "google": False},  # LLM results
                {"csv": True, "json": True, "vector": False}  # Storage results
            ]
            
            mock_features_service.is_feature_enabled.side_effect = lambda feature: feature in ["llm", "storage"]
            
            mock_dependency_checker.check_llm_dependencies.return_value = (True, [])
            mock_dependency_checker.check_storage_dependencies.return_value = (True, [])
            
            mock_dependency_checker.get_dependency_status_summary.return_value = {
                "llm": {"available_providers": ["openai"]},
                "storage": {"available_types": ["csv", "json"]}
            }
            
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test diagnose_system
            result = diagnose_system()
            
            # Verify consistent format
            assert result["success"] is True
            assert "outputs" in result
            assert "metadata" in result
            
            outputs = result["outputs"]
            assert "overall_status" in outputs
            assert "features" in outputs
            assert "suggestions" in outputs
            assert "environment" in outputs

    def test_validate_workflow_consistent_format(self, temp_csv_file):
        """Test that validate_workflow returns consistent format."""
        with patch('agentmap.runtime.ensure_initialized'), \
             patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
             patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
            
            # Setup mocks
            mock_container = Mock()
            mock_validation_service = Mock()
            mock_bundle_service = Mock()
            
            mock_resolve_path.return_value = (temp_csv_file, "test_graph")
            mock_container.validation_service.return_value = mock_validation_service
            mock_container.graph_bundle_service.return_value = mock_bundle_service
            
            # Mock successful validation
            mock_validation_service.validate_csv_for_bundling.return_value = None
            
            mock_bundle = Mock()
            mock_bundle.nodes = ["node1", "node2"]
            mock_bundle.edges = ["edge1"]
            mock_bundle.missing_declarations = set()
            mock_bundle.graph_name = "test_graph"
            mock_bundle_service.get_or_create_bundle.return_value = (
                mock_bundle,
                False,
            )
            
            mock_runtime_manager.get_container.return_value = mock_container
            
            # Test validation
            result = validate_workflow("test_graph")
            
            # Verify consistent format
            assert result["success"] is True
            assert "outputs" in result
            assert "metadata" in result
            
            outputs = result["outputs"]
            assert "csv_structure_valid" in outputs
            assert "total_nodes" in outputs
            assert "total_edges" in outputs
            assert "missing_declarations" in outputs
            assert "all_agents_defined" in outputs


class TestAdapterErrorConsistency:
    """Test that all adapters handle errors consistently."""
    
    def test_graph_not_found_consistency(self):
        """Test GraphNotFound is handled consistently across adapters."""
        test_cases = [
            ("run_workflow", ("missing_graph", {"input": "test"}), {}),
            ("validate_workflow", ("missing_graph",), {}),
        ]
        
        for func_name, args, kwargs in test_cases:
            with patch('agentmap.runtime.init_ops.ensure_initialized'), \
                 patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
                 patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
                
                # Setup to raise FileNotFoundError
                mock_container = Mock()
                mock_service = Mock()
                mock_service.get_or_create_bundle.side_effect = FileNotFoundError("File not found")
                mock_container.graph_bundle_service.return_value = mock_service
                mock_container.validation_service.return_value = mock_service
                
                mock_resolve_path.return_value = (Path("/missing/file.csv"), "missing_graph")
                mock_runtime_manager.get_container.return_value = mock_container
                
                # Import the function dynamically
                from agentmap import runtime_api
                func = getattr(runtime_api, func_name)
                
                # Test that GraphNotFound is raised consistently
                with pytest.raises(GraphNotFound):
                    func(*args, **kwargs)

    def test_invalid_inputs_consistency(self):
        """Test InvalidInputs is handled consistently across adapters."""
        test_cases = [
            ("run_workflow", ("test_graph", {"invalid": "inputs"}), {}),
            ("validate_workflow", ("test_graph",), {}),
        ]
        
        for func_name, args, kwargs in test_cases:
            with patch('agentmap.runtime.ensure_initialized'), \
                 patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
                 patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
                
                # Setup to raise ValueError
                mock_container = Mock()
                mock_service = Mock()
                mock_service.get_or_create_bundle.side_effect = ValueError("Invalid input")
                mock_service.validate_csv_for_bundling.side_effect = ValueError("Invalid input")
                mock_container.graph_bundle_service.return_value = mock_service
                mock_container.validation_service.return_value = mock_service
                
                mock_resolve_path.return_value = (Path("/test/file.csv"), "test_graph")
                mock_runtime_manager.get_container.return_value = mock_container
                
                # Import the function dynamically
                from agentmap import runtime_api
                func = getattr(runtime_api, func_name)
                
                # Test that InvalidInputs is raised consistently
                with pytest.raises(InvalidInputs):
                    func(*args, **kwargs)

    def test_runtime_error_consistency(self):
        """Test RuntimeError is handled consistently across adapters."""
        test_cases = [
            ("diagnose_system", (), {}),
        ]
        
        for func_name, args, kwargs in test_cases:
            with patch('agentmap.runtime.ensure_initialized'), \
                 patch('agentmap.runtime.runtime_manager.RuntimeManager') as mock_runtime_manager:
                
                # Setup to raise unexpected exception that doesn't get mapped to specific errors
                mock_container = Mock()
                mock_container.features_registry_service.side_effect = Exception("Unexpected error")
                
                mock_runtime_manager.get_container.return_value = mock_container
                
                # Import the function dynamically
                from agentmap import runtime_api
                func = getattr(runtime_api, func_name)
                
                # Test that RuntimeError is raised consistently
                with pytest.raises(RuntimeError):
                    func(*args, **kwargs)
    
    def test_graph_resolution_error_mapping(self):
        """Test that graph resolution errors are mapped to GraphNotFound consistently."""
        test_cases = [
            ("run_workflow", ("test_graph", {"input": "test"}), {}),
        ]
        
        for func_name, args, kwargs in test_cases:
            with patch('agentmap.runtime.ensure_initialized'), \
                 patch('agentmap.runtime.workflow_ops.RuntimeManager') as mock_runtime_manager, \
                 patch('agentmap.runtime.workflow_ops._resolve_csv_path') as mock_resolve_path:
                
                # Setup to raise unexpected exception during graph resolution
                mock_container = Mock()
                mock_runtime_manager.get_container.return_value = mock_container
                
                # Mock _resolve_csv_path to raise an exception to test error mapping
                mock_resolve_path.side_effect = GraphNotFound("test_graph", "Failed to resolve graph path: Unexpected error")
                
                # Import the function dynamically
                from agentmap import runtime_api
                func = getattr(runtime_api, func_name)
                
                # Test that graph resolution errors are mapped to GraphNotFound
                with pytest.raises(GraphNotFound, match="Failed to resolve graph path"):
                    func(*args, **kwargs)


class TestResponseFormatConsistency:
    """Test that all facade functions return consistent response formats."""
    
    def test_success_response_format(self):
        """Test that all successful responses follow the same format."""
        # All facade functions should return:
        # {
        #   "success": True,
        #   "outputs": {...},
        #   "metadata": {...}
        # }
        
        test_functions = [
            "run_workflow",
            "list_graphs", 
            "diagnose_system",
            "validate_workflow",
            "update_bundle",
            "scaffold_agents",
            "refresh_cache",
            "validate_cache",
            "get_config",
            "inspect_graph",
        ]
        
        for func_name in test_functions:
            # Skip functions that require complex setup for this format test
            if func_name in ["run_workflow", "update_bundle", "scaffold_agents", "validate_workflow", "inspect_graph"]:
                continue
                
            with patch('agentmap.runtime.ensure_initialized'), \
                 patch('agentmap.runtime.runtime_manager.RuntimeManager') as mock_runtime_manager:
                
                # Setup basic mocks for success case
                mock_container = Mock()
                
                if func_name == "list_graphs":
                    mock_app_config = Mock()
                    mock_app_config.get_csv_repository_path.return_value = Path("/nonexistent")
                    mock_container.app_config_service.return_value = mock_app_config
                    
                elif func_name == "diagnose_system":
                    # Setup comprehensive mocks for diagnose_system
                    mock_features_service = Mock()
                    mock_dependency_checker = Mock()
                    
                    mock_container.features_registry_service.return_value = mock_features_service
                    mock_container.dependency_checker_service.return_value = mock_dependency_checker
                    
                    mock_dependency_checker.discover_and_validate_providers.side_effect = [
                        {"openai": True}, {"csv": True}
                    ]
                    mock_features_service.is_feature_enabled.return_value = True
                    mock_dependency_checker.check_llm_dependencies.return_value = (True, [])
                    mock_dependency_checker.check_storage_dependencies.return_value = (True, [])
                    mock_dependency_checker.get_dependency_status_summary.return_value = {
                        "llm": {"available_providers": ["openai"]},
                        "storage": {"available_types": ["csv"]}
                    }
                    
                elif func_name in ["refresh_cache", "validate_cache"]:
                    mock_dependency_checker = Mock()
                    mock_validation_cache_service = Mock()
                    
                    mock_container.dependency_checker_service.return_value = mock_dependency_checker
                    mock_container.validation_cache_service.return_value = mock_validation_cache_service
                    
                    if func_name == "refresh_cache":
                        mock_dependency_checker.invalidate_environment_cache.return_value = None
                        mock_dependency_checker.discover_and_validate_providers.side_effect = [
                            {"openai": True}, {"csv": True}
                        ]
                        mock_dependency_checker.get_dependency_status_summary.return_value = {
                            "llm": {"available_providers": ["openai"]},
                            "storage": {"available_types": ["csv"]}
                        }
                    else:  # validate_cache
                        mock_validation_cache_service.get_validation_cache_stats.return_value = {
                            "total_files": 5,
                            "valid_files": 4,
                            "expired_files": 1,
                            "corrupted_files": 0
                        }
                        
                elif func_name == "get_config":
                    mock_app_config = Mock()
                    mock_app_config.get_all.return_value = {"test": "config"}
                    mock_container.app_config_service.return_value = mock_app_config
                
                mock_runtime_manager.get_container.return_value = mock_container
                
                # Import and call the function
                from agentmap import runtime_api
                func = getattr(runtime_api, func_name)
                
                # Call with minimal args
                if func_name == "refresh_cache":
                    result = func()
                elif func_name == "validate_cache":
                    result = func(stats=True)
                else:
                    result = func()
                
                # Verify consistent response format
                assert isinstance(result, dict), f"{func_name} should return a dict"
                assert "success" in result, f"{func_name} should have 'success' field"
                assert result["success"] is True, f"{func_name} should indicate success"
                assert "outputs" in result, f"{func_name} should have 'outputs' field"
                assert "metadata" in result, f"{func_name} should have 'metadata' field"
                assert isinstance(result["outputs"], dict), f"{func_name} outputs should be a dict"
                assert isinstance(result["metadata"], dict), f"{func_name} metadata should be a dict"


if __name__ == "__main__":
    pytest.main([__file__])
