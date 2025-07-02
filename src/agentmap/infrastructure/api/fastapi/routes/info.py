"""
Information and diagnostic routes for FastAPI server.

This module provides API endpoints for system information, diagnostics,
and configuration using the new service architecture.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer
from agentmap.infrastructure.api.fastapi.middleware.auth import require_admin_permission
from agentmap.services.auth_service import AuthContext


# Response models
class DiagnosticResponse(BaseModel):
    """Response model for diagnostic information."""

    llm: Dict[str, Any]
    storage: Dict[str, Any]
    environment: Dict[str, Any]
    package_versions: Dict[str, str]
    installation_suggestions: list


class CacheInfoResponse(BaseModel):
    """Response model for cache information."""

    cache_statistics: Dict[str, Any]
    suggestions: list


class CacheOperationResponse(BaseModel):
    """Response model for cache operations."""

    success: bool
    operation: str
    removed_count: int
    file_path: Optional[str] = None


# Import shared dependencies from the dependencies module
from agentmap.infrastructure.api.fastapi.dependencies import get_container


def get_adapter(container: ApplicationContainer = Depends(get_container)):
    """Get service adapter for dependency injection."""
    return create_service_adapter(container)


def get_auth_service(container: ApplicationContainer = Depends(get_container)):
    """Get AuthService through DI container."""
    return container.auth_service()


def get_features_service(container: ApplicationContainer = Depends(get_container)):
    """Get FeaturesRegistryService through DI container."""
    return container.features_registry_service()


def get_dependency_checker_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Get DependencyCheckerService through DI container."""
    return container.dependency_checker_service()


# Create security scheme for bearer tokens
security = HTTPBearer(auto_error=False)


def get_admin_auth_dependency():
    """Create admin auth dependency function for info routes."""

    def admin_auth_dependency(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        container: ApplicationContainer = Depends(get_container),
    ) -> AuthContext:
        try:
            auth_service = container.auth_service()
        except Exception as e:
            # Handle auth service creation errors gracefully
            raise HTTPException(
                status_code=503,
                detail=f"Authentication service unavailable: {str(e)}",
            )

        # Check if authentication is disabled
        if not auth_service.is_authentication_enabled():
            return AuthContext(
                authenticated=True,
                auth_method="disabled",
                user_id="system",
                permissions=["admin"],
            )

        # Check if endpoint is public
        public_endpoints = auth_service.get_public_endpoints()
        path = request.url.path
        for pattern in public_endpoints:
            if pattern.endswith("*") and path.startswith(pattern[:-1]):
                return AuthContext(
                    authenticated=True,
                    auth_method="public",
                    user_id="public",
                    permissions=["read"],
                )
            elif pattern == path:
                return AuthContext(
                    authenticated=True,
                    auth_method="public",
                    user_id="public",
                    permissions=["read"],
                )

        # Extract credentials
        token = None
        if credentials and credentials.credentials:
            token = credentials.credentials
        elif request.headers.get("x-api-key"):
            token = request.headers.get("x-api-key")
        elif request.query_params.get("api_key"):
            token = request.query_params.get("api_key")

        if not token:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token (try API key first, then JWT)
        auth_context = auth_service.validate_api_key(token)
        if not auth_context.authenticated:
            auth_context = auth_service.validate_jwt(token)
        if not auth_context.authenticated:
            auth_context = auth_service.validate_supabase_token(token)

        if not auth_context.authenticated:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check admin permission
        if "admin" not in auth_context.permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions. Admin access required.",
            )

        return auth_context

    return admin_auth_dependency


# Create router
router = APIRouter(prefix="/info", tags=["Information & Diagnostics"])


