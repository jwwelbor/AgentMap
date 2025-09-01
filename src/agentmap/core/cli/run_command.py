"""
CLI run command handler using Bundle-based execution.

This module provides the run command that uses GraphBundle
for intelligent caching and execution.
"""

import typer
from typing import Optional

from agentmap.di import initialize_di
from agentmap.core.cli.cli_utils import (
    resolve_csv_path,
    parse_json_state,
    handle_command_error
)


def run_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path (shorthand for --csv)"
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
    
    Supports shorthand: agentmap run file.csv is equivalent to agentmap run --csv file.csv
    """
    try:
        # Resolve CSV path using utility
        csv_path = resolve_csv_path(csv_file, csv)
        
        # Initialize DI container
        container = initialize_di(config_file)
        
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
            csv_path=csv_path,
            graph_name=graph,
            config_path=config_file
        )

        # Execute graph using bundle
        runner = container.graph_runner_service()        
        typer.echo(f"📊 Executing graph: {bundle.graph_name or graph or 'default'}")
        result = runner.run(bundle, initial_state)
        
        # Display result
        if result.success:
            typer.secho("✅ Graph execution completed successfully", fg=typer.colors.GREEN)
            
            if pretty:
                formatter_service = container.execution_formatter_service()
                formatted_output = formatter_service.format_execution_result(
                    result.final_state, verbose=verbose
                )
                print(formatted_output)
            else:
                print("✅ Output:", result.final_state)
        else:
            typer.secho(f"❌ Graph execution failed: {result.error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
            
    except Exception as e:
        handle_command_error(e, verbose)
