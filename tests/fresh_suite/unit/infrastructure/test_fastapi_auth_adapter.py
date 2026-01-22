"""
Unit tests for FastAPIAuthAdapter.

Tests FastAPI-specific authentication adapter that wraps pure AuthService.
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from agentmap.deployment.http.api.middleware.auth import FastAPIAuthAdapter
from agentmap.services.auth_service import AuthContext, AuthService


class TestFastAPIAuthAdapter(unittest.TestCase):
    """Test FastAPI authentication adapter."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock auth service
        self.mock_auth_service = MagicMock(spec=AuthService)
        self.mock_auth_service.is_authentication_enabled.return_value = True
        self.mock_auth_service.get_public_endpoints.return_value = [
            "/health",
            "/docs",
            "/",
            "/openapi.json",
        ]

        # Create adapter
        self.adapter = FastAPIAuthAdapter(self.mock_auth_service)

    def test_init(self):
        """Test adapter initialization."""
        self.assertIsInstance(self.adapter, FastAPIAuthAdapter)
        self.assertEqual(self.adapter.auth_service, self.mock_auth_service)
        self.assertIsNotNone(self.adapter.security)

    def test_get_auth_method_api_key_header(self):
        """Test auth method detection for API key in header."""
        request = MagicMock(spec=Request)
        request.headers = {"x-api-key": "test-key"}
        request.query_params = {}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "api_key")

    def test_get_auth_method_api_key_query(self):
        """Test auth method detection for API key in query."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.query_params = {"api_key": "test-key"}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "api_key")

    def test_get_auth_method_bearer_api_key(self):
        """Test auth method detection for bearer token (API key)."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer test-api-key"}
        request.query_params = {}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "api_key")

    def test_get_auth_method_jwt(self):
        """Test auth method detection for JWT token."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer eyJ.test.jwt"}
        request.query_params = {}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "jwt")

    def test_get_auth_method_supabase(self):
        """Test auth method detection for Supabase token."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer sb-test-token"}
        request.query_params = {}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "supabase")

    def test_get_auth_method_none(self):
        """Test auth method detection when no auth present."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.query_params = {}

        method = self.adapter._get_auth_method(request)
        self.assertEqual(method, "none")

    def test_extract_credentials_bearer_token(self):
        """Test credential extraction from bearer token."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.query_params = {}

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="test-token"
        )

        token = self.adapter._extract_credentials(request, credentials)
        self.assertEqual(token, "test-token")

    def test_extract_credentials_auth_header(self):
        """Test credential extraction from authorization header."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer test-token"}
        request.query_params = {}

        token = self.adapter._extract_credentials(request, None)
        self.assertEqual(token, "test-token")

    def test_extract_credentials_api_key_header(self):
        """Test credential extraction from X-API-Key header."""
        request = MagicMock(spec=Request)
        request.headers = {"x-api-key": "test-key"}
        request.query_params = {}

        token = self.adapter._extract_credentials(request, None)
        self.assertEqual(token, "test-key")

    def test_extract_credentials_query_param(self):
        """Test credential extraction from query parameter."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.query_params = {"api_key": "test-key"}

        token = self.adapter._extract_credentials(request, None)
        self.assertEqual(token, "test-key")

    def test_extract_credentials_none(self):
        """Test credential extraction when none present."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.query_params = {}

        token = self.adapter._extract_credentials(request, None)
        self.assertIsNone(token)

    def test_is_public_endpoint_exact_match(self):
        """Test public endpoint detection for exact match."""
        request = MagicMock(spec=Request)
        request.url.path = "/health"

        is_public = self.adapter._is_public_endpoint(request, ["/health", "/docs"])
        self.assertTrue(is_public)

    def test_is_public_endpoint_wildcard(self):
        """Test public endpoint detection for wildcard match."""
        request = MagicMock(spec=Request)
        request.url.path = "/docs/api"

        is_public = self.adapter._is_public_endpoint(request, ["/docs/*"])
        self.assertTrue(is_public)

    def test_is_public_endpoint_regex(self):
        """Test public endpoint detection for regex match."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/health"

        is_public = self.adapter._is_public_endpoint(request, ["^/api/v[0-9]+/health$"])
        self.assertTrue(is_public)

    def test_is_public_endpoint_no_match(self):
        """Test public endpoint detection when no match."""
        request = MagicMock(spec=Request)
        request.url.path = "/private/data"

        is_public = self.adapter._is_public_endpoint(request, ["/health", "/docs"])
        self.assertFalse(is_public)

    async def test_auth_dependency_disabled(self):
        """Test auth dependency when authentication is disabled."""
        self.mock_auth_service.is_authentication_enabled.return_value = False

        dependency = self.adapter.create_dependency()
        request = MagicMock(spec=Request)

        result = await dependency(request, None)

        self.assertIsInstance(result, AuthContext)
        self.assertTrue(result.authenticated)
        self.assertEqual(result.auth_method, "disabled")
        self.assertEqual(result.user_id, "system")
        self.assertIn("admin", result.permissions)

    async def test_auth_dependency_public_endpoint(self):
        """Test auth dependency for public endpoint."""
        dependency = self.adapter.create_dependency()

        request = MagicMock(spec=Request)
        request.url.path = "/health"

        result = await dependency(request, None)

        self.assertIsInstance(result, AuthContext)
        self.assertTrue(result.authenticated)
        self.assertEqual(result.auth_method, "public")
        self.assertEqual(result.user_id, "public")
        self.assertIn("read", result.permissions)

    async def test_auth_dependency_valid_api_key(self):
        """Test auth dependency with valid API key."""
        # Set up mock auth service response
        auth_context = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="test-user",
            permissions=["read", "write"],
        )
        self.mock_auth_service.validate_api_key.return_value = auth_context

        dependency = self.adapter.create_dependency()

        request = MagicMock(spec=Request)
        request.url.path = "/api/data"
        request.headers = {"x-api-key": "valid-key"}
        request.query_params = {}

        result = await dependency(request, None)

        self.assertEqual(result, auth_context)
        self.mock_auth_service.validate_api_key.assert_called_once_with("valid-key")

    async def test_auth_dependency_invalid_api_key(self):
        """Test auth dependency with invalid API key."""
        # Set up mock auth service response
        auth_context = AuthContext(authenticated=False, auth_method="api_key")
        self.mock_auth_service.validate_api_key.return_value = auth_context

        dependency = self.adapter.create_dependency()

        request = MagicMock(spec=Request)
        request.url.path = "/api/data"
        request.headers = {"x-api-key": "invalid-key"}
        request.query_params = {}

        with self.assertRaises(HTTPException) as context:
            await dependency(request, None)

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Invalid authentication credentials")

    async def test_auth_dependency_missing_token_required(self):
        """Test auth dependency when token missing and auth required."""
        dependency = self.adapter.create_dependency(optional=False)

        request = MagicMock(spec=Request)
        request.url.path = "/api/data"
        request.headers = {}
        request.query_params = {}

        with self.assertRaises(HTTPException) as context:
            await dependency(request, None)

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Authentication required")

    async def test_auth_dependency_missing_token_optional(self):
        """Test auth dependency when token missing and auth optional."""
        dependency = self.adapter.create_dependency(optional=True)

        request = MagicMock(spec=Request)
        request.url.path = "/api/data"
        request.headers = {}
        request.query_params = {}

        result = await dependency(request, None)

        self.assertIsInstance(result, AuthContext)
        self.assertFalse(result.authenticated)
        self.assertEqual(result.auth_method, "none")

    async def test_auth_dependency_invalid_token_optional(self):
        """Test auth dependency when token invalid and auth optional."""
        # Set up mock auth service response
        auth_context = AuthContext(authenticated=False, auth_method="api_key")
        self.mock_auth_service.validate_api_key.return_value = auth_context

        dependency = self.adapter.create_dependency(optional=True)

        request = MagicMock(spec=Request)
        request.url.path = "/api/data"
        request.headers = {"x-api-key": "invalid-key"}
        request.query_params = {}

        result = await dependency(request, None)

        self.assertIsInstance(result, AuthContext)
        self.assertFalse(result.authenticated)
        self.assertEqual(result.auth_method, "api_key")

    def test_require_permissions_authenticated(self):
        """Test permission check with authenticated user."""
        auth_context = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="test-user",
            permissions=["read", "write"],
        )

        perm_dependency = self.adapter.require_permissions(["read"])
        result = perm_dependency(auth_context)

        self.assertEqual(result, auth_context)

    def test_require_permissions_admin_bypass(self):
        """Test permission check with admin user."""
        auth_context = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="admin-user",
            permissions=["admin"],
        )

        perm_dependency = self.adapter.require_permissions(["read", "write", "execute"])
        result = perm_dependency(auth_context)

        self.assertEqual(result, auth_context)

    def test_require_permissions_missing(self):
        """Test permission check with missing permissions."""
        auth_context = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="test-user",
            permissions=["read"],
        )

        perm_dependency = self.adapter.require_permissions(["write", "execute"])

        with self.assertRaises(HTTPException) as context:
            perm_dependency(auth_context)

        self.assertEqual(context.exception.status_code, 403)
        self.assertIn("Missing: write, execute", context.exception.detail)

    def test_require_permissions_not_authenticated(self):
        """Test permission check with unauthenticated user."""
        auth_context = AuthContext(authenticated=False, auth_method="none")

        perm_dependency = self.adapter.require_permissions(["read"])

        with self.assertRaises(HTTPException) as context:
            perm_dependency(auth_context)

        self.assertEqual(context.exception.status_code, 401)

    def test_no_fastapi_imports_in_auth_service(self):
        """Test that AuthService has no FastAPI imports."""
        # Import the auth service module
        import agentmap.services.auth_service

        # Check that FastAPI modules are not imported
        module_dict = vars(agentmap.services.auth_service)
        fastapi_imports = [
            key
            for key in module_dict
            if key.startswith("fastapi")
            or (
                hasattr(module_dict[key], "__module__")
                and isinstance(module_dict[key].__module__, str)
                and "fastapi" in module_dict[key].__module__
            )
        ]

        self.assertEqual(
            fastapi_imports,
            [],
            f"Found FastAPI imports in auth_service.py: {fastapi_imports}",
        )


if __name__ == "__main__":
    unittest.main()
