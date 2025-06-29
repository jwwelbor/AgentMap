"""
Authentication middleware for AgentMap API.

This module provides FastAPI middleware and dependency functions for
authentication, supporting multiple auth methods with configurable
per-endpoint protection and graceful degradation.
"""

import re
from typing import Annotated, Optional, List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from agentmap.services.auth_service import AuthService, AuthContext


# FastAPI security scheme for extracting bearer tokens
security = HTTPBearer(auto_error=False)


def get_auth_method(request: Request) -> str:
    """
    Detect the authentication method from the request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Authentication method: 'api_key', 'jwt', 'supabase', or 'none'
    """
    # Check for Authorization header
    auth_header = request.headers.get('authorization', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Simple heuristics to detect token type
        if token.startswith('sb-'):  # Supabase tokens typically start with 'sb-'
            return 'supabase'
        elif '.' in token and len(token.split('.')) == 3:  # JWT has 3 parts separated by dots
            return 'jwt'
        else:
            return 'api_key'  # Default to API key for other bearer tokens
    
    # Check for X-API-Key header
    if request.headers.get('x-api-key'):
        return 'api_key'
    
    # Check for query parameter
    if request.query_params.get('api_key'):
        return 'api_key'
        
    return 'none'


def extract_credentials(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = None) -> Optional[str]:
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
    auth_header = request.headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Try X-API-Key header
    api_key = request.headers.get('x-api-key')
    if api_key:
        return api_key
    
    # Try query parameter
    api_key = request.query_params.get('api_key')
    if api_key:
        return api_key
        
    return None


def is_public_endpoint(request: Request, public_endpoints: List[str]) -> bool:
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
        if pattern.endswith('*'):
            if path.startswith(pattern[:-1]):
                return True
        elif pattern == path:
            return True
        # Support regex patterns (if they start with ^)
        elif pattern.startswith('^'):
            if re.match(pattern, path):
                return True
    
    return False


def is_embedded_mode(request: Request) -> bool:
    """
    Check if the request is coming from embedded mode.
    
    Embedded mode can bypass authentication for local development.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if request is from embedded mode
    """
    # Check for embedded mode headers
    embedded_header = request.headers.get('x-agentmap-embedded', '').lower()
    if embedded_header in ('true', '1', 'yes'):
        return True
    
    # Check if request is from localhost/127.0.0.1
    host = request.client.host if request.client else ''
    if host in ('127.0.0.1', '::1', 'localhost'):
        # Additional check for embedded mode query parameter
        if request.query_params.get('embedded', '').lower() in ('true', '1', 'yes'):
            return True
    
    return False


def create_auth_dependency(auth_service: AuthService, optional: bool = False):
    """
    Create authentication dependency function.
    
    Args:
        auth_service: AuthService instance
        optional: If True, authentication is optional
        
    Returns:
        FastAPI dependency function
    """
    def auth_dependency(
        request: Request,
        credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None
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
        if not auth_service.is_authentication_enabled():
            return AuthContext(
                authenticated=True,
                auth_method='disabled',
                user_id='system',
                permissions=['admin']
            )
        
        # Check if endpoint is public
        public_endpoints = auth_service.get_public_endpoints()
        if is_public_endpoint(request, public_endpoints):
            return AuthContext(
                authenticated=True,
                auth_method='public',
                user_id='public',
                permissions=['read']
            )
        
        # Check for embedded mode bypass
        if is_embedded_mode(request):
            return AuthContext(
                authenticated=True,
                auth_method='embedded',
                user_id='embedded',
                permissions=['admin']
            )
        
        # Extract credentials
        token = extract_credentials(request, credentials)
        
        if not token:
            if optional:
                return AuthContext(authenticated=False, auth_method='none')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Determine authentication method and validate
        auth_method = get_auth_method(request)
        auth_context = None
        
        if auth_method == 'api_key':
            auth_context = auth_service.validate_api_key(token)
        elif auth_method == 'jwt':
            auth_context = auth_service.validate_jwt(token)
        elif auth_method == 'supabase':
            auth_context = auth_service.validate_supabase_token(token)
        else:
            # Default to API key validation
            auth_context = auth_service.validate_api_key(token)
        
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


def require_auth(auth_service: AuthService):
    """
    Create dependency that requires authentication.
    
    Args:
        auth_service: AuthService instance
        
    Returns:
        FastAPI dependency function that requires authentication
    """
    return create_auth_dependency(auth_service, optional=False)


def optional_auth(auth_service: AuthService):
    """
    Create dependency for optional authentication.
    
    Args:
        auth_service: AuthService instance
        
    Returns:
        FastAPI dependency function with optional authentication
    """
    return create_auth_dependency(auth_service, optional=True)


def require_permissions(required_permissions: List[str]):
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
                detail="Authentication required"
            )
        
        # Admin permission grants all access
        if 'admin' in auth_context.permissions:
            return auth_context
        
        # Check if user has all required permissions
        missing_permissions = [
            perm for perm in required_permissions 
            if perm not in auth_context.permissions
        ]
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Missing: {', '.join(missing_permissions)}"
            )
        
        return auth_context
    
    return permission_dependency


def create_permission_dependency(auth_service: AuthService, required_permissions: List[str]):
    """
    Create combined auth + permission dependency.
    
    Args:
        auth_service: AuthService instance
        required_permissions: List of required permissions
        
    Returns:
        FastAPI dependency function that combines auth and permission checks
    """
    auth_dep = require_auth(auth_service)
    perm_dep = require_permissions(required_permissions)
    
    def combined_dependency(
        request: Request,
        credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None
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
        auth_context = auth_dep(request, credentials)
        
        # Then check permissions
        return perm_dep(auth_context)
    
    return combined_dependency


# Common permission combinations
def require_read_permission(auth_service: AuthService):
    """Dependency that requires read permission."""
    return create_permission_dependency(auth_service, ['read'])


def require_write_permission(auth_service: AuthService):
    """Dependency that requires write permission.""" 
    return create_permission_dependency(auth_service, ['write'])


def require_admin_permission(auth_service: AuthService):
    """Dependency that requires admin permission."""
    return create_permission_dependency(auth_service, ['admin'])


def require_execution_permission(auth_service: AuthService):
    """Dependency that requires execution permission."""
    return create_permission_dependency(auth_service, ['execute'])
