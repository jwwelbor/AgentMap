"""
Core adapter functions for converting between old interfaces and new service interfaces.

This module provides utilities for parameter conversion, result extraction, and error
handling that will be used across CLI, API, and serverless handlers.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from dependency_injector.containers import Container

from agentmap.models.execution_result import ExecutionResult
from agentmap.services.graph_runner_service import RunOptions


class ServiceAdapter:
    """Adapter for converting between old interfaces and new service interfaces."""

    def __init__(self, container: Container):
        """Initialize adapter with DI container."""
        self.container = container

    def create_run_options(
        self,
        csv: Optional[str] = None,
        state: Optional[Union[str, Dict[str, Any]]] = None,
        autocompile: Optional[bool] = None,
        validate_before_run: bool = False,
        track_execution: bool = True,
        force_compilation: bool = False,
        execution_mode: str = "standard",
        config_file: Optional[str] = None,
        **kwargs,
    ) -> RunOptions:
        """
        Convert CLI/API parameters to RunOptions.

        Note: graph_name is passed separately to run_graph() method.

        Args:
            csv: CSV path override
            state: Initial state (JSON string or dict)
            autocompile: Whether to autocompile if graph missing
            validate_before_run: Whether to validate before execution
            track_execution: Whether to enable execution tracking
            force_compilation: Whether to force recompilation
            execution_mode: Execution mode (standard, debug, minimal)
            config_file: Path to custom config file
            **kwargs: Additional parameters

        Returns:
            RunOptions: Configured options for GraphRunnerService
        """
        # Parse state if it's a JSON string
        if isinstance(state, str):
            try:
                parsed_state = json.loads(state) if state != "{}" else {}
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in state parameter: {e}")
        else:
            parsed_state = state or {}

        # Convert paths to Path objects if provided
        csv_path = Path(csv) if csv else None

        return RunOptions(
            initial_state=parsed_state,
            autocompile=autocompile,
            csv_path=csv_path,
            validate_before_run=validate_before_run,
            track_execution=track_execution,
            force_compilation=force_compilation,
            execution_mode=execution_mode,
        )

    def extract_result_state(self, result: ExecutionResult) -> Dict[str, Any]:
        """
        Convert ExecutionResult to legacy format for backward compatibility.

        Args:
            result: ExecutionResult from GraphRunnerService

        Returns:
            Dict containing legacy format result
        """
        return {
            "final_state": result.final_state,
            "success": result.success,
            "error": result.error,
            "execution_time": result.total_duration,
            "metadata": {
                "graph_name": result.graph_name,
                "source_info": getattr(result, "source_info", result.compiled_from),
                "execution_summary": result.execution_summary,
            },
        }

    def handle_execution_error(self, error: Exception) -> Dict[str, Any]:
        """
        Standardize error responses across entry points.

        Args:
            error: Exception that occurred during execution

        Returns:
            Dict containing standardized error response
        """
        error_type = type(error).__name__

        # Map specific exceptions to appropriate status information
        status_info = {
            "ValueError": {"code": 400, "category": "validation"},
            "FileNotFoundError": {"code": 404, "category": "file"},
            "PermissionError": {"code": 403, "category": "permission"},
            "TimeoutError": {"code": 408, "category": "timeout"},
        }

        info = status_info.get(error_type, {"code": 500, "category": "internal"})

        return {
            "success": False,
            "error": str(error),
            "error_type": error_type,
            "error_category": info["category"],
            "status_code": info["code"],
        }

    def initialize_services(self):
        """
        Initialize services from DI container using src_new paths.

        Returns:
            Tuple of commonly used services
        """
        try:
            graph_runner_service = self.container.graph_runner_service()
            app_config_service = self.container.app_config_service()
            logging_service = self.container.logging_service()

            return graph_runner_service, app_config_service, logging_service

        except Exception as e:
            raise RuntimeError(f"Failed to initialize services from DI container: {e}")


def create_service_adapter(container: Container) -> ServiceAdapter:
    """
    Factory function to create ServiceAdapter instance.

    Args:
        container: DI container with configured services

    Returns:
        ServiceAdapter: Configured adapter instance
    """
    return ServiceAdapter(container)


def validate_run_parameters(**params) -> None:
    """
    Validate common run parameters before processing.

    Args:
        **params: Parameters to validate

    Raises:
        ValueError: If validation fails
    """
    if "csv" in params and params["csv"]:
        csv_path = Path(params["csv"])
        if not csv_path.exists():
            raise ValueError(f"CSV file not found: {csv_path}")
        if not csv_path.suffix.lower() == ".csv":
            raise ValueError(f"File must have .csv extension: {csv_path}")

    if "state" in params and isinstance(params["state"], str):
        try:
            json.loads(params["state"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in state parameter: {e}")

    if "bundle_path" in params and params["bundle_path"]:
        bundle_path = Path(params["bundle_path"])
        if not bundle_path.exists():
            raise ValueError(f"Bundle file not found: {bundle_path}")
