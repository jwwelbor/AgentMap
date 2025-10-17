"""
CLI resume command - uses runtime facade for resume operations.

This command follows SPEC-DEP-001 by using only the runtime facade
and CLI presenter utilities for consistent behavior and error handling.
"""

import json
from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_presenter import (
    map_exception_to_exit_code,
    print_err,
    print_json,
)
from agentmap.runtime_api import ensure_initialized, resume_workflow


def resume_command(
    thread_id: str = typer.Argument(..., help="Thread ID to resume"),
    response: Optional[str] = typer.Argument(
        None, help="Response action (e.g., approve, reject, choose, respond, edit)"
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
        # Ensure runtime is initialized
        ensure_initialized(config_file=config_file)

        # Parse response data from various sources
        response_data = None
        if data:
            try:
                response_data = json.loads(data)
            except json.JSONDecodeError as e:
                print_err(f"Invalid JSON in --data: {e}")
                raise typer.Exit(
                    code=map_exception_to_exit_code(ValueError("Invalid JSON"))
                )
        elif data_file:
            try:
                with open(data_file, "r") as f:
                    response_data = json.load(f)
            except FileNotFoundError:
                print_err(f"Data file not found: {data_file}")
                raise typer.Exit(
                    code=map_exception_to_exit_code(ValueError("File not found"))
                )
            except json.JSONDecodeError as e:
                print_err(f"Invalid JSON in file {data_file}: {e}")
                raise typer.Exit(
                    code=map_exception_to_exit_code(ValueError("Invalid JSON"))
                )

        # Create resume token with thread_id and response action
        resume_token_data = {
            "thread_id": thread_id,
            "response_action": response,
        }
        if response_data:
            resume_token_data["response_data"] = response_data

        resume_token = json.dumps(resume_token_data)

        # Execute using runtime facade
        result = resume_workflow(
            resume_token=resume_token,
            config_file=config_file,
        )

        # Display result using CLI presenter for consistency
        if result.get("success", False):
            typer.secho(
                f"✅ Successfully resumed thread '{thread_id}' with action '{response}'",
                fg=typer.colors.GREEN,
            )

            # Check service availability
            if not result.get("services_available", True):
                typer.secho(
                    "⚠️  Graph services not available. Response saved but execution cannot restart.",
                    fg=typer.colors.YELLOW,
                )

            # Show outputs if available
            outputs = result.get("outputs")
            if outputs:
                typer.secho("📤 Resume result:", fg=typer.colors.BLUE, bold=True)
                print_json(outputs)

        else:
            # This shouldn't happen with the facade pattern, but handle gracefully
            error_msg = result.get("error", "Unknown error")
            print_err(f"Failed to resume thread '{thread_id}': {error_msg}")
            raise typer.Exit(code=1)

        raise typer.Exit(code=0)

    except typer.Exit:
        # Re-raise typer.Exit as-is to preserve exit codes
        raise
    except Exception as e:
        # Use CLI presenter for consistent error handling and exit codes
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
