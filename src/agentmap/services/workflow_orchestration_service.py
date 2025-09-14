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
        app_config_service = container.app_config_service()

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

        # Step 3: Resolve CSV path (same logic as run_command.py)
        csv_path = WorkflowOrchestrationService._resolve_csv_path(
            csv_or_workflow=csv_or_workflow,
            graph_name_ref=graph_name,
            csv_override=csv_override,
            app_config_service=app_config_service,
        )

        # Step 4: Extract graph_name from shorthand if needed (same as run_command.py)
        if csv_or_workflow and "/" in str(csv_or_workflow) and not graph_name:
            parts = str(csv_or_workflow).split("/", 1)
            if len(parts) > 1:
                graph_name = parts[1]

        # Step 5: Validate CSV if requested (same as run_command.py)
        if validate_csv:
            validation_service = container.validation_service()
            validation_service.validate_csv_for_bundling(csv_path)

        # Step 6: Get or create bundle (same as run_command.py)
        graph_bundle_service = container.graph_bundle_service()
        bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=graph_name, config_path=config_file
        )

        # Step 7: Execute using GraphRunnerService (same as run_command.py)
        # This will ultimately call your existing GraphExecutionService
        runner = container.graph_runner_service()
        result = runner.run(bundle, parsed_state)

        return result

    @staticmethod
    def _resolve_csv_path(
        csv_or_workflow: Optional[str],
        graph_name_ref: Optional[str],
        csv_override: Optional[str],
        app_config_service,
    ) -> Path:
        """
        Resolve CSV path using the exact same logic as run_command.py

        This preserves all the workflow resolution patterns:
        - Direct file paths
        - Workflow names from repository
        - workflow/graph shortcuts
        """
        from agentmap.deployment.cli.cli_utils import resolve_csv_path

        # Handle repository-based shorthand: workflow/graph (same as run_command.py)
        if (
            csv_or_workflow
            and "/" in csv_or_workflow
            and not csv_override
            and not graph_name_ref
        ):
            parts = csv_or_workflow.split("/", 1)
            workflow_name = parts[0]

            # Check if it's a repository workflow (same logic as run_command.py)
            csv_repository = app_config_service.get_csv_repository_path()
            potential_workflow = csv_repository / f"{workflow_name}.csv"

            if potential_workflow.exists():
                return potential_workflow
            else:
                # Maybe it's a file path, resolve normally
                return resolve_csv_path(csv_or_workflow, csv_override)
        else:
            # Check if csv_or_workflow is a workflow name in repository (same as run_command.py)
            if csv_or_workflow and not csv_override:
                csv_repository = app_config_service.get_csv_repository_path()
                potential_workflow = csv_repository / f"{csv_or_workflow}.csv"

                if potential_workflow.exists():
                    return potential_workflow
                else:
                    # Try to resolve as file path
                    return resolve_csv_path(csv_or_workflow, csv_override)
            else:
                # Standard resolution (same as run_command.py)
                return resolve_csv_path(csv_or_workflow, csv_override)


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


# Resume operations (extracted from resume_command.py)
class WorkflowResumeService:
    """
    Service for resuming interrupted workflows.

    This also preserves the existing architecture and just extracts the
    reusable logic from resume_command.py
    """

    @staticmethod
    def resume_workflow(
        thread_id: str,
        response_action: str,
        response_data: Optional[Union[Dict[str, Any], str]] = None,
        data_file_path: Optional[str] = None,
        config_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resume workflow using the same logic as resume_command.py

        This preserves the existing resume architecture and just makes it reusable.
        """
        # Initialize DI container (same as resume_command.py)
        container = initialize_di(config_file)
        system_storage_manager = container.system_storage_manager()

        # Check storage availability (same as resume_command.py)
        if not system_storage_manager:
            raise RuntimeError("Storage services are not available")

        # Get services (same as resume_command.py)
        storage_service = system_storage_manager.get_service("json")
        logging_service = container.logging_service()
        logger = logging_service.get_logger("agentmap.workflow.resume")

        # Parse response data (same logic as resume_command.py)
        parsed_response_data = WorkflowResumeService._parse_response_data(
            response_data, data_file_path
        )

        # Get graph services (same as resume_command.py)
        try:
            graph_bundle_service = container.graph_bundle_service()
            graph_runner_service = container.graph_runner_service()
            graph_checkpoint_service = container.graph_checkpoint_service()
            services_available = True
        except Exception as e:
            logger.warning(f"Graph services not available: {e}")
            graph_bundle_service = None
            graph_runner_service = None
            graph_checkpoint_service = None
            services_available = False

        # Create interaction handler (same as resume_command.py)
        from agentmap.deployment.cli.cli_handler import CLIInteractionHandler

        handler = CLIInteractionHandler(
            storage_service=storage_service,
            graph_bundle_service=graph_bundle_service,
            graph_runner_service=graph_runner_service,
            graph_checkpoint_service=graph_checkpoint_service,
        )

        # Resume execution (same as resume_command.py)
        result = handler.resume_execution(
            thread_id=thread_id,
            response_action=response_action,
            response_data=parsed_response_data,
        )

        return {
            "success": True,
            "thread_id": thread_id,
            "response_action": response_action,
            "services_available": services_available,
            "result": result,
        }

    @staticmethod
    def _parse_response_data(
        response_data: Optional[Union[Dict[str, Any], str]] = None,
        data_file_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse response data (same logic as resume_command.py)"""

        if response_data:
            if isinstance(response_data, str):
                try:
                    return json.loads(response_data)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in response_data: {e}")
            else:
                return response_data

        elif data_file_path:
            try:
                with open(data_file_path, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                raise ValueError(f"Data file not found: {data_file_path}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in file: {e}")

        return None


# Convenience function for resume
def resume_workflow(
    thread_id: str,
    response_action: str,
    response_data: Optional[Union[Dict[str, Any], str]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Convenience function for workflow resume that preserves existing architecture.
    """
    return WorkflowResumeService.resume_workflow(
        thread_id=thread_id,
        response_action=response_action,
        response_data=response_data,
        **kwargs,
    )
