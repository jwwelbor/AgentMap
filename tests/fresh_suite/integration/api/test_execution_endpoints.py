"""
Integration tests for execution API endpoints.

Tests the FastAPI execution routes for running and resuming workflows,
using real DI container and service implementations.

Fixed to remove unnecessary mocking that was breaking the properly configured system.
"""

import json
import unittest
from unittest.mock import patch, Mock, MagicMock

from tests.fresh_suite.integration.api.base_api_integration_test import BaseAPIIntegrationTest
from tests.utils.test_isolation_helpers import ensure_file_exists, ci_robust_test


class TestExecutionEndpoints(BaseAPIIntegrationTest):
    """
    Integration tests for execution API endpoints.
    
    Tests:
    - POST /execution/{workflow}/{graph} - Run workflow graph
    - POST /execution/run - Legacy run endpoint  
    - POST /execution/resume - Resume workflow
    
    Fixed to work with the properly configured CSV repository path.
    """
    
    def setUp(self):
        """Set up test fixtures for execution endpoint testing."""
        super().setUp()
        
        # Create a minimal valid CSV for testing execution
        # Use simple names without underscores to avoid path validation issues
        self.execution_csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
testgraph,start,default,Start execution test,Test start node,input_data,output_data,end,
testgraph,end,default,End execution test,Test end node,output_data,final_result,,
'''
        # Note: The base class already configures the CSV repository correctly
        # The file will be created in {temp_dir}/csv_data/ which is where the system expects it
        self.execution_csv_path = self.create_test_csv_file(
            self.execution_csv_content,
            "testworkflow.csv"
        )
        
        # Verify file was created correctly - critical for CI
        self.assertTrue(self.execution_csv_path.exists(), 
                       f"Test CSV file should exist at: {self.execution_csv_path}")
        
        # Additional validation to ensure file is readable and non-empty
        self.assertGreater(self.execution_csv_path.stat().st_size, 0,
                          "Test CSV file should not be empty")
        
        # Verify the CSV content is correct
        csv_content = self.execution_csv_path.read_text(encoding='utf-8')
        self.assertIn('testgraph', csv_content, "CSV should contain testgraph")
        self.assertIn('testworkflow', str(self.execution_csv_path), "File should be named testworkflow.csv")
    
    def create_mock_adapter(self):
        """Create a properly configured mock service adapter."""
        mock_adapter = Mock()
        
        # Mock the initialize_services method to return real services
        mock_adapter.initialize_services.return_value = (
            self.container.graph_runner_service(),
            self.container.app_config_service(), 
            self.container.logging_service()
        )
        
        # Mock create_run_options method
        def mock_create_run_options(graph=None, csv=None, state=None, autocompile=False, execution_id=None):
            mock_options = Mock()
            mock_options.graph = graph
            mock_options.csv = csv
            mock_options.state = state or {}
            mock_options.autocompile = autocompile
            mock_options.execution_id = execution_id
            return mock_options
        
        mock_adapter.create_run_options.side_effect = mock_create_run_options
        
        # Mock extract_result_state method - ensure it returns proper dictionaries
        def mock_extract_result_state(result):
            # Explicitly convert to ensure no Mock objects leak through
            final_state = result.final_state if result.final_state is not None else {}
            metadata = result.metadata if result.metadata is not None else {}
            
            # Ensure we return actual dictionaries, not Mock objects
            return {
                "final_state": dict(final_state) if final_state else {},
                "metadata": dict(metadata) if metadata else {}
            }
        
        mock_adapter.extract_result_state.side_effect = mock_extract_result_state
        
        return mock_adapter
    
    def test_run_workflow_graph_success(self):
        """Test successful workflow graph execution via RESTful endpoint."""
        request_data = {
            "state": {"input_data": "test_value"},
            "autocompile": True,
            "execution_id": "test_exec_001"
        }
        
        # Create mock adapter to handle dependency injection
        mock_adapter = self.create_mock_adapter()
        
        # Only mock the service adapter and graph runner - CSV path is already configured correctly
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter:
            
            # Configure mock adapter
            mock_create_adapter.return_value = mock_adapter
            
            # Create a simple result object that matches ExecutionResult interface
            from src.agentmap.models.execution_summary import ExecutionSummary
            
            class MockResult:
                def __init__(self):
                    # ExecutionResult interface
                    self.graph_name = 'testgraph'
                    self.final_state = {'final_result': 'test_output'}
                    self.execution_summary = ExecutionSummary(
                        graph_name='testgraph',
                        final_output={'final_result': 'test_output'},
                        graph_success=True,
                        status='completed'
                    )
                    self.success = True
                    self.total_duration = 1.23
                    self.compiled_from = 'memory'
                    self.error = None
                    
                    # Legacy interface for backward compatibility
                    self.error_message = None
                    self.execution_id = 'test_exec_001'
                    self.execution_time = 1.23
                    self.metadata = {'nodes_executed': 2}
            
            mock_result = MockResult()
            mock_run.return_value = mock_result
            
            response = self.client.post(
                "/execution/testworkflow/testgraph",
                json=request_data
            )
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "success", "output", "execution_id", "execution_time", "metadata"
        ])
        self.assertTrue(data["success"])
        self.assertEqual(data["execution_id"], "test_exec_001")
        self.assertIsNotNone(data["output"])
        self.assertIsNotNone(data["metadata"])
    
    def test_run_workflow_graph_failure(self):
        """Test workflow graph execution failure handling."""
        request_data = {
            "state": {"input_data": "test_value"},
            "autocompile": False
        }
        
        # Create mock adapter
        mock_adapter = self.create_mock_adapter()
        
        # Mock only the graph runner service - CSV path is configured correctly
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter:
            
            mock_create_adapter.return_value = mock_adapter
            
            # Create a simple result object for failure case that matches ExecutionResult interface
            from src.agentmap.models.execution_summary import ExecutionSummary
            
            class MockFailureResult:
                def __init__(self):
                    # ExecutionResult interface
                    self.graph_name = 'testgraph'
                    self.final_state = {}
                    self.execution_summary = ExecutionSummary(
                        graph_name='testgraph',
                        final_output=None,
                        graph_success=False,
                        status='failed'
                    )
                    self.success = False
                    self.total_duration = 0.5
                    self.compiled_from = 'memory'
                    self.error = 'Test execution failed'
                    
                    # Legacy interface for backward compatibility
                    self.error_message = 'Test execution failed'
                    self.execution_id = 'test_exec_002'
                    self.execution_time = 0.5
                    self.metadata = None
            
            mock_result = MockFailureResult()
            mock_run.return_value = mock_result
            
            response = self.client.post(
                "/execution/testworkflow/testgraph",
                json=request_data
            )
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Test execution failed")
        self.assertIsNone(data["execution_id"])  # No execution_id provided in request
        self.assertIsNone(data["output"])
    
    def test_run_workflow_graph_invalid_workflow(self):
        """Test execution with non-existent workflow."""
        request_data = {
            "state": {"input_data": "test_value"}
        }
        
        # This should fail naturally because the workflow doesn't exist
        # No mocking needed - the real system should handle this properly
        response = self.client.post(
            "/execution/nonexistent_workflow/test_graph",
            json=request_data
        )
        
        self.assert_file_not_found_response(response, "workflow")
    
    def test_run_workflow_graph_invalid_request_data(self):
        """Test execution with invalid request data."""
        # Test with invalid JSON structure
        invalid_data = {
            "state": "invalid_state_should_be_object",
            "autocompile": "invalid_boolean"
        }
        
        response = self.client.post(
            "/execution/execution_test/test_execution",
            json=invalid_data
        )
        
        self.assert_validation_error_response(response)
    
    def test_run_workflow_graph_large_request(self):
        """Test execution with oversized request data."""
        # Create large request that should trigger size validation
        large_request_data = self.create_large_test_data()
        
        response = self.client.post(
            "/execution/execution_test/test_execution",
            json=large_request_data
        )
        
        # Should return 413 Request Entity Too Large for oversized request
        self.assert_response_error(response, 413)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("too large", data["detail"].lower())
    
    def test_run_graph_legacy_success(self):
        """Test successful execution via legacy run endpoint."""
        request_data = {
            "graph": "testgraph",
            "csv": str(self.execution_csv_path),  # Use direct CSV path
            "state": {"input_data": "legacy_test_value"},
            "autocompile": True,
            "execution_id": "legacy_exec_001"
        }
        
        # Create mock adapter
        mock_adapter = self.create_mock_adapter()
        
        # Mock the graph runner service
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter:
            
            mock_create_adapter.return_value = mock_adapter
            
            # Create a simple result object instead of Mock to avoid serialization issues
            from src.agentmap.models.execution_summary import ExecutionSummary
            
            class MockLegacyResult:
                def __init__(self):
                    self.success = True
                    self.error = None
                    self.error_message = None
                    self.execution_id = 'legacy_exec_001'
                    self.execution_time = 2.1
                    self.total_duration = 2.1
                    self.final_state = {'final_result': 'legacy_output'}
                    self.metadata = {'execution_mode': 'legacy'}
                    # Additional attributes that might be expected
                    self.graph_name = 'testgraph'
                    self.compiled_from = 'memory'
                    self.execution_summary = ExecutionSummary(
                        graph_name='testgraph',
                        final_output={'final_result': 'legacy_output'},
                        graph_success=True,
                        status='completed'
                    )
            
            mock_result = MockLegacyResult()
            mock_run.return_value = mock_result
            
            response = self.client.post("/execution/run", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["execution_id"], "legacy_exec_001")
        self.assertIsNotNone(data["output"])
    
    def test_run_graph_legacy_with_workflow_lookup(self):
        """Test legacy endpoint with workflow repository lookup."""
        request_data = {
            "workflow": "testworkflow",  # Should lookup testworkflow.csv in the configured repo
            "graph": "testgraph",
            "state": {"input_data": "workflow_lookup_test"}
        }
        
        # Create mock adapter
        mock_adapter = self.create_mock_adapter()
        
        # Mock only the graph runner service - let the repository lookup work naturally
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter:
            
            mock_create_adapter.return_value = mock_adapter
            
            # Create a simple result object instead of Mock to avoid serialization issues
            from src.agentmap.models.execution_summary import ExecutionSummary
            
            class MockWorkflowResult:
                def __init__(self):
                    self.success = True
                    self.error = None
                    self.error_message = None
                    self.execution_id = None
                    self.execution_time = 1.5
                    self.total_duration = 1.5
                    self.final_state = {'final_result': 'workflow_lookup_output'}
                    self.metadata = {}
                    # Additional attributes that might be expected
                    self.graph_name = 'testgraph'
                    self.compiled_from = 'memory'
                    self.execution_summary = ExecutionSummary(
                        graph_name='testgraph',
                        final_output={'final_result': 'workflow_lookup_output'},
                        graph_success=True,
                        status='completed'
                    )
            
            mock_result = MockWorkflowResult()
            mock_run.return_value = mock_result
            
            response = self.client.post("/execution/run", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["output"])
    
    def test_run_graph_legacy_minimal_request(self):
        """Test legacy endpoint with minimal request data."""
        # Test with minimal data - should use defaults
        request_data = {
            "state": {"input_data": "minimal_test"}
        }
        
        # Create mock adapter
        mock_adapter = self.create_mock_adapter()
        
        # Mock the graph runner service
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter:
            
            mock_create_adapter.return_value = mock_adapter
            
            # Create a simple result object instead of Mock to avoid serialization issues
            from src.agentmap.models.execution_summary import ExecutionSummary
            
            class MockMinimalResult:
                def __init__(self):
                    self.success = True
                    self.error = None
                    self.error_message = None
                    self.execution_id = None
                    self.execution_time = 0.8
                    self.total_duration = 0.8
                    self.final_state = {'final_result': 'minimal_output'}
                    self.metadata = {}
                    # Additional attributes that might be expected
                    self.graph_name = 'testgraph'
                    self.compiled_from = 'memory'
                    self.execution_summary = ExecutionSummary(
                        graph_name='testgraph',
                        final_output={'final_result': 'minimal_output'},
                        graph_success=True,
                        status='completed'
                    )
            
            mock_result = MockMinimalResult()
            mock_run.return_value = mock_result
            
            response = self.client.post("/execution/run", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
    
    def test_resume_workflow_success(self):
        """Test successful workflow resumption."""
        # Use a valid UUID for the thread_id
        test_thread_id = "550e8400-e29b-41d4-a716-446655440000"
        test_request_id = "660e8400-e29b-41d4-a716-446655440001"
        
        # Mock storage service manager for resume functionality
        with patch.object(
            self.container, 'storage_service_manager'
        ) as mock_storage_manager_factory:
            # Create mock storage manager and storage service using MagicMock to handle truthiness and len() calls
            mock_storage_manager = MagicMock()
            mock_storage_manager_factory.return_value = mock_storage_manager
            mock_storage_service = MagicMock()
            mock_storage_manager.get_service.return_value = mock_storage_service
            
            # Mock storage reads to return valid UUID data
            mock_storage_service.read.side_effect = lambda collection, document_id: {
                "threads": {
                    test_thread_id: {
                        "pending_interaction_id": test_request_id,
                        "status": "waiting"
                    }
                },
                "interactions": {
                    test_request_id: {
                        "id": test_request_id,
                        "thread_id": test_thread_id,
                        "node_name": "approval_node",
                        "interaction_type": "approval"
                    }
                }
            }.get(collection, {}).get(document_id, None)
            
            # Mock successful write operations
            from agentmap.services.storage.types import StorageResult
            mock_storage_service.write.return_value = StorageResult(success=True, data={"document_id": test_request_id})
            
            request_data = {
                "thread_id": test_thread_id,
                "response_action": "continue",
                "response_data": {"user_choice": "yes"}
            }
            
            response = self.client.post("/execution/resume", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "success", "thread_id", "response_action", "message"
        ])
        self.assertTrue(data["success"])
        self.assertEqual(data["thread_id"], test_thread_id)
        self.assertEqual(data["response_action"], "continue")
    
    def test_resume_workflow_storage_unavailable(self):
        """Test resume workflow when storage is not available."""
        # Mock storage service manager to return None (storage unavailable)
        with patch.object(
            self.container, 'storage_service_manager'
        ) as mock_storage_manager_factory:
            mock_storage_manager_factory.return_value = None
            
            request_data = {
                "thread_id": "test_thread_unavailable",
                "response_action": "continue",
                "response_data": {"user_choice": "yes"}
            }
            
            response = self.client.post("/execution/resume", json=request_data)
        
        self.assert_response_error(response, 503)
        
        data = response.json()
        self.assertIn("Storage services are not available", data["detail"])
    
    def test_resume_workflow_thread_not_found(self):
        """Test resume workflow with non-existent thread ID."""
        # Use a valid UUID that doesn't exist
        nonexistent_thread_id = "770e8400-e29b-41d4-a716-446655440002"
        
        with patch.object(
            self.container, 'storage_service_manager'
        ) as mock_storage_manager_factory:
            # Use MagicMock to handle truthiness check and len() calls
            mock_storage_manager = MagicMock()
            mock_storage_manager_factory.return_value = mock_storage_manager
            mock_storage_service = MagicMock()
            mock_storage_manager.get_service.return_value = mock_storage_service
            
            # Mock storage read to return None for thread not found
            mock_storage_service.read.return_value = None
            
            request_data = {
                "thread_id": nonexistent_thread_id,
                "response_action": "continue",
                "response_data": {}
            }
            
            response = self.client.post("/execution/resume", json=request_data)
        
        self.assert_response_error(response, 404)
        
        data = response.json()
        # Check that the error message indicates thread was not found
        self.assertIn("not found", data["detail"].lower())
        self.assertIn(nonexistent_thread_id, data["detail"])
    
    def test_resume_workflow_invalid_request(self):
        """Test resume workflow with invalid request data."""
        # Test missing required fields
        invalid_data = {
            # Missing thread_id and response_action
            "response_data": {"user_choice": "yes"}
        }
        
        response = self.client.post("/execution/resume", json=invalid_data)
        
        self.assert_validation_error_response(response)
    
    def test_resume_workflow_storage_error(self):
        """Test resume workflow with storage service error."""
        # Use valid UUIDs
        test_thread_id = "880e8400-e29b-41d4-a716-446655440003"
        test_request_id = "990e8400-e29b-41d4-a716-446655440004"
        
        with patch.object(
            self.container, 'storage_service_manager'
        ) as mock_storage_manager_factory:
            # Use MagicMock to handle truthiness check and len() calls
            mock_storage_manager = MagicMock()
            mock_storage_manager_factory.return_value = mock_storage_manager
            mock_storage_service = MagicMock()
            mock_storage_manager.get_service.return_value = mock_storage_service
            
            # Mock storage reads to succeed but writes to fail
            def mock_read(collection, document_id):
                if collection == "threads" and document_id == test_thread_id:
                    return {
                        "pending_interaction_id": test_request_id,
                        "status": "waiting"
                    }
                elif collection == "interactions" and document_id == test_request_id:
                    return {
                        "id": test_request_id,
                        "thread_id": test_thread_id,
                        "node_name": "approval_node",
                        "interaction_type": "approval"
                    }
                return None
            
            mock_storage_service.read.side_effect = mock_read
            
            # Mock write to fail with storage error
            from agentmap.services.storage.types import StorageResult
            mock_storage_service.write.return_value = StorageResult(
                success=False, 
                error="Storage connection failed"
            )
            
            request_data = {
                "thread_id": test_thread_id,
                "response_action": "continue",
                "response_data": {"user_choice": "yes"}
            }
            
            response = self.client.post("/execution/resume", json=request_data)
        
        self.assert_response_error(response, 503)
        
        data = response.json()
        self.assertIn("Storage error", data["detail"])
    
    def test_execution_timeout_handling(self):
        """Test execution timeout handling."""
        # Ensure CSV file exists before test starts - this is critical for CI
        self.assertTrue(self.execution_csv_path.exists(), 
                       f"Test CSV file must exist at: {self.execution_csv_path}")
        
        request_data = {
            "state": {"input_data": "timeout_test"},
            "autocompile": False
        }
        
        # Create mock adapter
        mock_adapter = self.create_mock_adapter()
        
        # Mock the graph runner service to simulate timeout AND ensure path validation succeeds
        with patch.object(
            self.container.graph_runner_service(), 
            'run_graph'
        ) as mock_run, \
        patch('src.agentmap.core.adapters.create_service_adapter') as mock_create_adapter, \
        patch('agentmap.infrastructure.api.fastapi.routes.execution._resolve_workflow_path') as mock_resolve_path:
            
            mock_create_adapter.return_value = mock_adapter
            mock_run.side_effect = TimeoutError("Execution timeout")
            
            # Mock path resolution to return valid path and bypass file existence checks
            mock_resolve_path.return_value = self.execution_csv_path
            
            response = self.client.post(
                "/execution/testworkflow/testgraph",
                json=request_data
            )
        
        self.assert_response_error(response, 408)
        
        data = response.json()
        self.assertIn("detail", data)
        # Convert detail to string if it's not already
        detail_str = str(data["detail"]).lower()
        self.assertIn("timeout", detail_str)
    
    def test_execution_path_validation(self):
        """Test workflow and graph name validation."""
        # Ensure CSV exists for validation tests - important for CI
        ensure_file_exists(self.execution_csv_path, "Execution test CSV")
        
        request_data = {"state": {"input_data": "test"}}
        
        response = self.client.post(
            "/execution/../../../etc/passwd/malicious",
            json=request_data
        )
        
        # Path traversal attempts should return 404 Not Found
        self.assert_response_error(response, 404)
        
        # Test invalid graph name
        response = self.client.post(
            "/execution/testworkflow/invalid..graph..name",
            json=request_data
        )
        
        # Invalid graph names should also return 404 Not Found
        self.assert_response_error(response, 404)


if __name__ == '__main__':
    unittest.main()
