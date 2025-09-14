"""
REFACTORED CLI resume command - now uses shared workflow resume logic.

This demonstrates how the resume CLI would be updated to use the same
orchestration service as serverless functions while preserving the
existing resume architecture.
"""

from typing import Optional

import typer

from agentmap.services.workflow_orchestration_service import resume_workflow


def resume_command(
    thread_id: str = typer.Argument(..., help="Thread ID to resume"),
    response: str = typer.Argument(
        ..., help="Response action (e.g., approve, reject, choose, respond, edit)"
    ),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="Additional data as JSON string"
    ),
    data_file: Optional[str] = typer.Option(
        None, "--data-file", "-f", help="Path to JSON file containing additional data"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """Resume an interrupted workflow by providing thread ID and response data."""
    try:
        # Execute using shared orchestration service (preserves existing architecture!)
        result = resume_workflow(
            thread_id=thread_id,
            response_action=response,
            response_data=data,
            data_file_path=data_file,
            config_file=config_file,
        )

        # Display result (CLI-specific formatting)
        if result["success"]:
            typer.secho(
                f"✅ Successfully resumed thread '{thread_id}' with action '{response}'",
                fg=typer.colors.GREEN,
            )

            if not result["services_available"]:
                typer.secho(
                    "⚠️  Graph services not available. Response saved but execution cannot restart.",
                    fg=typer.colors.YELLOW,
                )
        else:
            typer.secho(
                f"❌ Failed to resume thread '{thread_id}': {result.get('error', 'Unknown error')}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    except ValueError as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except RuntimeError as e:
        typer.secho(f"❌ Storage error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# The CLI is now ~30 lines instead of 80+ lines!
# All orchestration logic is shared with serverless functions
# Existing resume architecture and services remain unchanged
