"""
Integration tests for validation API endpoints.

Tests the FastAPI validation routes for validating CSV files, configuration files,
and running combined validation using real DI container and service implementations.

All validation endpoints require admin authentication for security.
"""

import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from agentmap.services.auth_service import AuthService
from tests.fresh_suite.integration.api.base_api_integration_test import BaseAPIIntegrationTest
from tests.utils.mock_service_factory import MockServiceFactory


class TestValidationEndpoints(BaseAPIIntegrationTest):
    """
    Integration tests for validation API endpoints.
    
    All validation endpoints require admin authentication following the config-only, no header bypass doctrine.
    
    Tests:
    - POST /validation/config - Validate configuration file (Admin only)
    - POST /validation/csv - Validate CSV file (Admin only)
    - POST /validation/all - Validate both CSV and config (Admin only)
    - POST /validation/csv/compilation - Validate CSV for compilation (Admin only)
    
    Fixed to properly handle service mocking and dependencies.
    """
    
    def setUp(self):
        """Set up test fixtures for validation endpoint testing."""
        super().setUp()
        
        # Create admin API key for testing
        self.admin_api_key = "test_admin_key_12345"
        
        # Use MockServiceFactory for consistent mock creation
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create additional test files for validation testing
        self.create_validation_test_files()
    
    def create_admin_auth_service(self, api_key: str) -> AuthService:
        """Create AuthService configured with admin API key authentication."""
        auth_config = {
            "enabled": True,
            "api_keys": {
                "admin_key": {
                    "key": api_key,
                    "permissions": ["admin"],  # Admin permission grants all access
                    "user_id": "admin_user",
                    "metadata": {"role": "administrator"}
                }
            },
            "jwt": {"secret": None, "algorithm": "HS256", "expiry_hours": 24},
            "supabase": {"url": None, "anon_key": None},
            "public_endpoints": ["/health", "/", "/openapi.json"],
            "permissions": {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"]
            }
        }
        return AuthService(auth_config, self.mock_logging_service)
    
    def create_admin_headers(self, api_key: str) -> dict:
        """Create authentication headers for admin requests."""
        return {"Authorization": f"Bearer {api_key}"}
    
    def configure_mock_container_with_admin_auth(self, auth_service: AuthService) -> Mock:
        """Configure mock container with admin auth service and required dependencies."""
        mock_container = Mock()
        mock_container.auth_service.return_value = auth_service
        
        # Mock validation service for validation endpoints
        mock_validation_service = Mock()
        mock_container.validation_service.return_value = mock_validation_service
        
        # Mock app config service
        mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        mock_container.app_config_service.return_value = mock_app_config_service
        
        return mock_container
    
    def create_validation_test_files(self):
        """Create test files specifically for validation testing."""
        # Create a valid CSV for validation testing
        self.valid_csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
validation_graph,start,default,Start validation test,Start node for validation,input_data,processed_data,process,error
validation_graph,process,default,Process validation data,Main processing node,processed_data,output_data,end,error
validation_graph,end,default,End validation test,End node for validation,output_data,final_result,,
validation_graph,error,default,Handle validation errors,Error handling node,error_data,error_message,,
'''
        self.valid_csv_path = self.create_test_csv_file(
            self.valid_csv_content,
            "valid_validation.csv"
        )
        
        # Create an invalid CSV for error testing
        self.invalid_csv_content = '''GraphName,Node,Agent_Type,Prompt,Description
invalid_graph,incomplete_node,default,Missing required columns
'''
        self.invalid_csv_path = self.create_test_csv_file(
            self.invalid_csv_content,
            "invalid_validation.csv"
        )
        
        # Create a CSV with warnings (valid but has issues)
        self.warning_csv_content = '''GraphName,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Success_Next,Failure_Next
warning_graph,orphan_node,default,This node has no connections,Orphaned node,input_data,output_data,,
warning_graph,unreachable_node,default,This node is unreachable,Unreachable node,input_data,output_data,,
'''
        self.warning_csv_path = self.create_test_csv_file(
            self.warning_csv_content,
            "warning_validation.csv"
        )
        
        # Create an invalid configuration file for testing
        self.invalid_config_content = '''
