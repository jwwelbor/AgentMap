"""
CLI scaffold command handler for agent and function generation.

This command follows SPEC-DEP-001 by using only the runtime facade
and CLI presenter utilities for consistent behavior and error handling.
"""

from pathlib import Path
from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_presenter import (
    map_exception_to_exit_code,
    print_err,
    print_json,
)
from agentmap.runtime_api import ensure_initialized, scaffold_agents


def scaffold_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path or workflow/graph (e.g., 'hello_world/HelloWorld')"
    ),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to scaffold agents for"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Directory for agent output"
    ),
    func_dir: Optional[str] = typer.Option(
        None, "--functions", "-f", help="Directory for function output"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing agent files"
    ),
):
    """
    Scaffold agents and routing functions using bundle analysis.

    This command follows the facade pattern defined in SPEC-DEP-001 for
    consistent behavior across all deployment adapters.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=config_file)

        # Determine graph name - handle CSV override and shorthand patterns
        graph_name = graph or csv_file
        if csv and graph_name != csv:
            # CSV override provided - use the override path but keep graph name
            graph_name = csv

        if not graph_name:
            print_err("Must provide either csv_file argument or --graph option")
            raise typer.Exit(
                code=map_exception_to_exit_code(ValueError("No graph specified"))
            )

        # Execute using runtime facade
        typer.echo(f"📦 Analyzing graph structure from: {graph_name}")

        result = scaffold_agents(
            graph_name=graph_name,
            output_dir=output_dir,
            func_dir=func_dir,
            config_file=config_file,
            overwrite=overwrite,
        )

        # Display results using CLI presenter for consistency
        if result.get("success", False):
            outputs = result.get("outputs", {})
            scaffolded_count = outputs.get("scaffolded_count", 0)
            errors = outputs.get("errors", [])
            created_files = outputs.get("created_files", [])
            service_stats = outputs.get("service_stats", {})
            missing_declarations = outputs.get("missing_declarations", [])

            # Show errors if any
            if errors:
                typer.secho(
                    "⚠️ Scaffolding completed with errors:", fg=typer.colors.YELLOW
                )
                for error in errors:
                    typer.secho(f"   {error}", fg=typer.colors.RED)

            # Check if anything was scaffolded
            if scaffolded_count == 0:
                if missing_declarations:
                    typer.secho(
                        f"No unknown agents found to scaffold, but {len(missing_declarations)} are still missing:",
                        fg=typer.colors.YELLOW,
                    )
                    for agent_type in missing_declarations:
                        typer.echo(f"   • {agent_type}")
                else:
                    typer.secho(
                        "No unknown agents or functions found to scaffold.",
                        fg=typer.colors.YELLOW,
                    )
            else:
                # Success message
                typer.secho(
                    f"✅ Scaffolded {scaffolded_count} agents/functions.",
                    fg=typer.colors.GREEN,
                )

                # Show service statistics if available
                if service_stats:
                    typer.secho("   📊 Service integrations:", fg=typer.colors.CYAN)
                    for service, count in service_stats.items():
                        typer.secho(
                            f"      {service}: {count} agents", fg=typer.colors.CYAN
                        )

                # Show created files (limited)
                if created_files:
                    typer.secho("   📁 Created files:", fg=typer.colors.CYAN)
                    for file_path in created_files[:5]:
                        file_name = (
                            Path(file_path).name
                            if isinstance(file_path, str)
                            else file_path.name
                        )
                        typer.secho(f"      {file_name}", fg=typer.colors.CYAN)
                    if len(created_files) > 5:
                        typer.secho(
                            f"      ... and {len(created_files) - 5} more files",
                            fg=typer.colors.CYAN,
                        )

                typer.echo("\n🔄 Bundle updated with newly scaffolded agents.")

        else:
            # This shouldn't happen with the facade pattern, but handle gracefully
            error_msg = result.get("error", "Unknown error")
            print_err(f"Scaffold operation failed: {error_msg}")
            raise typer.Exit(code=1)

        raise typer.Exit(code=0)

    except Exception as e:
        # Use CLI presenter for consistent error handling and exit codes
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