@router.get("/config")
async def get_configuration(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    container: ApplicationContainer = Depends(get_container),
):
    """Get current AgentMap configuration (Admin only)."""
    try:
        app_config_service = container.app_config_service()
        configuration = app_config_service.get_all()

        return {"configuration": configuration, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {e}")


@router.get("/diagnose", response_model=DiagnosticResponse)
async def diagnose_system(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    features_service=Depends(get_features_service),
    dependency_checker=Depends(get_dependency_checker_service),
):
    """Run system diagnostics and dependency checks."""
    try:
        # Build diagnostic information using services
        diagnostic_info = {
            "llm": _build_llm_diagnostic(features_service, dependency_checker),
            "storage": _build_storage_diagnostic(features_service, dependency_checker),
            "environment": _build_environment_diagnostic(),
            "package_versions": _get_package_versions(),
            "installation_suggestions": _build_installation_suggestions(
                features_service, dependency_checker
            ),
        }

        return DiagnosticResponse(**diagnostic_info)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnostic check failed: {e}")


@router.get("/cache", response_model=CacheInfoResponse)
async def get_cache_info(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    container: ApplicationContainer = Depends(get_container),
):
    """Get validation cache information and statistics."""
    try:
        validation_cache_service = container.validation_cache_service()
        cache_stats = validation_cache_service.get_validation_cache_stats()

        suggestions = []
        if cache_stats["expired_files"] > 0:
            suggestions.append(
                "Run 'agentmap validate-cache --cleanup' to remove expired entries"
            )
        if cache_stats["corrupted_files"] > 0:
            suggestions.append(
                f"Found {cache_stats['corrupted_files']} corrupted cache files"
            )

        cache_info = {"cache_statistics": cache_stats, "suggestions": suggestions}

        return CacheInfoResponse(**cache_info)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache info: {e}")


@router.delete("/cache", response_model=CacheOperationResponse)
async def clear_cache(
    file_path: Optional[str] = None,
    cleanup_expired: bool = False,
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    container: ApplicationContainer = Depends(get_container),
):
    """Clear validation cache entries."""
    try:
        validation_cache_service = container.validation_cache_service()

        if file_path:
            removed = validation_cache_service.clear_validation_cache(file_path)
            operation = f"clear_file:{file_path}"
        elif cleanup_expired:
            removed = validation_cache_service.cleanup_validation_cache()
            operation = "cleanup_expired"
        else:
            removed = validation_cache_service.clear_validation_cache()
            operation = "clear_all"

        result = {
            "success": True,
            "operation": operation,
            "removed_count": removed,
            "file_path": file_path,
        }

        return CacheOperationResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")


@router.get("/version")
async def get_version(auth_context: AuthContext = Depends(get_admin_auth_dependency())):
    """Get AgentMap version information."""
    from agentmap._version import __version__

    return {"agentmap_version": __version__, "api_version": "2.0"}


@router.get("/paths")
async def get_system_paths(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    adapter=Depends(get_adapter),
):
    """Get system paths and directory information."""
    try:
        _, app_config_service, _ = adapter.initialize_services()

        return {
            "csv_path": str(app_config_service.get_csv_path()),
            "custom_agents_path": str(app_config_service.get_custom_agents_path()),
            "functions_path": str(app_config_service.get_functions_path()),
            "status": "success",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paths: {e}")


@router.get("/features")
async def get_feature_status(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    features_service=Depends(get_features_service),
):
    """Get status of optional features and dependencies."""
    try:
        # Build feature status using FeaturesRegistryService
        feature_status = {
            "llm": {
                "enabled": features_service.is_feature_enabled("llm"),
                "providers": {},
            },
            "storage": {
                "enabled": features_service.is_feature_enabled("storage"),
                "providers": {},
            },
        }

        # Check LLM providers
        for provider in ["openai", "anthropic", "google"]:
            feature_status["llm"]["providers"][provider] = {
                "available": features_service.is_provider_available("llm", provider),
                "registered": features_service.is_provider_registered("llm", provider),
                "validated": features_service.is_provider_validated("llm", provider),
            }

        # Check storage providers
        for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
            feature_status["storage"]["providers"][storage_type] = {
                "available": features_service.is_provider_available(
                    "storage", storage_type
                ),
                "registered": features_service.is_provider_registered(
                    "storage", storage_type
                ),
                "validated": features_service.is_provider_validated(
                    "storage", storage_type
                ),
            }

        return feature_status

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get feature status: {e}"
        )


@router.get("/health/detailed")
async def detailed_health_check(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    adapter=Depends(get_adapter),
):
    """Detailed health check including service status."""
    try:
        # Test service initialization
        graph_runner_service, app_config_service, logging_service = (
            adapter.initialize_services()
        )

        # Basic service checks
        service_status = {
            "graph_runner_service": "healthy",
            "app_config_service": "healthy",
            "logging_service": "healthy",
        }

        # Test configuration access
        try:
            app_config_service.get_all()
            config_status = "healthy"
        except Exception as e:
            config_status = f"error: {e}"

        # Test logger creation
        try:
            logging_service.get_logger("health_check")
            logging_status = "healthy"
        except Exception as e:
            logging_status = f"error: {e}"

        return {
            "status": "healthy",
            "services": service_status,
            "configuration": config_status,
            "logging": logging_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {e}")


# Helper functions for diagnostic information
def _build_llm_diagnostic(features_service, dependency_checker) -> Dict[str, Any]:
    """Build LLM diagnostic information."""
    llm_info = {
        "enabled": features_service.is_feature_enabled("llm"),
        "providers": {},
        "available_count": 0,
    }

    for provider in ["openai", "anthropic", "google"]:
        # Get fresh dependency check
        has_deps, missing = dependency_checker.check_llm_dependencies(provider)

        # Get registry status
        registered = features_service.is_provider_registered("llm", provider)
        validated = features_service.is_provider_validated("llm", provider)
        available = features_service.is_provider_available("llm", provider)

        provider_info = {
            "available": available,
            "registered": registered,
            "validated": validated,
            "has_dependencies": has_deps,
            "missing_dependencies": missing,
        }

        if available:
            llm_info["available_count"] += 1

        llm_info["providers"][provider] = provider_info

    return llm_info


def _build_storage_diagnostic(features_service, dependency_checker) -> Dict[str, Any]:
    """Build storage diagnostic information."""
    storage_info = {
        "enabled": features_service.is_feature_enabled("storage"),
        "providers": {},
        "available_count": 0,
    }

    for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
        # Get fresh dependency check
        has_deps, missing = dependency_checker.check_storage_dependencies(storage_type)

        # Get registry status
        available = features_service.is_provider_available("storage", storage_type)
        registered = features_service.is_provider_registered("storage", storage_type)
        validated = features_service.is_provider_validated("storage", storage_type)

        provider_info = {
            "available": available,
            "registered": registered,
            "validated": validated,
            "has_dependencies": has_deps,
            "missing_dependencies": missing,
        }

        if available:
            storage_info["available_count"] += 1

        storage_info["providers"][storage_type] = provider_info

    return storage_info


def _build_environment_diagnostic() -> Dict[str, Any]:
    """Build environment diagnostic information."""
    import os
    import sys

    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "current_directory": os.getcwd(),
        "platform": sys.platform,
    }


def _get_package_versions() -> Dict[str, str]:
    """Get versions of relevant packages."""
    packages = {
        "openai": "openai",
        "anthropic": "anthropic",
        "google.generativeai": "google-generativeai",
        "langchain": "langchain",
        "langchain_google_genai": "langchain-google-genai",
        "chromadb": "chromadb",
    }

    versions = {}
    for display_name, package_name in packages.items():
        try:
            if "." in package_name:
                base_pkg = package_name.split(".")[0]
                module = __import__(base_pkg)
                versions[display_name] = f"Installed (base package {base_pkg})"
            else:
                module = __import__(package_name)
                version = getattr(module, "__version__", "unknown")
                versions[display_name] = version
        except ImportError:
            versions[display_name] = "Not installed"

    return versions


def _build_installation_suggestions(features_service, dependency_checker) -> list:
    """Build installation suggestions based on missing dependencies."""
    suggestions = []

    # Check if LLM feature is enabled
    if not features_service.is_feature_enabled("llm"):
        suggestions.append("To enable LLM agents: pip install agentmap[llm]")

    # Check if storage feature is enabled
    if not features_service.is_feature_enabled("storage"):
        suggestions.append("To enable storage agents: pip install agentmap[storage]")

    # Check individual LLM providers
    has_openai, _ = dependency_checker.check_llm_dependencies("openai")
    if not has_openai:
        suggestions.append(
            "For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0"
        )

    has_anthropic, _ = dependency_checker.check_llm_dependencies("anthropic")
    if not has_anthropic:
        suggestions.append(
            "For Anthropic support: pip install agentmap[anthropic] or pip install anthropic"
        )

    has_google, _ = dependency_checker.check_llm_dependencies("google")
    if not has_google:
        suggestions.append(
            "For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai"
        )

    # Check vector storage
    has_vector, _ = dependency_checker.check_storage_dependencies("vector")
    if not has_vector:
        suggestions.append("For vector storage: pip install chromadb")

    return suggestions
