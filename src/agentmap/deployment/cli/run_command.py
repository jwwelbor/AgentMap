"""
CLI run command - uses runtime facade for execution.

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
from agentmap.runtime_api import ensure_initialized, run_workflow


def run_command(
    workflow: Optional[str] = typer.Argument(
        None,
        help="workflow file, workflow/graph, or filename::graph_name (e.g., 'customer_data::support_flow')",
    ),
    graph: str = typer.Option(
        "{}",
        "--workflow",
        "-w",
        help="workflow file, workflow_folder/workflow_file, or filename::graph_name (e.g., 'customer_data::support_flow')",
    ),
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
    force_create: bool = typer.Option(
        False,
        "--force-create",
        help="Force recreation of the bundle even if cached version exists",
    ),
):
    """
    Run a graph using the runtime facade.

    This command follows the facade pattern defined in SPEC-DEP-001 for
    consistent behavior across all deployment adapters.

    **Supported Syntax Examples:**

    • Traditional syntax:
      agentmap run workflow/graph_name
      agentmap run --csv workflow.csv --graph graph_name

    • Simplified syntax (NEW):
      agentmap run filename::graph_name
      agentmap run --workflow filename
      agentmap run --workflow filename::graph_name

    The :: syntax provides a convenient shorthand where the graph name
    defaults to the CSV filename (without .csv extension), but you can
    specify a different graph name after the :: delimiter.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=config_file)

        # Parse initial state
        try:
            initial_state = json.loads(state) if state != "{}" else {}
        except json.JSONDecodeError as e:
            print_err(f"Invalid JSON in --state: {e}")
            raise typer.Exit(
                code=map_exception_to_exit_code(ValueError("Invalid JSON in state"))
            )

        # Determine graph name - now supports :: syntax
        graph_name = workflow or graph

        if not graph_name:
            print_err("Must provide workflow argument")
            print_err("Examples:")
            print_err("  agentmap run workflow/graph_name")
            print_err("  agentmap run filename::graph_name")
            print_err("  agentmap run --csv workflow.csv --graph graph_name")
            raise typer.Exit(code=2)

        # Validate :: syntax if present
        # if "::" in graph_name:
        #     if graph_name.count("::") != 1:
        #         print_err("Invalid :: syntax - expected exactly one :: delimiter")
        #         raise typer.Exit(code=2)

        #     parts = graph_name.split("::", 1)
        #     if not parts[0].strip() or not parts[1].strip():
        #         print_err("Invalid :: syntax - both filename and graph name must be non-empty")
        #         raise typer.Exit(code=2)

        # Execute using runtime facade
        result = run_workflow(
            graph_name=graph_name,
            inputs=initial_state,
            config_file=config_file,
            force_create=force_create,
        )

        # Check if execution was interrupted for human interaction
        if result.get("interrupted", False):
            # Execution suspended for human interaction
            thread_id = result.get("thread_id")
            message = result.get(
                "message", "Execution interrupted for human interaction"
            )

            typer.secho(f"⏸️  {message}", fg=typer.colors.YELLOW)
            typer.secho(f"Thread ID: {thread_id}", fg=typer.colors.CYAN)
            typer.secho(
                "Use 'agentmap resume <thread_id>' to continue execution after providing input",
                fg=typer.colors.CYAN,
            )

            if pretty and verbose:
                metadata = result.get("metadata", {})
                if metadata:
                    typer.secho("ℹ️  Metadata:", fg=typer.colors.CYAN, bold=True)
                    print_json(metadata)

            raise typer.Exit(code=0)

        # Display result using CLI presenter for consistency
        if result.get("success", False):
            if pretty:
                # Pretty output with detailed information
                typer.secho(
                    "✅ Graph execution completed successfully", fg=typer.colors.GREEN
                )

                # Show outputs in pretty format
                outputs = result.get("outputs", {})
                if outputs:
                    typer.secho("📤 Outputs:", fg=typer.colors.BLUE, bold=True)
                    print_json(outputs)

                # Show metadata if verbose
                if verbose:
                    metadata = result.get("metadata", {})
                    if metadata:
                        typer.secho("ℹ️  Metadata:", fg=typer.colors.CYAN, bold=True)
                        print_json(metadata)
            else:
                # Simple JSON output for scripting
                print_json(result)

        else:
            # This shouldn't happen with the facade pattern, but handle gracefully
            print_err("Graph execution failed - no success status returned")
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


def parse_json_state(state: str) -> dict:
    """Helper function to parse JSON state (for backward compatibility)."""
    try:
        return json.loads(state) if state != "{}" else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in state: {e}")
