"""
Admin routes - System administration and diagnostics.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from agentmap.deployment.http.api.dependencies import requires_auth
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime_api import (
    diagnose_system,
    ensure_initialized,
    get_config,
    validate_cache,
)


# Simple response models
class DiagnosticsResponse(BaseModel):
    """System diagnostics information."""

    overall_status: str = Field(..., description="System status")
    llm_ready: bool = Field(..., description="LLM features ready")
    storage_ready: bool = Field(..., description="Storage features ready")
    features: Dict[str, Any] = Field(..., description="Feature details")
    suggestions: list = Field(..., description="Installation suggestions")


class ConfigResponse(BaseModel):
    """System configuration."""

    configuration: Dict[str, Any] = Field(..., description="Configuration values")


class CacheResponse(BaseModel):
    """Cache information."""

    action: str = Field(..., description="Action performed")
    stats: Optional[Dict[str, Any]] = Field(None, description="Cache statistics")
    removed_entries: Optional[int] = Field(None, description="Entries removed")


class VersionResponse(BaseModel):
    """Version information."""

    agentmap_version: str = Field(..., description="AgentMap version")
    api_version: str = Field(..., description="API version")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    initialized: bool = Field(..., description="Runtime initialized")


class PathsResponse(BaseModel):
    """System paths."""

    csv_repository: str = Field(..., description="CSV repository path")
    custom_agents: str = Field(..., description="Custom agents path")
    functions: str = Field(..., description="Functions path")


# Router
router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/diagnostics", response_model=DiagnosticsResponse)
@requires_auth("admin")
async def get_diagnostics(request: Request):
    """Get comprehensive system diagnostics."""
    try:
        ensure_initialized()

        result = diagnose_system()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Diagnostics failed")

        outputs = result.get("outputs", {})
        metadata = result.get("metadata", {})

        return DiagnosticsResponse(
            overall_status=outputs.get("overall_status", "unknown"),
            llm_ready=metadata.get("llm_ready", False),
            storage_ready=metadata.get("storage_ready", False),
            features=outputs.get("features", {}),
            suggestions=outputs.get("suggestions", []),
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=ConfigResponse)
@requires_auth("admin")
async def get_configuration(request: Request):
    """Get current system configuration."""
    try:
        ensure_initialized()

        result = get_config()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to get config")

        return ConfigResponse(configuration=result.get("outputs", {}))

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache", response_model=CacheResponse)
@requires_auth("admin")
async def get_cache_stats(request: Request):
    """Get cache statistics."""
    try:
        ensure_initialized()

        result = validate_cache(stats=True)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to get cache stats")

        outputs = result.get("outputs", {})
        return CacheResponse(action="stats", stats=outputs.get("cache_stats", {}))

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear", response_model=CacheResponse)
@requires_auth("admin")
async def clear_cache(
    file_path: Optional[str] = Query(None, description="Clear specific file only"),
    request: Request = None,
):
    """Clear validation cache."""
    try:
        ensure_initialized()

        if file_path:
            result = validate_cache(clear=True, file_path=file_path)
        else:
            result = validate_cache(clear=True)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to clear cache")

        outputs = result.get("outputs", {})
        return CacheResponse(
            action=outputs.get("action", "clear"),
            removed_entries=outputs.get("removed_entries", 0),
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version", response_model=VersionResponse)
async def get_version():
    """Get version information (no auth required)."""
    try:
        # TODO: Add get_version() to runtime_api
        # For now, get version directly
        from agentmap._version import __version__

        return VersionResponse(agentmap_version=__version__, api_version="2.0")
    except ImportError:
        return VersionResponse(agentmap_version="unknown", api_version="2.0")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check (no auth required)."""
    try:
        # TODO: Add get_health() to runtime_api
        # For now, just check if initialized
        ensure_initialized()
        return HealthResponse(status="healthy", initialized=True)
    except AgentMapNotInitialized:
        return HealthResponse(status="not_initialized", initialized=False)
    except Exception:
        return HealthResponse(status="unhealthy", initialized=False)


@router.get("/paths", response_model=PathsResponse)
@requires_auth("admin")
async def get_system_paths(request: Request):
    """Get system directory paths."""
    try:
        ensure_initialized()

        # TODO: Add get_system_paths() to runtime_api
        # For now, get from config
        result = get_config()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to get paths")

        config = result.get("outputs", {})

        return PathsResponse(
            csv_repository=config.get("csv_repository_path", ""),
            custom_agents=config.get("custom_agents_path", ""),
            functions=config.get("functions_path", ""),
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
