"""
Base API integration test class for FastAPI endpoint testing.

This module extends the BaseIntegrationTest with FastAPI-specific functionality
for testing REST API endpoints using the real DI container and service implementations.
"""

from abc import ABC
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import create_fastapi_app
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class BaseAPIIntegrationTest(BaseIntegrationTest, ABC):
    """
    Base class for FastAPI endpoint integration tests.
    
    This class provides:
    - FastAPI TestClient setup with real DI container
    - Common test data creation methods
    - HTTP request assertion helpers
    - Authentication testing utilities
    - Request/response validation helpers
    """
    
    def setUp(self):
        """Set up test fixtures with FastAPI client and real DI container."""
        super().setUp()
        
        # Create FastAPI app with the real DI container
        self.app = create_fastapi_app(self.container)
        self.client = TestClient(self.app)
        
        # Create test data files that endpoints will use
        self.setup_test_data()
    
    def setup_test_data(self):
        """Create test data files and configurations for API testing."""
        # Create test CSV files in the csv_data directory
        self.simple_csv_path = self.create_test_csv_file(
            self.create_simple_test_graph_csv(),
            "simple_test.csv"
        )
        
        self.complex_csv_path = self.create_test_csv_file(
            self.create_complex_test_graph_csv(),
            "complex_test.csv"
        )
        
        # Create additional test CSV for workflow repository testing
        self.workflow_csv_path = self.create_test_csv_file(
            self.create_workflow_test_csv(),
            "test_workflow.csv"
        )
        
        # Create test config files
        self.test_config_file = Path(self.temp_dir) / "test_config.yaml"
        self.create_test_config_file()
    
    def create_workflow_test_csv(self) -> str:
        """Create a test CSV with multiple graphs for workflow testing."""
        return '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
