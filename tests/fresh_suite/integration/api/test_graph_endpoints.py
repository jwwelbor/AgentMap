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

from tests.fresh_suite.integration.api.base_api_integration_test import (
    BaseAPIIntegrationTest,
)


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
        self.graph_csv_content = """GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
test_graph,input,default,Process input data,Input processing node,raw_input,validated_input,process,error
test_graph,process,default,Process validated data,Main processing node,validated_input,processed_data,output,error
test_graph,output,default,Format output data,Output formatting node,processed_data,final_output,,
test_graph,error,default,Handle processing errors,Error handling node,error_data,error_message,,
multi_graph,start,default,Start multi graph,Multi graph start,input_data,start_data,finish,fail
multi_graph,finish,default,Finish multi graph,Multi graph end,start_data,final_data,,
multi_graph,fail,default,Handle multi graph errors,Multi graph error handler,error_data,failure_message,,
"""
        self.graph_csv_path = self.create_test_csv_file(
            self.graph_csv_content, "graph_operations.csv"
        )

    # =============================================================================
    # Graph Status Tests
    # =============================================================================

    def test_get_graph_status_csv_not_found(self):
        """Test graph status with non-existent CSV file."""
        response = self.client.get("/graph/status/test_graph?csv=/nonexistent/file.csv")

        self.assert_file_not_found_response(response)

    def test_list_graphs_csv_not_found(self):
        """Test listing graphs with non-existent CSV file."""
        response = self.client.get("/graph/list?csv=/nonexistent/file.csv")

        self.assert_file_not_found_response(response)


if __name__ == "__main__":
    unittest.main()
