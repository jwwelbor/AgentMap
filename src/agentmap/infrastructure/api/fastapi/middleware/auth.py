"""
FastAPI authentication adapter for AgentMap API.

This module provides FastAPI-specific authentication middleware and dependency
functions, wrapping the pure AuthService with framework-specific concerns.
"""

import re
from typing import Annotated, Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentmap.services.auth_service import AuthContext, AuthService


class FastAPIAuthAdapter:
    """
    FastAPI authentication adapter that wraps pure AuthService.

    Handles all FastAPI-specific authentication concerns while delegating
    business logic to the pure AuthService.
    """

    def __init__(self, auth_service: AuthService):
        """
        Initialize FastAPI authentication adapter.

        Args:
            auth_service: Pure authentication service
        """
        self.auth_service = auth_service
        self.security = HTTPBearer(auto_error=False)

    def _get_auth_method(self, request: Request) -> str:
        """
        Detect the authentication method from the request.

        Args:
            request: FastAPI request object

        Returns:
            Authentication method: 'api_key', 'jwt', 'supabase', or 'none'
        """
        # Check for Authorization header
        auth_header = request.headers.get("authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove 'Bearer ' prefix

            # Simple heuristics to detect token type
            if token.startswith("sb-"):  # Supabase tokens typically start with 'sb-'
                return "supabase"
            elif (
                "." in token and len(token.split(".")) == 3
            ):  # JWT has 3 parts separated by dots
                return "jwt"
            else:
                return "api_key"  # Default to API key for other bearer tokens

        # Check for X-API-Key header
        if request.headers.get("x-api-key"):
            return "api_key"

        # Check for query parameter
        if request.query_params.get("api_key"):
            return "api_key"

        return "none"

    def _extract_credentials(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None,
    ) -> Optional[str]:
        """
        Extract authentication credentials from the request.

        Args:
            request: FastAPI request object
            credentials: Optional bearer token credentials

        Returns:
            Authentication token or None if not found
        """
        # Try bearer token first
        if credentials and credentials.credentials:
            return credentials.credentials

        # Try Authorization header manually (for non-bearer tokens)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        # Try X-API-Key header
        api_key = request.headers.get("x-api-key")
        if api_key:
            return api_key

        # Try query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key

        return None

    def _is_public_endpoint(
        self, request: Request, public_endpoints: List[str]
    ) -> bool:
        """
        Check if the requested endpoint is public (doesn't require authentication).

        Args:
            request: FastAPI request object
            public_endpoints: List of public endpoint patterns

        Returns:
            True if endpoint is public
        """
        path = request.url.path

        for pattern in public_endpoints:
            # Support both exact matches and wildcard patterns
            if pattern.endswith("*"):
                if path.startswith(pattern[:-1]):
                    return True
            elif pattern == path:
                return True
            # Support regex patterns (if they start with ^)
            elif pattern.startswith("^"):
                if re.match(pattern, path):
                    return True

        return False

    def create_dependency(self, optional: bool = False) -> Callable:
        """
        Create authentication dependency function.

        Args:
            optional: If True, authentication is optional

        Returns:
            FastAPI dependency function
        """

        async def auth_dependency(
            request: Request,
            credentials: Annotated[
                Optional[HTTPAuthorizationCredentials], Depends(self.security)
            ] = None,
        ) -> AuthContext:
            """
            FastAPI dependency for authentication.

            Args:
                request: FastAPI request object
                credentials: Optional bearer token credentials

            Returns:
                AuthContext with authentication results

            Raises:
                HTTPException: 401 if authentication required but failed
            """
            # Check if authentication is disabled
            if not self.auth_service.is_authentication_enabled():
                return AuthContext(
                    authenticated=True,
                    auth_method="disabled",
                    user_id="system",
                    permissions=["admin"],
                )

            # Check if endpoint is public
            public_endpoints = self.auth_service.get_public_endpoints()
            if self._is_public_endpoint(request, public_endpoints):
                return AuthContext(
                    authenticated=True,
                    auth_method="public",
                    user_id="public",
                    permissions=["read"],
                )

            # Extract credentials
            token = self._extract_credentials(request, credentials)

            if not token:
                if optional:
                    return AuthContext(authenticated=False, auth_method="none")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Determine authentication method and validate
            auth_method = self._get_auth_method(request)
            auth_context = None

            if auth_method == "api_key":
                auth_context = self.auth_service.validate_api_key(token)
            elif auth_method == "jwt":
                auth_context = self.auth_service.validate_jwt(token)
            elif auth_method == "supabase":
                auth_context = self.auth_service.validate_supabase_token(token)
            else:
                # Default to API key validation
                auth_context = self.auth_service.validate_api_key(token)

            # Check authentication result
            if not auth_context or not auth_context.authenticated:
                if optional:
                    return AuthContext(authenticated=False, auth_method=auth_method)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return auth_context

        return auth_dependency

    def require_auth(self) -> Callable:
        """
        Create dependency that requires authentication.

        Returns:
            FastAPI dependency function that requires authentication
        """
        return self.create_dependency(optional=False)

    def optional_auth(self) -> Callable:
        """
        Create dependency for optional authentication.

        Returns:
            FastAPI dependency function with optional authentication
        """
        return self.create_dependency(optional=True)

    def require_permissions(self, required_permissions: List[str]) -> Callable:
        """
        Create dependency that requires specific permissions.

        Args:
            required_permissions: List of required permissions

        Returns:
            FastAPI dependency function that checks permissions
        """

        def permission_dependency(auth_context: AuthContext) -> AuthContext:
            """
            Check if user has required permissions.

            Args:
                auth_context: Authentication context from auth dependency

            Returns:
                AuthContext if permissions are satisfied

            Raises:
                HTTPException: 403 if permissions are insufficient
            """
            if not auth_context.authenticated:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Admin permission grants all access
            if "admin" in auth_context.permissions:
                return auth_context

            # Check if user has all required permissions
            missing_permissions = [
                perm
                for perm in required_permissions
                if perm not in auth_context.permissions
            ]

            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Missing: {', '.join(missing_permissions)}",
                )

            return auth_context

        return permission_dependency

    def create_permission_dependency(self, required_permissions: List[str]) -> Callable:
        """
        Create combined auth + permission dependency.

        Args:
            required_permissions: List of required permissions

        Returns:
            FastAPI dependency function that combines auth and permission checks
        """
        auth_dep = self.require_auth()
        perm_dep = self.require_permissions(required_permissions)

        async def combined_dependency(
            request: Request,
            credentials: Annotated[
                Optional[HTTPAuthorizationCredentials], Depends(self.security)
            ] = None,
        ) -> AuthContext:
            """
            Combined authentication and permission check.

            Args:
                request: FastAPI request object
                credentials: Optional bearer token credentials

            Returns:
                AuthContext if auth and permissions are satisfied
            """
            # First check authentication
            auth_context = await auth_dep(request, credentials)

            # Then check permissions
            return perm_dep(auth_context)

        return combined_dependency

    # Common permission combinations
    def require_read_permission(self) -> Callable:
        """Dependency that requires read permission."""
        return self.create_permission_dependency(["read"])

    def require_write_permission(self) -> Callable:
        """Dependency that requires write permission."""
        return self.create_permission_dependency(["write"])

    def require_admin_permission(self) -> Callable:
        """Dependency that requires admin permission."""
        return self.create_permission_dependency(["admin"])

    def require_execution_permission(self) -> Callable:
        """Dependency that requires execution permission."""
        return self.create_permission_dependency(["execute"])


