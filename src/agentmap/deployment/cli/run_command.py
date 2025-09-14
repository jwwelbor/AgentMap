"""
REFACTORED CLI run command - now uses shared workflow orchestration logic.

This demonstrates how the CLI would be updated to use the same
orchestration service as serverless functions while preserving the
existing GraphExecutionService architecture.
"""

from typing import Optional

import typer

from agentmap.deployment.cli.cli_utils import (
    handle_command_error,
    parse_json_state,
)
from agentmap.services.workflow_orchestration_service import execute_workflow


def run_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path or workflow/graph (e.g., 'hello_world/HelloWorld')"
    ),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to run"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    state: str = typer.Option(
        "{}", "--state", "-s", help="Initial state as JSON string"
    ),
    validate: bool = typer.Option(
        False, "--validate", help="Validate CSV before running"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    pretty: bool = typer.Option(
        False, "--pretty", "-p", help="Format output for better readability"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed execution info with --pretty"
    ),
):
    """
    Run a graph using cached bundles for efficient execution.

    Uses the same orchestration logic as serverless functions while preserving
    the existing GraphExecutionService → GraphRunnerService → Bundle architecture.
    """
    try:
        # Parse initial state (could also let execute_workflow handle this)
        initial_state = parse_json_state(state)

        # Execute using shared orchestration service (preserves existing architecture!)
        result = execute_workflow(
            csv_or_workflow=csv_file,
            graph_name=graph,
            initial_state=initial_state,
            config_file=config_file,
            validate_csv=validate,
            csv_override=csv,
        )

        # Display result (CLI-specific formatting)
        if result.success:
            typer.secho(
                "✅ Graph execution completed successfully", fg=typer.colors.GREEN
            )

            if pretty:
                # Get formatter service for pretty output
                from agentmap.di import initialize_di

                container = initialize_di(config_file)
                formatter_service = container.execution_formatter_service()
                formatted_output = formatter_service.format_execution_result(
                    result.final_state, verbose=verbose
                )
                print(formatted_output)
            else:
                print("✅ Output:", result.final_state)
        else:
            typer.secho(
                f"❌ Graph execution failed: {result.error}", fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

    except Exception as e:
        handle_command_error(e, verbose)


# The CLI is now ~30 lines instead of 100+ lines!
# All orchestration logic is shared with serverless functions
# Existing GraphExecutionService and architecture remain unchanged
