"""
Information and diagnostic routes for FastAPI server.

This module provides API endpoints for system information, diagnostics,
and configuration using the new service architecture.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from agentmap.di import ApplicationContainer
from agentmap.core.adapters import create_service_adapter


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


def get_container() -> ApplicationContainer:
    """Get DI container for dependency injection."""
    from agentmap.di import initialize_di
    return initialize_di()


def get_adapter(container: ApplicationContainer = Depends(get_container)):
    """Get service adapter for dependency injection."""
    return create_service_adapter(container)


# Create router
router = APIRouter(prefix="/info", tags=["Information & Diagnostics"])


@router.get("/config")
async def get_configuration(adapter = Depends(get_adapter)):
    """Get current configuration values."""
    try:
        _, app_config_service, _ = adapter.initialize_services()
        config_data = app_config_service.get_all()
        
        return {
            "configuration": config_data,
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {e}")


@router.get("/diagnose", response_model=DiagnosticResponse)
async def diagnose_system():
    """Run system diagnostics and dependency checks."""
    try:
        from agentmap.core.cli.diagnostic_commands import diagnose_command
        
        diagnostic_info = diagnose_command()
        return DiagnosticResponse(**diagnostic_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnostic check failed: {e}")


@router.get("/cache", response_model=CacheInfoResponse)
async def get_cache_info():
    """Get validation cache information and statistics."""
    try:
        from agentmap.core.cli.diagnostic_commands import cache_info_command
        
        cache_info = cache_info_command()
        return CacheInfoResponse(**cache_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache info: {e}")


@router.delete("/cache", response_model=CacheOperationResponse)
async def clear_cache(
    file_path: Optional[str] = None,
    cleanup_expired: bool = False
):
    """Clear validation cache entries."""
    try:
        from agentmap.core.cli.diagnostic_commands import clear_cache_command
        
        result = clear_cache_command(
            file_path=file_path,
            cleanup_expired=cleanup_expired
        )
        
        return CacheOperationResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")


@router.get("/version")
async def get_version():
    """Get AgentMap version information."""
    from agentmap import __version__
    
    return {
        "agentmap_version": __version__,
        "api_version": "2.0"
    }


@router.get("/paths")
async def get_system_paths(adapter = Depends(get_adapter)):
    """Get system paths and directory information."""
    try:
        _, app_config_service, _ = adapter.initialize_services()
        
        return {
            "csv_path": str(app_config_service.get_csv_path()),
            "custom_agents_path": str(app_config_service.get_custom_agents_path()),
            "functions_path": str(app_config_service.get_functions_path()),
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paths: {e}")


@router.get("/features")
async def get_feature_status():
    """Get status of optional features and dependencies."""
    try:
        from agentmap.agents.features import is_llm_enabled, is_storage_enabled
        from agentmap.features_registry import features
        
        # Check feature status
        feature_status = {
            "llm": {
                "enabled": is_llm_enabled(),
                "providers": {}
            },
            "storage": {
                "enabled": is_storage_enabled(),
                "providers": {}
            }
        }
        
        # Check LLM providers
        for provider in ["openai", "anthropic", "google"]:
            feature_status["llm"]["providers"][provider] = {
                "available": features.is_provider_available("llm", provider),
                "registered": features.is_provider_registered("llm", provider),
                "validated": features.is_provider_validated("llm", provider)
            }
        
        # Check storage providers
        for storage_type in ["csv", "vector", "firebase", "azure_blob", "aws_s3", "gcp_storage"]:
            feature_status["storage"]["providers"][storage_type] = {
                "available": features.is_provider_available("storage", storage_type)
            }
        
        return feature_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feature status: {e}")


@router.get("/health/detailed")
async def detailed_health_check(adapter = Depends(get_adapter)):
    """Detailed health check including service status."""
    try:
        # Test service initialization
        graph_runner_service, app_config_service, logging_service = adapter.initialize_services()
        
        # Basic service checks
        service_status = {
            "graph_runner_service": "healthy",
            "app_config_service": "healthy", 
            "logging_service": "healthy"
        }
        
        # Test configuration access
        try:
            config_data = app_config_service.get_all()
            config_status = "healthy"
        except Exception as e:
            config_status = f"error: {e}"
        
        # Test logger creation
        try:
            logger = logging_service.get_logger("health_check")
            logging_status = "healthy"
        except Exception as e:
            logging_status = f"error: {e}"
        
        return {
            "status": "healthy",
            "services": service_status,
            "configuration": config_status,
            "logging": logging_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {e}")
