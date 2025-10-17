"""
Pure display utilities for CLI presentation.

This module contains pure presentation logic with no business logic or dependencies.
Functions here only format and display information to the user.
"""

import json
from typing import Any, Dict, Optional

import typer

from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType


def display_interaction_request(request: HumanInteractionRequest) -> None:
    """
    Display a human interaction request to the user.

    Pure presentation logic - no business logic or dependencies.

    Args:
        request: The interaction request to display
    """
    # Header
    typer.echo("\n" + "=" * 60)
    typer.echo("🤖 AGENT INTERACTION REQUIRED")
    typer.echo("=" * 60)

    # Basic info
    typer.echo(f"📍 Node: {request.node_name}")
    typer.echo(f"🔗 Thread: {request.thread_id}")

    # Handle interaction type display with fallback for None
    if request.interaction_type is not None:
        typer.echo(f"⚡ Type: {request.interaction_type.value.upper()}")
    else:
        typer.echo("⚡ Type: UNKNOWN")

    if request.timeout_seconds:
        typer.echo(f"⏱️  Timeout: {request.timeout_seconds} seconds")

    typer.echo("\n" + "-" * 60)

    # Main prompt
    typer.echo("💬 PROMPT:")
    typer.echo(f"{request.prompt}")

    # Context information (if provided)
    if request.context:
        typer.echo("\n📋 CONTEXT:")
        _display_context(request.context)

    # Type-specific instructions
    typer.echo("\n" + "-" * 60)
    _display_interaction_instructions(request)

    # Footer
    typer.echo("\n" + "=" * 60)
    typer.echo(
        "💡 To respond, use: agentmap resume <thread_id> --action <action> [--data <data>]"
    )
    typer.echo("=" * 60 + "\n")


def _display_context(context: Dict[str, Any]) -> None:
    """Display context information in a readable format."""
    for key, value in context.items():
        if isinstance(value, (dict, list)):
            typer.echo(f"  {key}:")
            try:
                formatted_value = json.dumps(value, indent=4)
                for line in formatted_value.split("\n"):
                    typer.echo(f"    {line}")
            except (TypeError, ValueError):
                typer.echo(f"    {str(value)}")
        else:
            typer.echo(f"  {key}: {value}")


def _display_interaction_instructions(request: HumanInteractionRequest) -> None:
    """Display type-specific interaction instructions."""
    interaction_type = request.interaction_type

    if interaction_type == InteractionType.APPROVAL:
        typer.echo("✅ APPROVAL REQUIRED:")
        typer.echo("  Actions: 'approve' or 'reject'")
        typer.echo("  Example: agentmap resume {thread_id} --action approve")
        typer.echo(
            '  Example: agentmap resume {thread_id} --action reject --data \'{"reason": "Not ready"}\''
        )

    elif interaction_type == InteractionType.CHOICE:
        typer.echo("📝 CHOOSE AN OPTION:")
        if request.options:
            typer.echo("  Available options:")
            for i, option in enumerate(request.options, 1):
                typer.echo(f"    {i}. {option}")
            typer.echo("  Actions: 'choose'")
            typer.echo(
                f"  Example: agentmap resume {request.thread_id} --action choose --data '{{\"choice\": \"{request.options[0] if request.options else 'option_name'}\"}}'}}"
            )
        else:
            typer.echo("  Actions: 'choose'")
            typer.echo(
                f"  Example: agentmap resume {request.thread_id} --action choose"
                + ' --data \'{"choice": "your_choice"}}\''
            )

    elif interaction_type == InteractionType.TEXT_INPUT:
        typer.echo("✏️  TEXT INPUT REQUIRED:")
        typer.echo("  Actions: 'submit'")
        typer.echo(
            f"  Example: agentmap resume {request.thread_id} --action submit "
            + '--data \'{"text": "Your response here"}\''
        )

    elif interaction_type == InteractionType.EDIT:
        typer.echo("📝 EDITING REQUIRED:")
        typer.echo("  Actions: 'save', 'cancel'")
        typer.echo(
            f"  Example: agentmap resume {request.thread_id} --action save"
            + ' --data \'{"content": "Updated content"}\''
        )
        typer.echo(f"  Example: agentmap resume {request.thread_id} --action cancel")

    elif interaction_type == InteractionType.CONVERSATION:
        typer.echo("💬 CONVERSATION:")
        typer.echo("  Actions: 'reply', 'continue', 'end'")
        typer.echo(
            f"  Example: agentmap resume {request.thread_id} --action reply"
            + ' --data \'{"message": "Your message here"}\''
        )
        typer.echo(f"  Example: agentmap resume {request.thread_id} --action continue")

    else:
        # Generic fallback
        typer.echo("⚙️  INTERACTION REQUIRED:")
        typer.echo("  Actions: 'continue', 'cancel'")
        typer.echo(f"  Example: agentmap resume {request.thread_id} --action continue")

    # Common cancel option
    typer.echo("\n  Cancel: agentmap resume {thread_id} --action cancel")


