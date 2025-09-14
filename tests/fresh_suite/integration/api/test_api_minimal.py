"""
Minimal API integration tests - focused on fixing the dependency injection issue.

Starting with the simplest possible test to establish working patterns.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock

from agentmap.deployment.http.api.server import create_fastapi_app
from agentmap.di import ApplicationContainer


class TestAPIBasics(unittest.TestCase):
    """Minimal API tests to establish working dependency injection pattern."""
    
    def setUp(self):
        """Set up with proper dependency overrides to avoid args/kwargs issue."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock container with properly mocked services
        self.container = Mock(spec=ApplicationContainer)
        
        # Mock app config service
        mock_app_config = Mock()
        mock_app_config.get_csv_repository_path.return_value = Path(self.temp_dir)
        mock_app_config.get_csv_path.return_value = Path(self.temp_dir) / "default.csv"
        self.container.app_config_service.return_value = mock_app_config
        
        # Mock graph runner service
        mock_graph_runner = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.final_state = {"result": "test_success"}
        mock_result.error = None
        mock_result.total_duration = 1.0
        mock_result.execution_summary = None
        mock_graph_runner.run.return_value = mock_result
        self.container.graph_runner_service.return_value = mock_graph_runner
        
        # Mock graph bundle service
        mock_graph_bundle = Mock()
        mock_bundle = Mock()
        mock_graph_bundle.get_or_create_bundle.return_value = mock_bundle
        self.container.graph_bundle_service.return_value = mock_graph_bundle
        
        # Mock logging service (optional)
        mock_logging = Mock()
        mock_logger = Mock()
        mock_logging.get_logger.return_value = mock_logger
        self.container.logging_service.return_value = mock_logging
        
        # Mock auth service
        mock_auth = Mock()
        mock_auth.is_authentication_enabled.return_value = False  # Disable auth for tests
        self.container.auth_service.return_value = mock_auth
        
        # Create the FastAPI app
        app = create_fastapi_app()
        
        # Override the container in app state (this is how the new architecture works)
        app.state.container = self.container
        
        self.client = TestClient(app)
    
    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_endpoint_works(self):
        """Test that basic health endpoint works."""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
    
    def test_root_endpoint_works(self):
        """Test that root endpoint works."""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
    
    def test_execution_endpoint_basic(self):
        """Test basic execution endpoint with minimal request."""
        # Create a test CSV file
        csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
test_graph,start,default,Start test,Test start,input,output,,
'''
        csv_path = Path(self.temp_dir) / "test_workflow.csv"
        csv_path.write_text(csv_content)
        
        request_data = {
            "state": {"input": "test"}
        }
        
        response = self.client.post("/execution/run", json=request_data)
        
        # At this point, we just want to avoid the 422 args/kwargs error
        # Even if it fails for other reasons, it shouldn't be the dependency injection issue
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")


if __name__ == '__main__':
    unittest.main()
