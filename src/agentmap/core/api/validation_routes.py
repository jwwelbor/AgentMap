"""
Validation routes for FastAPI server.

This module provides API endpoints for validating CSV files, configuration files,
and running combined validation using the new service architecture.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agentmap.di import ApplicationContainer


# Request models
class ValidateConfigRequest(BaseModel):
    """Request model for config validation."""

    config_path: str = Field(..., description="Path to the YAML configuration file to validate")
    no_cache: bool = Field(default=False, description="Skip cache and force fresh validation")
    
    class Config:
        schema_extra = {
            "example": {
                "config_path": "agentmap_config.yaml",
                "no_cache": False
            },
            "description": "Validate YAML configuration file structure and settings"
        }


class ValidateCSVRequest(BaseModel):
    """Request model for CSV validation."""

    csv_path: Optional[str] = Field(None, description="Path to CSV file (uses config default if not provided)")
    no_cache: bool = Field(default=False, description="Skip cache and force fresh validation")
    
    class Config:
        schema_extra = {
            "example": {
                "csv_path": "workflows/customer_service.csv",
                "no_cache": True
            },
            "description": "Validate CSV workflow definition file"
        }


class ValidateAllRequest(BaseModel):
    """Request model for combined validation."""

    csv_path: Optional[str] = Field(None, description="Path to CSV file (uses config default if not provided)")
    config_path: str = Field(default="agentmap_config.yaml", description="Path to configuration file")
    no_cache: bool = Field(default=False, description="Skip cache and force fresh validation")
    fail_on_warnings: bool = Field(default=False, description="Treat warnings as failures")
    
    class Config:
        schema_extra = {
            "example": {
                "csv_path": "workflows/my_workflow.csv",
                "config_path": "config/production.yaml",
                "no_cache": False,
                "fail_on_warnings": True
            },
            "description": "Validate both CSV and configuration files together"
        }


# Response models
class ValidationResult(BaseModel):
    """Validation result details."""

    has_errors: bool = Field(..., description="Whether validation found any errors")
    has_warnings: bool = Field(..., description="Whether validation found any warnings")
    errors: List[str] = Field(default=[], description="List of error messages")
    warnings: List[str] = Field(default=[], description="List of warning messages")
    summary: str = Field(..., description="Summary of validation results")
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "Successful Validation",
                    "value": {
                        "has_errors": False,
                        "has_warnings": False,
                        "errors": [],
                        "warnings": [],
                        "summary": "Validation completed successfully"
                    }
                },
                {
                    "name": "Validation with Issues",
                    "value": {
                        "has_errors": True,
                        "has_warnings": True,
                        "errors": ["Missing required field 'AgentType' in row 5"],
                        "warnings": ["Deprecated agent type 'old_agent' used in row 3"],
                        "summary": "Validation failed with 1 error and 1 warning"
                    }
                }
            ]
        }
    summary: str


class ValidateConfigResponse(BaseModel):
    """Response model for config validation."""

    success: bool = Field(..., description="Whether validation completed without errors")
    result: ValidationResult = Field(..., description="Detailed validation results")
    file_path: str = Field(..., description="Path to the validated configuration file")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "result": {
                    "has_errors": False,
                    "has_warnings": False,
                    "errors": [],
                    "warnings": [],
                    "summary": "Configuration validation completed successfully"
                },
                "file_path": "agentmap_config.yaml"
            }
        }


class ValidateCSVResponse(BaseModel):
    """Response model for CSV validation."""

    success: bool = Field(..., description="Whether validation completed without errors")
    result: ValidationResult = Field(..., description="Detailed validation results")
    file_path: str = Field(..., description="Path to the validated CSV file")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "result": {
                    "has_errors": True,
                    "has_warnings": False,
                    "errors": ["Invalid agent type 'missing_agent' in row 3"],
                    "warnings": [],
                    "summary": "CSV validation failed with 1 error"
                },
                "file_path": "workflows/my_workflow.csv"
            }
        }


class ValidateAllResponse(BaseModel):
    """Response model for combined validation."""

    success: bool = Field(..., description="Whether both validations completed without errors")
    csv_result: ValidationResult = Field(..., description="CSV validation results")
    config_result: Optional[ValidationResult] = Field(None, description="Configuration validation results")
    csv_path: str = Field(..., description="Path to the validated CSV file")
    config_path: str = Field(..., description="Path to the validated configuration file")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "csv_result": {
                    "has_errors": False,
                    "has_warnings": True,
                    "errors": [],
                    "warnings": ["Consider using newer agent type for better performance"],
                    "summary": "CSV validation completed with warnings"
                },
                "config_result": {
                    "has_errors": False,
                    "has_warnings": False,
                    "errors": [],
                    "warnings": [],
                    "summary": "Configuration validation successful"
                },
                "csv_path": "workflows/customer_service.csv",
                "config_path": "agentmap_config.yaml"
            }
        }


def get_container() -> ApplicationContainer:
    """Get DI container for dependency injection."""
    from agentmap.di import initialize_di

    return initialize_di()


def get_validation_service(container: ApplicationContainer = Depends(get_container)):
    """Get ValidationService through DI container."""
    return container.validation_service()


def get_app_config_service(container: ApplicationContainer = Depends(get_container)):
    """Get AppConfigService through DI container."""
    return container.app_config_service()


# Create router
router = APIRouter(prefix="/validation", tags=["Validation"])


@router.post(
    "/config", 
    response_model=ValidateConfigResponse,
    summary="Validate Configuration File",
    description="Validate YAML configuration file syntax, structure, and settings",
    response_description="Validation results with detailed error and warning information",
    responses={
        200: {"description": "Configuration validation completed"},
        400: {"description": "Validation failed due to configuration errors"},
        404: {"description": "Configuration file not found"}
    },
    tags=["Validation"]
)
async def validate_config(
    request: ValidateConfigRequest,
    validation_service=Depends(get_validation_service),
):
    """
    **Validate YAML Configuration File**
    
    This endpoint validates configuration file syntax, structure,
    and ensures all required settings are present with valid values.
    Validation covers YAML syntax, required fields, data types,
    and cross-field dependencies.
    
    **Validation Checks:**
    - YAML syntax and structure
    - Required configuration sections
    - Data type validation
    - Path existence for file references
    - Service configuration completeness
    
    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/validation/config" \\
         -H "Content-Type: application/json" \\
         -d '{
           "config_path": "agentmap_config.yaml",
           "no_cache": false
         }'
    ```
    
    **Success Response:**
    ```json
    {
      "success": true,
      "result": {
        "has_errors": false,
        "has_warnings": false,
        "errors": [],
        "warnings": [],
        "summary": "Configuration validation completed successfully"
      },
      "file_path": "agentmap_config.yaml"
    }
    ```
    
    **Rate Limiting:** 120 requests per minute
    
    **Authentication:** None required
    """
    config_file = Path(request.config_path)

    if not config_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Config file not found: {config_file}"
        )

    try:
        result = validation_service.validate_config(
            config_file, use_cache=not request.no_cache
        )

        # Convert validation result to response format
        validation_result = ValidationResult(
            has_errors=result.has_errors,
            has_warnings=result.has_warnings,
            errors=result.errors if hasattr(result, 'errors') else [],
            warnings=result.warnings if hasattr(result, 'warnings') else [],
            summary=f"Validation {'failed' if result.has_errors else 'completed'}"
        )

        return ValidateConfigResponse(
            success=not result.has_errors,
            result=validation_result,
            file_path=str(config_file),
        )

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Validation failed: {e}"
        )


@router.post(
    "/csv", 
    response_model=ValidateCSVResponse,
    summary="Validate CSV Workflow",
    description="Validate CSV workflow definition file structure and logic",
    response_description="Validation results with workflow-specific checks",
    responses={
        200: {"description": "CSV validation completed"},
        400: {"description": "Validation failed due to CSV errors"},
        404: {"description": "CSV file not found"}
    },
    tags=["Validation"]
)
async def validate_csv(
    request: ValidateCSVRequest,
    validation_service=Depends(get_validation_service),
    app_config_service=Depends(get_app_config_service),
):
    """
    **Validate CSV Workflow Definition File**
    
    This endpoint validates CSV structure, agent definitions,
    and workflow logic to ensure proper execution. Performs
    comprehensive checks on workflow definitions including
    node relationships, agent configurations, and data flow.
    
    **Validation Checks:**
    - CSV structure and required columns
    - Agent type availability and configuration
    - Node connectivity and graph completeness
    - Field mappings and data flow
    - Success/failure path validation
    - Circular dependency detection
    
    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/validation/csv" \\
         -H "Content-Type: application/json" \\
         -d '{
           "csv_path": "workflows/customer_service.csv",
           "no_cache": true
         }'
    ```
    
    **Success Response:**
    ```json
    {
      "success": true,
      "result": {
        "has_errors": false,
        "has_warnings": true,
        "errors": [],
        "warnings": ["Consider adding failure paths for critical nodes"],
        "summary": "CSV validation completed with minor warnings"
      },
      "file_path": "workflows/customer_service.csv"
    }
    ```
    
    **Rate Limiting:** 120 requests per minute
    
    **Authentication:** None required
    """
    # Determine CSV path
    csv_file = Path(request.csv_path) if request.csv_path else app_config_service.get_csv_path()

    if not csv_file.exists():
        raise HTTPException(
            status_code=404, detail=f"CSV file not found: {csv_file}"
        )

    try:
        result = validation_service.validate_csv(
            csv_file, use_cache=not request.no_cache
        )

        # Convert validation result to response format
        validation_result = ValidationResult(
            has_errors=result.has_errors,
            has_warnings=result.has_warnings,
            errors=result.errors if hasattr(result, 'errors') else [],
            warnings=result.warnings if hasattr(result, 'warnings') else [],
            summary=f"Validation {'failed' if result.has_errors else 'completed'}"
        )

        return ValidateCSVResponse(
            success=not result.has_errors,
            result=validation_result,
            file_path=str(csv_file),
        )

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Validation failed: {e}"
        )


@router.post(
    "/all", 
    response_model=ValidateAllResponse,
    summary="Validate All Files",
    description="Comprehensive validation of both CSV workflow and configuration files",
    response_description="Combined validation results for both file types",
    responses={
        200: {"description": "Combined validation completed"},
        400: {"description": "Validation failed for one or more files"},
        404: {"description": "One or more files not found"}
    },
    tags=["Validation"]
)
async def validate_all(
    request: ValidateAllRequest,
    validation_service=Depends(get_validation_service),
    app_config_service=Depends(get_app_config_service),
):
    """
    **Comprehensive File Validation**
    
    This endpoint performs comprehensive validation of both
    workflow definition and configuration files in a single
    operation. Ideal for CI/CD pipelines and deployment verification.
    
    **Validation Coverage:**
    - Configuration file validation (YAML structure, settings)
    - CSV workflow validation (structure, agents, logic)
    - Cross-file consistency checks
    - Dependency validation
    
    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/validation/all" \\
         -H "Content-Type: application/json" \\
         -d '{
           "csv_path": "workflows/production_flow.csv",
           "config_path": "config/production.yaml",
           "no_cache": false,
           "fail_on_warnings": true
         }'
    ```
    
    **Success Response:**
    ```json
    {
      "success": true,
      "csv_result": {
        "has_errors": false,
        "has_warnings": false,
        "errors": [],
        "warnings": [],
        "summary": "CSV validation passed"
      },
      "config_result": {
        "has_errors": false,
        "has_warnings": false,
        "errors": [],
        "warnings": [],
        "summary": "Configuration validation passed"
      },
      "csv_path": "workflows/production_flow.csv",
      "config_path": "config/production.yaml"
    }
    ```
    
    **Rate Limiting:** 120 requests per minute
    
    **Authentication:** None required
    """
    # Determine paths
    csv_file = Path(request.csv_path) if request.csv_path else app_config_service.get_csv_path()
    config_file = Path(request.config_path)

    # Check files exist
    missing_files = []
    if not csv_file.exists():
        missing_files.append(f"CSV: {csv_file}")
    if not config_file.exists():
        missing_files.append(f"Config: {config_file}")

    if missing_files:
        raise HTTPException(
            status_code=404, detail=f"Files not found: {', '.join(missing_files)}"
        )

    try:
        csv_result, config_result = validation_service.validate_both(
            csv_file, config_file, use_cache=not request.no_cache
        )

        # Convert CSV result
        csv_validation_result = ValidationResult(
            has_errors=csv_result.has_errors,
            has_warnings=csv_result.has_warnings,
            errors=csv_result.errors if hasattr(csv_result, 'errors') else [],
            warnings=csv_result.warnings if hasattr(csv_result, 'warnings') else [],
            summary=f"CSV validation {'failed' if csv_result.has_errors else 'completed'}"
        )

        # Convert config result (if exists)
        config_validation_result = None
        if config_result:
            config_validation_result = ValidationResult(
                has_errors=config_result.has_errors,
                has_warnings=config_result.has_warnings,
                errors=config_result.errors if hasattr(config_result, 'errors') else [],
                warnings=config_result.warnings if hasattr(config_result, 'warnings') else [],
                summary=f"Config validation {'failed' if config_result.has_errors else 'completed'}"
            )

        # Determine overall success
        has_errors = csv_result.has_errors or (
            config_result.has_errors if config_result else False
        )
        has_warnings = csv_result.has_warnings or (
            config_result.has_warnings if config_result else False
        )

        # Check fail_on_warnings setting
        overall_success = not has_errors and not (has_warnings and request.fail_on_warnings)

        return ValidateAllResponse(
            success=overall_success,
            csv_result=csv_validation_result,
            config_result=config_validation_result,
            csv_path=str(csv_file),
            config_path=str(config_file),
        )

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Validation failed: {e}"
        )


@router.post("/csv/compilation")
async def validate_csv_for_compilation(
    csv_path: Optional[str] = None,
    validation_service=Depends(get_validation_service),
    app_config_service=Depends(get_app_config_service),
):
    """
    Validate CSV specifically for compilation requirements.
    
    This endpoint performs specialized validation to ensure
    the CSV is ready for workflow compilation.
    """
    # Determine CSV path
    csv_file = Path(csv_path) if csv_path else app_config_service.get_csv_path()

    if not csv_file.exists():
        raise HTTPException(
            status_code=404, detail=f"CSV file not found: {csv_file}"
        )

    try:
        validation_service.validate_csv_for_compilation(csv_file)
        return {
            "success": True,
            "file_path": str(csv_file),
            "message": "CSV validation for compilation passed",
        }
    except Exception as e:
        return {
            "success": False,
            "file_path": str(csv_file),
            "error": str(e),
            "message": "CSV validation for compilation failed",
        }