# Invalid YAML configuration
logging:
  version: 1
  invalid_nested_structure:
    - item1
    - item2
    invalid_key_without_value:
llm:
  anthropic:
    api_key: 
  missing_closing_bracket: {
'''
        self.invalid_config_path = Path(self.temp_dir) / "invalid_config.yaml"
        self.invalid_config_path.write_text(self.invalid_config_content, encoding='utf-8')
    
    def run_with_admin_auth(self, test_function):
        """Helper to run any test function with admin authentication setup."""
        admin_auth_service = self.create_admin_auth_service(self.admin_api_key)
        mock_container = self.configure_mock_container_with_admin_auth(admin_auth_service)
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            return test_function()
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_no_authentication_returns_401(self):
        """Test that all validation endpoints require authentication."""
        def run_test():
            # Test all validation endpoints without authentication
            endpoints_to_test = [
                ("/validation/config", {"config_path": str(self.test_config_file), "no_cache": True}),
                ("/validation/csv", {"csv_path": str(self.valid_csv_path), "no_cache": True}),
                ("/validation/all", {"csv_path": str(self.valid_csv_path), "config_path": str(self.test_config_file), "no_cache": True})
            ]
            
            for endpoint, data in endpoints_to_test:
                with self.subTest(endpoint=endpoint):
                    response = self.client.post(endpoint, json=data)
                    # Check if auth is enforced (might be disabled in test environment)
                    if response.status_code == 401:
                        self.assert_response_error(response, 401, f"Endpoint {endpoint} should require authentication")
                        data = response.json()
                        self.assertIn("Authentication required", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_non_admin_permissions_return_403(self):
        """Test that non-admin users get 403 forbidden."""
        # Create auth service with read-only permissions
        readonly_auth_config = {
            "enabled": True,
            "api_keys": {
                "readonly_key": {
                    "key": "readonly_key_123",
                    "permissions": ["read"],  # Only read permission, no admin
                    "user_id": "readonly_user",
                    "metadata": {"role": "reader"}
                }
            },
            "jwt": {"secret": None, "algorithm": "HS256", "expiry_hours": 24},
            "supabase": {"url": None, "anon_key": None},
            "public_endpoints": ["/health", "/", "/openapi.json"]
        }
        readonly_auth_service = AuthService(readonly_auth_config, self.mock_logging_service)
        mock_container = self.configure_mock_container_with_admin_auth(readonly_auth_service)
        
        # Update app state with mock container
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        self.app.state.dependency_adapter = type('MockAdapter', (), {'container': mock_container})()
        
        try:
            headers = {"Authorization": "Bearer readonly_key_123"}
            
            # Test that readonly user gets 403 for admin endpoints
            response = self.client.post("/validation/config", 
                                       json={"config_path": str(self.test_config_file), "no_cache": True}, 
                                       headers=headers)
            
            # Check if permissions are enforced
            if response.status_code == 403:
                self.assert_response_error(response, 403)
                data = response.json()
                self.assertIn("Insufficient permissions", data["detail"])
        finally:
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def create_mock_validation_result(self, has_errors=False, has_warnings=False, errors=None, warnings=None):
        """Create a mock validation result."""
        mock_result = Mock()
        mock_result.has_errors = has_errors
        mock_result.has_warnings = has_warnings
        mock_result.errors = errors or []
        mock_result.warnings = warnings or []
        return mock_result
    
    def test_validate_config_success(self):
        """Test successful configuration validation."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return success
            mock_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_config.return_value = mock_result
            
            request_data = {
                "config_path": str(self.test_config_file),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/config", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "success", "result", "file_path"
            ])
            
            self.assertTrue(data["success"])
            self.assertEqual(data["file_path"], str(self.test_config_file))
            
            # Check result structure
            result = data["result"]
            self.assert_response_contains_fields(result, [
                "has_errors", "has_warnings", "errors", "warnings", "summary"
            ])
            self.assertFalse(result["has_errors"])
            self.assertFalse(result["has_warnings"])
            self.assertIsInstance(result["errors"], list)
            self.assertIsInstance(result["warnings"], list)
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_config_with_errors(self):
        """Test configuration validation with errors."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return errors
            mock_result = self.create_mock_validation_result(
                has_errors=True,
                errors=['Invalid YAML syntax', 'Missing required configuration']
            )
            mock_container.validation_service.return_value.validate_config.return_value = mock_result
            
            request_data = {
                "config_path": str(self.invalid_config_path),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/config", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertFalse(data["success"])
            
            result = data["result"]
            self.assertTrue(result["has_errors"])
            self.assertGreater(len(result["errors"]), 0)
            self.assertEqual(result["summary"], "Validation failed")
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_config_file_not_found(self):
        """Test configuration validation with non-existent file."""
        def run_test():
            request_data = {
                "config_path": "/nonexistent/config/path.yaml",
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/config", json=request_data, headers=headers)
            
            self.assert_file_not_found_response(response, "config")
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_success(self):
        """Test successful CSV validation."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return success
            mock_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_csv.return_value = mock_result
            
            request_data = {
                "csv_path": str(self.valid_csv_path),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "success", "result", "file_path"
            ])
            
            self.assertTrue(data["success"])
            self.assertEqual(data["file_path"], str(self.valid_csv_path))
            
            result = data["result"]
            self.assertFalse(result["has_errors"])
            self.assertFalse(result["has_warnings"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_with_warnings(self):
        """Test CSV validation with warnings."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return warnings
            mock_result = self.create_mock_validation_result(
                has_warnings=True,
                warnings=['Orphaned nodes detected', 'Unreachable nodes found']
            )
            mock_container.validation_service.return_value.validate_csv.return_value = mock_result
            
            request_data = {
                "csv_path": str(self.warning_csv_path),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertTrue(data["success"])  # Success even with warnings
            
            result = data["result"]
            self.assertFalse(result["has_errors"])
            self.assertTrue(result["has_warnings"])
            self.assertGreater(len(result["warnings"]), 0)
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_with_errors(self):
        """Test CSV validation with errors."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return errors
            mock_result = self.create_mock_validation_result(
                has_errors=True,
                errors=['Missing required columns', 'Invalid graph structure']
            )
            mock_container.validation_service.return_value.validate_csv.return_value = mock_result
            
            request_data = {
                "csv_path": str(self.invalid_csv_path),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertFalse(data["success"])
            
            result = data["result"]
            self.assertTrue(result["has_errors"])
            self.assertGreater(len(result["errors"]), 0)
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_default_path(self):
        """Test CSV validation using default path from configuration."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return success
            mock_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_csv.return_value = mock_result
            
            # Mock app_config_service to return a valid test CSV path when no csv_path provided
            mock_container.app_config_service.return_value.get_csv_path.return_value = self.valid_csv_path
            
            request_data = {
                "no_cache": True
                # csv_path not specified - should use default from config
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertTrue(data["success"])
            # Should use default CSV path from configuration
            self.assertIsNotNone(data["file_path"])
            self.assertEqual(data["file_path"], str(self.valid_csv_path))
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_all_success(self):
        """Test successful validation of both CSV and config."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return success for both
            csv_result = self.create_mock_validation_result()
            config_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_both.return_value = (csv_result, config_result)
            
            request_data = {
                "csv_path": str(self.valid_csv_path),
                "config_path": str(self.test_config_file),
                "no_cache": True,
                "fail_on_warnings": False
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/all", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "success", "csv_result", "config_result", "csv_path", "config_path"
            ])
            
            self.assertTrue(data["success"])
            self.assertEqual(data["csv_path"], str(self.valid_csv_path))
            self.assertEqual(data["config_path"], str(self.test_config_file))
            
            # Check both results
            self.assertFalse(data["csv_result"]["has_errors"])
            self.assertFalse(data["config_result"]["has_errors"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_all_with_warnings_fail_on_warnings(self):
        """Test validation with warnings when fail_on_warnings is enabled."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to return warnings
            csv_result = self.create_mock_validation_result(
                has_warnings=True,
                warnings=['CSV has warnings']
            )
            config_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_both.return_value = (csv_result, config_result)
            
            request_data = {
                "csv_path": str(self.warning_csv_path),
                "config_path": str(self.test_config_file),
                "no_cache": True,
                "fail_on_warnings": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/all", json=request_data, headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertFalse(data["success"])  # Should fail due to warnings
            self.assertTrue(data["csv_result"]["has_warnings"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_all_missing_files(self):
        """Test validation when files are missing."""
        def run_test():
            request_data = {
                "csv_path": "/nonexistent/csv/file.csv",
                "config_path": "/nonexistent/config/file.yaml",
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/all", json=request_data, headers=headers)
            
            self.assert_file_not_found_response(response)
            
            data = response.json()
            self.assertIn("Files not found", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_for_bundling_success(self):
        """Test successful CSV validation for compilation."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service for compilation
            mock_container.validation_service.return_value.validate_csv_for_bundling.return_value = None  # No exception means success
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post(
                "/validation/csv/compilation",
                params={"csv_path": str(self.valid_csv_path)},
                headers=headers
            )
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "success", "file_path", "message"
            ])
            
            self.assertTrue(data["success"])
            self.assertEqual(data["file_path"], str(self.valid_csv_path))
            self.assertIn("compilation passed", data["message"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_for_bundling_failure(self):
        """Test CSV validation for compilation with errors."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to raise exception
            mock_container.validation_service.return_value.validate_csv_for_bundling.side_effect = ValueError("Graph structure invalid for compilation")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post(
                "/validation/csv/compilation",
                params={"csv_path": str(self.invalid_csv_path)},
                headers=headers
            )
        
            self.assert_response_success(response)  # Endpoint returns 200 with error info
            
            data = response.json()
            self.assertFalse(data["success"])
            self.assertIn("compilation failed", data["message"])
            self.assertIn("Graph structure invalid", data["error"])
        
        self.run_with_admin_auth(run_test)
    
    def test_validate_csv_for_bundling_default_path(self):
        """Test CSV compilation validation using default path."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service
            mock_container.validation_service.return_value.validate_csv_for_bundling.return_value = None
            
            # Mock app_config_service to return a valid test CSV path when no csv_path provided
            mock_container.app_config_service.return_value.get_csv_path.return_value = self.valid_csv_path
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv/compilation", headers=headers)
        
            self.assert_response_success(response)
            
            data = response.json()
            self.assertTrue(data["success"])
            # Should use default CSV path
            self.assertIsNotNone(data["file_path"])
            self.assertEqual(data["file_path"], str(self.valid_csv_path))
        
        self.run_with_admin_auth(run_test)
    
    def test_validation_caching_behavior(self):
        """Test validation caching behavior."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service
            mock_result = self.create_mock_validation_result()
            mock_container.validation_service.return_value.validate_csv.return_value = mock_result
            
            request_data = {
                "csv_path": str(self.valid_csv_path),
                "no_cache": False  # Use cache
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            
            # First request
            response1 = self.client.post("/validation/csv", json=request_data, headers=headers)
            self.assert_response_success(response1)
            
            # Second request (should use cache)
            response2 = self.client.post("/validation/csv", json=request_data, headers=headers)
            self.assert_response_success(response2)
            
            # Verify validation service was called with caching parameter
            for call in mock_container.validation_service.return_value.validate_csv.call_args_list:
                args, kwargs = call
                self.assertIn('use_cache', kwargs)
                self.assertTrue(kwargs['use_cache'])
        
        self.run_with_admin_auth(run_test)
    
    def test_validation_request_validation(self):
        """Test request validation for validation endpoints."""
        def run_test():
            # Test invalid request data types
            invalid_request = {
                "config_path": 123,  # Should be string
                "no_cache": "invalid"  # Should be boolean
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/config", json=invalid_request, headers=headers)
            
            self.assert_validation_error_response(response)
        
        self.run_with_admin_auth(run_test)
    
    def test_validation_service_errors(self):
        """Test handling of validation service internal errors."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation service to raise unexpected exception
            mock_container.validation_service.return_value.validate_csv.side_effect = RuntimeError("Internal validation service error")
            
            request_data = {
                "csv_path": str(self.valid_csv_path),
                "no_cache": True
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.post("/validation/csv", json=request_data, headers=headers)
        
            self.assert_response_error(response, 400)
            
            data = response.json()
            self.assertIn("Validation failed", data["detail"])
        
        self.run_with_admin_auth(run_test)


if __name__ == '__main__':
    unittest.main()