# Factory functions for backward compatibility during migration
def create_auth_adapter(auth_service: AuthService) -> FastAPIAuthAdapter:
    """
    Create FastAPI authentication adapter.

    Args:
        auth_service: Pure authentication service

    Returns:
        FastAPIAuthAdapter instance
    """
    return FastAPIAuthAdapter(auth_service)


# Legacy compatibility wrappers
def create_auth_dependency(
    auth_service: AuthService, optional: bool = False
) -> Callable:
    """
    Legacy wrapper for creating authentication dependency.

    Args:
        auth_service: AuthService instance
        optional: If True, authentication is optional

    Returns:
        FastAPI dependency function
    """
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.create_dependency(optional=optional)


def require_auth(auth_service: AuthService) -> Callable:
    """
    Legacy wrapper for requiring authentication.

    Args:
        auth_service: AuthService instance

    Returns:
        FastAPI dependency function that requires authentication
    """
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.require_auth()


def optional_auth(auth_service: AuthService) -> Callable:
    """
    Legacy wrapper for optional authentication.

    Args:
        auth_service: AuthService instance

    Returns:
        FastAPI dependency function with optional authentication
    """
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.optional_auth()


def require_admin_permission(auth_service: AuthService) -> Callable:
    """Legacy wrapper for admin permission dependency."""
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.require_admin_permission()


def require_read_permission(auth_service: AuthService) -> Callable:
    """Legacy wrapper for read permission dependency."""
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.require_read_permission()


def require_write_permission(auth_service: AuthService) -> Callable:
    """Legacy wrapper for write permission dependency."""
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.require_write_permission()


def require_execution_permission(auth_service: AuthService) -> Callable:
    """Legacy wrapper for execution permission dependency."""
    adapter = FastAPIAuthAdapter(auth_service)
    return adapter.require_execution_permission()
