"""
Workflow Orchestration Service - extracts reusable logic from run_command.py

This service sits ABOVE GraphExecutionService and handles the workflow-level
orchestration that run_command.py currently does. It does NOT replace the
existing GraphExecutionService which correctly handles low-level execution.

Architecture:
  WorkflowOrchestrationService (this service)
      ↓ (CSV resolution, Bundle creation, parameter parsing)
  GraphRunnerService
      ↓ (High-level execution coordination)
  GraphExecutionService (existing - unchanged)
      ↓ (Low-level graph execution)
  Executable Graph (LangGraph)
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.di import initialize_di
from agentmap.models.execution.result import ExecutionResult
from agentmap.runtime.workflow_ops import _resolve_csv_path


class WorkflowOrchestrationService:
    """
    Service that orchestrates workflow execution using the same logic as run_command.py

    This extracts the reusable workflow-level logic while preserving the existing
    GraphExecutionService for low-level graph execution.
    """

    @staticmethod
    def execute_workflow(
        csv_or_workflow: Optional[str] = None,
        graph_name: Optional[str] = None,
        initial_state: Optional[Union[Dict[str, Any], str]] = None,
        config_file: Optional[str] = None,
        validate_csv: bool = False,
        csv_override: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a workflow using the same orchestration logic as run_command.py

        This function handles:
        1. DI container initialization
        2. CSV/workflow path resolution
        3. Bundle creation/retrieval
        4. Parameter parsing and validation
        5. Delegation to GraphRunnerService (which uses GraphExecutionService)

        Args:
            csv_or_workflow: CSV file path, workflow name, or workflow/graph pattern
            graph_name: Graph name to execute
            initial_state: Initial state dict or JSON string
            config_file: Optional config file path
            validate_csv: Whether to validate CSV before execution
            csv_override: CSV path override

        Returns:
            ExecutionResult: Result from GraphRunnerService.run() (unchanged)
        """
        # Step 1: Initialize DI container (same as run_command.py)
        container = initialize_di(config_file)

        # Step 2: Parse initial state (same logic as run_command.py)
        if isinstance(initial_state, str):
            try:
                parsed_state = (
                    json.loads(initial_state) if initial_state != "{}" else {}
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in initial_state: {e}")
        else:
            parsed_state = initial_state or {}

        # Step 3: Handle the graph identifier resolution
        # Combine csv_or_workflow and graph_name into a single identifier for resolution
        if csv_or_workflow:
            # Handle the csv_override case
            if csv_override:
                # If csv_override is provided, use it as the path directly
                csv_path = Path(csv_override)
                resolved_graph_name = graph_name or csv_or_workflow
            else:
                # Use the comprehensive resolution logic from workflow_ops
                # If graph_name is provided separately, use :: syntax for resolution
                if graph_name and "/" not in str(csv_or_workflow):
                    graph_identifier = f"{csv_or_workflow}::{graph_name}"
                else:
                    graph_identifier = csv_or_workflow

                csv_path, resolved_graph_name = _resolve_csv_path(
                    graph_identifier, container
                )

                # If graph_name was explicitly provided, use it instead of resolved name
                if graph_name:
                    resolved_graph_name = graph_name
        else:
            # No csv_or_workflow provided, check for csv_override
            if csv_override:
                csv_path = Path(csv_override)
                resolved_graph_name = graph_name
            else:
                # Use default resolution with just the graph_name
                csv_path, resolved_graph_name = _resolve_csv_path(
                    graph_name or "", container
                )

        # Step 4: Extract graph_name from shorthand if needed (same as run_command.py)
        # This handles the workflow/graph shorthand syntax
        if csv_or_workflow and "/" in str(csv_or_workflow) and not graph_name:
            parts = str(csv_or_workflow).split("/", 1)
            if len(parts) > 1:
                resolved_graph_name = parts[1]

        # Step 5: Validate CSV if requested (same as run_command.py)
        if validate_csv:
            validation_service = container.validation_service()
            validation_service.validate_csv_for_bundling(csv_path)

        # Step 6: Get or create bundle (same as run_command.py)
        graph_bundle_service = container.graph_bundle_service()
        bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=resolved_graph_name, config_path=config_file
        )

        # Step 7: Execute using GraphRunnerService (same as run_command.py)
        # This will ultimately call your existing GraphExecutionService
        runner = container.graph_runner_service()
        result = runner.run(bundle, parsed_state)

        return result


# Convenience function for external usage
def execute_workflow(
    csv_or_workflow: Optional[str] = None,
    graph_name: Optional[str] = None,
    initial_state: Optional[Union[Dict[str, Any], str]] = None,
    config_file: Optional[str] = None,
    **kwargs,
) -> ExecutionResult:
    """
    Convenience function for workflow execution that preserves existing architecture.

    This delegates to WorkflowOrchestrationService which preserves the existing
    execution chain through GraphRunnerService → GraphExecutionService.
    """
    return WorkflowOrchestrationService.execute_workflow(
        csv_or_workflow=csv_or_workflow,
        graph_name=graph_name,
        initial_state=initial_state,
        config_file=config_file,
        **kwargs,
    )
