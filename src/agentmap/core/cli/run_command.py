"""
CLI run command handler using Bundle-based execution.

This module provides the run command that uses GraphBundle
for intelligent caching and execution.

Enhanced to support repository-based execution patterns:
- Direct file: agentmap run file.csv --graph GraphName
- Repository shorthand: agentmap run workflow/GraphName
- Repository with options: agentmap run --csv workflow --graph GraphName
"""

from pathlib import Path
from typing import Optional

import typer

from agentmap.core.cli.cli_utils import (
    handle_command_error,
    parse_json_state,
    resolve_csv_path,
)
from agentmap.di import initialize_di


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

    Supports multiple patterns:
    - Direct file: agentmap run file.csv --graph GraphName
    - Repository shorthand: agentmap run workflow/GraphName
    - Repository with options: agentmap run --csv workflow --graph GraphName

    Examples:
        agentmap run workflows/hello_world.csv --graph HelloWorld
        agentmap run hello_world/HelloWorld
        agentmap run --csv hello_world --graph HelloWorld
    """
    try:
        # Initialize DI container
        container = initialize_di(config_file)
        app_config_service = container.app_config_service()

        # Handle repository-based shorthand: workflow/graph
        if csv_file and "/" in csv_file and not csv and not graph:
            parts = csv_file.split("/", 1)
            workflow_name = parts[0]
            graph = parts[1] if len(parts) > 1 else None

            # Check if it's a repository workflow (not a file path)
            csv_repository = app_config_service.get_csv_repository_path()
            potential_workflow = csv_repository / f"{workflow_name}.csv"

            if potential_workflow.exists():
                # It's a repository workflow
                csv_path = potential_workflow
            else:
                # Maybe it's a file path, resolve normally
                csv_path = resolve_csv_path(csv_file, csv)
        else:
            # Check if csv_file is a workflow name in repository
            if csv_file and not csv:
                csv_repository = app_config_service.get_csv_repository_path()
                potential_workflow = csv_repository / f"{csv_file}.csv"

                if potential_workflow.exists():
                    # It's a workflow name from repository
                    csv_path = potential_workflow
                else:
                    # Try to resolve as file path
                    csv_path = resolve_csv_path(csv_file, csv)
            else:
                # Standard resolution
                csv_path = resolve_csv_path(csv_file, csv)

        # Validate CSV if requested
        if validate:
            typer.echo("🔍 Validating CSV file before execution")
            validation_service = container.validation_service()

            try:
                validation_service.validate_csv_for_bundling(csv_path)
                typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Parse initial state using utility
        initial_state = parse_json_state(state)

        # Get or create bundle using GraphBundleService
        graph_bundle_service = container.graph_bundle_service()
        bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=graph, config_path=config_file
        )

        # Execute graph using bundle
        runner = container.graph_runner_service()
        typer.echo(f"📊 Executing graph: {bundle.graph_name or graph or 'default'}")

        # Show if from repository
        csv_repository = app_config_service.get_csv_repository_path()
        if csv_path.is_relative_to(csv_repository):
            workflow_name = csv_path.stem
            typer.echo(f"   From workflow: {workflow_name} (repository)")
        else:
            typer.echo(f"   From file: {csv_path}")

        result = runner.run(bundle, initial_state)

        # Display result
        if result.success:
            typer.secho(
                "✅ Graph execution completed successfully", fg=typer.colors.GREEN
            )

            if pretty:
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
