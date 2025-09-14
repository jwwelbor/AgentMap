"""
CLI interaction handler for human-in-the-loop workflows.

This module provides a CLI handler for displaying interaction requests
and managing the resume process using storage services.
"""

from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import typer

from agentmap.models.execution.config import ExecutionConfig
from agentmap.models.human_interaction import (
    HumanInteractionRequest,
    HumanInteractionResponse,
    InteractionType,
)
from agentmap.services.storage.protocols import StorageService
from agentmap.services.storage.types import WriteMode


class CLIInteractionHandler:
    """
    CLI handler for human interaction requests.

    This handler displays interaction requests to users via the CLI
    and manages the resume process by persisting interaction data.
    """

    def __init__(
        self,
        storage_service: StorageService,
        graph_bundle_service: Optional[Any] = None,
        graph_runner_service: Optional[Any] = None,
        graph_checkpoint_service: Optional[Any] = None,
    ):
        """
        Initialize the CLI interaction handler.

        Args:
            storage_service: Storage service for persisting interaction data
            graph_bundle_service: Optional GraphBundleService for bundle rehydration
            graph_runner_service: Optional GraphRunnerService for execution resumption
            graph_checkpoint_service: Optional GraphCheckpointService for state management
        """
        self.storage_service = storage_service
        self.collection_name = "interactions"

        # Graph services for resumption (optional for backwards compatibility)
        self.graph_bundle_service = graph_bundle_service
        self.graph_runner_service = graph_runner_service
        self.graph_checkpoint_service = graph_checkpoint_service

    def display_interaction_request(self, request: HumanInteractionRequest) -> None:
        """
        Display an interaction request to the user.

        Formats and displays the interaction request using typer.echo,
        showing all relevant information including prompt, context, and options.

        Args:
            request: The human interaction request to display
        """
        # Display header
        typer.echo("")
        typer.secho("=" * 60, fg=typer.colors.CYAN, bold=True)
        typer.secho("🤝 Human Interaction Required", fg=typer.colors.YELLOW, bold=True)
        typer.secho("=" * 60, fg=typer.colors.CYAN, bold=True)
        typer.echo("")

        # Display request details
        typer.echo(f"Thread ID: {request.thread_id}")
        typer.echo(f"Node: {request.node_name}")
        typer.echo(f"Type: {request.interaction_type.value}")
        typer.echo(f"Request ID: {request.id}")
        typer.echo("")

        # Display prompt
        typer.secho("Prompt:", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  {request.prompt}")
        typer.echo("")

        # Display context if available
        if request.context:
            typer.secho("Context:", fg=typer.colors.GREEN, bold=True)
            for key, value in request.context.items():
                typer.echo(f"  {key}: {value}")
            typer.echo("")

        # Display options for choice-based interactions
        if request.interaction_type == InteractionType.CHOICE and request.options:
            typer.secho("Options:", fg=typer.colors.GREEN, bold=True)
            for idx, option in enumerate(request.options, 1):
                typer.echo(f"  {idx}. {option}")
            typer.echo("")

        # Display timeout if set
        if request.timeout_seconds:
            typer.echo(f"⏱️  Timeout: {request.timeout_seconds} seconds")
            typer.echo("")

        # Display resume command example
        typer.secho("To resume execution:", fg=typer.colors.BLUE, bold=True)

        if request.interaction_type == InteractionType.APPROVAL:
            typer.echo(f"  agentmap resume {request.thread_id} --action approve")
            typer.echo(f"  agentmap resume {request.thread_id} --action reject")
        elif request.interaction_type == InteractionType.CHOICE:
            typer.echo(
                f'  agentmap resume {request.thread_id} --action choose --data \'{"choice": 1}\''
            )
        elif request.interaction_type == InteractionType.TEXT_INPUT:
            typer.echo(
                f'  agentmap resume {request.thread_id} --action respond --data \'{"text": "your response"}\''
            )
        elif request.interaction_type == InteractionType.EDIT:
            typer.echo(
                f'  agentmap resume {request.thread_id} --action edit --data \'{"edited": "new content"}\''
            )
        else:
            typer.echo(
                f"  agentmap resume {request.thread_id} --action <action> --data '<json_data>'"
            )

        typer.echo("")
        typer.secho("=" * 60, fg=typer.colors.CYAN, bold=True)
        typer.echo("")

    def resume_execution(
        self, thread_id: str, response_action: str, response_data: Optional[Any] = None
    ) -> HumanInteractionResponse:
        """
        Resume workflow execution with a human response.

        Loads the interaction request from storage, creates a response,
        saves it to storage, and updates the thread status to 'resuming'.

        Args:
            thread_id: Thread ID to resume
            response_action: Action taken by the user (e.g., 'approve', 'reject', 'choose')
            response_data: Additional data for the response

        Returns:
            HumanInteractionResponse object

        Raises:
            ValueError: If thread or interaction request not found
            RuntimeError: If storage operations fail
        """
        try:
            # Load thread data from storage
            # this is a json service passed in during class creation
            thread_data = self.storage_service.read(
                collection=f"{self.collection_name}_threads", document_id=thread_id
            )

            if not thread_data:
                raise ValueError(f"Thread '{thread_id}' not found in storage")

            # Find the pending interaction request
            request_id = thread_data.get("pending_interaction_id")
            if not request_id:
                raise ValueError(
                    f"No pending interaction found for thread '{thread_id}'"
                )

            # Load the interaction request
            request_data = self.storage_service.read(
                collection=self.collection_name, document_id=str(request_id)
            )

            if not request_data:
                raise ValueError(f"Interaction request '{request_id}' not found")

            # Create the response
            response = HumanInteractionResponse(
                request_id=UUID(request_id),
                action=response_action,
                data=response_data or {},
            )

            # Save the response to storage
            save_result = self.storage_service.write(
                collection=f"{self.collection_name}_responses",
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

            # Update thread status to 'resuming'
            update_result = self.storage_service.write(
                collection=f"{self.collection_name}_threads",
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

            # Display success message
            typer.secho(
                f"✅ Response saved. Thread '{thread_id}' marked for resumption.",
                fg=typer.colors.GREEN,
            )

            # Call _resume_graph_execution
            self._resume_graph_execution(thread_id, response)

            return response

        except Exception as e:
            typer.secho(f"❌ Failed to resume execution: {str(e)}", fg=typer.colors.RED)
            raise

    def _resume_graph_execution(
        self, thread_id: str, response: HumanInteractionResponse
    ) -> None:
        """
        Resume graph execution after human interaction.

        Loads thread metadata from storage, rehydrates the bundle,
        and resumes graph execution with checkpoint support.

        Args:
            thread_id: Thread ID to resume
            response: Human interaction response
        """
        try:
            # Check if graph services are available
            if not self.graph_bundle_service or not self.graph_runner_service:
                typer.echo(
                    f"⚠️  Graph services not available. Cannot resume execution. "
                    f"Thread '{thread_id}' is ready to resume with response."
                )
                return

            # Load thread metadata from storage
            thread_data = self.storage_service.read(
                collection=f"{self.collection_name}_threads", document_id=thread_id
            )

            if not thread_data:
                raise ValueError(f"Thread metadata not found for '{thread_id}'")

            # Extract bundle information from thread metadata
            bundle_info = thread_data.get("bundle_info", {})
            graph_name = thread_data.get("graph_name")
            node_name = thread_data.get("node_name")

            if not bundle_info:
                raise ValueError(
                    f"No bundle information found for thread '{thread_id}'"
                )

            # Rehydrate bundle from metadata
            bundle = self._rehydrate_bundle_from_metadata(bundle_info, graph_name)

            if not bundle:
                raise ValueError(f"Failed to rehydrate bundle for thread '{thread_id}'")

            # Create execution config for resumption
            resume_state = {
                "human_response": {
                    "action": response.action,
                    "data": response.data,
                    "request_id": str(response.request_id),
                },
                "node_name": node_name,
                "__resuming_from_human_interaction": True,
            }

            execution_config = ExecutionConfig.for_resume(
                thread_id=thread_id,
                checkpointer=self.graph_checkpoint_service,
                resume_state=resume_state,
                metadata={
                    "resumed_from_node": node_name,
                    "human_response_action": response.action,
                },
            )

            typer.echo(f"🔄 Resuming graph execution for thread '{thread_id}'...")

            # Resume execution with checkpoint support
            result = self.graph_runner_service.run_with_config(
                bundle=bundle, config=execution_config
            )

            # Display result
            if result.success:
                typer.secho(
                    f"✅ Graph execution resumed and completed successfully for thread '{thread_id}'",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    f"❌ Graph execution failed after resumption for thread '{thread_id}': {result.error}",
                    fg=typer.colors.RED,
                )

        except Exception as e:
            typer.secho(
                f"❌ Failed to resume graph execution for thread '{thread_id}': {str(e)}",
                fg=typer.colors.RED,
            )
            raise

    def _rehydrate_bundle_from_metadata(
        self, bundle_info: Dict[str, Any], graph_name: Optional[str]
    ) -> Optional[Any]:
        """
        Rehydrate GraphBundle from stored metadata.

        Args:
            bundle_info: Bundle metadata from thread storage
            graph_name: Graph name for bundle lookup

        Returns:
            GraphBundle if rehydration succeeds, None otherwise
        """
        try:
            # Try to reload bundle using different available information
            csv_hash = bundle_info.get("csv_hash")
            bundle_path = bundle_info.get("bundle_path")
            csv_path = bundle_info.get("csv_path")

            # Method 1: Load from bundle path if available
            if bundle_path:
                bundle = self.graph_bundle_service.load_bundle(Path(bundle_path))
                if bundle:
                    return bundle

            # Method 2: Lookup by csv_hash and graph_name
            if csv_hash and graph_name:
                bundle = self.graph_bundle_service.lookup_bundle(csv_hash, graph_name)
                if bundle:
                    return bundle

            # Method 3: Recreate from CSV path if available
            if csv_path:
                bundle = self.graph_bundle_service.get_or_create_bundle(
                    csv_path=Path(csv_path), graph_name=graph_name
                )
                if bundle:
                    return bundle

            # No method worked
            typer.secho(
                f"⚠️  Could not rehydrate bundle from metadata: {bundle_info}",
                fg=typer.colors.YELLOW,
            )
            return None

        except Exception as e:
            typer.secho(f"❌ Bundle rehydration failed: {str(e)}", fg=typer.colors.RED)
            return None
