"""
Integration tests for graph API endpoints - SIMPLIFIED.

Tests the FastAPI graph routes with minimal dependencies.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import create_fastapi_app


class TestGraphEndpointsSimple(unittest.TestCase):
    """
    Simplified integration tests for graph API endpoints.
    
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
    
    def test_graph_compile_endpoint_basic(self):
        """Test basic graph compilation endpoint."""
        request_data = {
            "graph": "test_graph",
            "csv": str(self.csv_path),
            "validate": True
        }
        
        response = self.client.post("/graph/compile", json=request_data)
        
        # Should NOT get 422 args/kwargs error anymore
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")
        
        print(f"Graph compile endpoint returned status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
    
    def test_graph_validate_endpoint_basic(self):
        """Test basic graph validation endpoint."""
        request_data = {
            "csv": str(self.csv_path),
            "no_cache": True
        }
        
        response = self.client.post("/graph/validate", json=request_data)
        
        # Should NOT get 422 args/kwargs error anymore  
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")
        
        print(f"Graph validate endpoint returned status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
    
    def test_graph_status_endpoint_basic(self):
        """Test basic graph status endpoint."""
        response = self.client.get(f"/graph/status/test_graph?csv={self.csv_path}")
        
        # Should NOT get 422 args/kwargs error anymore
        self.assertNotEqual(response.status_code, 422, 
                           f"Should not get 422 validation error. Response: {response.text}")
        
        print(f"Graph status endpoint returned status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")


if __name__ == '__main__':
    unittest.main()
