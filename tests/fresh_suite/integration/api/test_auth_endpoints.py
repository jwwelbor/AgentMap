"""
Integration tests for API authentication and authorization.

Tests the AuthService integration with FastAPI endpoints using established
testing patterns from the fresh test suite guide.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.auth_service import AuthContext, AuthService
from tests.fresh_suite.integration.api.base_api_integration_test import BaseAPIIntegrationTest
from tests.utils.mock_service_factory import MockServiceFactory


class TestAuthenticationEndpoints(BaseAPIIntegrationTest):
    """
    Integration tests for API authentication and authorization.
    
    Following established patterns:
    - Use MockServiceFactory for consistent service mocking
    - Test AuthService integration with FastAPI routes
    - Focus on service interfaces, not implementation details
    - Use proper dependency injection patterns
    """
    
    def setUp(self):
        """Set up test fixtures using established patterns."""
        super().setUp()
        
        # Create test tokens and credentials
        self.valid_api_key = "test_api_key_12345"
        self.invalid_api_key = "invalid_api_key"
        self.valid_jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidGVzdF91c2VyIiwicGVybWlzc2lvbnMiOlsicmVhZCIsIndyaXRlIl19.test_signature"
        self.supabase_token = "sb-test-supabase-token-12345"
        
        # Use MockServiceFactory for consistent mock creation
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
    
    def create_auth_headers(self, token: str, method: str = "bearer") -> dict:
        """Create authentication headers for requests."""
        if method == "bearer":
            return {"Authorization": f"Bearer {token}"}
        elif method == "api_key_header":
            return {"X-API-Key": token}
        else:
            return {}
    
    def create_auth_service_with_config(self, auth_config: dict) -> AuthService:
        """Create AuthService with specific configuration."""
        return AuthService(auth_config, self.mock_logging_service)
    
    def create_disabled_auth_service(self) -> AuthService:
        """Create AuthService with authentication disabled."""
        disabled_config = {
            "enabled": False,
            "api_keys": {},
            "jwt": {"secret": None, "algorithm": "HS256", "expiry_hours": 24},
            "supabase": {"url": None, "anon_key": None},
            "public_endpoints": ["/", "/health", "/docs", "/openapi.json", "/redoc"],

            "permissions": {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"]
            }
        }
        return self.create_auth_service_with_config(disabled_config)
    
    def create_api_key_auth_service(self, api_key: str, permissions: list = None) -> AuthService:
        """Create AuthService configured with API key authentication."""
        if permissions is None:
            permissions = ["read", "write", "execute"]
            
        auth_config = {
            "enabled": True,
            "api_keys": {
                "test_key": {
                    "key": api_key,
                    "permissions": permissions,
                    "user_id": "test_user",
                    "metadata": {}
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
        return self.create_auth_service_with_config(auth_config)
    
    def test_public_endpoints_no_auth_required(self):
        """Test that public endpoints work without authentication."""
        # Test health endpoint (should be public)
        response = self.client.get("/health")
        self.assert_response_success(response)
        
        # Test root endpoint (should be public)
        response = self.client.get("/")
        self.assert_response_success(response)
        
        # Test OpenAPI docs (should be public)
        response = self.client.get("/openapi.json")
        self.assert_response_success(response)
    
    def test_authentication_disabled_mode(self):
        """Test API access when authentication is completely disabled."""
        # Create disabled auth service
        disabled_auth_service = self.create_disabled_auth_service()
        
        # Verify auth service behavior directly
        self.assertFalse(disabled_auth_service.is_authentication_enabled())
        
        # Test that disabled auth service allows access
        auth_context = disabled_auth_service.validate_api_key("any_key")
        self.assertTrue(auth_context.authenticated)
        self.assertEqual(auth_context.auth_method, 'disabled')
        self.assertIn('admin', auth_context.permissions)
        
        # Test that public endpoints work without authentication (this should always work)
        response = self.client.get("/health")
        self.assert_response_success(response)
        
        # Configure mock container to return our disabled auth service
        mock_container = Mock()
        mock_container.auth_service.return_value = disabled_auth_service
        # Also need to provide other services that /info/cache depends on
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Should be able to access protected endpoints without credentials when auth is disabled
            response = self.client.get("/info/cache")
            # The key test is that we don't get 401 Unauthorized due to auth being disabled
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_api_key_authentication_success(self):
        """Test successful API key authentication."""
        # Create auth service with valid API key
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        # Verify auth service behavior directly
        self.assertTrue(auth_service.is_authentication_enabled())
        
        # Test API key validation
        auth_context = auth_service.validate_api_key(self.valid_api_key)
        self.assertTrue(auth_context.authenticated)
        self.assertEqual(auth_context.auth_method, 'api_key')
        self.assertEqual(auth_context.user_id, 'test_user')
        self.assertIn('read', auth_context.permissions)
        self.assertIn('write', auth_context.permissions)
        
        # Test with FastAPI integration using established pattern
        # Configure mock container
        mock_container = Mock()
        mock_container.auth_service.return_value = auth_service
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Test with bearer token
            headers = self.create_auth_headers(self.valid_api_key)
            response = self.client.get("/info/cache", headers=headers)
            # Should not get 401 (auth passed), might get other errors due to service deps
            self.assertNotEqual(response.status_code, 401)
            
            # Test with X-API-Key header
            headers = self.create_auth_headers(self.valid_api_key, "api_key_header")
            response = self.client.get("/info/cache", headers=headers)
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_api_key_authentication_failure(self):
        """Test API key authentication failure."""
        # Create auth service with valid API key (but we'll test with invalid one)
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        # Verify auth service rejects invalid key
        auth_context = auth_service.validate_api_key(self.invalid_api_key)
        self.assertFalse(auth_context.authenticated)
        self.assertEqual(auth_context.auth_method, 'api_key')
        
        # Test with FastAPI integration
        # Configure mock container
        mock_container = Mock()
        mock_container.auth_service.return_value = auth_service
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Test with invalid API key
            headers = self.create_auth_headers(self.invalid_api_key)
            response = self.client.get("/info/cache", headers=headers)
            self.assert_response_error(response, 401)
            
            data = response.json()
            self.assertIn("Invalid authentication credentials", data["detail"])
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_no_authentication_credentials(self):
        """Test API access without any authentication credentials."""
        # Create auth service with enabled authentication
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        # Test with FastAPI integration
        # Configure mock container
        mock_container = Mock()
        mock_container.auth_service.return_value = auth_service
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Try to access protected endpoint without credentials
            response = self.client.get("/info/cache")
            self.assert_response_error(response, 401)
            
            data = response.json()
            self.assertIn("Authentication required", data["detail"])
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_config_based_authentication_only(self):
        """Test that authentication is based only on configuration, not headers."""
        # Test 1: When authentication is DISABLED in config -> allow access
        disabled_auth_service = self.create_disabled_auth_service()
        
        # Verify auth service behavior directly
        self.assertFalse(disabled_auth_service.is_authentication_enabled())
        
        # Configure mock container with disabled auth
        mock_container = Mock()
        mock_container.auth_service.return_value = disabled_auth_service
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Should work without any credentials when auth is disabled
            response = self.client.get("/info/cache")
            self.assertNotEqual(response.status_code, 401)
            
            # Headers should have no effect when auth is disabled
            headers = {"X-AgentMap-Embedded": "true"}
            response = self.client.get("/info/cache", headers=headers)
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
        
        # Test 2: When authentication is ENABLED in config -> require credentials
        enabled_auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        mock_container.auth_service.return_value = enabled_auth_service
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # Should require authentication when auth is enabled
            response = self.client.get("/info/cache")
            self.assertEqual(response.status_code, 401)
            
            # Headers should NOT bypass auth when auth is enabled
            headers = {"X-AgentMap-Embedded": "true"}
            response = self.client.get("/info/cache", headers=headers)
            self.assertEqual(response.status_code, 401)
            
            # Valid credentials should work
            headers = {"Authorization": f"Bearer {self.valid_api_key}"}
            response = self.client.get("/info/cache", headers=headers)
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_permission_based_access_control(self):
        """Test permission-based access control."""
        # Create auth service with limited permissions
        readonly_auth_service = self.create_api_key_auth_service(
            self.valid_api_key, 
            permissions=["read"]  # Only read permission
        )
        
        # Verify auth service behavior directly
        auth_context = readonly_auth_service.validate_api_key(self.valid_api_key)
        self.assertTrue(auth_context.authenticated)
        self.assertIn('read', auth_context.permissions)
        self.assertNotIn('write', auth_context.permissions)
        
        # Test permission validation
        self.assertTrue(readonly_auth_service.validate_permissions(auth_context, ['read']))
        self.assertFalse(readonly_auth_service.validate_permissions(auth_context, ['write']))
        
        # Test with FastAPI integration
        # Configure mock container
        mock_container = Mock()
        mock_container.auth_service.return_value = readonly_auth_service
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            headers = self.create_auth_headers(self.valid_api_key)
            
            # Should be able to access read endpoints
            response = self.client.get("/info/cache", headers=headers)
            # Auth should pass (not 401), may fail on other service dependencies
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_admin_permission_full_access(self):
        """Test that admin permission grants full access."""
        # Create auth service with admin permissions
        admin_auth_service = self.create_api_key_auth_service(
            self.valid_api_key,
            permissions=["admin"]  # Admin permission grants all access
        )
        
        # Verify auth service behavior directly
        auth_context = admin_auth_service.validate_api_key(self.valid_api_key)
        self.assertTrue(auth_context.authenticated)
        self.assertIn('admin', auth_context.permissions)
        
        # Test that admin permission allows everything
        self.assertTrue(admin_auth_service.validate_permissions(auth_context, ['read']))
        self.assertTrue(admin_auth_service.validate_permissions(auth_context, ['write']))
        self.assertTrue(admin_auth_service.validate_permissions(auth_context, ['execute']))
        self.assertTrue(admin_auth_service.validate_permissions(auth_context, ['admin']))
        
        # Test with FastAPI integration
        # Configure mock container
        mock_container = Mock()
        mock_container.auth_service.return_value = admin_auth_service
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            headers = self.create_auth_headers(self.valid_api_key)
            
            # Should be able to access all endpoints
            response = self.client.get("/info/cache", headers=headers)
            self.assertNotEqual(response.status_code, 401)
            
            # Should be able to access cache management
            response = self.client.get("/info/cache", headers=headers)
            self.assertNotEqual(response.status_code, 401)
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_auth_service_functionality(self):
        """Test AuthService core functionality directly."""
        # Test disabled authentication
        disabled_service = self.create_disabled_auth_service()
        self.assertFalse(disabled_service.is_authentication_enabled())
        
        # Test enabled authentication
        enabled_service = self.create_api_key_auth_service(self.valid_api_key)
        self.assertTrue(enabled_service.is_authentication_enabled())
        
        # Test API key validation
        valid_context = enabled_service.validate_api_key(self.valid_api_key)
        self.assertTrue(valid_context.authenticated)
        
        invalid_context = enabled_service.validate_api_key(self.invalid_api_key)
        self.assertFalse(invalid_context.authenticated)
        
        # Test public endpoints
        public_endpoints = enabled_service.get_public_endpoints()
        self.assertIn("/health", public_endpoints)
        self.assertIn("/", public_endpoints)
        
        # Test permission validation
        admin_context = AuthContext(
            authenticated=True,
            auth_method='api_key',
            user_id='admin',
            permissions=['admin']
        )
        self.assertTrue(enabled_service.validate_permissions(admin_context, ['read', 'write']))
        
        readonly_context = AuthContext(
            authenticated=True,
            auth_method='api_key',
            user_id='user',
            permissions=['read']
        )
        self.assertTrue(enabled_service.validate_permissions(readonly_context, ['read']))
        self.assertFalse(enabled_service.validate_permissions(readonly_context, ['write']))
    
    def test_auth_service_unavailable(self):
        """Test API behavior when auth service is unavailable."""
        # Test with container that raises exceptions when accessing auth service
        mock_container = Mock()
        mock_container.auth_service.side_effect = RuntimeError("Auth service unavailable")
        # Mock validation cache service for /info/cache endpoint
        mock_container.validation_cache_service.return_value = Mock()
        mock_container.validation_cache_service.return_value.get_validation_cache_stats.return_value = {
            "total_files": 0,
            "expired_files": 0,
            "corrupted_files": 0
        }
        
        # Store original dependency adapter
        original_adapter = getattr(self.app.state, 'dependency_adapter', None)
        
        # Create a mock adapter with our mock container
        mock_adapter = type('MockAdapter', (), {'container': mock_container})()
        self.app.state.dependency_adapter = mock_adapter
        
        try:
            # API should handle auth service errors gracefully
            response = self.client.get("/info/cache")
            # Should return 503 service unavailable, not 401
            self.assertIn(response.status_code, [500, 503])
        finally:
            # Restore original adapter
            if original_adapter:
                self.app.state.dependency_adapter = original_adapter
            else:
                delattr(self.app.state, 'dependency_adapter')
    
    def test_jwt_authentication_stub(self):
        """Test JWT authentication (stub implementation)."""
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        # JWT validation should return false (not implemented yet)
        jwt_context = auth_service.validate_jwt(self.valid_jwt)
        self.assertFalse(jwt_context.authenticated)
        self.assertEqual(jwt_context.auth_method, 'jwt')
    
    def test_supabase_authentication_stub(self):
        """Test Supabase authentication (stub implementation)."""
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        # Supabase validation should return false (not implemented yet)
        supabase_context = auth_service.validate_supabase_token(self.supabase_token)
        self.assertFalse(supabase_context.authenticated)
        self.assertEqual(supabase_context.auth_method, 'supabase')
    
    def test_auth_service_statistics(self):
        """Test auth service statistics and monitoring."""
        auth_service = self.create_api_key_auth_service(self.valid_api_key)
        
        stats = auth_service.get_auth_stats()
        self.assertTrue(stats['enabled'])
        self.assertEqual(stats['total_api_keys'], 1)
        self.assertEqual(stats['active_api_keys'], 1)
        self.assertFalse(stats['jwt_configured'])
        self.assertFalse(stats['supabase_configured'])
        self.assertGreater(stats['public_endpoints_count'], 0)


if __name__ == '__main__':
    unittest.main()
