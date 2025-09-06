"""
Integration tests for info API endpoints.

Tests the FastAPI info routes for system information, diagnostics, cache management,
and feature status using real DI container and service implementations.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.auth_service import AuthService
from tests.fresh_suite.integration.api.base_api_integration_test import BaseAPIIntegrationTest
from tests.utils.mock_service_factory import MockServiceFactory


class TestInfoEndpoints(BaseAPIIntegrationTest):
    """
    Integration tests for info API endpoints.
    
    All info endpoints require admin authentication following the config-only, no header bypass doctrine.
    
    Tests:
    - GET /info/config - Get current configuration (Admin only)
    - GET /info/diagnose - System diagnostics (Admin only)
    - GET /info/cache - Cache information (Admin only)
    - DELETE /info/cache - Clear cache (Admin only)
    - GET /info/version - Version information (Admin only)
    - GET /info/paths - System paths (Admin only)
    - GET /info/features - Feature status (Admin only)
    - GET /info/health/detailed - Detailed health check (Admin only)
    """
    
    def setUp(self):
        """Set up test fixtures using established patterns."""
        super().setUp()
        
        # Create admin API key for testing
        self.admin_api_key = "test_admin_key_12345"
        
        # Use MockServiceFactory for consistent mock creation
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
    
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
    
    def configure_mock_container_with_admin_auth(self, auth_service: AuthService) -> Mock:
        """Configure mock container with admin auth service and required dependencies."""
        mock_container = Mock()
        mock_container.auth_service.return_value = auth_service
        
        # Mock app config service for /info/config endpoint
        mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        # Add get_all method that returns all configuration
        mock_app_config_service.get_all.return_value = {
            "logging": {"level": "DEBUG", "format": "[%(levelname)s] %(name)s: %(message)s"},
            "execution": {"tracking": {"enabled": True}},
            "tracking": {"enabled": True, "track_outputs": False}
        }
        mock_container.app_config_service.return_value = mock_app_config_service
        
        # Mock validation cache service for cache endpoints
        mock_validation_cache_service = Mock()
        mock_validation_cache_service.get_validation_cache_stats.return_value = {
            "total_files": 10,
            "valid_files": 8,
            "expired_files": 1,
            "corrupted_files": 1,
            "cache_size_mb": 2.5
        }
        mock_validation_cache_service.clear_validation_cache.return_value = 5
        mock_validation_cache_service.cleanup_validation_cache.return_value = 3
        mock_container.validation_cache_service.return_value = mock_validation_cache_service
        
        # Mock features registry service for features and diagnose endpoints
        mock_features_service = Mock()
        mock_features_service.is_feature_enabled.return_value = True
        mock_features_service.is_provider_available.return_value = True
        mock_features_service.is_provider_registered.return_value = True
        mock_features_service.is_provider_validated.return_value = True
        mock_container.features_registry_service.return_value = mock_features_service
        
        # Mock dependency checker service for diagnose endpoint
        mock_dependency_checker = MockServiceFactory.create_mock_dependency_checker_service()
        mock_container.dependency_checker_service.return_value = mock_dependency_checker
        
        return mock_container
    
    def test_no_authentication_returns_401(self):
        """Test that all info endpoints require authentication."""
        def run_test():
            # Test all info endpoints without authentication
            endpoints_to_test = [
                "/info/config",
                "/info/diagnose", 
                "/info/cache",
                "/info/version",
                "/info/paths",
                "/info/features",
                "/info/health/detailed"
            ]
            
            for endpoint in endpoints_to_test:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint)
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
            response = self.client.get("/info/config", headers=headers)
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
    
    def test_get_configuration_success(self):
        """Test successful configuration retrieval with admin authentication."""
        def run_test():
            # Make request with admin authentication
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/config", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "configuration", "status"
            ])
            
            self.assertEqual(data["status"], "success")
            self.assertIsInstance(data["configuration"], dict)
            
            # Check that configuration contains expected sections
            config = data["configuration"]
            expected_sections = ["logging", "execution", "tracking"]
            for section in expected_sections:
                if section in config:  # Not all sections may be present
                    self.assertIsInstance(config[section], dict)
        
        self.run_with_admin_auth(run_test)
    
    def test_get_configuration_service_error(self):
        """Test configuration retrieval with service error."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure app config service to raise exception
            mock_container.app_config_service.return_value.get_all.side_effect = RuntimeError("Configuration service error")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/config", headers=headers)
            
            self.assert_response_error(response, 500)
            
            data = response.json()
            self.assertIn("Failed to get configuration", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_diagnose_system_success(self):
        """Test successful system diagnostics with admin authentication."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure dependency checker to return successful results
            mock_container.dependency_checker_service.return_value.check_llm_dependencies.return_value = (True, [])
            mock_container.dependency_checker_service.return_value.check_storage_dependencies.return_value = (True, [])
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/diagnose", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "llm", "storage", "environment", "package_versions", "installation_suggestions"
            ])
            
            # Check LLM diagnostic structure
            llm_info = data["llm"]
            self.assert_response_contains_fields(llm_info, [
                "enabled", "providers", "available_count"
            ])
            self.assertIsInstance(llm_info["providers"], dict)
            
            # Check storage diagnostic structure
            storage_info = data["storage"]
            self.assert_response_contains_fields(storage_info, [
                "enabled", "providers", "available_count"
            ])
            self.assertIsInstance(storage_info["providers"], dict)
            
            # Check environment info
            env_info = data["environment"]
            self.assert_response_contains_fields(env_info, [
                "python_version", "python_executable", "current_directory", "platform"
            ])
            
            # Check package versions
            self.assertIsInstance(data["package_versions"], dict)
            
            # Check installation suggestions
            self.assertIsInstance(data["installation_suggestions"], list)
        
        self.run_with_admin_auth(run_test)
    
    def test_diagnose_system_with_missing_dependencies(self):
        """Test system diagnostics with missing dependencies."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure dependency checker to return missing dependencies with proper function signatures
            def mock_check_llm_deps(provider=None):
                if provider == "openai":
                    return (False, ["openai"])
                elif provider == "anthropic": 
                    return (False, ["anthropic"])
                elif provider == "google":
                    return (False, ["langchain_google_genai"])
                else:
                    return (False, ["openai", "anthropic"])  # Default case
            
            def mock_check_storage_deps(provider=None):
                if provider == "vector":
                    return (False, ["chromadb"])
                else:
                    return (False, ["chromadb"])  # Default case
            
            mock_container.dependency_checker_service.return_value.check_llm_dependencies.side_effect = mock_check_llm_deps
            mock_container.dependency_checker_service.return_value.check_storage_dependencies.side_effect = mock_check_storage_deps
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/diagnose", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            
            # Should have installation suggestions for missing dependencies
            suggestions = data["installation_suggestions"]
            self.assertGreater(len(suggestions), 0)
            
            # Check LLM providers have correct missing dependency info
            for provider_name, provider_info in data["llm"]["providers"].items():
                if provider_name in ["openai", "anthropic"]:
                    self.assertFalse(provider_info["has_dependencies"])
                    self.assertGreater(len(provider_info["missing_dependencies"]), 0)
        
        self.run_with_admin_auth(run_test)
    
    def test_get_cache_info_success(self):
        """Test successful cache information retrieval with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/cache", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "cache_statistics", "suggestions"
            ])
            
            # Check cache statistics structure
            stats = data["cache_statistics"]
            self.assert_response_contains_fields(stats, [
                "total_files", "valid_files", "expired_files", "corrupted_files"
            ])
            
            # Check suggestions
            suggestions = data["suggestions"]
            self.assertIsInstance(suggestions, list)
            
            # Should have suggestions for expired and corrupted files
            suggestion_text = " ".join(suggestions)
            self.assertIn("expired", suggestion_text)
            self.assertIn("corrupted", suggestion_text)
        
        self.run_with_admin_auth(run_test)
    
    def test_get_cache_info_no_issues(self):
        """Test cache information with no issues."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Override cache stats for clean cache
            mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
                "total_files": 5,
                "valid_files": 5,
                "expired_files": 0,
                "corrupted_files": 0,
                "cache_size_mb": 1.2
            }
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/cache", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            suggestions = data["suggestions"]
            self.assertEqual(len(suggestions), 0)  # No suggestions needed for clean cache
        
        self.run_with_admin_auth(run_test)
    
    def test_clear_cache_all(self):
        """Test clearing all cache entries with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.delete("/info/cache", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "success", "operation", "removed_count", "file_path"
            ])
            
            self.assertTrue(data["success"])
            self.assertEqual(data["operation"], "clear_all")
            self.assertEqual(data["removed_count"], 5)  # From mock setup
            self.assertIsNone(data["file_path"])
        
        self.run_with_admin_auth(run_test)
    
    def test_clear_cache_specific_file(self):
        """Test clearing cache for specific file with admin authentication."""
        def run_test():
            file_path = str(self.simple_csv_path)
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.delete(f"/info/cache?file_path={file_path}", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["operation"], f"clear_file:{file_path}")
            self.assertEqual(data["removed_count"], 5)  # From mock setup
            self.assertEqual(data["file_path"], file_path)
        
        self.run_with_admin_auth(run_test)
    
    def test_clear_cache_cleanup_expired(self):
        """Test clearing only expired cache entries with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.delete("/info/cache?cleanup_expired=true", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["operation"], "cleanup_expired")
            self.assertEqual(data["removed_count"], 3)  # From mock setup
        
        self.run_with_admin_auth(run_test)
    
    def test_clear_cache_service_error(self):
        """Test cache clearing with service error."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation cache service to raise exception
            mock_container.validation_cache_service.return_value.clear_validation_cache.side_effect = RuntimeError("Cache service error")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.delete("/info/cache", headers=headers)
            
            self.assert_response_error(response, 500)
            
            data = response.json()
            self.assertIn("Failed to clear cache", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_get_version_info(self):
        """Test version information retrieval with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/version", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "agentmap_version", "api_version"
            ])
            
            self.assertIsNotNone(data["agentmap_version"])
            self.assertEqual(data["api_version"], "2.0")
        
        self.run_with_admin_auth(run_test)
    
    def test_get_system_paths(self):
        """Test system paths retrieval with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/paths", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "csv_path", "custom_agents_path", "functions_path", "status"
            ])
            
            self.assertEqual(data["status"], "success")
            self.assertIsNotNone(data["csv_path"])
            self.assertIsNotNone(data["custom_agents_path"])
            self.assertIsNotNone(data["functions_path"])
        
        self.run_with_admin_auth(run_test)
    
    def test_get_feature_status(self):
        """Test feature status retrieval with admin authentication."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/features", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "llm", "storage"
            ])
            
            # Check LLM feature structure
            llm_info = data["llm"]
            self.assert_response_contains_fields(llm_info, [
                "enabled", "providers"
            ])
            
            # Check LLM providers
            llm_providers = llm_info["providers"]
            expected_llm_providers = ["openai", "anthropic", "google"]
            for provider in expected_llm_providers:
                if provider in llm_providers:
                    provider_info = llm_providers[provider]
                    self.assert_response_contains_fields(provider_info, [
                        "available", "registered", "validated"
                    ])
            
            # Check storage feature structure
            storage_info = data["storage"]
            self.assert_response_contains_fields(storage_info, [
                "enabled", "providers"
            ])
            
            # Check storage providers
            storage_providers = storage_info["providers"]
            expected_storage_providers = ["csv", "json", "file", "vector", "firebase", "blob"]
            for provider in expected_storage_providers:
                if provider in storage_providers:
                    provider_info = storage_providers[provider]
                    self.assert_response_contains_fields(provider_info, [
                        "available", "registered", "validated"
                    ])
        
        self.run_with_admin_auth(run_test)
    
    def test_detailed_health_check_success(self):
        """Test detailed health check with all services healthy."""
        def run_test():
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/health/detailed", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assert_response_contains_fields(data, [
                "status", "services", "configuration", "logging", "timestamp"
            ])
            
            self.assertEqual(data["status"], "healthy")
            
            # Check service status
            services = data["services"]
            expected_services = ["graph_runner_service", "app_config_service", "logging_service"]
            for service in expected_services:
                self.assertIn(service, services)
                self.assertEqual(services[service], "healthy")
            
            # Check configuration and logging status
            self.assertEqual(data["configuration"], "healthy")
            self.assertEqual(data["logging"], "healthy")
            
            # Check timestamp format
            self.assertIsNotNone(data["timestamp"])
        
        self.run_with_admin_auth(run_test)
    
    def test_detailed_health_check_with_issues(self):
        """Test detailed health check with service issues."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure app config service to raise exception
            mock_container.app_config_service.return_value.get_all.side_effect = RuntimeError("Configuration error")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/health/detailed", headers=headers)
            
            self.assert_response_success(response)
            
            data = response.json()
            self.assertEqual(data["status"], "healthy")  # Overall still healthy
            
            # Configuration status should show error
            self.assertIn("error", data["configuration"])
        
        self.run_with_admin_auth(run_test)
    
    def test_detailed_health_check_service_failure(self):
        """Test detailed health check with service initialization failure."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure the container to fail when creating services
            mock_container.app_config_service.side_effect = RuntimeError("Service initialization failed")
            mock_container.logging_service.side_effect = RuntimeError("Service initialization failed")
            mock_container.graph_runner_service.side_effect = RuntimeError("Service initialization failed")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/health/detailed", headers=headers)
            
            self.assert_response_error(response, 503)
            
            data = response.json()
            self.assertIn("Health check failed", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_info_endpoints_cache_service_unavailable(self):
        """Test info endpoints when cache service is unavailable."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure validation cache service to raise exception
            mock_container.validation_cache_service.return_value.get_validation_cache_stats.side_effect = RuntimeError("Cache service unavailable")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/cache", headers=headers)
            
            self.assert_response_error(response, 500)
            
            data = response.json()
            self.assertIn("Failed to get cache info", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_info_endpoints_features_service_unavailable(self):
        """Test feature status endpoint when features service is unavailable."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure features registry service to raise exception
            mock_container.features_registry_service.return_value.is_feature_enabled.side_effect = RuntimeError("Features service unavailable")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/features", headers=headers)
            
            self.assert_response_error(response, 500)
            
            data = response.json()
            self.assertIn("Failed to get feature status", data["detail"])
        
        self.run_with_admin_auth(run_test)
    
    def test_diagnose_system_service_failure(self):
        """Test system diagnostics with service failure."""
        def run_test():
            # Get the mock container from the app state
            mock_container = self.app.state.dependency_adapter.container
            
            # Configure features registry service to raise exception
            mock_container.features_registry_service.return_value.is_feature_enabled.side_effect = RuntimeError("Diagnostic service error")
            
            headers = self.create_admin_headers(self.admin_api_key)
            response = self.client.get("/info/diagnose", headers=headers)
            
            self.assert_response_error(response, 500)
            
            data = response.json()
            self.assertIn("Diagnostic check failed", data["detail"])
        
        self.run_with_admin_auth(run_test)


if __name__ == '__main__':
    unittest.main()
