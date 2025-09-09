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
            # ✅ FIXED: Mock the instantiation summary method that API actually calls
            mock_instantiation_summary = {
                "graph_name": "test_graph",
                "total_nodes": 4,
                "instantiated": 4,
                "missing": 0,
                "agent_types": {
                    "default": {"count": 4, "instantiated": 4}
                }
            }
            
            with patch.object(
                self.container.graph_agent_instantiation_service(),
                'get_instantiation_summary',
                return_value=mock_instantiation_summary
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

    
    # =============================================================================
    # Error Handling Tests
    # =============================================================================

    
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
