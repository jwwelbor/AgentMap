"""
Information and diagnostics routes for FastAPI server.

This module provides API endpoints for system information, diagnostics,
and cache management using the new service architecture.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agentmap.deployment.http.api.dependencies import (
    get_container,
    requires_auth,
)


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


# Create router
router = APIRouter(prefix="/info", tags=["Information & Diagnostics"])


@router.get("/config")
@requires_auth("admin")
async def get_configuration(request: Request):
    """Get current AgentMap configuration (Admin only)."""
    try:
        container = request.app.state.container
        app_config_service = container.app_config_service()
        configuration = app_config_service.get_all()

        return {"configuration": configuration, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {e}")


@router.get("/diagnose", response_model=DiagnosticResponse)
@requires_auth("admin")
async def diagnose_system(request: Request):
    """Run system diagnostics and dependency checks."""
    try:
        container = request.app.state.container
        features_service = container.features_registry_service()
        dependency_checker = container.dependency_checker_service()

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
@requires_auth("admin")
async def get_cache_info(request: Request):
    """Get validation cache information and statistics."""
    try:
        container = request.app.state.container
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
@requires_auth("admin")
async def clear_cache(
    file_path: Optional[str] = None,
    cleanup_expired: bool = False,
    request: Request = None,
):
    """Clear validation cache entries."""
    try:
        container = request.app.state.container
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
@requires_auth("admin")
async def get_version(request: Request):
    """Get AgentMap version information."""
    try:
        from agentmap._version import __version__

        return {"agentmap_version": __version__, "api_version": "2.0"}
    except ImportError:
        return {"agentmap_version": "unknown", "api_version": "2.0"}


@router.get("/paths")
@requires_auth("admin")
async def get_system_paths(request: Request):
    """Get system paths and directory information."""
    try:
        container = request.app.state.container
        app_config_service = container.app_config_service()

        return {
            "csv_path": str(app_config_service.get_csv_repository_path()),
            "custom_agents_path": str(app_config_service.get_custom_agents_path()),
            "functions_path": str(app_config_service.get_functions_path()),
            "status": "success",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paths: {e}")


@router.get("/features")
@requires_auth("admin")
async def get_feature_status(request: Request):
    """Get status of optional features and dependencies."""
    try:
        container = request.app.state.container
        features_service = container.features_registry_service()

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
@requires_auth("admin")
async def detailed_health_check(request: Request):
    """Detailed health check including service status."""
    try:
        container = request.app.state.container

        # Test basic service access
        app_config_service = container.app_config_service()
        logging_service = container.logging_service()

        # Basic service checks
        service_status = {
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
        try:
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
        except Exception as e:
            # Handle errors gracefully
            llm_info["providers"][provider] = {
                "available": False,
                "registered": False,
                "validated": False,
                "has_dependencies": False,
                "missing_dependencies": [f"Error checking dependencies: {e}"],
            }

    return llm_info


def _build_storage_diagnostic(features_service, dependency_checker) -> Dict[str, Any]:
    """Build storage diagnostic information."""
    storage_info = {
        "enabled": features_service.is_feature_enabled("storage"),
        "providers": {},
        "available_count": 0,
    }

    for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
        try:
            # Get fresh dependency check
            has_deps, missing = dependency_checker.check_storage_dependencies(
                storage_type
            )

            # Get registry status
            available = features_service.is_provider_available("storage", storage_type)
            registered = features_service.is_provider_registered(
                "storage", storage_type
            )
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
        except Exception as e:
            # Handle errors gracefully
            storage_info["providers"][storage_type] = {
                "available": False,
                "registered": False,
                "validated": False,
                "has_dependencies": False,
                "missing_dependencies": [f"Error checking dependencies: {e}"],
            }

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

    try:
        # Check if LLM feature is enabled
        if not features_service.is_feature_enabled("llm"):
            suggestions.append("To enable LLM agents: pip install agentmap[llm]")

        # Check if storage feature is enabled
        if not features_service.is_feature_enabled("storage"):
            suggestions.append(
                "To enable storage agents: pip install agentmap[storage]"
            )

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
    except Exception as e:
        suggestions.append(f"Error checking dependencies: {e}")

    return suggestions
