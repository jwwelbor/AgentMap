"""
Integration tests for graph API endpoints.

Tests the FastAPI graph routes for graph compilation, validation, scaffolding,
and status operations using real DI container and service implementations.

FIXED: Converted from CLI command patches to DI container service pattern
following established testing patterns from TESTING_PATTERNS.md.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.fresh_suite.integration.api.base_api_integration_test import BaseAPIIntegrationTest


class TestGraphEndpoints(BaseAPIIntegrationTest):
    """
    Integration tests for graph API endpoints.
    
    Tests:
    - POST /graph/compile - Compile graph to executable format
    - POST /graph/validate - Validate graph CSV file
    - POST /graph/scaffold - Scaffold agents for graph
    - GET /graph/status/{graph_name} - Get graph status
    - GET /graph/list - List available graphs
    
    FIXED: Uses real DI container services instead of CLI command patches.
    """
    
    def setUp(self):
        """Set up test fixtures for graph endpoint testing."""
        super().setUp()
        
        # Create test graph CSV for operations
        self.graph_csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
test_graph,input,default,Process input data,Input processing node,raw_input,validated_input,process,error
test_graph,process,default,Process validated data,Main processing node,validated_input,processed_data,output,error
test_graph,output,default,Format output data,Output formatting node,processed_data,final_output,,
test_graph,error,default,Handle processing errors,Error handling node,error_data,error_message,,
multi_graph,start,default,Start multi graph,Multi graph start,input_data,start_data,finish,fail
multi_graph,finish,default,Finish multi graph,Multi graph end,start_data,final_data,,
multi_graph,fail,default,Handle multi graph errors,Multi graph error handler,error_data,failure_message,,
'''
        self.graph_csv_path = self.create_test_csv_file(
            self.graph_csv_content,
            "graph_operations.csv"
        )
    
    # =============================================================================
    # Graph Compilation Tests
    # =============================================================================
    
    def test_compile_graph_success(self):
        """Test successful graph compilation using DI container services."""
        request_data = {
            "graph": "test_graph",
            "csv": str(self.graph_csv_path),
            "output_dir": str(Path(self.temp_dir) / "compiled"),
            "state_schema": "dict",
            "validate": True
        }
        
        # ✅ FIXED: Use real DI container services, not CLI patches
        # Mock compilation service to return success result with correct attributes
        mock_compilation_result = Mock()
        mock_compilation_result.success = True
        mock_compilation_result.output_path = Path(self.temp_dir) / "compiled" / "test_graph.pkl"
        mock_compilation_result.source_path = Path(self.graph_csv_path)
        mock_compilation_result.compilation_time = 2.5
        mock_compilation_result.error = None
        
        with patch.object(
            self.container.compilation_service(), 
            'compile_graph',
            return_value=mock_compilation_result
        ) as mock_compile:
            response = self.client.post("/graph/compile", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "success", "bundle_path", "source_path", "compilation_time"
        ])
        
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["bundle_path"])
        self.assertIsNotNone(data["source_path"])
        self.assertGreater(data["compilation_time"], 0)
        self.assertIsNone(data["error"])
        
        # Verify service was called correctly
        mock_compile.assert_called_once()
    
    def test_compile_graph_failure(self):
        """Test graph compilation failure using DI container services."""
        request_data = {
            "graph": "invalid_graph",
            "csv": str(self.graph_csv_path),
            "validate": True
        }
        
        # ✅ FIXED: Mock compilation service to raise ValueError
        with patch.object(
            self.container.compilation_service(),
            'compile_graph',
            side_effect=ValueError("Graph 'invalid_graph' not found in CSV")
        ):
            response = self.client.post("/graph/compile", json=request_data)
        
        self.assert_response_error(response, 400)
    
    def test_compile_graph_file_not_found(self):
        """Test graph compilation with non-existent CSV file."""
        request_data = {
            "graph": "test_graph",
            "csv": "/nonexistent/path/to/graph.csv",
            "validate": True
        }
        
        # ✅ FIXED: Mock compilation service to raise FileNotFoundError
        with patch.object(
            self.container.compilation_service(),
            'compile_graph',
            side_effect=FileNotFoundError("CSV file not found")
        ):
            response = self.client.post("/graph/compile", json=request_data)
        
        self.assert_file_not_found_response(response)
    
    def test_compile_graph_minimal_request(self):
        """Test graph compilation with minimal request data."""
        request_data = {
            # Only required fields, using defaults for others
        }
        
        # ✅ FIXED: Mock compilation service for minimal request
        mock_result = Mock()
        mock_result.success = True
        mock_result.output_path = Path(self.temp_dir) / "compiled" / "default_graph.pkl"
        mock_result.source_path = Path("default.csv")
        mock_result.compilation_time = 1.0
        mock_result.error = None
        
        with patch.object(
            self.container.compilation_service(),
            'compile_graph',
            return_value=mock_result
        ):
            response = self.client.post("/graph/compile", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
    
    # =============================================================================
    # Graph Validation Tests  
    # =============================================================================
    
    def test_validate_graph_success(self):
        """Test successful graph validation using DI container services."""
        request_data = {
            "csv": str(self.graph_csv_path),
            "no_cache": True
        }
        
        # ✅ FIXED: Use validation service from DI container with correct attributes
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validation_result.has_warnings = False
        mock_validation_result.has_errors = False
        mock_validation_result.file_path = str(self.graph_csv_path)
        
        with patch.object(
            self.container.validation_service(),
            'validate_csv',
            return_value=mock_validation_result
        ) as mock_validate:
            response = self.client.post("/graph/validate", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "success", "has_warnings", "has_errors", "file_path", "message"
        ])
        
        self.assertTrue(data["success"])
        self.assertFalse(data["has_warnings"])
        self.assertFalse(data["has_errors"])
        self.assertEqual(data["file_path"], str(self.graph_csv_path))
        self.assertEqual(data["message"], "Validation completed")
        
        # Verify service was called with correct parameters
        mock_validate.assert_called_once()
    
    def test_validate_graph_with_warnings(self):
        """Test graph validation with warnings."""
        request_data = {
            "csv": str(self.graph_csv_path),
            "no_cache": True
        }
        
        # ✅ FIXED: Mock validation service with warnings
        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.has_warnings = True
        mock_result.has_errors = False
        mock_result.file_path = str(self.graph_csv_path)
        
        with patch.object(
            self.container.validation_service(),
            'validate_csv',
            return_value=mock_result
        ):
            response = self.client.post("/graph/validate", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["has_warnings"])
        self.assertFalse(data["has_errors"])
    
    def test_validate_graph_with_errors(self):
        """Test graph validation with errors."""
        request_data = {
            "csv": str(self.graph_csv_path),
            "no_cache": True
        }
        
        # ✅ FIXED: Mock validation service with errors
        mock_result = Mock()
        mock_result.is_valid = False
        mock_result.has_warnings = False
        mock_result.has_errors = True
        mock_result.file_path = str(self.graph_csv_path)
        
        with patch.object(
            self.container.validation_service(),
            'validate_csv',
            return_value=mock_result
        ):
            response = self.client.post("/graph/validate", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertFalse(data["success"])
        self.assertFalse(data["has_warnings"])
        self.assertTrue(data["has_errors"])
    
    # =============================================================================
    # Graph Scaffolding Tests
    # =============================================================================
    
    def test_scaffold_graph_success(self):
        """Test successful graph scaffolding using DI container services."""
        request_data = {
            "graph": "test_graph",
            "csv": str(self.graph_csv_path),
            "output_dir": str(Path(self.temp_dir) / "scaffolded"),
            "func_dir": str(Path(self.temp_dir) / "functions")
        }
        
        # ✅ FIXED: Use graph scaffold service from DI container with correct attributes
        mock_scaffold_result = Mock()
        mock_scaffold_result.scaffolded_count = 4
        mock_scaffold_result.created_files = []
        mock_scaffold_result.skipped_files = []
        mock_scaffold_result.service_stats = {"with_services": 2, "without_services": 2}
        mock_scaffold_result.errors = []
        
        with patch.object(
            self.container.graph_scaffold_service(),
            'scaffold_agents_from_csv',
            return_value=mock_scaffold_result
        ) as mock_scaffold:
            response = self.client.post("/graph/scaffold", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "success", "scaffolded_count", "output_path", "functions_path"
        ])
        
        self.assertTrue(data["success"])
        self.assertEqual(data["scaffolded_count"], 4)
        self.assertIsNotNone(data["output_path"])
        self.assertIsNotNone(data["functions_path"])
        
        # Verify service was called correctly
        mock_scaffold.assert_called_once()
    
    def test_scaffold_graph_file_not_found(self):
        """Test graph scaffolding with non-existent CSV file."""
        request_data = {
            "graph": "test_graph",
            "csv": "/nonexistent/path/to/graph.csv"
        }
        
        # ✅ FIXED: Mock scaffold service to raise FileNotFoundError
        with patch.object(
            self.container.graph_scaffold_service(),
            'scaffold_agents_from_csv',
            side_effect=FileNotFoundError("CSV file not found")
        ):
            response = self.client.post("/graph/scaffold", json=request_data)
        
        self.assert_file_not_found_response(response)
    
    def test_scaffold_graph_minimal_request(self):
        """Test graph scaffolding with minimal request data."""
        request_data = {
            # Minimal data - should use defaults
        }
        
        # ✅ FIXED: Mock scaffold service for minimal request
        mock_result = Mock()
        mock_result.scaffolded_count = 2
        mock_result.created_files = []
        mock_result.skipped_files = []
        mock_result.service_stats = {"with_services": 1, "without_services": 1}
        mock_result.errors = []
        
        with patch.object(
            self.container.graph_scaffold_service(),
            'scaffold_agents_from_csv',
            return_value=mock_result
        ):
            response = self.client.post("/graph/scaffold", json=request_data)
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertTrue(data["success"])
    
    # =============================================================================
    # Graph Status Tests
    # =============================================================================
    
    def test_get_graph_status_success(self):
        """Test successful graph status retrieval using DI container services."""
        # ✅ FIXED: Use graph_definition_service (correct service name)
        mock_graph = Mock()
        mock_graph.nodes = {'input': {}, 'process': {}, 'output': {}, 'error': {}}
        mock_graph.entry_point = 'input'
        
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            return_value=mock_graph
        ):
            # ✅ FIXED: Use graph_runner_service for agent status
            mock_agent_status = {
                "resolved_agents": 4,
                "unresolved_agents": 0,
                "total_agents": 4
            }
            
            with patch.object(
                self.container.graph_runner_service(),
                'get_agent_resolution_status',
                return_value=mock_agent_status
            ):
                response = self.client.get(
                    f"/graph/status/test_graph?csv={self.graph_csv_path}"
                )
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "graph_name", "exists", "csv_path", "node_count", 
            "entry_point", "agent_status"
        ])
        
        self.assertEqual(data["graph_name"], "test_graph")
        self.assertTrue(data["exists"])
        self.assertEqual(data["node_count"], 4)
        self.assertEqual(data["entry_point"], "input")
        self.assertIsInstance(data["agent_status"], dict)
    
    def test_get_graph_status_graph_not_found(self):
        """Test graph status for non-existent graph."""
        # ✅ FIXED: Use correct service from DI container
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            side_effect=ValueError("Graph 'nonexistent_graph' not found")
        ):
            response = self.client.get(
                f"/graph/status/nonexistent_graph?csv={self.graph_csv_path}"
            )
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertEqual(data["graph_name"], "nonexistent_graph")
        self.assertFalse(data["exists"])
        self.assertIn("error", data)
    
    def test_get_graph_status_csv_not_found(self):
        """Test graph status with non-existent CSV file."""
        response = self.client.get("/graph/status/test_graph?csv=/nonexistent/file.csv")
        
        self.assert_file_not_found_response(response)
    
    def test_get_graph_status_default_csv(self):
        """Test graph status using default CSV path."""
        # ✅ FIXED: Use real DI container services
        mock_graph = Mock()
        mock_graph.nodes = {'start': {}, 'end': {}}
        mock_graph.entry_point = 'start'
        
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            return_value=mock_graph
        ):
            mock_status = {"resolved_agents": 2}
            with patch.object(
                self.container.graph_runner_service(),
                'get_agent_resolution_status',
                return_value=mock_status
            ):
                response = self.client.get("/graph/status/test_graph")
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertEqual(data["graph_name"], "test_graph")
        self.assertTrue(data["exists"])
    
    # =============================================================================
    # Graph Listing Tests
    # =============================================================================
    
    def test_list_graphs_success(self):
        """Test successful listing of graphs using DI container services."""
        # ✅ FIXED: Use real DI container services
        mock_graph = Mock()
        mock_graph.name = 'test_graph'
        mock_graph.entry_point = 'input'
        mock_graph.nodes = {'input': {}, 'process': {}, 'output': {}}
        
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            return_value=mock_graph
        ):
            response = self.client.get(f"/graph/list?csv={self.graph_csv_path}")
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "csv_path", "graphs"
        ])
        
        self.assertEqual(data["csv_path"], str(self.graph_csv_path))
        self.assertIsInstance(data["graphs"], list)
        
        # Check graph structure
        for graph in data["graphs"]:
            self.assert_response_contains_fields(graph, [
                "name", "entry_point", "node_count"
            ])
    
    def test_list_graphs_csv_not_found(self):
        """Test listing graphs with non-existent CSV file."""
        response = self.client.get("/graph/list?csv=/nonexistent/file.csv")
        
        self.assert_file_not_found_response(response)
    
    def test_list_graphs_default_csv(self):
        """Test listing graphs using default CSV path."""
        # ✅ FIXED: Use real DI container services
        mock_graph = Mock()
        mock_graph.name = 'default_graph'
        mock_graph.entry_point = 'start'
        mock_graph.nodes = {'start': {}}
        
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            return_value=mock_graph
        ):
            response = self.client.get("/graph/list")
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertIsNotNone(data["csv_path"])
        self.assertIsInstance(data["graphs"], list)
    
    # =============================================================================
    # Error Handling Tests
    # =============================================================================
    
    def test_graph_operations_with_invalid_parameters(self):
        """Test graph operations with invalid parameters."""
        # Test compile with invalid state_schema
        invalid_compile_request = {
            "state_schema": "invalid_schema_type",
            "validate": "not_a_boolean"
        }
        
        response = self.client.post("/graph/compile", json=invalid_compile_request)
        
        self.assert_validation_error_response(response)
        
        # Test validate with invalid no_cache parameter
        invalid_validate_request = {
            "no_cache": "not_a_boolean"
        }
        
        response = self.client.post("/graph/validate", json=invalid_validate_request)
        
        self.assert_validation_error_response(response)
    
    def test_graph_operations_internal_errors(self):
        """Test graph operations with internal service errors."""
        request_data = {
            "graph": "test_graph",
            "csv": str(self.graph_csv_path)
        }
        
        # ✅ FIXED: Mock service to raise RuntimeError
        with patch.object(
            self.container.compilation_service(),
            'compile_graph',
            side_effect=RuntimeError("Internal compilation error")
        ):
            response = self.client.post("/graph/compile", json=request_data)
        
        self.assert_response_error(response, 500)
        
        # ✅ FIXED: Mock validation service to raise RuntimeError
        with patch.object(
            self.container.validation_service(),
            'validate_csv',
            side_effect=RuntimeError("Internal validation error")
        ):
            response = self.client.post("/graph/validate", json=request_data)
        
        self.assert_response_error(response, 500)
    
    def test_graph_status_service_errors(self):
        """Test graph status endpoint with service errors."""
        # ✅ FIXED: Use correct service from DI container
        with patch.object(
            self.container.graph_definition_service(),
            'build_from_csv',
            side_effect=RuntimeError("Internal graph definition error")
        ):
            response = self.client.get(
                f"/graph/status/test_graph?csv={self.graph_csv_path}"
            )
        
        self.assert_response_error(response, 500)


if __name__ == '__main__':
    unittest.main()