graph1,start,default,Start node for graph1,First graph start,input_data,processed_data,process,error
graph1,process,default,Process data for graph1,Process node,processed_data,result,end,error
graph1,end,default,End node for graph1,End processing,result,final_output,,
graph1,error,default,Handle errors for graph1,Error handler,error_data,error_message,,
graph2,begin,default,Begin node for graph2,Second graph start,input_data,validated_data,transform,fail
graph2,transform,default,Transform data for graph2,Data transformation,validated_data,transformed_data,finish,fail
graph2,finish,default,Finish node for graph2,Complete processing,transformed_data,final_result,,
graph2,fail,default,Failure node for graph2,Handle failures,error_data,failure_message,,
'''
    
    def create_test_config_file(self):
        """Create a test YAML configuration file."""
        config_content = """
# Test configuration for API integration tests
logging:
  version: 1
  disable_existing_loggers: false
  formatters:
    simple:
      format: '[%(levelname)s] %(name)s: %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      level: DEBUG
      formatter: simple
      stream: ext://sys.stdout
  root:
    level: DEBUG
    handlers: [console]

llm:
  anthropic:
    api_key: test_key_anthropic
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
  openai:
    api_key: test_key_openai
    model: gpt-3.5-turbo
    temperature: 0.7

execution:
  max_retries: 3
  timeout: 30
  tracking:
    enabled: true
    track_inputs: false
    track_outputs: false

paths:
  csv_data: {csv_data_path}
  compiled_graphs: {compiled_path}
  custom_agents: {custom_agents_path}
  functions: {functions_path}
""".format(
            csv_data_path=str(Path(self.temp_dir) / "csv_data"),
            compiled_path=str(Path(self.temp_dir) / "compiled"),
            custom_agents_path=str(Path(self.temp_dir) / "custom_agents"),
            functions_path=str(Path(self.temp_dir) / "functions")
        )
        
        self.test_config_file.write_text(config_content, encoding='utf-8')
    
    def assert_response_success(self, response, expected_status: int = 200, message: str = ""):
        """Assert that an HTTP response indicates success."""
        if message:
            message = f" - {message}"
        
        self.assertEqual(
            response.status_code, 
            expected_status,
            f"Expected status {expected_status}, got {response.status_code}{message}. "
            f"Response: {response.text}"
        )
    
    def assert_response_error(self, response, expected_status: int, message: str = ""):
        """Assert that an HTTP response indicates the expected error."""
        if message:
            message = f" - {message}"
            
        self.assertEqual(
            response.status_code,
            expected_status,
            f"Expected error status {expected_status}, got {response.status_code}{message}. "
            f"Response: {response.text}"
        )
    
    def assert_json_response(self, response, expected_status: int = 200):
        """Assert that response is valid JSON and return parsed data."""
        self.assert_response_success(response, expected_status)
        
        try:
            return response.json()
        except ValueError as e:
            self.fail(f"Response is not valid JSON: {e}. Response text: {response.text}")
    
    def assert_response_contains_fields(self, response_data: Dict[str, Any], required_fields: list):
        """Assert that response data contains all required fields."""
        for field in required_fields:
            self.assertIn(field, response_data, f"Response missing required field: {field}")
    
    def assert_validation_error_response(self, response, field_name: str = None):
        """Assert that response indicates a validation error."""
        self.assert_response_error(response, 422)
        
        response_data = response.json()
        self.assertIn("detail", response_data)
        
        if field_name:
            detail = response_data["detail"]
            if isinstance(detail, str):
                self.assertIn(field_name, detail.lower())
            elif isinstance(detail, list):
                # FastAPI validation errors return list of error objects
                field_errors = [error for error in detail if field_name in str(error)]
                self.assertGreater(len(field_errors), 0, 
                                 f"No validation errors found for field '{field_name}'")
    
    def assert_file_not_found_response(self, response, file_type: str = "file"):
        """Assert that response indicates a file not found error."""
        self.assert_response_error(response, 404)
        
        response_data = response.json()
        self.assertIn("detail", response_data)
        self.assertIn("not found", response_data["detail"].lower())
    
    def create_test_request_data(self, **kwargs) -> Dict[str, Any]:
        """Create test request data with default values."""
        default_data = {
            "state": {"input_data": "test_input"},
            "execution_id": None
        }
        default_data.update(kwargs)
        return default_data
    
    def create_resume_request_data(self, **kwargs) -> Dict[str, Any]:
        """Create test request data for resume endpoint."""
        default_data = {
            "thread_id": "test_thread_123",
            "response_action": "continue",
            "response_data": {"user_choice": "yes"}
        }
        default_data.update(kwargs)
        return default_data
    
    def create_validation_request_data(self, **kwargs) -> Dict[str, Any]:
        """Create test request data for validation endpoints."""
        default_data = {
            "csv_path": str(self.simple_csv_path),
            "no_cache": True
        }
        default_data.update(kwargs)
        return default_data
    
    def test_health_endpoint(self):
        """Test that health endpoint works as expected."""
        response = self.client.get("/health")
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "agentmap-api")
    
    def test_root_endpoint(self):
        """Test that root endpoint returns API information."""
        response = self.client.get("/")
        
        self.assert_response_success(response)
        
        data = response.json()
        self.assert_response_contains_fields(data, [
            "message", "version", "documentation", "authentication", "quick_start"
        ])
        self.assertEqual(data["version"], "2.0")
        # Removed old endpoints validation - now using standard FastAPI docs

        
        # Verify documentation structure
        self.assertIn("documentation", data)
        documentation = data["documentation"]
        self.assertIsInstance(documentation, dict)
        self.assertIn("interactive_docs", documentation)
        self.assertIn("openapi_schema", documentation)
        
        # Verify authentication structure
        self.assertIn("authentication", data)
        auth = data["authentication"]
        self.assertIsInstance(auth, dict)
        self.assertIn("modes", auth)
        self.assertIsInstance(auth["modes"], list)
        
        # Verify endpoints structure
        # Old endpoints validation removed - using FastAPI /docs instead
        # Test structure aligns with FastAPI standards







        
        # Verify additional helpful sections
        self.assertIn("quick_start", data)
        self.assertIsInstance(data["quick_start"], dict)
        self.assertIn("repository_structure", data)
        self.assertIsInstance(data["repository_structure"], dict)
    
    def test_openapi_docs_accessible(self):
        """Test that OpenAPI documentation is accessible."""
        # Test OpenAPI JSON
        response = self.client.get("/openapi.json")
        self.assert_response_success(response)
        
        openapi_data = response.json()
        self.assertIn("openapi", openapi_data)
        self.assertIn("info", openapi_data)
        self.assertIn("paths", openapi_data)
        
        # Test Swagger UI docs
        response = self.client.get("/docs")
        self.assert_response_success(response)
        self.assertIn("swagger", response.text.lower())
    
    def create_invalid_csv_content(self) -> str:
        """Create invalid CSV content for testing error cases."""
        return '''Invalid,CSV,Structure
missing_required_columns,test,content
'''
    
    def create_large_test_data(self) -> Dict[str, Any]:
        """Create test data that exceeds size limits for testing validation."""
        # Create a large state object that should trigger size validation
        large_data = {"key_" + str(i): "value_" * 1000 for i in range(1000)}
        return {"state": large_data}


class APITestCase(BaseAPIIntegrationTest):
    """
    Alias for BaseAPIIntegrationTest for backward compatibility.
    """
    pass
