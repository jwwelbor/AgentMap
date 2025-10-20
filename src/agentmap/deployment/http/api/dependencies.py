"""
FastAPI dependency injection for direct container access.

This module provides minimal dependency injection support for FastAPI routes
by providing direct access to the ApplicationContainer stored in app state.
"""

import functools
from typing import Callable, Optional

from fastapi import HTTPException, Request, status

from agentmap.di import ApplicationContainer
from agentmap.services.auth_service import AuthContext


def get_container(request: Request) -> ApplicationContainer:
    """
    Get DI container for FastAPI dependency injection.

    This function provides direct access to the ApplicationContainer
    that is stored in app.state.container by the FastAPI server.
    Routes can use this to access any service from the container:

    Example usage in routes:
        container = Depends(get_container)
        service = container.my_service()

    Args:
        request: FastAPI request object containing app state

    Returns:
        ApplicationContainer instance with all registered services
    """
    return request.app.state.container


def requires_auth(permission: Optional[str] = None) -> Callable:
    """
    Authentication decorator for FastAPI route functions.

    This decorator replaces complex FastAPI Depends() chains by providing
    direct authentication and authorization through a simple decorator pattern.

    Args:
        permission: Optional permission string to check (e.g. "execute", "admin", "read", "write")

    Returns:
        Decorator function that validates authentication and permissions

    Example usage:
        @requires_auth("execute")
        async def execute_workflow(request: Request, auth_context: AuthContext):
            # Route implementation with validated auth_context
            pass

        @requires_auth()  # Just authentication, no specific permission
        async def protected_endpoint(request: Request, auth_context: AuthContext):
            # Route implementation
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # For FastAPI routes, the request is typically the first positional argument
            # or available in kwargs
            request = None

            # Method 1: Check if request is in args (most common)
            if args and isinstance(args[0], Request):
                request = args[0]
            # Method 2: Check if request is in kwargs
            elif "request" in kwargs and isinstance(kwargs["request"], Request):
                request = kwargs["request"]
            # Method 3: Search through all args for Request object
            else:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                # Debug info to help troubleshoot
                arg_types = [type(arg).__name__ for arg in args]
                kwarg_info = {k: type(v).__name__ for k, v in kwargs.items()}
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Request object not found. Args types: {arg_types}, Kwargs: {kwarg_info}",
                )

            # Get container from request app state with retry for lifespan race condition
            import asyncio

            container = None
            max_retries = 20  # Increased from 10
            retry_delay = 0.15  # Increased from 0.1s to 150ms (total 3 seconds)

            for attempt in range(max_retries):
                try:
                    container = request.app.state.container
                    if container is not None:
                        break
                except AttributeError:
                    pass

                # Wait before retrying
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

            if container is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Application container not initialized. Please wait for server startup to complete.",
                )

            # Get auth service from container with retry logic
            # This must be done first to check if authentication is disabled
            auth_service = None
            for attempt in range(10):  # Try up to 10 times
                try:
                    auth_service = container.auth_service()
                    break
                except Exception as e:
                    if attempt < 9:
                        await asyncio.sleep(0.1)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Auth service not available after {attempt+1} attempts: {str(e)}",
                        )

            # Check if authentication is disabled (this avoids race conditions)
            # Tests mock auth_service.is_authentication_enabled() so check that
            if not auth_service.is_authentication_enabled():
                auth_context = AuthContext(
                    authenticated=True,
                    auth_method="disabled",
                    user_id="system",
                    permissions=["admin"],
                )
            else:

                # Extract authentication token from request
                auth_token = _extract_auth_token(request)

                # Authenticate the request
                if not auth_token:
                    # No token provided - check if endpoint is public
                    public_endpoints = auth_service.get_public_endpoints()
                    if _is_public_endpoint(request.url.path, public_endpoints):
                        auth_context = AuthContext(
                            authenticated=True,
                            auth_method="public",
                            user_id="public",
                            permissions=["read"],
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                else:
                    # Validate the token using auth service
                    auth_context = _validate_token(auth_service, auth_token)

                    if not auth_context.authenticated:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authentication credentials",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

            # Check permissions if specified
            if permission and not _check_permission(auth_context, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required permission: {permission}",
                )

            # Store auth_context in request state instead of function arguments
            request.state.auth_context = auth_context

            # Call the original function (no longer injecting auth_context)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_auth_token(request: Request) -> Optional[str]:
    """
    Extract authentication token from request headers or query parameters.

    Args:
        request: FastAPI request object

    Returns:
        Authentication token if found, None otherwise
    """
    # Try Authorization header first
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


def _validate_token(auth_service, token: str) -> AuthContext:
    """
    Validate authentication token using appropriate method.

    Args:
        auth_service: Authentication service instance
        token: Authentication token to validate

    Returns:
        AuthContext with validation results
    """
    # Determine token type and validate accordingly
    if token.startswith("sb-"):  # Supabase token
        return auth_service.validate_supabase_token(token)
    elif "." in token and len(token.split(".")) == 3:  # JWT token
        return auth_service.validate_jwt(token)
    else:  # Default to API key
        return auth_service.validate_api_key(token)


def _is_public_endpoint(path: str, public_endpoints: list) -> bool:
    """
    Check if the requested path is a public endpoint.

    Args:
        path: Request path
        public_endpoints: List of public endpoint patterns

    Returns:
        True if endpoint is public
    """
    import re

    for pattern in public_endpoints:
        # Support exact matches and wildcard patterns
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


def _check_permission(auth_context: AuthContext, required_permission: str) -> bool:
    """
    Check if auth context has the required permission.

    Args:
        auth_context: Authentication context
        required_permission: Required permission string

    Returns:
        True if permission is granted
    """
    if not auth_context.authenticated:
        return False

    # Admin permission grants all access
    if "admin" in auth_context.permissions:
        return True

    # Check for specific permission
    return required_permission in auth_context.permissions


def get_auth_context(request: Request) -> AuthContext:
    """
    Get authentication context from request state.

    This helper function retrieves the AuthContext that was stored
    by the @requires_auth decorator.

    Args:
        request: FastAPI request object

    Returns:
        AuthContext stored by the authentication decorator

    Raises:
        HTTPException: If auth context not found (decorator not applied)

    Example usage:
        @router.get("/protected")
        @requires_auth("admin")
        async def protected_endpoint(request: Request):
            auth_context = get_auth_context(request)
            print(f"User: {auth_context.user_id}")
    """
    if not hasattr(request.state, "auth_context"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication context not found - ensure @requires_auth decorator is applied",
        )
    return request.state.auth_context


def get_app_config_service(request: Request):
    """
    Get app config service for FastAPI dependency injection.

    This function provides access to the AppConfigService from the container
    for use in FastAPI routes that need configuration data.

    Args:
        request: FastAPI request object containing app state

    Returns:
        AppConfigService instance for configuration access
    """
    container = get_container(request)
    return container.app_config_service()


# Export functions
__all__ = [
    "get_container",
    "get_app_config_service",
    "requires_auth",
    "get_auth_context",
]
