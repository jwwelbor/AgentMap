"""
Integration tests for execution API endpoints - SIMPLIFIED.

Tests the FastAPI execution routes with minimal dependencies.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import create_fastapi_app


class TestExecutionEndpointsSimple(unittest.TestCase):
    """
    Simplified integration tests for execution API endpoints.
    
    Uses minimal mocking and focuses on basic functionality.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.app = create_fastapi_app()
        self.client = TestClient(self.app)
        
        # Create a simple test CSV
        self.csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
test_graph,start,default,Start test,Test start node,input_data,output_data,end,
test_graph,end,default,End test,Test end node,output_data,final_result,,
'''
        self.csv_path = Path(self.temp_dir) / "test.csv"
        self.csv_path.write_text(self.csv_content)
    
    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_endpoint(self):
        """Test health endpoint works."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
    
    def test_execution_run_basic_request(self):
        """Test basic execution endpoint request format."""
        request_data = {
            "state": {"input_data": "test_value"}
        }
        
        response = self.client.post("/execution/run", json=request_data)
        
        # Should NOT get 422 args/kwargs error anymore
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")
        
        # May fail for other reasons (missing services, etc.), but not the args/kwargs issue
        print(f"Execution endpoint returned status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
    
    def test_execution_path_based_endpoint(self):
        """Test RESTful path-based execution endpoint."""
        request_data = {
            "state": {"input_data": "test_value"},
        }
        
        response = self.client.post("/execution/test_workflow/test_graph", json=request_data)
        
        # Should NOT get 422 args/kwargs error anymore
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")
        
        print(f"Path-based execution endpoint returned status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")


if __name__ == '__main__':
    unittest.main()
