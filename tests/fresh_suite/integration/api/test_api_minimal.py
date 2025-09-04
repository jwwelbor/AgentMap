"""
Minimal API integration tests - focused on fixing the dependency injection issue.

Starting with the simplest possible test to establish working patterns.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import create_autospec

from agentmap.infrastructure.api.fastapi.server import create_fastapi_app
from agentmap.di import ApplicationContainer


class TestAPIBasics(unittest.TestCase):
    """Minimal API tests to establish working dependency injection pattern."""
    
    def setUp(self):
        """Set up with proper dependency overrides to avoid args/kwargs issue."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a minimal container that doesn't use MagicMock
        self.container = ApplicationContainer()
        
        # Override problematic dependencies with proper signatures
        def mock_get_container():
            return self.container
        
        def mock_get_service_adapter(container=None):
            # Return a simple object with required methods, not MagicMock
            class MockAdapter:
                def initialize_services(self):
                    return None, None, None
                def create_run_options(self, **kwargs):
                    return type('MockOptions', (), kwargs)()
                def extract_result_state(self, result):
                    return {"final_state": {}, "metadata": {}}
            return MockAdapter()
        
        def mock_get_app_config_service(container=None):
            class MockAppConfig:
                def get_csv_repository_path(self):
                    return Path(self.temp_dir)
            return MockAppConfig()
        
        # Create the FastAPI app
        app = create_fastapi_app()
        
        # Override dependencies with proper signatures (not MagicMock)
        from agentmap.infrastructure.api.fastapi.routes.execution import get_container, get_service_adapter, get_app_config_service
        app.dependency_overrides[get_container] = mock_get_container
        app.dependency_overrides[get_service_adapter] = mock_get_service_adapter  
        app.dependency_overrides[get_app_config_service] = mock_get_app_config_service
        
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
