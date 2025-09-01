"""
CLI validate command handler for bundle-based validation.

This module provides the validate command that checks CSV structure
and identifies missing agent declarations using bundle analysis.
"""

from typing import Optional

import typer

from agentmap.core.cli.cli_utils import handle_command_error, resolve_csv_path
from agentmap.di import initialize_di


def validate_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path (shorthand for --csv)"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path to validate"),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to validate"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """
    Validate CSV and graph configuration using bundle analysis.

    Checks CSV structure and identifies missing agent declarations.
    """
    try:
        # Resolve CSV path using utility
        csv_path = resolve_csv_path(csv_file, csv)

        # Initialize container
        container = initialize_di(config_file)

        # Get validation service
        validation_service = container.validation_service()

        # Validate CSV structure
        typer.echo(f"🔍 Validating CSV structure: {csv_path}")
        validation_service.validate_csv_for_bundling(csv_path)
        typer.secho("✅ CSV structure validation passed", fg=typer.colors.GREEN)

        # Create bundle to check for missing declarations
        typer.echo("📦 Analyzing graph dependencies...")
        graph_bundle_service = container.graph_bundle_service()
        bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=graph, config_path=config_file
        )

        # Report bundle analysis
        if graph:
            typer.echo(f"   Graph name: {bundle.graph_name or graph}")

        typer.echo(f"   Total nodes: {len(bundle.nodes)}")
        typer.echo(f"   Total edges: {len(bundle.edges)}")

        if bundle.missing_declarations:
            typer.secho(
                f"⚠️ Missing agent declarations: {', '.join(bundle.missing_declarations)}",
                fg=typer.colors.YELLOW,
            )
            typer.echo("   Run 'agentmap scaffold' to generate these agents")
        else:
            typer.secho("✅ All agent types are defined", fg=typer.colors.GREEN)

    except Exception as e:
        handle_command_error(e, verbose=False)
