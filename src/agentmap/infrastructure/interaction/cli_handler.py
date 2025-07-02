"""
CLI interaction handler for human-in-the-loop workflows.

This module provides a CLI handler for displaying interaction requests
and managing the resume process using storage services.
"""

from typing import Any, Optional
from uuid import UUID

import typer

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

    def __init__(self, storage_service: StorageService):
        """
        Initialize the CLI interaction handler.

        Args:
            storage_service: Storage service for persisting interaction data
        """
        self.storage_service = storage_service
        self.collection_name = "interactions"

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
            thread_data = self.storage_service.read(
                collection="threads", document_id=thread_id
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
                collection="threads",
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

            # Call _resume_graph_execution (placeholder for now)
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

        This is a placeholder method that will be implemented
        when the graph execution service supports resumption.

        Args:
            thread_id: Thread ID to resume
            response: Human interaction response
        """
        # Placeholder implementation
        typer.echo(
            f"⚠️  Graph resumption not yet implemented. "
            f"Thread '{thread_id}' is ready to resume with response."
        )
        # TODO: Call graph execution service to resume workflow
        # This will be implemented when the graph execution service
        # has the necessary resume functionality
