"""
CLI validate command handler for bundle-based validation.

This module provides the validate command that checks CSV structure
and identifies missing agent declarations using bundle analysis.
"""

from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_utils import (
    handle_command_error,
    resolve_csv_path,
)
from agentmap.runtime_api import validate_workflow


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

        # Use graph name or derive from CSV path
        graph_name = graph or str(csv_path)

        # Validate using facade
        typer.echo(f"🔍 Validating CSV structure: {csv_path}")
        result = validate_workflow(graph_name, config_file=config_file)

        outputs = result["outputs"]
        metadata = result["metadata"]

        typer.secho("✅ CSV structure validation passed", fg=typer.colors.GREEN)

        # Report bundle analysis
        typer.echo("📦 Analyzing graph dependencies...")
        if metadata.get("bundle_name"):
            typer.echo(f"   Graph name: {metadata['bundle_name']}")

        typer.echo(f"   Total nodes: {outputs['total_nodes']}")
        typer.echo(f"   Total edges: {outputs['total_edges']}")

        if outputs["missing_declarations"]:
            typer.secho(
                f"⚠️ Missing agent declarations: {', '.join(outputs['missing_declarations'])}",
                fg=typer.colors.YELLOW,
            )
            typer.echo("   Run 'agentmap scaffold' to generate these agents")
        else:
            typer.secho("✅ All agent types are defined", fg=typer.colors.GREEN)

    except Exception as e:
        handle_command_error(e, verbose=False)
