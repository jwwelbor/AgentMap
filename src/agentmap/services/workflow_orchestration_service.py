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
from uuid import UUID

from agentmap.di import initialize_di
from agentmap.models.execution.result import ExecutionResult
from agentmap.models.human_interaction import HumanInteractionResponse
from agentmap.runtime.workflow_ops import _resolve_csv_path
from agentmap.services.storage.types import WriteMode


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

    @staticmethod
    def resume_workflow(
        thread_id: str,
        response_action: str,
        response_data: Optional[Any] = None,
        config_file: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Resume a paused workflow - service orchestration layer.

        This function handles:
        1. DI container initialization
        2. Thread metadata loading from storage
        3. GraphBundle rehydration from stored metadata
        4. HumanInteractionResponse creation and storage
        5. Delegation to GraphRunnerService.resume_from_checkpoint()

        Args:
            thread_id: Thread ID to resume
            response_action: User action (approve, reject, choose, etc.)
            response_data: Additional response data
            config_file: Optional config file path

        Returns:
            ExecutionResult from GraphRunnerService.resume_from_checkpoint()
        """
        # Step 1: Initialize DI container (same pattern as execute_workflow)
        container = initialize_di(config_file)

        # Step 2: Get required services
        storage_service = container.json_storage_service()
        graph_bundle_service = container.graph_bundle_service()
        graph_runner_service = container.graph_runner_service()

        try:
            # Step 3: Load thread metadata from storage
            thread_data = storage_service.read(
                collection="interactions_threads", document_id=thread_id
            )
            if not thread_data:
                raise ValueError(f"Thread '{thread_id}' not found in storage")

            # Step 4: Load interaction request
            request_id = thread_data.get("pending_interaction_id")
            if not request_id:
                raise ValueError(
                    f"No pending interaction found for thread '{thread_id}'"
                )

            # Step 5: Rehydrate GraphBundle from stored metadata
            bundle_info = thread_data.get("bundle_info", {})
            graph_name = thread_data.get("graph_name")

            bundle = _rehydrate_bundle_from_metadata(
                bundle_info, graph_name, graph_bundle_service
            )
            if not bundle:
                raise RuntimeError("Failed to rehydrate GraphBundle from metadata")

            # Step 6: Create and save HumanInteractionResponse
            response = HumanInteractionResponse(
                request_id=UUID(request_id),
                action=response_action,
                data=response_data or {},
            )

            save_result = storage_service.write(
                collection="interactions_responses",
                data={
                    "request_id": str(response.request_id),
                    "action": response.action,
                    "data": response.data,
                    "timestamp": response.timestamp.isoformat(),
                },
                document_id=str(response.request_id),
                mode=WriteMode.WRITE,
            )
            if not save_result.success:
                raise RuntimeError(f"Failed to save response: {save_result.error}")

            # Step 7: Update thread status to 'resuming'
            update_result = storage_service.write(
                collection="interactions_threads",
                data={
                    "status": "resuming",
                    "pending_interaction_id": None,
                    "last_response_id": str(response.request_id),
                },
                document_id=thread_id,
                mode=WriteMode.UPDATE,
            )
            if not update_result.success:
                raise RuntimeError(
                    f"Failed to update thread status: {update_result.error}"
                )

            # Step 8: Prepare checkpoint state with human response injected
            checkpoint_data = thread_data.get("checkpoint_data", {})
            checkpoint_state = checkpoint_data.copy()
            checkpoint_state["__human_response"] = {
                "action": response.action,
                "data": response.data,
                "request_id": str(response.request_id),
            }

            # Step 9: Delegate to business logic layer
            result = graph_runner_service.resume_from_checkpoint(
                bundle=bundle,
                thread_id=thread_id,
                checkpoint_state=checkpoint_state,
                resume_node=thread_data.get("node_name"),
            )

            return result

        except Exception as e:
            raise RuntimeError(
                f"Resume workflow failed for thread {thread_id}: {str(e)}"
            ) from e


def _rehydrate_bundle_from_metadata(
    bundle_info: Dict[str, Any], graph_name: Optional[str], graph_bundle_service
) -> Optional[Any]:  # Return type is GraphBundle but avoiding import
    """Rehydrate GraphBundle from stored metadata using multiple strategies."""
    try:
        csv_hash = bundle_info.get("csv_hash")
        bundle_path = bundle_info.get("bundle_path")
        csv_path = bundle_info.get("csv_path")

        # Method 1: Load from bundle path
        if bundle_path:
            bundle = graph_bundle_service.load_bundle(Path(bundle_path))
            if bundle:
                return bundle

        # Method 2: Lookup by csv_hash and graph_name
        if csv_hash and graph_name:
            bundle = graph_bundle_service.lookup_bundle(csv_hash, graph_name)
            if bundle:
                return bundle

        # Method 3: Recreate from CSV path
        if csv_path:
            bundle = graph_bundle_service.get_or_create_bundle(
                csv_path=Path(csv_path), graph_name=graph_name
            )
            if bundle:
                return bundle

        return None

    except Exception:
        return None


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
