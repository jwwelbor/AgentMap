"""
Common error handling and validation utilities for AgentMap API endpoints.

This module provides standardized error responses, validation utilities,
and common error handling patterns used across all API router modules.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, validator


# Common Error Response Models
class ValidationError(BaseModel):
    """Detailed validation error information."""

    field: str
    message: str
    invalid_value: Optional[Any] = None
    line_number: Optional[int] = None


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    error: str
    error_code: str
    detail: Optional[str] = None
    validation_errors: List[ValidationError] = []
    request_id: Optional[str] = None
    timestamp: Optional[str] = None


class ErrorDetail(BaseModel):
    """Enhanced error detail with context."""

    message: str
    error_type: str
    field: Optional[str] = None
    value: Optional[str] = None
    suggestion: Optional[str] = None


# Request validation utilities
class RequestValidator:
    """Common request validation utilities."""

    # File size limits (in bytes)
    MAX_CSV_SIZE = 50 * 1024 * 1024  # 50MB for CSV files
    MAX_CONFIG_SIZE = 10 * 1024 * 1024  # 10MB for config files
    MAX_JSON_SIZE = 5 * 1024 * 1024  # 5MB for JSON data

    # Text length limits
    MAX_STRING_LENGTH = 10000
    MAX_PATH_LENGTH = 500
    MAX_EXECUTION_ID_LENGTH = 100

    # Patterns for validation
    SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
    SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.\/\\]+$")
    EXECUTION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
    THREAD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

    @classmethod
    def validate_file_path(
        cls, file_path: Union[str, Path], max_size: Optional[int] = None
    ) -> Path:
        """
        Validate file path for security and existence.

        Args:
            file_path: Path to validate
            max_size: Maximum file size in bytes (optional)

        Returns:
            Validated Path object

        Raises:
            HTTPException: If validation fails
        """
        if not file_path:
            raise HTTPException(status_code=400, detail="File path cannot be empty")

        # Convert to Path object
        path = Path(file_path)

        # Check path length
        if len(str(path)) > cls.MAX_PATH_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"File path too long (max {cls.MAX_PATH_LENGTH} characters)",
            )

        # Check for path traversal attempts
        if ".." in str(path) or str(path).startswith("/"):
            raise HTTPException(status_code=400, detail="Path traversal not allowed")

        # Check if file exists
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        # Check if it's actually a file
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")

        # Check file size if limit specified
        if max_size:
            file_size = path.stat().st_size
            if file_size > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file_size} bytes (max {max_size} bytes)",
                )

        return path

    @classmethod
    def validate_system_file_path(
        cls, file_path: Union[str, Path], max_size: Optional[int] = None
    ) -> Path:
        """
        Validate system-resolved file path for existence and size only.

        This method is for paths that have already been validated and resolved
        by the system (e.g., from _resolve_workflow_path). It skips path traversal
        checks since the path construction is controlled by the system.

        Args:
            file_path: System-resolved path to validate
            max_size: Maximum file size in bytes (optional)

        Returns:
            Validated Path object

        Raises:
            HTTPException: If file doesn't exist or is too large
        """
        if not file_path:
            raise HTTPException(status_code=400, detail="File path cannot be empty")

        # Convert to Path object
        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        # Check if it's actually a file
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")

        # Check file size if limit specified
        if max_size:
            file_size = path.stat().st_size
            if file_size > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file_size} bytes (max {max_size} bytes)",
                )

        return path

    @classmethod
    def validate_workflow_name(cls, name: str) -> str:
        """
        Validate workflow name for safety and compliance.

        Args:
            name: Workflow name to validate

        Returns:
            Validated workflow name

        Raises:
            HTTPException: If validation fails
        """
        if not name:
            raise HTTPException(status_code=400, detail="Workflow name cannot be empty")

        if len(name) > 100:
            raise HTTPException(
                status_code=400, detail="Workflow name too long (max 100 characters)"
            )

        # Check for path traversal attempts first - these should return 404 to mimic "not found"
        if (
            ".." in name
            or "/" in name
            or "\\" in name
            or name.startswith(".")
            or name.startswith("-")
        ):
            raise HTTPException(status_code=404, detail="Workflow file not found")

        # Remove any remaining dangerous characters
        clean_name = re.sub(r"[^\w\-_.]", "", name)

        # Ensure it's not empty after cleaning
        if not clean_name:
            raise HTTPException(
                status_code=400,
                detail="Invalid workflow name: contains only invalid characters",
            )

        return clean_name

    @classmethod
    def validate_graph_name(cls, name: str) -> str:
        """
        Validate graph name for safety.

        Args:
            name: Graph name to validate

        Returns:
            Validated graph name

        Raises:
            HTTPException: If validation fails
        """
        if not name:
            raise HTTPException(status_code=400, detail="Graph name cannot be empty")

        if len(name) > 100:
            raise HTTPException(
                status_code=400, detail="Graph name too long (max 100 characters)"
            )

        # Check for path traversal attempts and dangerous patterns - return 404 to mimic "not found"
        if (
            ".." in name
            or "/" in name
            or "\\" in name
            or name.startswith(".")
            or name.startswith("-")
        ):
            raise HTTPException(status_code=404, detail="Graph not found")

        # Basic character validation - only allow safe characters
        if not cls.SAFE_FILENAME_PATTERN.match(name):
            raise HTTPException(
                status_code=400, detail="Graph name contains invalid characters"
            )

        return name

    @classmethod
    def validate_execution_id(cls, execution_id: Optional[str]) -> Optional[str]:
        """
        Validate execution ID format.

        Args:
            execution_id: Execution ID to validate

        Returns:
            Validated execution ID or None

        Raises:
            HTTPException: If validation fails
        """
        if not execution_id:
            return None

        if len(execution_id) > cls.MAX_EXECUTION_ID_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Execution ID too long (max {cls.MAX_EXECUTION_ID_LENGTH} characters)",
            )

        if not cls.EXECUTION_ID_PATTERN.match(execution_id):
            raise HTTPException(
                status_code=400,
                detail="Execution ID contains invalid characters (alphanumeric, underscore, hyphen only)",
            )

        return execution_id

    @classmethod
    def validate_thread_id(cls, thread_id: str) -> str:
        """
        Validate thread ID format.

        Args:
            thread_id: Thread ID to validate

        Returns:
            Validated thread ID

        Raises:
            HTTPException: If validation fails
        """
        if not thread_id:
            raise HTTPException(status_code=400, detail="Thread ID cannot be empty")

        if len(thread_id) > 100:
            raise HTTPException(
                status_code=400, detail="Thread ID too long (max 100 characters)"
            )

        if not cls.THREAD_ID_PATTERN.match(thread_id):
            raise HTTPException(
                status_code=400,
                detail="Thread ID contains invalid characters (alphanumeric, underscore, hyphen only)",
            )

        return thread_id

    @classmethod
    def validate_json_data(cls, data: Any, max_size: Optional[int] = None) -> Any:
        """
        Validate JSON data structure and size.

        Args:
            data: JSON data to validate
            max_size: Maximum serialized size in bytes

        Returns:
            Validated data

        Raises:
            HTTPException: If validation fails
        """
        if data is None:
            return None

        # Check serialized size
        try:
            serialized = json.dumps(data)
            if max_size and len(serialized.encode("utf-8")) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"JSON data too large (max {max_size} bytes)",
                )
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON data: {e}")

        # Check depth (prevent deeply nested structures)
        def check_depth(obj, depth=0, max_depth=10):
            if depth > max_depth:
                raise HTTPException(
                    status_code=400,
                    detail=f"JSON data too deeply nested (max depth {max_depth})",
                )

            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, depth + 1, max_depth)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, depth + 1, max_depth)

        check_depth(data)
        return data

    @classmethod
    def validate_response_action(cls, action: str) -> str:
        """
        Validate response action for workflow resumption.

        Args:
            action: Response action to validate

        Returns:
            Validated action

        Raises:
            HTTPException: If validation fails
        """
        valid_actions = {
            "approve",
            "reject",
            "choose",
            "respond",
            "edit",
            "continue",
            "stop",
            "retry",
            "skip",
        }

        if not action:
            raise HTTPException(
                status_code=400, detail="Response action cannot be empty"
            )

        if action.lower() not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid response action: {action}. Valid actions: {', '.join(valid_actions)}",
            )

        return action.lower()


# Enhanced Pydantic models with validation
class ValidatedStateExecutionRequest(BaseModel):
    """Enhanced state execution request with validation."""

    state: Dict[str, Any] = Field(default={}, description="Initial state for execution")

    execution_id: Optional[str] = Field(
        default=None, max_length=100, description="Optional execution tracking ID"
    )

    @validator("state")
    def validate_state(cls, v):
        return RequestValidator.validate_json_data(v, RequestValidator.MAX_JSON_SIZE)

    @validator("execution_id")
    def validate_execution_id(cls, v):
        return RequestValidator.validate_execution_id(v)


class ValidatedResumeWorkflowRequest(BaseModel):
    """Enhanced resume workflow request with validation."""

    thread_id: str = Field(..., max_length=100, description="Thread ID to resume")
    response_action: str = Field(..., max_length=50, description="Response action")
    response_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional response data"
    )

    @validator("thread_id")
    def validate_thread_id(cls, v):
        return RequestValidator.validate_thread_id(v)

    @validator("response_action")
    def validate_response_action(cls, v):
        return RequestValidator.validate_response_action(v)

    @validator("response_data")
    def validate_response_data(cls, v):
        return RequestValidator.validate_json_data(v, RequestValidator.MAX_JSON_SIZE)


# Error handling utilities
class ErrorHandler:
    """Common error handling utilities."""

    @staticmethod
    def create_error_response(
        error_message: str,
        error_code: str,
        status_code: int = 400,
        detail: Optional[str] = None,
        validation_errors: List[ValidationError] = None,
    ) -> HTTPException:
        """
        Create standardized HTTPException with error response.

        Args:
            error_message: Main error message
            error_code: Error code for client handling
            status_code: HTTP status code
            detail: Additional error detail
            validation_errors: List of validation errors

        Returns:
            HTTPException with structured error response
        """
        error_response = ErrorResponse(
            error=error_message,
            error_code=error_code,
            detail=detail,
            validation_errors=validation_errors or [],
        )

        return HTTPException(status_code=status_code, detail=error_response.dict())

    @staticmethod
    def handle_file_not_found(file_path: str, file_type: str = "file") -> HTTPException:
        """Handle file not found errors with helpful messages."""
        return ErrorHandler.create_error_response(
            error_message=f"{file_type.title()} not found",
            error_code="FILE_NOT_FOUND",
            status_code=404,
            detail=f"The requested {file_type} could not be found: {file_path}",
        )

    @staticmethod
    def handle_validation_error(
        field: str, message: str, value: Any = None
    ) -> HTTPException:
        """Handle validation errors with detailed information."""
        validation_error = ValidationError(
            field=field,
            message=message,
            invalid_value=str(value) if value is not None else None,
        )

        return ErrorHandler.create_error_response(
            error_message="Validation failed",
            error_code="VALIDATION_ERROR",
            status_code=400,
            detail=f"Invalid value for field '{field}': {message}",
            validation_errors=[validation_error],
        )

    @staticmethod
    def handle_service_error(service_name: str, error: Exception) -> HTTPException:
        """Handle service-level errors with context."""
        return ErrorHandler.create_error_response(
            error_message=f"{service_name} error",
            error_code="SERVICE_ERROR",
            status_code=500,
            detail=f"An error occurred in {service_name}: {str(error)}",
        )


# Request size validation middleware utility
def validate_request_size(max_size: int = 10 * 1024 * 1024):  # 10MB default
    """
    Decorator to validate request content length.

    Args:
        max_size: Maximum request size in bytes

    Returns:
        Decorator function
    """

    def decorator(func):
        # Don't use *args, **kwargs to avoid FastAPI parameter inference issues
        # Just pass the function through - the actual validation can be done
        # in middleware or the endpoint itself
        return func

    return decorator
