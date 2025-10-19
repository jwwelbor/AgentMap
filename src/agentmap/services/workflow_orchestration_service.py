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
from agentmap.services.state_adapter_service import StateAdapterService


class WorkflowOrchestrationService:
    """
    Service that orchestrates workflow execution using the same logic as run_command.py

    This extracts the reusable workflow-level logic while preserving the existing
    GraphExecutionService for low-level graph execution.
    """

    @staticmethod
    def execute_workflow(
        workflow: Optional[str] = None,
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
            workflow: CSV file path, workflow name, or workflow/graph pattern
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

        # Step 2: Parse initial state (same logic as run_command.py), only triggered if it's json
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
        # Combine workflow and graph_name into a single identifier for resolution
        if csv_override:
            csv_path = Path(csv_override)
            resolved_graph_name = graph_name or workflow or "default"
        else:
            # Build identifier for _resolve_csv_path
            if graph_name and workflow:
                graph_identifier = f"{workflow}::{graph_name}"
            else:
                graph_identifier = workflow or graph_name or ""

            csv_path, resolved_graph_name = _resolve_csv_path(
                graph_identifier, container
            )

        # Step 4: Extract graph_name from shorthand if needed (same as run_command.py)
        # This handles the workflow/graph shorthand syntax
        if workflow and "/" in str(workflow) and not graph_name:
            parts = str(workflow).split("/", 1)
            if len(parts) > 1:
                resolved_graph_name = parts[1]

        # Step 5: Validate CSV if requested (same as run_command.py)
        if validate_csv:
            validation_service = container.validation_service()
            validation_service.validate_csv_for_bundling(csv_path)

        # Step 6: Get or create bundle (same as run_command.py)
        graph_bundle_service = container.graph_bundle_service()
        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=resolved_graph_name, config_path=config_file
        )

        # Step 7: Execute using GraphRunnerService (same as run_command.py)
        # This will ultimately call your existing GraphExecutionService
        runner = container.graph_runner_service()

        # ===== INJECT StateAdapter normalization here =====
        state_adapter_service = container.state_adapter_service()

        # Normalize initial state for LangGraph compatibility
        # Supports json, pydantic, or dictionary input -> normalized dict output
        normalized_state = _normalize_initial_state_for_execution(
            parsed_state, state_adapter_service
        )

        result = runner.run(bundle, normalized_state)
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
        interaction_handler = container.interaction_handler_service()
        graph_bundle_service = container.graph_bundle_service()
        graph_runner_service = container.graph_runner_service()

        try:
            # Step 3: Load thread metadata from pickle storage
            thread_data = interaction_handler.get_thread_metadata(thread_id)
            if not thread_data:
                raise ValueError(f"Thread '{thread_id}' not found in storage")

            # Step 4: Rehydrate GraphBundle from stored metadata
            bundle_info = thread_data.get("bundle_info", {})
            graph_name = thread_data.get("graph_name")

            bundle = _rehydrate_bundle_from_metadata(
                bundle_info, graph_name, graph_bundle_service
            )
            if not bundle:
                raise RuntimeError("Failed to rehydrate GraphBundle from metadata")

            # Step 5: Prepare checkpoint state
            checkpoint_data = thread_data.get("checkpoint_data", {})
            checkpoint_state = checkpoint_data.copy()

            # Step 6: Handle both HumanAgent (with interaction) and SuspendAgent (without)
            request_id = thread_data.get("pending_interaction_id")

            if request_id:
                # HumanAgent path - requires human interaction response
                if not response_action:
                    raise ValueError(
                        f"Pending interaction '{request_id}' requires a response_action"
                    )

                # This is a human-interaction suspend - save response
                response = HumanInteractionResponse(
                    request_id=UUID(request_id),
                    action=response_action,
                    data=response_data or {},
                )

                # Save response using InteractionHandlerService
                save_success = interaction_handler.save_interaction_response(
                    response_id=str(response.request_id),
                    thread_id=thread_id,
                    action=response.action,
                    data=response.data,
                )
                if not save_success:
                    raise RuntimeError("Failed to save interaction response")

                # Update thread status to 'resuming' with response ID
                update_success = interaction_handler.mark_thread_resuming(
                    thread_id=thread_id, last_response_id=str(response.request_id)
                )
                if not update_success:
                    raise RuntimeError("Failed to update thread status to resuming")

                # Inject human response into checkpoint state
                checkpoint_state["__human_response"] = {
                    "action": response.action,
                    "data": response.data,
                    "request_id": str(response.request_id),
                }
            else:
                # SuspendAgent path - no human interaction required
                # Mark thread as resuming
                update_success = interaction_handler.mark_thread_resuming(
                    thread_id=thread_id
                )
                if not update_success:
                    raise RuntimeError("Failed to update thread status to resuming")

                # If response_action provided, pass it as the resume value
                # SuspendAgent will receive this via interrupt() return value
                if response_action:
                    checkpoint_state["__resume_value"] = response_action
                if response_data:
                    checkpoint_state["__resume_data"] = response_data

            # Step 7: Delegate to business logic layer
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
            bundle, _ = graph_bundle_service.get_or_create_bundle(
                csv_path=Path(csv_path), graph_name=graph_name
            )
            if bundle:
                return bundle

        return None

    except Exception:
        return None


# Convenience function for external usage
def execute_workflow(
    workflow: Optional[str] = None,
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
        workflow=workflow,
        graph_name=graph_name,
        initial_state=initial_state,
        config_file=config_file,
        **kwargs,
    )


def _normalize_initial_state_for_execution(
    initial_state: Any, state_adapter_service: StateAdapterService
) -> Dict[str, Any]:
    """
    Normalize initial state for LangGraph execution using StateAdapterService.

    This function implements the original design intent to support json, pydantic,
    or dictionary state objects and translate them into LangGraph-compatible format.

    Args:
        initial_state: Raw state from user input (dict, pydantic model, JSON-parsed, etc.)
        state_adapter_service: StateAdapterService for normalization

    Returns:
        Dict[str, Any]: Normalized state ready for LangGraph execution
    """
    if initial_state is None:
        return {}

    # If already a dict, check if it needs any normalization
    if isinstance(initial_state, dict):
        # Already a dict, but might contain complex objects that need normalization
        # StateAdapter handles dict format natively, just ensure it's clean
        return initial_state

    # For pydantic models or objects with dict() method
    if hasattr(initial_state, "dict") and callable(getattr(initial_state, "dict")):
        return initial_state.dict()

    # For pydantic v2 models with model_dump() method
    if hasattr(initial_state, "model_dump") and callable(
        getattr(initial_state, "model_dump")
    ):
        return initial_state.model_dump()

    # For objects with __dict__ attribute
    if hasattr(initial_state, "__dict__"):
        return initial_state.__dict__

    # For simple values, wrap in a state structure
    if isinstance(initial_state, (str, int, float, bool, list)):
        return {"value": initial_state}

    # Fallback: try to convert to dict representation
    try:
        return dict(initial_state)
    except (TypeError, ValueError):
        # If all else fails, wrap the object
        return {"state": initial_state}