def display_resume_instructions(
    thread_id: str,
    graph_name: str,
    interrupt_type: str,
    config_file: Optional[str] = None,
) -> None:
    """Display formatted resume instructions for interrupted workflows."""

    icon = "👤" if interrupt_type == "human_interaction" else "🔄"
    header = "=" * 60

    typer.secho("\n" + header, fg=typer.colors.BLUE)
    typer.secho(f"{icon}  EXECUTION PAUSED", fg=typer.colors.YELLOW, bold=True)
    typer.secho(f"Graph: {graph_name}", fg=typer.colors.CYAN)
    typer.secho(f"Thread ID: {thread_id}", fg=typer.colors.CYAN)

    typer.secho("\n📋 Resume Command", fg=typer.colors.GREEN, bold=True)
    config_arg = f" --config {config_file}" if config_file else ""
    base_command = f'agentmap resume {thread_id} "<response>"{config_arg}'
    typer.echo(f"  {base_command}")

    if interrupt_type == "human_interaction":
        typer.echo("\n💡 Examples:")
        typer.echo(f'  • Approval: agentmap resume {thread_id} "approve"{config_arg}')
        typer.echo(f'  • Rejection: agentmap resume {thread_id} "reject"{config_arg}')
        typer.echo(f'  • Text: agentmap resume {thread_id} "your response"{config_arg}')
    else:
        typer.echo("\nℹ️  Provide the external result when ready and resume the run.")

    typer.secho(header + "\n", fg=typer.colors.BLUE)


def display_resume_result(result: Dict[str, Any]) -> None:
    """
    Display the result of a resume operation.

    Args:
        result: Result dictionary from workflow_ops.resume_workflow()
    """
    if result.get("success"):
        typer.echo("\n✅ WORKFLOW RESUMED SUCCESSFULLY")
        typer.echo("=" * 50)

        metadata = result.get("metadata", {})
        if metadata.get("thread_id"):
            typer.echo(f"🔗 Thread: {metadata['thread_id']}")
        if metadata.get("response_action"):
            typer.echo(f"⚡ Action: {metadata['response_action']}")
        if metadata.get("graph_name"):
            typer.echo(f"📊 Graph: {metadata['graph_name']}")
        if metadata.get("duration"):
            typer.echo(f"⏱️  Duration: {metadata['duration']:.2f}s")

        execution_summary = result.get("execution_summary")
        if execution_summary:
            typer.echo("\n📋 EXECUTION SUMMARY:")
            if isinstance(execution_summary, dict):
                for key, value in execution_summary.items():
                    typer.echo(f"  {key}: {value}")
            else:
                typer.echo(f"  {execution_summary}")

        outputs = result.get("outputs")
        if outputs:
            typer.echo("\n📤 FINAL OUTPUTS:")
            _display_context(outputs)

    else:
        typer.echo("\n❌ WORKFLOW RESUME FAILED")
        typer.echo("=" * 50)

        error = result.get("error", "Unknown error")
        typer.echo(f"💥 Error: {error}")

        metadata = result.get("metadata", {})
        if metadata.get("resume_token"):
            typer.echo(f"🔗 Token: {metadata['resume_token']}")

    typer.echo("=" * 50 + "\n")


def display_error(error_message: str, error_type: str = "Error") -> None:
    """
    Display an error message with consistent formatting.

    Args:
        error_message: The error message to display
        error_type: Type of error (e.g., "Error", "Warning", "Critical")
    """
    typer.echo(f"\n❌ {error_type.upper()}")
    typer.echo("-" * 30)
    typer.echo(f"💥 {error_message}")
    typer.echo("-" * 30 + "\n")


def display_success(message: str, title: str = "Success") -> None:
    """
    Display a success message with consistent formatting.

    Args:
        message: The success message to display
        title: Title for the success message
    """
    typer.echo(f"\n✅ {title.upper()}")
    typer.echo("-" * 30)
    typer.echo(f"🎉 {message}")
    typer.echo("-" * 30 + "\n")
